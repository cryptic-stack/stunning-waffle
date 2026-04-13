# foss-browserlab

`foss-browserlab` is a self-hosted, open-source browser session platform modeled around live interactive browser streaming with a small control plane and ephemeral session workers.

This repository now contains a working Phase 0-6 MVP:

- React frontend launcher and session list in `apps/frontend`
- FastAPI API with session lifecycle, signaling, RTC config, and cleanup sweeper in `apps/api`
- shared TypeScript packages in `packages/`
- Docker Compose stack with `frontend`, `api`, `redis`, `postgres`, and `coturn`
- Chromium, Firefox, Brave, Edge, Vivaldi, Ubuntu XFCE, and Kali XFCE session worker images plus the Python session agent in `images/` and `apps/session-agent`
- baseline lint, format, test, and CI wiring
- initial architecture, API, threat-model, and runbook docs
- Browserling parity gap analysis in `docs/browserling-gap-analysis.md`

## Quick start

The host environment only needs Docker for the current scaffold.

```bash
make dev-up
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/dev-up.ps1
```

The dev-up scripts now prebuild all worker images before starting the stack and explicitly set `AUTH_MODE=dev` for local-only use.

Expected endpoints after startup:

- Frontend: `http://localhost:3000`
- API health: `http://localhost:8000/healthz`
- Sessions API: `http://localhost:8000/api/v1/sessions`

## Developer workflow

- `make prebuild-workers` builds all browser and desktop worker images up front
- `make dev-up` starts the stack
- `make dev-up-live` starts the API plus Vite frontend override
- `make dev-down` stops the stack
- `make test` runs backend tests in Docker
- `make lint` runs frontend ESLint and backend Ruff in Docker
- `make typecheck` runs frontend TypeScript checks in Docker
- `make build` runs the frontend production build in Docker
- `make test-e2e` runs the Playwright viewer smoke against a live local stack started in `AUTH_MODE=dev`

Shell script equivalents live in `infra/scripts/`.
PowerShell variants are included for Windows hosts.
Release refresh guidance lives in `docs/runbooks/release-refresh.md`.

## Repository layout

```text
foss-browserlab/
├── apps/
│   ├── frontend/
│   ├── api/
│   └── session-agent/
├── images/
│   ├── chromium/
│   ├── firefox/
│   ├── brave/
│   ├── edge/
│   └── vivaldi/
├── infra/
│   ├── compose/
│   ├── coturn/
│   ├── haproxy/
│   └── scripts/
├── packages/
│   ├── shared-types/
│   └── shared-client/
├── tests/
├── docs/
└── README.md
```

## Current status

Implemented:

- session create/list/get/delete plus heartbeat, clipboard, file-upload, download-out, screenshot capture, RTC config, and target URL launch
- first-class `browser` and `desktop` session kinds with browser workers and full desktop workers
- bearer-authenticated automation session create/get/delete/bootstrap for embed-style clients
- single-host local target access for `localhost` and loopback URLs via Docker host-gateway rewriting
- Redis-backed TTL tracking, sweeper-driven expiry, and orphan cleanup
- Postgres-backed session and audit-style event records
- Docker-backed Chromium, Firefox, Brave, Edge, Vivaldi, Ubuntu XFCE, and Kali XFCE workers with resource limits and read-only rootfs defaults
- ownership-aware signaling for viewer and worker peers
- WebRTC media viewer with mouse, keyboard, clipboard, screenshot, downloads, and reconnect logic across browser and desktop sessions

Still ahead:

- production auth proxy integration beyond the header-based adapter
- broader remote TURN validation outside the single-host Compose setup
- optional post-v1 features such as recording, persistent profiles, and shared sessions
- broader Browserling parity items such as remote SSH tunneling, browser/OS expansion, recording export, and geo/network controls

## Authenticated frontend notes

- Browser viewers now bootstrap through `GET /api/v1/sessions/{session_id}/bootstrap`, which returns a short-lived viewer token and a ready-to-use signaling WebSocket URL
- For local header-auth testing without an auth proxy, the frontend build can embed request headers with `VITE_AUTH_USER_ID`, `VITE_AUTH_USER_EMAIL`, and `VITE_AUTH_USER_NAME`
- In production, prefer a real auth proxy that injects identity upstream instead of baking user headers into the frontend build

## Release-candidate defaults

- The API now fails closed by default with `AUTH_MODE=header`
- Local dev scripts explicitly opt into `AUTH_MODE=dev`
- Worker images are expected to be prebuilt before the API starts
- Runtime session creation no longer silently builds or pulls missing worker images unless `WORKER_ALLOW_RUNTIME_IMAGE_RESOLUTION=true`
