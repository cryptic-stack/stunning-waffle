from __future__ import annotations

import sys

from session_agent.capture import capture_png_bytes


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: browserlab-session-screenshot <width> <height> [session_id] [browser]")

    width = int(sys.argv[1])
    height = int(sys.argv[2])
    session_id = sys.argv[3] if len(sys.argv) > 3 else "manual"
    browser = sys.argv[4] if len(sys.argv) > 4 else "browser"
    sys.stdout.buffer.write(
        capture_png_bytes(
            resolution_width=width,
            resolution_height=height,
            session_id=session_id,
            browser=browser,
        )
    )


if __name__ == "__main__":
    main()
