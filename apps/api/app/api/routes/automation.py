from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, status

from app.api.routes.rtc import build_rtc_config
from app.auth import AuthenticatedUser
from app.config import Settings
from app.dependencies import get_automation_user, get_session_service, get_settings
from app.schemas import AutomationSessionBootstrapResponse, SessionCreateRequest, SessionResponse
from app.services.sessions import SessionService

router = APIRouter(prefix="/api/v1/automation/sessions", tags=["automation"])


@router.post(
    "",
    response_model=AutomationSessionBootstrapResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_automation_session(
    request: Request,
    payload: SessionCreateRequest,
    session_service: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(get_automation_user),
) -> AutomationSessionBootstrapResponse:
    session = session_service.create_session(payload, user)
    viewer_token = session_service.issue_viewer_token(session.session_id, user)
    return _build_bootstrap_response(
        request=request,
        settings=settings,
        session=session,
        viewer_token=viewer_token,
    )


@router.get("/{session_id}", response_model=SessionResponse)
def get_automation_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_automation_user),
) -> SessionResponse:
    return session_service.get_session(session_id, user)


@router.get("/{session_id}/bootstrap", response_model=AutomationSessionBootstrapResponse)
def get_automation_bootstrap(
    request: Request,
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    settings: Settings = Depends(get_settings),
    user: AuthenticatedUser = Depends(get_automation_user),
) -> AutomationSessionBootstrapResponse:
    session = session_service.get_session(session_id, user)
    viewer_token = session_service.issue_viewer_token(session_id, user)
    return _build_bootstrap_response(
        request=request,
        settings=settings,
        session=session,
        viewer_token=viewer_token,
    )


@router.delete("/{session_id}", response_model=SessionResponse)
def delete_automation_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
    user: AuthenticatedUser = Depends(get_automation_user),
) -> SessionResponse:
    return session_service.delete_session(session_id, user)


def _build_bootstrap_response(
    *,
    request: Request,
    settings: Settings,
    session: SessionResponse,
    viewer_token: str,
) -> AutomationSessionBootstrapResponse:
    api_base = str(request.base_url).rstrip("/")
    signaling_base = api_base.replace("https://", "wss://").replace("http://", "ws://")
    query = urlencode({"role": "viewer", "viewer_token": viewer_token})
    return AutomationSessionBootstrapResponse(
        session=session,
        viewer_token=viewer_token,
        session_api_url=f"{api_base}/api/v1/automation/sessions/{session.session_id}",
        signaling_websocket_url=f"{signaling_base}{session.signaling_url}?{query}",
        rtc_config=build_rtc_config(settings),
    )
