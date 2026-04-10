# Local Development

## Start the stack

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/dev-up.ps1
```

## Start the live-reload frontend

```bash
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml up --build frontend api
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/dev-up-live.ps1
```

The development override runs the frontend with Vite on port `3000` and keeps the runtime nginx image tag separate so it does not overwrite the production-style container image.

## Validate services

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000/healthz`
- Sessions API: `http://localhost:8000/api/v1/sessions`
- RTC config: `http://localhost:8000/api/v1/rtc/config`

## Smoke test session lifecycle

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H 'content-type: application/json' \
  -d '{
    "browser": "chromium",
    "resolution": { "width": 1280, "height": 720 },
    "timeout_seconds": 30,
    "idle_timeout_seconds": 15,
    "allow_file_upload": true
  }'
```

The response should include a `session_id` and `container_id`. Deleting the same session should remove the corresponding `browserlab-session-*` Docker container.

Desktop sessions use the same endpoint with `session_kind: "desktop"` and a `desktop_profile`, for example `ubuntu-xfce` or `kali-xfce`. Desktop launches ignore `target_url` in v1.

You can also target services running on the host machine itself. For example, launching a session with `http://localhost:3000` or `http://127.0.0.1:8000/healthz` keeps that URL in the API response, but the worker rewrites it to the Docker host-gateway alias internally so the browser container can actually reach the host service.

## Full smoke script

```bash
bash infra/scripts/e2e-smoke.sh
```

The script checks health endpoints, fetches RTC config, launches Chromium and Firefox smoke sessions, waits for worker heartbeats, and then deletes the sessions.

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/e2e-smoke.ps1
```

## Stop the stack

```bash
docker compose -f infra/compose/docker-compose.yml down --remove-orphans
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/dev-down.ps1
```

## Notes

- The scaffold is intentionally container-first because the host may not have Node.js or Python installed.
- `infra/compose/docker-compose.dev.yml` swaps the frontend container to the dev target with Vite.
- `AUTH_MODE=dev` is convenient locally; switch to `AUTH_MODE=header` when testing identity-proxy behavior.
- Set `AUTOMATION_API_KEYS_JSON` when you want to exercise the bearer-based automation API locally.
- For local WebRTC relay, keep `TURN_PUBLIC_HOST=localhost` and `TURN_INTERNAL_HOST=coturn` unless you are testing a different edge host.
- On Docker Desktop, set `TURN_EXTERNAL_IP` to the host machine's reachable IPv4 address so coturn advertises relay candidates that both the browser and worker container can reach.
- Chromium workers now rely on Chromium's own sandbox instead of `--no-sandbox`, which means local Chromium sessions run with a relaxed Docker seccomp profile (`seccomp=unconfined`) so the browser can create its internal namespaces.
- The current local-testing path is single-host only. It is not a remote SSH tunnel or cross-network private access feature yet.
- Files uploaded into a session land in `/home/browserlab/Downloads` and can now be listed and downloaded back out through the session downloads API.
- Desktop worker images are much larger than the browser-only workers. Expect the first Ubuntu XFCE and Kali XFCE image builds to take noticeably longer and use more disk.
