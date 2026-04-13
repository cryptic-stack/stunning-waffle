# Threat Model

## Primary trust boundaries

- User browser to frontend and API edge
- Control plane to worker container runtime
- Worker container to public internet
- TURN relay traffic to session workers

## Main risks

- Browser compromise inside a worker session
- Desktop-environment compromise inside a fuller worker session
- Cross-session access caused by weak isolation
- Orphaned containers consuming compute or leaking state
- Abuse of TURN relay or outbound network access
- Control plane compromise through oversized scope or excessive privileges

## Current mitigations

- Keep the control plane small and separate from future browser workers
- Use one-worker-per-session as the baseline design
- Run browser and desktop workers as a non-root user
- Reach Docker from the API through a restricted socket proxy rather than mounting the raw host socket directly into the control-plane container
- Keep Chromium's own Linux sandbox enabled inside the worker image
- Apply CPU, memory, pid, and read-only filesystem limits to worker containers
- Use tmpfs for browser write paths and runtime scratch space
- Use tmpfs for desktop session state such as `.config`, `.local/share`, `Desktop`, and `Downloads`
- Enforce per-user ownership on session REST and signaling operations
- Sweep expired sessions and remove orphaned managed containers
- Keep workers off the public edge
- Keep TURN relay ports constrained to a small UDP range

## Current tradeoffs

- Chromium workers currently run with `seccomp=unconfined` so the browser's namespace sandbox can start inside Docker. This keeps Chromium's internal sandbox on, but it relaxes the container-level seccomp layer for Chromium sessions.
- Full desktop workers carry a larger package and UI surface than browser-only workers, so they increase the attack surface even though the one-container-per-session isolation model stays the same.

## Deferred to later phases

- oauth2-proxy or equivalent identity proxy in front of the header adapter
- outbound egress policy enforcement beyond the current allow/deny hook
- file upload sandboxing
- richer audit export and alerting
