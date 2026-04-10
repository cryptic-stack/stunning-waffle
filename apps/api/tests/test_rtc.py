from app.api.routes.rtc import build_rtc_config
from app.config import Settings


def test_rtc_config_exposes_turn_and_stun_servers() -> None:
    settings = Settings(
        turn_public_host="localhost",
        turn_username="browserlab",
        turn_password="change-me",
    )

    config = build_rtc_config(settings)

    assert len(config.ice_servers) == 2
    assert config.ice_servers[0].urls == ["stun:localhost:3478"]
    assert "turn:localhost:3478?transport=udp" in config.ice_servers[1].urls
