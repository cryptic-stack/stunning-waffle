from __future__ import annotations

from pathlib import Path

from session_agent.capture import SessionVideoTrack, _target_fps_for_session
from session_agent.config import AgentConfig


def make_config(*, session_kind: str, browser: str | None, desktop_profile: str | None) -> AgentConfig:
    return AgentConfig(
        session_id="sess_test",
        worker_token="worker-token",
        api_base_url="http://api:8000",
        session_kind=session_kind,
        browser=browser,
        desktop_profile=desktop_profile,
        resolution_width=1280,
        resolution_height=720,
        homepage_url="https://example.com/",
        display=":99",
        heartbeat_interval_seconds=5,
        turn_internal_host="coturn",
        turn_username="browserlab",
        turn_password="change-me",
        turn_tls_enabled=False,
    )


def test_target_fps_prefers_desktop_friendly_rate() -> None:
    browser_config = make_config(session_kind="browser", browser="chromium", desktop_profile=None)
    desktop_config = make_config(
        session_kind="desktop",
        browser=None,
        desktop_profile="kali-xfce",
    )

    assert _target_fps_for_session(browser_config) == 24
    assert _target_fps_for_session(desktop_config) == 20


def test_capture_frame_uses_bgra_path(monkeypatch) -> None:
    class FakeShot:
        width = 4
        height = 3
        bgra = b"\x00" * (width * height * 4)

    class FakeSct:
        def grab(self, monitor):
            assert monitor["width"] == 1280
            assert monitor["height"] == 720
            return FakeShot()

    track = SessionVideoTrack(make_config(session_kind="desktop", browser=None, desktop_profile="ubuntu-xfce"))
    track.sct = FakeSct()

    frame = track._capture_frame()

    assert frame.width == 4
    assert frame.height == 3
    assert frame.format.name == "bgra"
