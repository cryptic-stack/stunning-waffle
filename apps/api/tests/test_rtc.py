from __future__ import annotations

from app.config import Settings
from app.main import create_app


def test_rtc_config_exposes_stun_and_turn(client) -> None:
    response = client.get("/api/v1/rtc/config")

    assert response.status_code == 200
    body = response.json()
    assert body["ice_servers"][0]["urls"] == ["stun:localhost:3478"]
    assert "turn:localhost:3478?transport=udp" in body["ice_servers"][1]["urls"]
    assert body["ice_servers"][1]["username"] == "browserlab"


def test_default_auth_mode_requires_user_header(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'default-auth.db'}",
        redis_url="redis://unused",
        session_launch_mode="stub",
    )
    app = create_app(settings)

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "browser": "chromium",
                "resolution": {"width": 1280, "height": 720},
                "timeout_seconds": 30,
                "idle_timeout_seconds": 30,
                "allow_file_upload": True,
            },
        )

    assert response.status_code == 401


def test_header_auth_mode_requires_user_header(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        redis_url="redis://unused",
        session_launch_mode="stub",
        auth_mode="header",
    )
    app = create_app(settings)

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/sessions",
            json={
                "browser": "chromium",
                "resolution": {"width": 1280, "height": 720},
                "timeout_seconds": 30,
                "idle_timeout_seconds": 30,
                "allow_file_upload": True,
            },
        )

    assert response.status_code == 401
