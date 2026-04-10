from __future__ import annotations

import asyncio
import time

from conftest import fetch_session
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, SessionEvent


def create_payload(timeout_seconds: int = 30) -> dict:
    return {
        "browser": "chromium",
        "resolution": {"width": 1280, "height": 720},
        "timeout_seconds": timeout_seconds,
        "idle_timeout_seconds": 60,
        "allow_file_upload": True,
        "target_url": "https://example.com",
    }


def create_desktop_payload(profile: str = "ubuntu-xfce", timeout_seconds: int = 30) -> dict:
    return {
        "session_kind": "desktop",
        "desktop_profile": profile,
        "resolution": {"width": 1280, "height": 720},
        "timeout_seconds": timeout_seconds,
        "idle_timeout_seconds": 60,
        "allow_file_upload": True,
        "target_url": "https://example.com",
    }


def test_create_get_and_delete_session(client, app_state) -> None:
    create_response = client.post("/api/v1/sessions", json=create_payload())

    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "starting"
    assert body["session_kind"] == "browser"
    assert body["desktop_profile"] is None
    assert body["container_id"].startswith("stub-sess_")
    assert body["target_url"] == "https://example.com/"
    assert create_response.headers["X-Request-ID"]

    session_id = body["session_id"]

    get_response = client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id

    with Session(app_state.state.engine) as session:
        events = session.scalars(
            select(SessionEvent)
            .where(SessionEvent.session_id == session_id)
            .order_by(SessionEvent.id)
        ).all()
        assert [event.event_type for event in events] == ["session.created"]

    assert app_state.state.redis_store.session_alive(session_id) is True

    delete_response = client.delete(f"/api/v1/sessions/{session_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "terminated"
    assert app_state.state.redis_store.session_alive(session_id) is False
    assert app_state.state.launcher.terminated == [body["container_id"]]


def test_delete_rejects_closed_session(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 200

    second_delete = client.delete(f"/api/v1/sessions/{session_id}")
    assert second_delete.status_code == 409


def test_firefox_session_is_recorded(client, app_state) -> None:
    payload = create_payload()
    payload["browser"] = "firefox"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["session_kind"] == "browser"
    assert create_response.json()["browser"] == "firefox"
    assert app_state.state.launcher.launched[0]["browser"] == "firefox"


def test_browser_session_kind_explicitly_supported(client, app_state) -> None:
    payload = create_payload()
    payload["session_kind"] = "browser"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["session_kind"] == "browser"
    assert app_state.state.launcher.launched[0]["runtime_name"] == "chromium"


def test_mobile_viewport_is_accepted(client, app_state) -> None:
    payload = create_payload()
    payload["resolution"] = {"width": 390, "height": 844}

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["resolution"] == {"width": 390, "height": 844}
    assert app_state.state.launcher.launched[0]["resolution_width"] == 390
    assert app_state.state.launcher.launched[0]["resolution_height"] == 844


def test_vivaldi_session_is_recorded(client, app_state) -> None:
    payload = create_payload()
    payload["browser"] = "vivaldi"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["browser"] == "vivaldi"
    assert app_state.state.launcher.launched[0]["browser"] == "vivaldi"


def test_desktop_session_is_recorded(client, app_state) -> None:
    create_response = client.post("/api/v1/sessions", json=create_desktop_payload())

    assert create_response.status_code == 201
    assert create_response.json()["session_kind"] == "desktop"
    assert create_response.json()["browser"] is None
    assert create_response.json()["desktop_profile"] == "ubuntu-xfce"
    assert app_state.state.launcher.launched[0]["session_kind"] == "desktop"
    assert app_state.state.launcher.launched[0]["desktop_profile"] == "ubuntu-xfce"


def test_desktop_session_rejects_invalid_profile(client) -> None:
    payload = create_desktop_payload(profile="invalid-desktop")

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 422


def test_custom_target_url_is_persisted(client, app_state) -> None:
    payload = create_payload()
    payload["target_url"] = "https://openai.com"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["target_url"] == "https://openai.com/"
    assert app_state.state.launcher.launched[0]["target_url"] == "https://openai.com/"

    record = fetch_session(app_state, create_response.json()["session_id"])
    assert record.target_url == "https://openai.com/"


def test_desktop_target_url_is_ignored_for_worker_launch(client, app_state) -> None:
    payload = create_desktop_payload()
    payload["target_url"] = "https://openai.com"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["target_url"] == "https://openai.com/"
    assert app_state.state.launcher.launched[0]["target_url"] == "https://openai.com/"


def test_localhost_target_is_rewritten_only_for_worker(client, app_state) -> None:
    payload = create_payload()
    payload["target_url"] = "http://localhost:3000"

    create_response = client.post("/api/v1/sessions", json=payload)

    assert create_response.status_code == 201
    assert create_response.json()["target_url"] == "http://localhost:3000/"
    assert app_state.state.launcher.launched[0]["target_url"] == "http://host.docker.internal:3000/"


def test_session_expires_after_ttl(client, app_state) -> None:
    session_id = client.post(
        "/api/v1/sessions",
        json=create_payload(timeout_seconds=1),
    ).json()["session_id"]

    time.sleep(1.2)

    get_response = client.get(f"/api/v1/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "expired"

    record = fetch_session(app_state, session_id)
    assert record.status == "expired"
    assert record.terminated_at is not None


def test_list_and_ownership_enforcement(client) -> None:
    own_session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    list_response = client.get("/api/v1/sessions")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["session_id"] == own_session_id

    forbidden = client.get(
        f"/api/v1/sessions/{own_session_id}",
        headers={"X-User-Id": "someone-else"},
    )
    assert forbidden.status_code == 403


def test_list_sessions_hides_closed_sessions_by_default(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 200

    list_response = client.get("/api/v1/sessions")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    history_response = client.get("/api/v1/sessions?include_closed=true")
    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["session_id"] == session_id


def test_heartbeat_marks_session_active(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    heartbeat = client.post(
        f"/api/v1/sessions/{session_id}/heartbeat",
        json={"state": "active"},
    )

    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "active"


def test_worker_heartbeat_marks_session_active(client, app_state) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    worker_token = app_state.state.launcher.launched[0]["worker_token"]

    heartbeat = client.post(
        f"/api/v1/sessions/{session_id}/heartbeat?worker_token={worker_token}",
        json={"state": "active"},
    )

    assert heartbeat.status_code == 200
    assert heartbeat.json()["status"] == "active"


def test_clipboard_route_forwards_to_connected_worker(client, app_state) -> None:
    class DummySocket:
        def __init__(self) -> None:
            self.messages: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.messages.append(payload)

    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    worker_socket = DummySocket()
    asyncio.run(app_state.state.signaling_registry.register(session_id, "worker", worker_socket))

    response = client.post(
        f"/api/v1/sessions/{session_id}/clipboard",
        json={"text": "hello remote browser"},
    )

    assert response.status_code == 200
    assert response.json()["delivered"] is True
    assert worker_socket.messages == [
        {
            "type": "control",
            "event": "clipboard-paste",
            "payload": {"text": "hello remote browser"},
        }
    ]


def test_file_upload_copies_into_worker_launcher(client, app_state) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/file-upload",
        files={"upload": ("notes.txt", b"hello from upload", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "notes.txt"
    assert response.json()["size_bytes"] == 17
    assert app_state.state.launcher.uploaded_files == [
        {
            "container_id": f"stub-{session_id}",
            "filename": "notes.txt",
            "destination_path": "/home/browserlab/Downloads/notes.txt",
            "size_bytes": 17,
        }
    ]


def test_file_upload_rejects_disabled_session(client) -> None:
    payload = create_payload()
    payload["allow_file_upload"] = False
    session_id = client.post("/api/v1/sessions", json=payload).json()["session_id"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/file-upload",
        files={"upload": ("notes.txt", b"blocked", "text/plain")},
    )

    assert response.status_code == 403


def test_downloads_are_listed_and_retrieved(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    client.post(
        f"/api/v1/sessions/{session_id}/file-upload",
        files={"upload": ("notes.txt", b"hello world", "text/plain")},
    )

    list_response = client.get(f"/api/v1/sessions/{session_id}/downloads")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == [
        {
            "filename": "notes.txt",
            "destination_path": "/home/browserlab/Downloads/notes.txt",
            "size_bytes": 11,
        }
    ]

    download_response = client.get(f"/api/v1/sessions/{session_id}/downloads/notes.txt")
    assert download_response.status_code == 200
    assert download_response.content == b"hello world"
    assert download_response.headers["content-disposition"] == 'attachment; filename="notes.txt"'


def test_missing_download_returns_not_found(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    response = client.get(f"/api/v1/sessions/{session_id}/downloads/missing.txt")

    assert response.status_code == 404


def test_screenshot_capture_returns_png_attachment(client) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]

    response = client.get(f"/api/v1/sessions/{session_id}/screenshot")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{session_id}-screenshot.png"'
    )
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_dead_worker_is_cleaned_up(client, app_state) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    app_state.state.launcher.is_container_running = lambda _container_id: False

    get_response = client.get(f"/api/v1/sessions/{session_id}")

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "terminated"
    assert app_state.state.redis_store.session_alive(session_id) is False


def test_audit_events_written_for_create_and_delete(client, app_state) -> None:
    session_id = client.post("/api/v1/sessions", json=create_payload()).json()["session_id"]
    client.delete(f"/api/v1/sessions/{session_id}")

    with Session(app_state.state.engine) as session:
        audit_events = session.scalars(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .order_by(AuditEvent.id)
        ).all()

    assert [event.action for event in audit_events] == ["session.create", "session.delete"]
