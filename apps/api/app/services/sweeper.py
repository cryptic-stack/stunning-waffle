from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.launcher import SessionLauncher
from app.models import AuditEvent, BrowserSession, SessionEvent
from app.redis_store import RedisSessionStore
from app.services.sessions import SessionService


class SessionSweeper:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        redis_store: RedisSessionStore,
        launcher: SessionLauncher,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.redis_store = redis_store
        self.launcher = launcher
        self.settings = settings
        self.logger = structlog.get_logger("session-sweeper")

    def sweep_once(self) -> None:
        with self.session_factory() as db:
            service = SessionService(
                db=db,
                redis_store=self.redis_store,
                launcher=self.launcher,
                settings=self.settings,
            )
            active_records = db.scalars(
                select(BrowserSession).where(
                    BrowserSession.status.not_in(["terminated", "expired"])
                )
            ).all()
            for record in active_records:
                service._expire_if_needed(record)

            active_session_ids = {
                session_id
                for session_id in db.scalars(
                    select(BrowserSession.id).where(
                        BrowserSession.status.not_in(["terminated", "expired"])
                    )
                ).all()
            }
            purged_session_ids = self._prune_closed_sessions(db)

        self.launcher.cleanup_orphans(active_session_ids)
        self.logger.info(
            "session_sweep_completed",
            active_sessions=len(active_session_ids),
            purged_sessions=len(purged_session_ids),
        )

    def _prune_closed_sessions(self, db: Session) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=self.settings.closed_session_retention_seconds
        )
        closed_session_ids = list(
            db.scalars(
                select(BrowserSession.id).where(
                    BrowserSession.status.in_(["terminated", "expired"]),
                    BrowserSession.terminated_at.is_not(None),
                    BrowserSession.terminated_at < cutoff,
                )
            ).all()
        )
        if not closed_session_ids:
            return []

        db.execute(delete(SessionEvent).where(SessionEvent.session_id.in_(closed_session_ids)))
        db.execute(delete(AuditEvent).where(AuditEvent.session_id.in_(closed_session_ids)))
        db.execute(delete(BrowserSession).where(BrowserSession.id.in_(closed_session_ids)))
        db.commit()
        self.logger.info("closed_sessions_pruned", count=len(closed_session_ids))
        return closed_session_ids
