# API

## Implemented

### `GET /healthz`

Returns the API process health status.

Example response:

```json
{
  "status": "ok",
  "service": "api"
}
```

### `GET /readyz`

Returns a readiness response for the API process.

### `POST /api/v1/sessions`

Creates a new ephemeral session record, allocates Redis TTL state, and launches either a browser worker or a desktop worker container.

Accepted launch fields now include:

- `session_kind`: `browser` or `desktop`
- `browser` for browser sessions
- `desktop_profile` for desktop sessions
- optional `target_url`

When `target_url` is omitted for browser sessions, the API falls back to the configured default target URL before handing the value to the worker. Desktop sessions currently ignore `target_url` at runtime in v1, but the field remains accepted for compatibility.

For single-host deployments, `http://localhost:...`, `http://127.0.0.1:...`, and `http://[::1]:...` targets are preserved in the API response but rewritten internally to the configured Docker host-gateway alias for the worker container.

### `GET /api/v1/sessions`

Lists open sessions owned by the current user.

Use `?include_closed=true` to include `terminated` and `expired` sessions that are still within the retention window.

Closed session metadata is retained only for the configured retention window, after which the sweeper removes old session rows plus their session and audit events.

### `GET /api/v1/sessions/{session_id}`

Returns the current session state. If the Redis TTL has elapsed, the session is marked `expired` during the read.

### `DELETE /api/v1/sessions/{session_id}`

Stops and removes the worker container, deletes Redis TTL state, and marks the session terminated in Postgres.

### `POST /api/v1/sessions/{session_id}/heartbeat`

Refreshes TTL state and marks the session active.

### `POST /api/v1/sessions/{session_id}/clipboard`

Accepts clipboard text from the authenticated session owner, records the sync event, and forwards the text to the connected worker when one is online.

### `POST /api/v1/sessions/{session_id}/file-upload`

Accepts a multipart file upload from the authenticated session owner and copies the file into the worker container's `/home/browserlab/Downloads` directory for single-host deployments.

### `GET /api/v1/sessions/{session_id}/downloads`

Lists files currently present in the worker container's `/home/browserlab/Downloads` directory.

### `GET /api/v1/sessions/{session_id}/downloads/{filename}`

Streams a single file back from the worker container as an attachment response.

### `GET /api/v1/sessions/{session_id}/screenshot`

Captures the current browser surface from the worker container and returns a PNG attachment.

### `POST /api/v1/automation/sessions`

Creates a session through a bearer-authenticated automation surface and returns an embed/bootstrap payload with:

- the session record
- a session-scoped viewer token
- an absolute signaling WebSocket URL
- the RTC ICE server config

### `GET /api/v1/automation/sessions/{session_id}`

Returns the current session state for the bearer-authenticated automation client that owns it.

### `GET /api/v1/automation/sessions/{session_id}/bootstrap`

Reissues a fresh viewer token for the session and returns a current bootstrap payload.

### `DELETE /api/v1/automation/sessions/{session_id}`

Terminates a session through the bearer-authenticated automation surface.

### `GET /api/v1/rtc/config`

Returns the ICE server list the frontend uses when creating the WebRTC peer.

### `WS /ws/signaling/{session_id}`

Thin signaling socket for `offer`, `answer`, `ice-candidate`, `control`, and `error` messages.

- viewer connections are authorized by session ownership
- worker connections are authorized by the internal session worker token
- media does not transit the API service

## Auth stub

The API now supports two auth adapter modes:

- `AUTH_MODE=dev`: fall back to the local development user when headers are absent
- `AUTH_MODE=header`: require the configured identity headers, which fits future oauth2-proxy style deployments

The header adapter resolves users from:

- `X-User-Id`
- `X-User-Email`
- `X-User-Name`

Worker connections never use user headers. They authenticate with the session-scoped worker token.

## Automation auth

The automation API uses `Authorization: Bearer <key>` instead of the user-header adapter.

Configure bearer keys with `AUTOMATION_API_KEYS_JSON`, for example:

```json
{
  "dev-automation-key": {
    "user_id": "automation-dev",
    "email": "automation@example.com",
    "display_name": "Automation Dev"
  }
}
```

Viewer peers created through the automation surface connect to signaling with the returned `viewer_token` query parameter instead of user headers.
