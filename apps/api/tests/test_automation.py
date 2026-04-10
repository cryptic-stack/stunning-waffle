from __future__ import annotations


def automation_headers(token: str = "automation-test-key") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_payload() -> dict:
    return {
        "browser": "chromium",
        "resolution": {"width": 1280, "height": 720},
        "timeout_seconds": 30,
        "idle_timeout_seconds": 60,
        "allow_file_upload": True,
        "target_url": "https://example.com",
    }


def test_automation_session_create_returns_bootstrap(client, app_state) -> None:
    response = client.post(
        "/api/v1/automation/sessions",
        json=create_payload(),
        headers=automation_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["session"]["session_kind"] == "browser"
    assert body["session"]["browser"] == "chromium"
    assert body["session"]["session_id"].startswith("sess_")
    assert body["session"]["target_url"] == "https://example.com/"
    assert body["viewer_token"]
    assert body["session_api_url"].endswith(
        f"/api/v1/automation/sessions/{body['session']['session_id']}"
    )
    assert f"viewer_token={body['viewer_token']}" in body["signaling_websocket_url"]
    assert len(body["rtc_config"]["ice_servers"]) == 2
    assert app_state.state.launcher.launched[0]["user_id"] == "api-user"


def test_automation_endpoints_require_valid_bearer_key(client) -> None:
    response = client.post(
        "/api/v1/automation/sessions",
        json=create_payload(),
        headers=automation_headers("wrong-key"),
    )

    assert response.status_code == 401


def test_automation_get_bootstrap_and_delete(client) -> None:
    create_response = client.post(
        "/api/v1/automation/sessions",
        json=create_payload(),
        headers=automation_headers(),
    )
    session_id = create_response.json()["session"]["session_id"]

    get_response = client.get(
        f"/api/v1/automation/sessions/{session_id}",
        headers=automation_headers(),
    )
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id

    bootstrap_response = client.get(
        f"/api/v1/automation/sessions/{session_id}/bootstrap",
        headers=automation_headers(),
    )
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["session"]["session_id"] == session_id

    delete_response = client.delete(
        f"/api/v1/automation/sessions/{session_id}",
        headers=automation_headers(),
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "terminated"
