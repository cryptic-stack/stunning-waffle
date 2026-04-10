from dataclasses import dataclass
import os


@dataclass(slots=True)
class AgentConfig:
    session_id: str
    worker_token: str
    api_base_url: str
    session_kind: str
    browser: str | None
    desktop_profile: str | None
    resolution_width: int
    resolution_height: int
    homepage_url: str
    display: str
    heartbeat_interval_seconds: int
    turn_internal_host: str
    turn_username: str
    turn_password: str
    turn_tls_enabled: bool

    @property
    def runtime_name(self) -> str:
        return self.browser or self.desktop_profile or "runtime"

    @property
    def signaling_url(self) -> str:
        base = self.api_base_url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{base}/ws/signaling/{self.session_id}?role=worker&token={self.worker_token}"

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls(
            session_id=os.environ["SESSION_ID"],
            worker_token=os.environ["SESSION_WORKER_TOKEN"],
            api_base_url=os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/"),
            session_kind=os.environ.get("SESSION_KIND", "browser"),
            browser=os.environ.get("SESSION_BROWSER") or None,
            desktop_profile=os.environ.get("SESSION_DESKTOP_PROFILE") or None,
            resolution_width=int(os.environ.get("SESSION_WIDTH", "1280")),
            resolution_height=int(os.environ.get("SESSION_HEIGHT", "720")),
            homepage_url=os.environ.get("SESSION_HOMEPAGE_URL", "https://example.com"),
            display=os.environ.get("DISPLAY", ":99"),
            heartbeat_interval_seconds=int(os.environ.get("HEARTBEAT_INTERVAL_SECONDS", "5")),
            turn_internal_host=os.environ.get("TURN_INTERNAL_HOST", "coturn"),
            turn_username=os.environ.get("TURN_USERNAME", "browserlab"),
            turn_password=os.environ.get("TURN_PASSWORD", "change-me"),
            turn_tls_enabled=os.environ.get("TURN_TLS_ENABLED", "false").lower() == "true",
        )
