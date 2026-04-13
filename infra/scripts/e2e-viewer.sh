#!/usr/bin/env bash
set -euo pipefail

playwright_base_url="${PLAYWRIGHT_BASE_URL:-http://host.docker.internal:3000}"
playwright_api_base_url="${PLAYWRIGHT_API_BASE_URL:-http://host.docker.internal:8000}"
playwright_auth_user_id="${PLAYWRIGHT_AUTH_USER_ID:-}"
playwright_auth_user_email="${PLAYWRIGHT_AUTH_USER_EMAIL:-}"
playwright_auth_user_name="${PLAYWRIGHT_AUTH_USER_NAME:-}"

status_code="$(curl -s -o /dev/null -w '%{http_code}' "${playwright_api_base_url}/api/v1/sessions")"
if [[ ("${status_code}" == "401" || "${status_code}" == "403") && -z "${playwright_auth_user_id}" ]]; then
  echo "Viewer e2e requires AUTH_MODE=dev, or a frontend rebuilt with VITE_AUTH_USER_ID plus PLAYWRIGHT_AUTH_USER_ID set." >&2
  echo "Start it with 'make dev-up' or pass the header-mode env vars before running this check." >&2
  exit 1
fi

docker run --rm \
  --add-host host.docker.internal:host-gateway \
  -e PLAYWRIGHT_BASE_URL="${playwright_base_url}" \
  -e PLAYWRIGHT_API_BASE_URL="${playwright_api_base_url}" \
  -e PLAYWRIGHT_AUTH_USER_ID="${playwright_auth_user_id}" \
  -e PLAYWRIGHT_AUTH_USER_EMAIL="${playwright_auth_user_email}" \
  -e PLAYWRIGHT_AUTH_USER_NAME="${playwright_auth_user_name}" \
  -v "${PWD}:/workspace" \
  -w /workspace/apps/frontend \
  mcr.microsoft.com/playwright:v1.59.1-noble \
  sh -lc "corepack enable && pnpm install --frozen-lockfile && pnpm test:e2e"
