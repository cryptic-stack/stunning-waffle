# Production Single Host

## Intended edge layout

- `browser.example.com` -> frontend service
- `api.example.com` -> FastAPI service
- `turn.example.com` -> coturn service

## Networking baseline

- Keep session workers on an internal Docker network
- Expose only frontend, API, and TURN listeners
- Reserve a narrow TURN relay UDP range
- Publish TCP `80/443` for the edge, TURN `3478/5349`, and TURN relay UDP `49160-49200`
- Point the frontend at `browser.example.com`, API at `api.example.com`, and TURN at `turn.example.com`

## Operations baseline

- Deploy with Docker Compose for the initial milestone
- Keep Postgres data on a named volume
- Provide TURN credentials through environment-managed secrets
- Set `AUTH_MODE=header` when placing the API behind an identity-aware proxy
- Rebuild the Chromium worker image before first launch on a new host

## pfSense / firewall checklist

- Allow `80/tcp` and `443/tcp` to the HAProxy edge host
- Allow `3478/tcp` and `3478/udp` to coturn
- Allow `5349/tcp` and `5349/udp` if TLS TURN is enabled
- Allow UDP `49160-49200` to coturn for relay traffic
- Keep worker containers off the public edge; they should only use the internal Docker network
