from fastapi import APIRouter, Depends

from app.config import Settings
from app.dependencies import get_settings
from app.schemas import IceServerModel, RtcConfigResponse

router = APIRouter(prefix="/api/v1/rtc", tags=["rtc"])


def build_rtc_config(settings: Settings) -> RtcConfigResponse:
    scheme = "turns" if settings.turn_tls_enabled else "turn"
    transport = "tcp" if settings.turn_tls_enabled else "udp"
    return RtcConfigResponse(
        ice_servers=[
            IceServerModel(urls=[f"stun:{settings.turn_public_host}:3478"]),
            IceServerModel(
                urls=[
                    f"{scheme}:{settings.turn_public_host}:3478?transport=udp",
                    f"{scheme}:{settings.turn_public_host}:3478?transport=tcp",
                    f"{scheme}:{settings.turn_public_host}:5349?transport={transport}",
                ],
                username=settings.turn_username,
                credential=settings.turn_password,
            ),
        ]
    )


@router.get("/config", response_model=RtcConfigResponse)
def get_rtc_config(settings: Settings = Depends(get_settings)) -> RtcConfigResponse:
    return build_rtc_config(settings)
