from __future__ import annotations

import json
from datetime import datetime, timezone

from redis import Redis


class RedisSessionStore:
    def __init__(self, client: Redis, namespace: str) -> None:
        self.client = client
        self.namespace = namespace

    def _ttl_key(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}:ttl"

    def _heartbeat_key(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}:heartbeat"

    def _viewer_token_key(self, session_id: str) -> str:
        return f"{self.namespace}:session:{session_id}:viewer-token"

    def create_session(self, session_id: str, timeout_seconds: int) -> None:
        self.client.set(self._ttl_key(session_id), "1", ex=timeout_seconds)

    def delete_session(self, session_id: str) -> None:
        self.client.delete(
            self._ttl_key(session_id),
            self._heartbeat_key(session_id),
            self._viewer_token_key(session_id),
        )

    def session_alive(self, session_id: str) -> bool:
        return bool(self.client.exists(self._ttl_key(session_id)))

    def record_heartbeat(self, session_id: str, state: str, timeout_seconds: int) -> None:
        self.client.set(self._ttl_key(session_id), "1", ex=timeout_seconds)
        self.client.set(
            self._heartbeat_key(session_id),
            json.dumps({"state": state, "at": datetime.now(timezone.utc).isoformat()}),
            ex=timeout_seconds,
        )

    def issue_viewer_token(self, session_id: str, viewer_token: str, timeout_seconds: int) -> None:
        self.client.set(self._viewer_token_key(session_id), viewer_token, ex=timeout_seconds)

    def validate_viewer_token(self, session_id: str, viewer_token: str | None) -> bool:
        if not viewer_token:
            return False
        stored = self.client.get(self._viewer_token_key(session_id))
        return stored == viewer_token
