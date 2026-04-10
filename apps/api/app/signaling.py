from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from fastapi import WebSocket

Role = Literal["viewer", "worker"]


@dataclass(slots=True)
class Connection:
    websocket: WebSocket
    role: Role


class SignalingRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, dict[Role, Connection]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def register(self, session_id: str, role: Role, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[session_id][role] = Connection(websocket=websocket, role=role)

    async def unregister(self, session_id: str, role: Role) -> Connection | None:
        async with self._lock:
            role_map = self._connections.get(session_id, {})
            connection = role_map.pop(role, None)
            if not role_map and session_id in self._connections:
                self._connections.pop(session_id, None)
            return connection

    async def connection(self, session_id: str, role: Role) -> Connection | None:
        async with self._lock:
            role_map = self._connections.get(session_id, {})
            return role_map.get(role)

    async def peer(self, session_id: str, role: Role) -> Connection | None:
        peer_role: Role = "worker" if role == "viewer" else "viewer"
        return await self.connection(session_id, peer_role)
