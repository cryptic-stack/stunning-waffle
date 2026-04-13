from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ResolutionModel(BaseModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=320, le=4320)


class SessionCreateRequest(BaseModel):
    session_kind: Literal["browser", "desktop"] = "browser"
    browser: Literal["chromium", "firefox", "brave", "edge", "vivaldi"] | None = None
    desktop_profile: Literal["ubuntu-xfce", "kali-xfce"] | None = None
    resolution: ResolutionModel
    timeout_seconds: int = Field(ge=1, le=86_400)
    idle_timeout_seconds: int = Field(ge=1, le=86_400)
    allow_file_upload: bool = True
    target_url: AnyHttpUrl | None = None

    @model_validator(mode="after")
    def validate_runtime(self) -> "SessionCreateRequest":
        if self.session_kind == "browser":
            if self.browser is None:
                raise ValueError("browser is required when session_kind is 'browser'")
            if self.desktop_profile is not None:
                raise ValueError("desktop_profile must not be set for browser sessions")
            return self

        if self.desktop_profile is None:
            raise ValueError("desktop_profile is required when session_kind is 'desktop'")
        if self.browser is not None:
            raise ValueError("browser must not be set for desktop sessions")
        return self


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    session_kind: Literal["browser", "desktop"]
    status: str
    browser: str | None
    desktop_profile: Literal["ubuntu-xfce", "kali-xfce"] | None = None
    container_id: str | None = None
    signaling_url: str
    expires_at: datetime
    terminated_at: datetime | None = None
    resolution: ResolutionModel
    timeout_seconds: int
    idle_timeout_seconds: int
    allow_file_upload: bool
    target_url: str


class SessionBootstrapResponse(BaseModel):
    session: SessionResponse
    viewer_token: str
    session_api_url: str
    signaling_websocket_url: str
    rtc_config: "RtcConfigResponse"


class AutomationSessionBootstrapResponse(BaseModel):
    session: SessionResponse
    viewer_token: str
    session_api_url: str
    signaling_websocket_url: str
    rtc_config: "RtcConfigResponse"


class SessionListResponse(BaseModel):
    items: list[SessionResponse]


class SessionHeartbeatRequest(BaseModel):
    state: Literal["active", "idle"] = "active"


class ClipboardSyncRequest(BaseModel):
    text: str = Field(max_length=100_000)


class ClipboardSyncResponse(BaseModel):
    session_id: str
    delivered: bool
    text_length: int


class FileUploadResponse(BaseModel):
    session_id: str
    filename: str
    destination_path: str
    size_bytes: int
    delivered: bool


class DownloadItemResponse(BaseModel):
    filename: str
    destination_path: str
    size_bytes: int


class DownloadListResponse(BaseModel):
    session_id: str
    items: list[DownloadItemResponse]


class IceServerModel(BaseModel):
    urls: list[str]
    username: str | None = None
    credential: str | None = None


class RtcConfigResponse(BaseModel):
    ice_servers: list[IceServerModel]


class SignalEnvelope(BaseModel):
    type: Literal["offer", "answer", "ice-candidate", "control", "error"]
    sdp: str | None = None
    candidate: dict | None = None
    event: str | None = None
    detail: str | None = None
    code: str | None = None
    payload: dict | None = None
