# Firefox worker image

This image installs:

- Firefox ESR
- Xvfb for a headful virtual display
- the shared `session-agent` worker process

Firefox uses the same WebRTC publication and input bridge path as Chromium, so the
control plane can select either browser per session while keeping the worker model
ephemeral and self-hosted.
