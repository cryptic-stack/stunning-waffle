# session-agent

`session-agent` is the worker-side bridge that runs inside each ephemeral browser container.

Current responsibilities:

- launch Chromium or Firefox into a virtual X display
- connect to the API signaling socket as the worker peer
- publish a WebRTC video track sourced from the display surface
- receive control messages over the data channel or signaling fallback
- inject mouse, keyboard, wheel, and clipboard actions into the browser session
- refresh worker heartbeats back to the control plane
