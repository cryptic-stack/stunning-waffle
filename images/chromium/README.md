# Chromium worker image

This image installs:

- Chromium
- Xvfb for a headful virtual display
- the `session-agent` worker process

The worker joins the API signaling channel as the session worker peer, refreshes heartbeats, and publishes a WebRTC video track sourced from the virtual display.
