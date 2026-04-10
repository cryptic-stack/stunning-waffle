from app.config import Settings
from app.targets import resolve_session_target


def test_public_target_is_unchanged() -> None:
    settings = Settings()

    resolved = resolve_session_target("https://example.com/docs", settings)

    assert resolved.requested_url == "https://example.com/docs"
    assert resolved.worker_url == "https://example.com/docs"
    assert resolved.access_mode == "public"


def test_localhost_target_is_rewritten_for_worker() -> None:
    settings = Settings(host_gateway_alias="host.docker.internal")

    resolved = resolve_session_target("http://localhost:3000/demo?tab=1", settings)

    assert resolved.requested_url == "http://localhost:3000/demo?tab=1"
    assert resolved.worker_url == "http://host.docker.internal:3000/demo?tab=1"
    assert resolved.access_mode == "host-local"


def test_loopback_target_can_be_disabled() -> None:
    settings = Settings(enable_host_local_targets=False)

    resolved = resolve_session_target("http://127.0.0.1:8080", settings)

    assert resolved.worker_url == "http://127.0.0.1:8080"
    assert resolved.access_mode == "public"
