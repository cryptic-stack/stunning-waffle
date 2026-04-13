#!/usr/bin/env bash
set -euo pipefail

export AUTH_MODE="${AUTH_MODE:-header}"
export VITE_AUTH_USER_ID="${VITE_AUTH_USER_ID:-rc-validator}"
export VITE_AUTH_USER_EMAIL="${VITE_AUTH_USER_EMAIL:-rc-validator@example.com}"
export VITE_AUTH_USER_NAME="${VITE_AUTH_USER_NAME:-RC Validator}"
export PLAYWRIGHT_AUTH_USER_ID="${PLAYWRIGHT_AUTH_USER_ID:-${VITE_AUTH_USER_ID}}"
export PLAYWRIGHT_AUTH_USER_EMAIL="${PLAYWRIGHT_AUTH_USER_EMAIL:-${VITE_AUTH_USER_EMAIL}}"
export PLAYWRIGHT_AUTH_USER_NAME="${PLAYWRIGHT_AUTH_USER_NAME:-${VITE_AUTH_USER_NAME}}"

cleanup() {
  if [[ "${KEEP_STACK_UP:-false}" != "true" ]]; then
    docker compose -f infra/compose/docker-compose.yml down --remove-orphans >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

echo "==> Prebuilding worker images"
bash infra/scripts/prebuild-workers.sh

echo "==> Starting release-candidate stack"
docker compose -f infra/compose/docker-compose.yml up --build -d

echo "==> Waiting for API readiness"
for _ in $(seq 1 30); do
  ready_code="$(curl -s -o /tmp/browserlab-readyz.json -w '%{http_code}' http://localhost:8000/readyz || true)"
  if [[ "${ready_code}" == "200" ]]; then
    cat /tmp/browserlab-readyz.json
    echo
    break
  fi
  sleep 2
done

if [[ "${ready_code:-}" != "200" ]]; then
  echo "API did not become ready." >&2
  cat /tmp/browserlab-readyz.json 2>/dev/null || true
  exit 1
fi

echo "==> Linting API"
docker compose -f infra/compose/docker-compose.yml run --rm api python -m ruff check app tests

echo "==> Auditing dependencies"
bash infra/scripts/dependency-audit.sh

echo "==> Testing API"
docker compose -f infra/compose/docker-compose.yml run --rm api pytest

echo "==> Linting frontend"
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm lint

echo "==> Typechecking frontend"
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm typecheck

echo "==> Testing frontend"
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm test

echo "==> Building frontend"
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml run --rm --no-deps frontend pnpm build

echo "==> Running runtime smoke"
bash infra/scripts/e2e-smoke.sh

echo "==> Running viewer end-to-end checks"
bash infra/scripts/e2e-viewer.sh

echo "RC validation passed."
