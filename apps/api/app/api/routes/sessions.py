import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.auth import AuthenticatedUser
from app.config import Settings
from app.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_session_service,
    get_settings,
    get_signaling_registry,
)
from app.schemas import (
    ClipboardSyncRequest,
    ClipboardSyncResponse,
    DownloadListResponse,
    FileUploadResponse,
    SessionCreateRequest,
    SessionHeartbeatRequest,
    SessionListResponse,
    SessionResponse,
)
from app.services.sessions import SessionService
from app.signaling import SignalingRegistry

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: SessionCreateRequest,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SessionResponse:
    return session_service.create_session(request, user)


@router.get("", response_model=SessionListResponse)
def list_sessions(
    include_closed: bool = Query(default=False),
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SessionListResponse:
    return SessionListResponse(
        items=session_service.list_sessions(user, include_closed=include_closed)
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SessionResponse:
    return session_service.get_session(session_id, user)


@router.delete("/{session_id}", response_model=SessionResponse)
def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> SessionResponse:
    return session_service.delete_session(session_id, user)


@router.post("/{session_id}/heartbeat", response_model=SessionResponse)
def heartbeat(
    session_id: str,
    request: SessionHeartbeatRequest,
    worker_token: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser | None = Depends(get_optional_current_user),
) -> SessionResponse:
    resolved_user = None if worker_token is not None else user
    return session_service.heartbeat(
        session_id,
        request,
        user=resolved_user,
        worker_token=worker_token,
    )


@router.post("/{session_id}/clipboard", response_model=ClipboardSyncResponse)
async def sync_clipboard(
    session_id: str,
    request: ClipboardSyncRequest,
    session_service: SessionService = Depends(get_session_service),
    registry: SignalingRegistry = Depends(get_signaling_registry),
    user: AuthenticatedUser = Depends(get_current_user),
) -> ClipboardSyncResponse:
    record = session_service.sync_clipboard(session_id, request, user)
    worker_connection = await registry.connection(session_id, "worker")
    delivered = worker_connection is not None
    if worker_connection is not None:
        await worker_connection.websocket.send_json(
            {
                "type": "control",
                "event": "clipboard-paste",
                "payload": {"text": request.text},
            }
        )
    return ClipboardSyncResponse(
        session_id=record.id,
        delivered=delivered,
        text_length=len(request.text),
    )


@router.post("/{session_id}/file-upload", response_model=FileUploadResponse)
async def upload_file(
    session_id: str,
    upload: UploadFile = File(...),
    session_service: SessionService = Depends(get_session_service),
    registry: SignalingRegistry = Depends(get_signaling_registry),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(get_current_user),
) -> FileUploadResponse:
    filename = Path(upload.filename or "").name
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename",
        )

    content = await upload.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded file exceeds the configured size limit",
        )

    result = session_service.upload_file(
        session_id,
        user,
        filename=filename,
        content=content,
        content_type=upload.content_type,
    )
    worker_connection = await registry.connection(session_id, "worker")
    delivered = worker_connection is not None
    if worker_connection is not None:
        await worker_connection.websocket.send_json(
            {
                "type": "control",
                "event": "file-uploaded",
                "payload": {
                    "filename": result.filename,
                    "path": result.destination_path,
                    "size_bytes": result.size_bytes,
                },
            }
        )
    return FileUploadResponse(
        session_id=session_id,
        filename=result.filename,
        destination_path=result.destination_path,
        size_bytes=result.size_bytes,
        delivered=delivered,
    )


@router.get("/{session_id}/downloads", response_model=DownloadListResponse)
def list_downloads(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> DownloadListResponse:
    return DownloadListResponse(
        session_id=session_id,
        items=session_service.list_downloads(session_id, user),
    )


@router.get("/{session_id}/downloads/{filename}")
def get_download(
    session_id: str,
    filename: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    safe_filename = Path(filename).name
    if safe_filename != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    download = session_service.read_download(session_id, user, safe_filename)
    media_type = mimetypes.guess_type(download.filename)[0] or "application/octet-stream"
    return Response(
        content=download.content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{download.filename}"',
            "X-Download-Path": download.destination_path,
            "X-Download-Size": str(download.size_bytes),
        },
    )


@router.get("/{session_id}/screenshot")
def capture_screenshot(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_current_user),
) -> Response:
    screenshot = session_service.capture_screenshot(session_id, user)
    return Response(
        content=screenshot.content,
        media_type=screenshot.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{screenshot.filename}"',
            "X-Screenshot-Size": str(screenshot.size_bytes),
        },
    )
