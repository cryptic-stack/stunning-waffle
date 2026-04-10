from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AuthenticatedUser
from app.config import Settings
from app.launcher import SessionLauncher, UploadResult
from app.models import AuditEvent, BrowserSession, SessionEvent, User
from app.redis_store import RedisSessionStore
from app.schemas import (
    ClipboardSyncRequest,
    DownloadItemResponse,
    SessionCreateRequest,
    SessionHeartbeatRequest,
    SessionResponse,
)
from app.targets import resolve_session_target


class SessionService:
    def __init__(
        self,
        db: Session,
        redis_store: RedisSessionStore,
        launcher: SessionLauncher,
        settings: Settings,
    ) -> None:
        self.db = db
        self.redis_store = redis_store
        self.launcher = launcher
        self.settings = settings
        self.logger = structlog.get_logger("session-service")

    def list_sessions(
        self,
        user: AuthenticatedUser,
        include_closed: bool = False,
    ) -> list[SessionResponse]:
        query = select(BrowserSession).where(BrowserSession.user_id == user.user_id)
        if not include_closed:
            query = query.where(BrowserSession.status.not_in(["terminated", "expired"]))

        records = self.db.scalars(query.order_by(BrowserSession.created_at.desc())).all()
        return [self._to_response(self._expire_if_needed(record)) for record in records]

    def create_session(
        self,
        request: SessionCreateRequest,
        user: AuthenticatedUser,
    ) -> SessionResponse:
        now = datetime.now(timezone.utc)
        session_id = f"{self.settings.session_id_prefix}_{uuid4().hex[:12]}"
        worker_token = secrets.token_urlsafe(24)
        expires_at = now + timedelta(seconds=request.timeout_seconds)
        session_kind = request.session_kind
        runtime_name = request.browser if session_kind == "browser" else request.desktop_profile
        if runtime_name is None:  # pragma: no cover - schema validation should prevent this
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session runtime is required",
            )
        target_url = str(request.target_url or self.settings.default_session_target_url)
        resolved_target = (
            resolve_session_target(target_url, self.settings)
            if session_kind == "browser"
            else None
        )

        self._ensure_user(user)

        record = BrowserSession(
            id=session_id,
            user_id=user.user_id,
            session_kind=session_kind,
            browser=request.browser,
            desktop_profile=request.desktop_profile,
            status="starting",
            worker_token=worker_token,
            resolution_width=request.resolution.width,
            resolution_height=request.resolution.height,
            timeout_seconds=request.timeout_seconds,
            idle_timeout_seconds=request.idle_timeout_seconds,
            allow_file_upload=request.allow_file_upload,
            target_url=(
                resolved_target.requested_url if resolved_target is not None else target_url
            ),
            created_at=now,
            expires_at=expires_at,
        )
        self.db.add(record)
        self.db.flush()

        try:
            launch_result = self.launcher.launch(
                session_id=session_id,
                user_id=user.user_id,
                session_kind=session_kind,
                runtime_name=runtime_name,
                worker_token=worker_token,
                resolution_width=request.resolution.width,
                resolution_height=request.resolution.height,
                target_url=(
                    resolved_target.worker_url if resolved_target is not None else target_url
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive path
            self.db.rollback()
            self.logger.exception(
                "session_launch_failed",
                user_id=user.user_id,
                session_kind=session_kind,
                runtime_name=runtime_name,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        record.container_id = launch_result.container_id
        self.redis_store.create_session(session_id, request.timeout_seconds)
        self._record_event(
            record.id,
            "session.created",
            {
                "container_id": record.container_id,
                "session_kind": session_kind,
                "runtime_name": runtime_name,
                "target_url": record.target_url,
                "worker_target_url": (
                    resolved_target.worker_url if resolved_target is not None else None
                ),
                "target_access_mode": (
                    resolved_target.access_mode if resolved_target is not None else "ignored"
                ),
            },
        )
        self._record_audit_event(
            action="session.create",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={
                "session_kind": session_kind,
                "runtime_name": runtime_name,
                "browser": request.browser,
                "desktop_profile": request.desktop_profile,
                "target_url": record.target_url,
                "worker_target_url": (
                    resolved_target.worker_url if resolved_target is not None else None
                ),
                "target_access_mode": (
                    resolved_target.access_mode if resolved_target is not None else "ignored"
                ),
            },
        )
        self.db.commit()
        self.db.refresh(record)

        self.logger.info(
            "session_created",
            session_id=record.id,
            user_id=user.user_id,
            session_kind=record.session_kind,
            runtime_name=self._runtime_name(record),
            container_id=record.container_id,
        )
        return self._to_response(record)

    def issue_viewer_token(
        self,
        session_id: str,
        user: AuthenticatedUser,
    ) -> str:
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Session is no longer active",
            )

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        remaining_seconds = max(
            1,
            int((expires_at - datetime.now(timezone.utc)).total_seconds()),
        )
        viewer_token = secrets.token_urlsafe(24)
        self.redis_store.issue_viewer_token(record.id, viewer_token, remaining_seconds)
        self._record_event(
            record.id,
            "session.viewer_token_issued",
            {"ttl_seconds": remaining_seconds},
        )
        self._record_audit_event(
            action="session.viewer_token_issue",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={"ttl_seconds": remaining_seconds},
        )
        self.db.commit()
        return viewer_token

    def get_session(self, session_id: str, user: AuthenticatedUser) -> SessionResponse:
        record = self._get_owned_session(session_id, user.user_id)
        return self._to_response(self._expire_if_needed(record))

    def get_session_for_role(
        self,
        session_id: str,
        role: str,
        user: AuthenticatedUser | None = None,
        worker_token: str | None = None,
        viewer_token: str | None = None,
    ) -> BrowserSession:
        record = self._get_session_record(session_id)
        self._expire_if_needed(record)

        if role == "viewer":
            if self.redis_store.validate_viewer_token(session_id, viewer_token):
                pass
            elif user is None or record.user_id != user.user_id:
                self._record_audit_event(
                    action="session.access",
                    outcome="denied",
                    session_id=session_id,
                    user_id=user.user_id if user is not None else None,
                    detail="viewer ownership check failed",
                )
                self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Session ownership required",
                )
        else:
            if worker_token is None or worker_token != record.worker_token:
                self._record_audit_event(
                    action="session.worker_access",
                    outcome="denied",
                    session_id=session_id,
                    detail="worker token invalid",
                )
                self.db.commit()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Worker token invalid",
                )

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Session is no longer active",
            )

        return record

    def delete_session(self, session_id: str, user: AuthenticatedUser) -> SessionResponse:
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        self.launcher.terminate(record.container_id)
        now = datetime.now(timezone.utc)
        record.status = "terminated"
        record.terminated_at = now
        self.redis_store.delete_session(record.id)
        self._record_event(record.id, "session.terminated", {"container_id": record.container_id})
        self._record_audit_event(
            action="session.delete",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
        )
        self.db.commit()
        self.db.refresh(record)

        self.logger.info("session_terminated", session_id=record.id, user_id=user.user_id)
        return self._to_response(record)

    def heartbeat(
        self,
        session_id: str,
        request: SessionHeartbeatRequest,
        user: AuthenticatedUser | None = None,
        worker_token: str | None = None,
    ) -> SessionResponse:
        if worker_token is not None:
            record = self.get_session_for_role(session_id, role="worker", worker_token=worker_token)
        elif user is not None:
            record = self._get_owned_session(session_id, user.user_id)
        else:  # pragma: no cover - defensive path
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Heartbeat auth required",
            )
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        now = datetime.now(timezone.utc)
        if record.started_at is None:
            record.started_at = now
        record.status = "active"
        self.redis_store.record_heartbeat(record.id, request.state, record.timeout_seconds)
        self._record_event(record.id, "session.heartbeat", {"state": request.state})
        self.db.commit()
        self.db.refresh(record)
        return self._to_response(record)

    def sync_clipboard(
        self,
        session_id: str,
        request: ClipboardSyncRequest,
        user: AuthenticatedUser,
    ) -> BrowserSession:
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        self._record_event(
            record.id,
            "session.clipboard_sync",
            {"text_length": len(request.text)},
        )
        self._record_audit_event(
            action="session.clipboard_sync",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={"text_length": len(request.text)},
        )
        self.db.commit()
        self.db.refresh(record)
        return record

    def upload_file(
        self,
        session_id: str,
        user: AuthenticatedUser,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> UploadResult:
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )
        if not record.allow_file_upload:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="File upload is disabled for this session",
            )

        upload = self.launcher.upload_file(record.container_id, filename, content)
        self._record_event(
            record.id,
            "session.file_uploaded",
            {
                "filename": upload.filename,
                "destination_path": upload.destination_path,
                "size_bytes": upload.size_bytes,
                "content_type": content_type,
            },
        )
        self._record_audit_event(
            action="session.file_upload",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={
                "filename": upload.filename,
                "size_bytes": upload.size_bytes,
                "content_type": content_type,
            },
        )
        self.db.commit()
        return upload

    def list_downloads(
        self,
        session_id: str,
        user: AuthenticatedUser,
    ) -> list[DownloadItemResponse]:
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        downloads = self.launcher.list_downloads(record.container_id)
        self._record_event(
            record.id,
            "session.downloads_listed",
            {"count": len(downloads)},
        )
        self._record_audit_event(
            action="session.downloads_list",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={"count": len(downloads)},
        )
        self.db.commit()
        return [
            DownloadItemResponse(
                filename=item.filename,
                destination_path=item.destination_path,
                size_bytes=item.size_bytes,
            )
            for item in downloads
        ]

    def read_download(
        self,
        session_id: str,
        user: AuthenticatedUser,
        filename: str,
    ):
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        try:
            download = self.launcher.read_download(record.container_id, filename)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Download not found",
            ) from exc

        self._record_event(
            record.id,
            "session.download_retrieved",
            {"filename": download.filename, "size_bytes": download.size_bytes},
        )
        self._record_audit_event(
            action="session.download_get",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={"filename": download.filename, "size_bytes": download.size_bytes},
        )
        self.db.commit()
        return download

    def capture_screenshot(
        self,
        session_id: str,
        user: AuthenticatedUser,
    ):
        record = self._get_owned_session(session_id, user.user_id)
        record = self._expire_if_needed(record)

        if record.status in {"terminated", "expired"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session already closed",
            )

        screenshot = self.launcher.capture_screenshot(
            record.container_id,
            record.id,
            record.resolution_width,
            record.resolution_height,
        )
        self._record_event(
            record.id,
            "session.screenshot_captured",
            {"filename": screenshot.filename, "size_bytes": screenshot.size_bytes},
        )
        self._record_audit_event(
            action="session.screenshot_capture",
            outcome="success",
            session_id=record.id,
            user_id=user.user_id,
            payload={"filename": screenshot.filename, "size_bytes": screenshot.size_bytes},
        )
        self.db.commit()
        return screenshot

    def _expire_if_needed(self, record: BrowserSession) -> BrowserSession:
        if record.status in {"terminated", "expired"}:
            return record

        container_running = self.launcher.is_container_running(record.container_id)
        if container_running is False:
            now = datetime.now(timezone.utc)
            record.status = "terminated"
            record.terminated_at = now
            self.redis_store.delete_session(record.id)
            self._record_event(record.id, "session.worker_exited", {"reason": "container_stopped"})
            self._record_audit_event(
                action="session.worker_exit",
                outcome="success",
                session_id=record.id,
                user_id=record.user_id,
                detail="worker container exited before session completion",
            )
            self.db.commit()
            self.db.refresh(record)
            self.logger.warning(
                "session_worker_exited",
                session_id=record.id,
                user_id=record.user_id,
            )
            return record

        if self.redis_store.session_alive(record.id):
            return record

        self.launcher.terminate(record.container_id)
        now = datetime.now(timezone.utc)
        record.status = "expired"
        record.terminated_at = now
        self._record_event(record.id, "session.expired", {"reason": "ttl_elapsed"})
        self._record_audit_event(
            action="session.expire",
            outcome="success",
            session_id=record.id,
            user_id=record.user_id,
        )
        self.db.commit()
        self.db.refresh(record)
        self.logger.info("session_expired", session_id=record.id, user_id=record.user_id)
        return record

    def _get_owned_session(self, session_id: str, user_id: str) -> BrowserSession:
        record = self._get_session_record(session_id)
        if record.user_id != user_id:
            self._record_audit_event(
                action="session.access",
                outcome="denied",
                session_id=session_id,
                user_id=user_id,
                detail="rest ownership check failed",
            )
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session ownership required",
            )
        return record

    def _get_session_record(self, session_id: str) -> BrowserSession:
        record = self.db.get(BrowserSession, session_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        return record

    def _ensure_user(self, user: AuthenticatedUser) -> None:
        existing = self.db.get(User, user.user_id)
        if existing is not None:
            existing.email = user.email
            existing.display_name = user.display_name
            return
        self.db.add(
            User(
                id=user.user_id,
                subject=user.user_id,
                email=user.email,
                display_name=user.display_name,
            )
        )

    def _record_event(self, session_id: str, event_type: str, payload: dict | None = None) -> None:
        self.db.add(
            SessionEvent(
                session_id=session_id,
                event_type=event_type,
                payload_json=payload,
            )
        )

    def _record_audit_event(
        self,
        action: str,
        outcome: str,
        session_id: str | None = None,
        user_id: str | None = None,
        detail: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            AuditEvent(
                user_id=user_id,
                session_id=session_id,
                action=action,
                outcome=outcome,
                detail=detail,
                payload_json=payload,
            )
        )

    def _to_response(self, record: BrowserSession) -> SessionResponse:
        return SessionResponse(
            session_id=record.id,
            session_kind=record.session_kind,
            status=record.status,
            browser=record.browser,
            desktop_profile=record.desktop_profile,
            container_id=record.container_id,
            signaling_url=f"/ws/signaling/{record.id}",
            expires_at=record.expires_at,
            terminated_at=record.terminated_at,
            resolution={
                "width": record.resolution_width,
                "height": record.resolution_height,
            },
            timeout_seconds=record.timeout_seconds,
            idle_timeout_seconds=record.idle_timeout_seconds,
            allow_file_upload=record.allow_file_upload,
            target_url=record.target_url or self.settings.default_session_target_url,
        )

    @staticmethod
    def _runtime_name(record: BrowserSession) -> str:
        return record.browser or record.desktop_profile or "unknown"
