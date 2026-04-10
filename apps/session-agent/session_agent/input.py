from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass


SPECIAL_KEYS = {
    "AltLeft": "Alt_L",
    "AltRight": "Alt_R",
    "ArrowDown": "Down",
    "ArrowLeft": "Left",
    "ArrowRight": "Right",
    "ArrowUp": "Up",
    "Backspace": "BackSpace",
    "CapsLock": "Caps_Lock",
    "ControlLeft": "Control_L",
    "ControlRight": "Control_R",
    "Delete": "Delete",
    "End": "End",
    "Enter": "Return",
    "Escape": "Escape",
    "Home": "Home",
    "Insert": "Insert",
    "MetaLeft": "Super_L",
    "MetaRight": "Super_R",
    "PageDown": "Page_Down",
    "PageUp": "Page_Up",
    "ShiftLeft": "Shift_L",
    "ShiftRight": "Shift_R",
    "Space": "space",
    "Tab": "Tab",
}


@dataclass(slots=True)
class X11InputController:
    display: str
    resolution_width: int
    resolution_height: int

    def handle(self, event: str, payload: dict | None = None) -> dict | None:
        payload = payload or {}
        if event == "pointer-move":
            self.move_pointer(int(payload["x"]), int(payload["y"]))
            return None
        if event == "pointer-click":
            self.click(int(payload.get("button", 1)), int(payload["x"]), int(payload["y"]))
            return None
        if event == "pointer-down":
            self.mouse_down(int(payload.get("button", 1)), int(payload["x"]), int(payload["y"]))
            return None
        if event == "pointer-up":
            self.mouse_up(int(payload.get("button", 1)), int(payload["x"]), int(payload["y"]))
            return None
        if event == "wheel":
            self.scroll(int(payload.get("delta_x", 0)), int(payload.get("delta_y", 0)))
            return None
        if event == "key-press":
            self.key_press(payload)
            return None
        if event == "text-input":
            self.type_text(str(payload.get("text", "")))
            return None
        if event == "clipboard-paste":
            text = str(payload.get("text", ""))
            self.set_clipboard(text)
            self.key_combo(["ctrl"], "v")
            return None
        if event == "clipboard-read":
            return {"text": self.get_clipboard()}
        return None

    def move_pointer(self, x: int, y: int) -> None:
        self._run("xdotool", "mousemove", "--sync", str(self._clamp_x(x)), str(self._clamp_y(y)))

    def click(self, button: int, x: int, y: int) -> None:
        self.move_pointer(x, y)
        self._run("xdotool", "click", str(self._button_number(button)))

    def mouse_down(self, button: int, x: int, y: int) -> None:
        self.move_pointer(x, y)
        self._run("xdotool", "mousedown", str(self._button_number(button)))

    def mouse_up(self, button: int, x: int, y: int) -> None:
        self.move_pointer(x, y)
        self._run("xdotool", "mouseup", str(self._button_number(button)))

    def scroll(self, delta_x: int, delta_y: int) -> None:
        if delta_y:
            button = 5 if delta_y > 0 else 4
            for _ in range(max(1, abs(delta_y) // 120)):
                self._run("xdotool", "click", str(button))
        if delta_x:
            button = 7 if delta_x > 0 else 6
            for _ in range(max(1, abs(delta_x) // 120)):
                self._run("xdotool", "click", str(button))

    def key_press(self, payload: dict) -> None:
        modifiers = [
            name
            for name, enabled in {
                "ctrl": bool(payload.get("ctrlKey")),
                "alt": bool(payload.get("altKey")),
                "shift": bool(payload.get("shiftKey")),
                "super": bool(payload.get("metaKey")),
            }.items()
            if enabled
        ]
        key = self._resolve_key(payload)
        self.key_combo(modifiers, key)

    def key_combo(self, modifiers: list[str], key: str) -> None:
        combo = "+".join([*modifiers, key]) if modifiers else key
        self._run("xdotool", "key", "--clearmodifiers", combo)

    def type_text(self, text: str) -> None:
        if not text:
            return
        self._run("xdotool", "type", "--delay", "0", "--clearmodifiers", text)

    def set_clipboard(self, text: str) -> None:
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-in"],
            input=text,
            text=True,
            env=self._env,
            check=True,
        )

    def get_clipboard(self) -> str:
        completed = subprocess.run(
            ["xclip", "-selection", "clipboard", "-out"],
            capture_output=True,
            text=True,
            env=self._env,
            check=False,
        )
        return completed.stdout

    @property
    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def _run(self, *command: str) -> None:
        subprocess.run(command, env=self._env, check=True)

    def _resolve_key(self, payload: dict) -> str:
        code = str(payload.get("code", ""))
        key = str(payload.get("key", ""))
        if code in SPECIAL_KEYS:
            return SPECIAL_KEYS[code]
        if key in SPECIAL_KEYS:
            return SPECIAL_KEYS[key]
        if code.startswith("Key") and len(code) == 4:
            return code[-1].lower()
        if code.startswith("Digit") and len(code) == 6:
            return code[-1]
        if len(key) == 1:
            return key
        return key or "space"

    def _button_number(self, button: int) -> int:
        return {0: 1, 1: 2, 2: 3}.get(button, 1)

    def _clamp_x(self, x: int) -> int:
        return max(0, min(self.resolution_width - 1, x))

    def _clamp_y(self, y: int) -> int:
        return max(0, min(self.resolution_height - 1, y))


def parse_control_message(raw_message: str) -> tuple[str | None, dict | None]:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return None, None
    if payload.get("type") != "control":
        return None, None
    return payload.get("event"), payload.get("payload")
