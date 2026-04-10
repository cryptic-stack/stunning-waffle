from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.models import BrowserSession


def create_session(client) -> str:
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
    return response.json()["session_id"]


def worker_token(app_state, session_id: str) -> str:
    with Session(app_state.state.engine) as session:
        record = session.get(BrowserSession, session_id)
        assert record is not None
        return record.worker_token


def assert_peer_connected(viewer, worker) -> None:
    assert viewer.receive_json() == {"type": "control", "event": "peer-connected"}
    assert worker.receive_json() == {"type": "control", "event": "peer-connected"}


def test_invalid_session_rejected(client) -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/signaling/does-not-exist"):
            pass


def test_unauthorized_viewer_rejected(client) -> None:
    session_id = create_session(client)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/ws/signaling/{session_id}",
            headers={"X-User-Id": "other-user"},
        ):
            pass


def test_offer_answer_and_candidate_relay(client, app_state) -> None:
    session_id = create_session(client)
    token = worker_token(app_state, session_id)

    with client.websocket_connect(f"/ws/signaling/{session_id}") as viewer:
        with client.websocket_connect(
            f"/ws/signaling/{session_id}?role=worker&token={token}"
        ) as worker:
            assert_peer_connected(viewer, worker)
            viewer.send_json({"type": "offer", "sdp": "viewer-offer"})
            assert worker.receive_json() == {"type": "offer", "sdp": "viewer-offer"}

            worker.send_json({"type": "answer", "sdp": "worker-answer"})
            assert viewer.receive_json() == {"type": "answer", "sdp": "worker-answer"}

            viewer.send_json({"type": "ice-candidate", "candidate": {"candidate": "abc"}})
            assert worker.receive_json() == {
                "type": "ice-candidate",
                "candidate": {"candidate": "abc"},
            }


def test_disconnect_notifies_peer(client, app_state) -> None:
    session_id = create_session(client)
    token = worker_token(app_state, session_id)

    with client.websocket_connect(f"/ws/signaling/{session_id}") as viewer:
        worker = client.websocket_connect(f"/ws/signaling/{session_id}?role=worker&token={token}")
        with worker:
            assert_peer_connected(viewer, worker)
        assert viewer.receive_json() == {"type": "control", "event": "peer-disconnected"}


def test_viewer_token_allows_external_signaling(client, app_state) -> None:
    create_response = client.post(
        "/api/v1/automation/sessions",
        json={
            "browser": "chromium",
            "resolution": {"width": 1280, "height": 720},
            "timeout_seconds": 30,
            "idle_timeout_seconds": 30,
            "allow_file_upload": True,
        },
        headers={"Authorization": "Bearer automation-test-key"},
    )
    session_id = create_response.json()["session"]["session_id"]
    viewer_token = create_response.json()["viewer_token"]
    token = worker_token(app_state, session_id)

    with client.websocket_connect(
        f"/ws/signaling/{session_id}?role=viewer&viewer_token={viewer_token}"
    ) as viewer:
        with client.websocket_connect(
            f"/ws/signaling/{session_id}?role=worker&token={token}"
        ) as worker:
            assert_peer_connected(viewer, worker)
