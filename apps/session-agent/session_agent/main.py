from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import httpx
import websockets
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp

from session_agent.browser import BrowserRuntime, start_browser_runtime
from session_agent.capture import SessionVideoTrack
from session_agent.config import AgentConfig
from session_agent.input import X11InputController, parse_control_message


logging.basicConfig(level=logging.INFO, format="%(message)s")
LOGGER = logging.getLogger("session-agent")


class SessionAgent:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.peer_connection = self._create_peer_connection()
        self.video_track = SessionVideoTrack(config)
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.websocket: websockets.ClientConnection | None = None
        self.browser_runtime: BrowserRuntime | None = None
        self.control_channel = None
        self.input_controller = X11InputController(
            display=config.display,
            resolution_width=config.resolution_width,
            resolution_height=config.resolution_height,
        )
        self.shutdown_event = asyncio.Event()
        self._offer_started = False
        self._last_state = "idle"

    async def run(self) -> None:
        self.browser_runtime = start_browser_runtime(self.config)
        await self._connect_signaling()

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        signaling_task = asyncio.create_task(self._signaling_loop())

        try:
            await asyncio.wait(
                [heartbeat_task, signaling_task],
                return_when=asyncio.FIRST_EXCEPTION,
            )
        finally:
            heartbeat_task.cancel()
            signaling_task.cancel()
            with contextlib.suppress(Exception):
                await self.http_client.aclose()
            if self.websocket is not None:
                await self.websocket.close()
            await self.peer_connection.close()
            if self.browser_runtime is not None:
                self.browser_runtime.stop()

    async def _connect_signaling(self) -> None:
        self.websocket = await websockets.connect(self.config.signaling_url, max_size=2_000_000)
        await self._send({"type": "control", "event": "worker-ready"})
        LOGGER.info("worker_connected")

    async def _signaling_loop(self) -> None:
        assert self.websocket is not None
        async for raw_message in self.websocket:
            payload = json.loads(raw_message)
            message_type = payload["type"]

            if message_type == "control" and payload.get("event") == "peer-connected":
                continue
            if message_type == "offer":
                await self._handle_offer(payload["sdp"])
            elif message_type == "ice-candidate" and payload.get("candidate"):
                await self._handle_ice(payload["candidate"])
            elif message_type == "control" and payload.get("event") not in {"peer-disconnected"}:
                await self._handle_control(payload.get("event"), payload.get("payload"))
            elif message_type == "control" and payload.get("event") == "peer-disconnected":
                self.control_channel = None
                await self.peer_connection.close()
                self.peer_connection = self._create_peer_connection()
                self._offer_started = False
            elif message_type == "error":
                LOGGER.error("signaling_error %s", payload)

    async def _handle_offer(self, sdp: str) -> None:
        if not self._offer_started:
            self.peer_connection.addTrack(self.video_track)
            self._offer_started = True
            self.peer_connection.on("icecandidate", self._on_ice_candidate)
            self.peer_connection.on("connectionstatechange", self._on_connection_state_change)
            self.peer_connection.on("datachannel", self._on_data_channel)

        await self.peer_connection.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="offer"))
        answer = await self.peer_connection.createAnswer()
        await self.peer_connection.setLocalDescription(answer)
        await self._send(
            {
                "type": "answer",
                "sdp": self.peer_connection.localDescription.sdp,
            }
        )

    async def _handle_ice(self, candidate: dict[str, Any]) -> None:
        ice = candidate_from_sdp(candidate.get("candidate", ""))
        ice.sdpMid = candidate.get("sdpMid")
        ice.sdpMLineIndex = candidate.get("sdpMLineIndex")
        await self.peer_connection.addIceCandidate(ice)

    async def _heartbeat_loop(self) -> None:
        while True:
            await self.http_client.post(
                f"{self.config.api_base_url}/api/v1/sessions/{self.config.session_id}/heartbeat",
                params={"worker_token": self.config.worker_token},
                json={"state": self._last_state},
            )
            await asyncio.sleep(self.config.heartbeat_interval_seconds)

    def _create_peer_connection(self) -> RTCPeerConnection:
        scheme = "turns" if self.config.turn_tls_enabled else "turn"
        transport = "tcp" if self.config.turn_tls_enabled else "udp"
        return RTCPeerConnection(
            RTCConfiguration(
                iceServers=[
                    RTCIceServer(urls=[f"stun:{self.config.turn_internal_host}:3478"]),
                    RTCIceServer(
                        urls=[
                            f"{scheme}:{self.config.turn_internal_host}:3478?transport=udp",
                            f"{scheme}:{self.config.turn_internal_host}:3478?transport=tcp",
                            f"{scheme}:{self.config.turn_internal_host}:5349?transport={transport}",
                        ],
                        username=self.config.turn_username,
                        credential=self.config.turn_password,
                    ),
                ]
            )
        )

    def _on_data_channel(self, channel) -> None:
        self.control_channel = channel

        @channel.on("open")
        def on_open() -> None:
            LOGGER.info("data_channel_open")

        @channel.on("close")
        def on_close() -> None:
            self.control_channel = None

        @channel.on("message")
        def on_message(message) -> None:
            if isinstance(message, str):
                event, payload = parse_control_message(message)
                if event:
                    asyncio.create_task(self._handle_control(event, payload))

    async def _on_ice_candidate(self, candidate) -> None:
        if candidate is None:
            return
        await self._send(
            {
                "type": "ice-candidate",
                "candidate": {
                    "candidate": candidate.to_sdp(),
                    "sdpMid": candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                },
            }
        )

    async def _on_connection_state_change(self) -> None:
        self._last_state = "active" if self.peer_connection.connectionState == "connected" else "idle"
        LOGGER.info("connection_state_changed %s", self.peer_connection.connectionState)

    async def _handle_control(self, event: str | None, payload: dict | None) -> None:
        if event is None:
            return
        try:
            response = await asyncio.to_thread(self.input_controller.handle, event, payload)
        except Exception as exc:  # pragma: no cover - worker runtime guard
            LOGGER.exception("control_event_failed %s", exc)
            await self._send({"type": "error", "code": "CONTROL_EVENT_FAILED", "detail": str(exc)})
            return

        if event == "clipboard-read" and response is not None:
            await self._send_control("clipboard-update", response)

    async def _send(self, payload: dict[str, Any]) -> None:
        assert self.websocket is not None
        await self.websocket.send(json.dumps(payload))

    async def _send_control(self, event: str, payload: dict[str, Any]) -> None:
        message = json.dumps({"type": "control", "event": event, "payload": payload})
        if self.control_channel is not None and getattr(self.control_channel, "readyState", None) == "open":
            self.control_channel.send(message)
            return
        await self._send({"type": "control", "event": event, "payload": payload})


async def _async_main() -> None:
    config = AgentConfig.from_env()
    agent = SessionAgent(config)
    await agent.run()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
