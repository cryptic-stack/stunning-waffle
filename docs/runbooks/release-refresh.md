# Release Refresh

Use this runbook whenever we refresh pinned dependencies or base images for a release candidate.

## Goals

- keep Python and frontend builds deterministic
- refresh base image digests in a controlled way
- verify all primary runtimes before a release tag

## What is pinned today

- Python app dependencies are pinned in `apps/api/constraints.txt`
- Session-agent dependencies are pinned in `apps/session-agent/constraints.txt`
- Frontend installs use `pnpm-lock.yaml`
- API and worker Dockerfiles pin their base images by digest
- Frontend Docker builds pin `node:20-alpine` and `nginx:1.27-alpine` by digest
- The API reaches Docker through the internal `dockerproxy` service using `DOCKER_HOST=tcp://dockerproxy:2375`

## Refresh process

1. Update Python constraints deliberately.
   - Recreate the dependency environment in a disposable container.
   - Capture the new `pip freeze` output.
   - Replace only the relevant app constraints file.

2. Refresh Docker base digests deliberately.
   - Pull the intended tag, for example `python:3.12-slim`, `ubuntu:24.04`, or `kalilinux/kali-rolling`.
   - Record the new digest with `docker image inspect`.
   - Update the Dockerfiles to the new digest rather than leaving floating tags.

3. Refresh frontend lock data deliberately.
   - Use `pnpm install --frozen-lockfile` to confirm the lock is still valid.
   - If dependencies changed, update `pnpm-lock.yaml` in one dedicated commit.

4. Rebuild the runtime artifacts.
   - `powershell -ExecutionPolicy Bypass -File infra/scripts/prebuild-workers.ps1`
   - `docker compose -f infra/compose/docker-compose.yml build api frontend`

## Validation checklist

- `docker compose -f infra/compose/docker-compose.yml run --rm api python -m ruff check app tests`
- `bash infra/scripts/dependency-audit.sh`
- `docker compose -f infra/compose/docker-compose.yml run --rm api pytest tests/test_rtc.py tests/test_launcher.py tests/test_sessions.py`
- `docker run --rm -v ${PWD}/apps/session-agent:/src -w /src python:3.12-slim sh -lc "python -m pip install -c constraints.txt .[dev] >/dev/null && pytest"`
- `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm lint`
- `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm typecheck`
- `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm test`
- `docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm build`
- `powershell -ExecutionPolicy Bypass -File infra/scripts/e2e-smoke.ps1`
- `docker run --rm -v ${PWD}:/workspace -w /workspace/apps/frontend mcr.microsoft.com/playwright:v1.59.1-noble sh -lc "corepack enable && pnpm install --frozen-lockfile && pnpm test:e2e"`

## RC gate

For a full release-candidate gate on a local machine, use one command instead of running the checklist by hand:

- `bash infra/scripts/rc-validate.sh`
- `powershell -ExecutionPolicy Bypass -File infra/scripts/rc-validate.ps1`

These scripts:

- prebuild worker images
- start the stack in `AUTH_MODE=header`
- wait for `readyz`
- run dependency audits for JavaScript and pinned Python constraints
- run backend lint/tests
- run frontend lint/typecheck/tests/build
- run browser and desktop runtime smoke
- run the real viewer Playwright checks
- stop the stack afterward unless `KEEP_STACK_UP=true`

## Release expectation

Do not tag an RC unless the browser and desktop smoke coverage passes for:

- Chrome
- Firefox
- Ubuntu XFCE
- Kali XFCE

If any of those fail after a dependency or base-image refresh, fix the regression first or revert the refresh.
