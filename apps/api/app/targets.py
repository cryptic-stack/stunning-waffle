from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from app.config import Settings


@dataclass(slots=True)
class ResolvedSessionTarget:
    requested_url: str
    worker_url: str
    access_mode: str


def resolve_session_target(target_url: str, settings: Settings) -> ResolvedSessionTarget:
    parsed = urlsplit(target_url)
    hostname = (parsed.hostname or "").lower()
    local_hostnames = {
        hostname.strip().lower()
        for hostname in settings.host_local_target_hostnames.split(",")
        if hostname.strip()
    }

    if settings.enable_host_local_targets and hostname in local_hostnames:
        worker_netloc = _build_netloc(parsed, settings.host_gateway_alias)
        worker_url = urlunsplit(parsed._replace(netloc=worker_netloc))
        return ResolvedSessionTarget(
            requested_url=target_url,
            worker_url=worker_url,
            access_mode="host-local",
        )

    return ResolvedSessionTarget(
        requested_url=target_url,
        worker_url=target_url,
        access_mode="public",
    )


def _build_netloc(parsed: SplitResult, hostname: str) -> str:
    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    formatted_hostname = hostname
    if ":" in formatted_hostname and not formatted_hostname.startswith("["):
        formatted_hostname = f"[{formatted_hostname}]"

    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{userinfo}{formatted_hostname}{port}"
