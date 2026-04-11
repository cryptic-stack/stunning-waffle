from __future__ import annotations

from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.launcher import StubSessionLauncher
from app.main import create_app
from app.models import BrowserSession


@pytest.fixture()
def test_app(tmp_path: Path):
    database_path = tmp_path / "browserlab-test.db"
    settings = Settings(
        database_url=f"sqlite:///{database_path}",
        redis_url="redis://unused",
        auth_mode="dev",
        session_launch_mode="stub",
        default_user_id="user-1",
        default_user_email="user-1@example.com",
        default_user_display_name="User One",
        host_gateway_alias="host.docker.internal",
        turn_public_host="localhost",
        turn_internal_host="coturn",
        automation_api_keys_json=(
            '{"automation-test-key":{"user_id":"api-user","email":"api@example.com",'
            '"display_name":"API User"}}'
        ),
    )
    app = create_app(settings)

    with TestClient(app, headers={"X-User-Id": "user-1"}) as client:
        app.state.redis_client = fakeredis.FakeStrictRedis(decode_responses=True)
        app.state.redis_store.client = app.state.redis_client
        app.state.launcher = StubSessionLauncher()
        yield app, client


@pytest.fixture()
def client(test_app):
    _, client = test_app
    return client


@pytest.fixture()
def app_state(test_app):
    app, _ = test_app
    return app


def fetch_session(app_state, session_id: str) -> BrowserSession:
    with Session(app_state.state.engine) as session:
        record = session.get(BrowserSession, session_id)
        assert record is not None
        session.expunge(record)
        return record
