from __future__ import annotations

import asyncio
import io
import time
from datetime import datetime, timezone
from fractions import Fraction

import av
import mss
import numpy as np
from aiortc import VideoStreamTrack
from aiortc.mediastreams import VIDEO_CLOCK_RATE
from PIL import Image, ImageDraw

from session_agent.config import AgentConfig


def capture_png_bytes(
    resolution_width: int,
    resolution_height: int,
    *,
    session_id: str = "manual",
    browser: str = "browser",
) -> bytes:
    monitor = {
        "top": 0,
        "left": 0,
        "width": resolution_width,
        "height": resolution_height,
    }
    try:
        with mss.mss() as sct:
            shot = sct.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)
    except Exception:
        image = _synthetic_image(
            resolution_width=resolution_width,
            resolution_height=resolution_height,
            session_id=session_id,
            browser=browser,
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class SessionVideoTrack(VideoStreamTrack):
    def __init__(self, config: AgentConfig) -> None:
        super().__init__()
        self.config = config
        self.sct: mss.mss | None = None
        self.target_fps = _target_fps_for_session(config)
        self._timestamp_step = max(1, int(VIDEO_CLOCK_RATE / self.target_fps))
        self.monitor = {
            "top": 0,
            "left": 0,
            "width": config.resolution_width,
            "height": config.resolution_height,
        }

    async def recv(self) -> av.VideoFrame:
        pts, time_base = await self.next_timestamp()
        frame = self._capture_frame()
        frame.pts = pts
        frame.time_base = time_base
        return frame

    async def next_timestamp(self) -> tuple[int, Fraction]:
        if self.readyState != "live":
            raise av.error.EOFError("Media stream is no longer live")

        if hasattr(self, "_timestamp"):
            self._timestamp += self._timestamp_step
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - time.time()
            await asyncio.sleep(max(0.0, wait))
        else:
            self._start = time.time()
            self._timestamp = 0
        return self._timestamp, Fraction(1, VIDEO_CLOCK_RATE)

    def _capture_frame(self) -> av.VideoFrame:
        try:
            if self.sct is None:
                self.sct = mss.mss()
            shot = self.sct.grab(self.monitor)
            bgra = np.frombuffer(shot.bgra, dtype=np.uint8).reshape((shot.height, shot.width, 4))
            return av.VideoFrame.from_ndarray(bgra, format="bgra")
        except Exception:
            rgb = self._synthetic_frame()
            return av.VideoFrame.from_ndarray(rgb, format="rgb24")

    def _synthetic_frame(self) -> np.ndarray:
        image = _synthetic_image(
            resolution_width=self.config.resolution_width,
            resolution_height=self.config.resolution_height,
            session_id=self.config.session_id,
            browser=self.config.runtime_name,
        )
        return np.array(image, dtype=np.uint8)


def _synthetic_image(
    *,
    resolution_width: int,
    resolution_height: int,
    session_id: str,
    browser: str,
) -> Image.Image:
    width = resolution_width
    height = resolution_height
    image = Image.new("RGB", (width, height), color=(18, 32, 51))
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, width - 40, height - 40), outline=(34, 197, 94), width=6)
    draw.text((70, 80), "foss-browserlab worker", fill=(255, 255, 255))
    draw.text((70, 130), f"session: {session_id}", fill=(186, 230, 253))
    draw.text((70, 180), f"browser: {browser}", fill=(186, 230, 253))
    draw.text(
        (70, 230),
        datetime.now(timezone.utc).strftime("UTC %Y-%m-%d %H:%M:%S"),
        fill=(255, 255, 255),
    )
    return image


def _target_fps_for_session(config: AgentConfig) -> int:
    if config.session_kind == "desktop":
        return 20
    return 24
