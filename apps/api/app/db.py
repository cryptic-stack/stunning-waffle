from collections.abc import Generator

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Base


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


def create_engine_and_factory(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    database_url = _normalize_database_url(settings.database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
    return engine, sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations(engine)


def _apply_lightweight_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return

    session_column_info = {column["name"]: column for column in inspector.get_columns("sessions")}
    session_columns = set(session_column_info)
    with engine.begin() as connection:
        if "session_kind" not in session_columns:
            connection.execute(
                text("ALTER TABLE sessions ADD COLUMN session_kind VARCHAR(32) DEFAULT 'browser'")
            )
            connection.execute(
                text("UPDATE sessions SET session_kind = 'browser' WHERE session_kind IS NULL")
            )
        if "desktop_profile" not in session_columns:
            connection.execute(text("ALTER TABLE sessions ADD COLUMN desktop_profile VARCHAR(64)"))
        if "target_url" not in session_columns:
            connection.execute(text("ALTER TABLE sessions ADD COLUMN target_url TEXT"))
        if (
            engine.dialect.name == "postgresql"
            and "browser" in session_column_info
            and session_column_info["browser"].get("nullable") is False
        ):
            connection.execute(text("ALTER TABLE sessions ALTER COLUMN browser DROP NOT NULL"))


def get_db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
