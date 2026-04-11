from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from redis import Redis
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from app.auth import (
    AuthenticatedUser,
    auth_headers,
    authorization_header,
    require_authenticated_user,
    resolve_api_key_user,
)
from app.config import Settings
from app.db import get_db_session
from app.launcher import SessionLauncher
from app.redis_store import RedisSessionStore
from app.services.sessions import SessionService
from app.signaling import SignalingRegistry


def get_settings(connection: HTTPConnection) -> Settings:
    return connection.app.state.settings


def get_db(connection: HTTPConnection) -> Generator[Session, None, None]:
    yield from get_db_session(connection.app.state.session_factory)


def get_redis_client(connection: HTTPConnection) -> Redis:
    return connection.app.state.redis_client


def get_redis_store(connection: HTTPConnection) -> RedisSessionStore:
    return connection.app.state.redis_store


def get_launcher(connection: HTTPConnection) -> SessionLauncher:
    return connection.app.state.launcher


def get_signaling_registry(connection: HTTPConnection) -> SignalingRegistry:
    return connection.app.state.signaling_registry


def get_session_service(
    db: Session = Depends(get_db),
    redis_store: RedisSessionStore = Depends(get_redis_store),
    launcher: SessionLauncher = Depends(get_launcher),
    settings: Settings = Depends(get_settings),
) -> SessionService:
    return SessionService(db=db, redis_store=redis_store, launcher=launcher, settings=settings)


def get_current_user(
    headers: tuple[str | None, str | None, str | None] = Depends(auth_headers),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    return require_authenticated_user(settings, *headers)


def get_optional_current_user(
    headers: tuple[str | None, str | None, str | None] = Depends(auth_headers),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser | None:
    if settings.auth_mode != "dev" and not headers[0]:
        return None
    return require_authenticated_user(settings, *headers)


def get_automation_user(
    authorization: str | None = Depends(authorization_header),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    return resolve_api_key_user(settings, authorization)
