from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request

from app.api.routes.rtc import build_rtc_config
from app.config import Settings
from app.schemas import SessionBootstrapResponse, SessionResponse


def build_session_bootstrap_response(
    *,
    request: Request,
    settings: Settings,
    session: SessionResponse,
    viewer_token: str,
    session_api_url: str,
) -> SessionBootstrapResponse:
    api_base = str(request.base_url).rstrip("/")
    signaling_base = api_base.replace("https://", "wss://").replace("http://", "ws://")
    query = urlencode({"role": "viewer", "viewer_token": viewer_token})
    return SessionBootstrapResponse(
        session=session,
        viewer_token=viewer_token,
        session_api_url=f"{api_base}{session_api_url}",
        signaling_websocket_url=f"{signaling_base}{session.signaling_url}?{query}",
        rtc_config=build_rtc_config(settings),
    )
