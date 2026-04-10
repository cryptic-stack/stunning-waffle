from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState

from app.auth import AuthenticatedUser
from app.dependencies import get_current_user, get_db, get_session_service, get_signaling_registry
from app.models import AuditEvent
from app.schemas import SignalEnvelope
from app.services.sessions import SessionService
from app.signaling import SignalingRegistry

router = APIRouter(tags=["signaling"])
LOGGER = structlog.get_logger("signaling")


@router.websocket("/ws/signaling/{session_id}")
async def signaling_socket(
    websocket: WebSocket,
    session_id: str,
    role: Literal["viewer", "worker"] = Query(default="viewer"),
    token: str | None = Query(default=None),
    viewer_token: str | None = Query(default=None),
    session_service: SessionService = Depends(get_session_service),
    registry: SignalingRegistry = Depends(get_signaling_registry),
    db: Session = Depends(get_db),
) -> None:
    user: AuthenticatedUser | None = None
    record_user_id: str | None = None
    try:
        if role == "viewer":
            settings = websocket.app.state.settings
            if viewer_token is None:
                user = get_current_user(
                    headers=(
                        websocket.headers.get(settings.owner_header_name),
                        websocket.headers.get(settings.owner_email_header_name),
                        websocket.headers.get(settings.owner_name_header_name),
                    ),
                    settings=settings,
                )
            record = session_service.get_session_for_role(
                session_id,
                role=role,
                user=user,
                viewer_token=viewer_token,
            )
        else:
            record = session_service.get_session_for_role(
                session_id,
                role=role,
                worker_token=token,
            )
        record_user_id = record.user_id
    except Exception:
        LOGGER.warning("signaling_connection_rejected", session_id=session_id, role=role)
        db.add(
            AuditEvent(
                user_id=user.user_id if user is not None else record_user_id,
                session_id=session_id,
                action="signaling.connect",
                outcome="denied",
                detail=f"{role} signaling authorization failed",
            )
        )
        db.commit()
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await registry.register(session_id, role, websocket)
    db.add(
        AuditEvent(
            user_id=user.user_id if user is not None else record_user_id,
            session_id=session_id,
            action="signaling.connect",
            outcome="success",
            detail=f"{role} peer connected",
        )
    )
    db.commit()
    peer = await registry.peer(session_id, role)  # type: ignore[arg-type]
    if peer is not None:
        await websocket.send_json({"type": "control", "event": "peer-connected"})
        await peer.websocket.send_json({"type": "control", "event": "peer-connected"})

    try:
        while True:
            payload = await websocket.receive_json()
            envelope = SignalEnvelope.model_validate(payload)
            peer = await registry.peer(session_id, role)  # type: ignore[arg-type]
            if peer is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "PEER_UNAVAILABLE",
                        "detail": "No peer is currently connected for this session.",
                    }
                )
                continue
            await peer.websocket.send_json(envelope.model_dump(exclude_none=True))
    except WebSocketDisconnect:
        peer = await registry.peer(session_id, role)  # type: ignore[arg-type]
        if peer and peer.websocket.application_state == WebSocketState.CONNECTED:
            await peer.websocket.send_json({"type": "control", "event": "peer-disconnected"})
    finally:
        db.add(
            AuditEvent(
                user_id=user.user_id if user is not None else record_user_id,
                session_id=session_id,
                action="signaling.disconnect",
                outcome="success",
                detail=f"{role} peer disconnected",
            )
        )
        db.commit()
        await registry.unregister(session_id, role)  # type: ignore[arg-type]
