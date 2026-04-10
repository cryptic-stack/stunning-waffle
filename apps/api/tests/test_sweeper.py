from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, BrowserSession, SessionEvent, User


def test_sweeper_prunes_old_closed_sessions(app_state) -> None:
    app_state.state.settings.closed_session_retention_seconds = 60
    old_terminated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent_terminated_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    with Session(app_state.state.engine) as session:
        session.add(
            User(
                id="user-1",
                subject="user-1",
                email="user-1@example.com",
                display_name="User One",
            )
        )
        session.add_all(
            [
                BrowserSession(
                    id="sess-old",
                    user_id="user-1",
                    session_kind="browser",
                    browser="chromium",
                    status="terminated",
                    container_id="stub-sess-old",
                    worker_token="token-old",
                    resolution_width=1280,
                    resolution_height=720,
                    timeout_seconds=30,
                    idle_timeout_seconds=15,
                    allow_file_upload=True,
                    expires_at=old_terminated_at,
                    terminated_at=old_terminated_at,
                ),
                BrowserSession(
                    id="sess-recent",
                    user_id="user-1",
                    session_kind="browser",
                    browser="chromium",
                    status="terminated",
                    container_id="stub-sess-recent",
                    worker_token="token-recent",
                    resolution_width=1280,
                    resolution_height=720,
                    timeout_seconds=30,
                    idle_timeout_seconds=15,
                    allow_file_upload=True,
                    expires_at=recent_terminated_at,
                    terminated_at=recent_terminated_at,
                ),
            ]
        )
        session.add_all(
            [
                SessionEvent(session_id="sess-old", event_type="session.terminated"),
                SessionEvent(session_id="sess-recent", event_type="session.terminated"),
                AuditEvent(
                    session_id="sess-old",
                    user_id="user-1",
                    action="session.delete",
                    outcome="success",
                ),
                AuditEvent(
                    session_id="sess-recent",
                    user_id="user-1",
                    action="session.delete",
                    outcome="success",
                ),
            ]
        )
        session.commit()

    app_state.state.sweeper.sweep_once()

    with Session(app_state.state.engine) as session:
        remaining_sessions = set(session.scalars(select(BrowserSession.id)).all())
        remaining_events = {
            row[0] for row in session.execute(select(SessionEvent.session_id)).all()
        }
        remaining_audits = {
            row[0] for row in session.execute(select(AuditEvent.session_id)).all()
        }

    assert remaining_sessions == {"sess-recent"}
    assert remaining_events == {"sess-recent"}
    assert remaining_audits == {"sess-recent"}
