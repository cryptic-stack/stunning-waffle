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
- Keep `AUTH_MODE=header` behind an identity-aware proxy
- Prebuild all worker images before starting the API on a new host
- Keep `WORKER_VERIFY_IMAGES_ON_STARTUP=true` so missing worker artifacts fail fast during boot
- Keep `WORKER_ALLOW_RUNTIME_IMAGE_RESOLUTION=false` so session creation never hides image build/pull latency in the request path

## pfSense / firewall checklist

- Allow `80/tcp` and `443/tcp` to the HAProxy edge host
- Allow `3478/tcp` and `3478/udp` to coturn
- Allow `5349/tcp` and `5349/udp` if TLS TURN is enabled
- Allow UDP `49160-49200` to coturn for relay traffic
- Keep worker containers off the public edge; they should only use the internal Docker network
