import json
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = "sqlite:///./browserlab.db"
    redis_url: str = "redis://localhost:6379/0"
    auth_mode: Literal["dev", "header"] = "header"
    session_launch_mode: str = "stub"
    worker_image: str = "foss-browserlab-chromium-worker:latest"
    worker_build_context: str | None = None
    worker_dockerfile: str | None = None
    firefox_worker_image: str = "foss-browserlab-firefox-worker:latest"
    firefox_worker_build_context: str | None = None
    firefox_worker_dockerfile: str | None = None
    brave_worker_image: str = "foss-browserlab-brave-worker:latest"
    brave_worker_build_context: str | None = None
    brave_worker_dockerfile: str | None = None
    edge_worker_image: str = "foss-browserlab-edge-worker:latest"
    edge_worker_build_context: str | None = None
    edge_worker_dockerfile: str | None = None
    vivaldi_worker_image: str = "foss-browserlab-vivaldi-worker:latest"
    vivaldi_worker_build_context: str | None = None
    vivaldi_worker_dockerfile: str | None = None
    ubuntu_xfce_worker_image: str = "foss-browserlab-ubuntu-xfce-worker:latest"
    ubuntu_xfce_worker_build_context: str | None = None
    ubuntu_xfce_worker_dockerfile: str | None = None
    kali_xfce_worker_image: str = "foss-browserlab-kali-xfce-worker:latest"
    kali_xfce_worker_build_context: str | None = None
    kali_xfce_worker_dockerfile: str | None = None
    worker_network: str | None = None
    worker_command: str | None = "sh -c \"trap 'exit 0' TERM INT; while true; do sleep 60; done\""
    worker_cpu_limit: float = 1.5
    worker_memory_limit: str = "2g"
    worker_pids_limit: int = 256
    worker_read_only_rootfs: bool = True
    worker_tmpfs_size_mb: int = 512
    worker_allow_outbound_network: bool = True
    worker_allow_runtime_image_resolution: bool = False
    worker_verify_images_on_startup: bool = True
    enable_host_local_targets: bool = True
    host_gateway_alias: str = "host.docker.internal"
    host_local_target_hostnames: str = "localhost,127.0.0.1,::1"
    default_user_id: str = "dev-user"
    default_user_email: str = "dev@example.com"
    default_user_display_name: str = "Developer"
    default_session_target_url: str = "https://example.com"
    session_id_prefix: str = "sess"
    correlation_id_header: str = "X-Request-ID"
    owner_header_name: str = "X-User-Id"
    owner_email_header_name: str = "X-User-Email"
    owner_name_header_name: str = "X-User-Name"
    automation_api_keys_json: str = "{}"
    turn_public_host: str = "turn.example.com"
    turn_internal_host: str = "coturn"
    turn_username: str = "browserlab"
    turn_password: str = "change-me"
    turn_tls_enabled: bool = False
    turn_min_port: int = 49160
    turn_max_port: int = 49200
    log_level: str = "INFO"
    redis_namespace: str = Field(default="browserlab", min_length=1)
    sweeper_interval_seconds: int = 30
    closed_session_retention_seconds: int = 900
    max_upload_bytes: int = 25 * 1024 * 1024

    def automation_api_keys(self) -> dict[str, dict[str, str | None]]:
        raw = json.loads(self.automation_api_keys_json or "{}")
        if not isinstance(raw, dict):
            return {}

        parsed: dict[str, dict[str, str | None]] = {}
        for token, value in raw.items():
            if not isinstance(token, str) or not token:
                continue
            if isinstance(value, str):
                parsed[token] = {
                    "user_id": value,
                    "email": None,
                    "display_name": None,
                }
                continue
            if isinstance(value, dict) and isinstance(value.get("user_id"), str):
                parsed[token] = {
                    "user_id": value["user_id"],
                    "email": value.get("email"),
                    "display_name": value.get("display_name"),
                }
        return parsed


@lru_cache
def get_settings() -> Settings:
    return Settings()
