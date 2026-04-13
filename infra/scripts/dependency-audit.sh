#!/usr/bin/env bash
set -euo pipefail

echo "==> Auditing JavaScript dependencies"
docker run --rm \
  -v "${PWD}:/workspace" \
  -w /workspace \
  node:20-alpine@sha256:f598378b5240225e6beab68fa9f356db1fb8efe55173e6d4d8153113bb8f333c \
  sh -lc "export COREPACK_ENABLE_DOWNLOAD_PROMPT=0 && corepack enable >/dev/null && pnpm install --frozen-lockfile >/dev/null && pnpm audit --prod"

echo "==> Auditing API Python constraints"
docker run --rm \
  -v "${PWD}/apps/api:/workspace" \
  -w /workspace \
  python:3.12-slim \
  sh -lc "export PIP_DISABLE_PIP_VERSION_CHECK=1 && python -m pip install --root-user-action=ignore --no-cache-dir pip-audit==2.9.0 >/dev/null && pip-audit -r constraints.txt"

echo "==> Auditing session-agent Python constraints"
docker run --rm \
  -v "${PWD}/apps/session-agent:/workspace" \
  -w /workspace \
  python:3.12-slim \
  sh -lc "export PIP_DISABLE_PIP_VERSION_CHECK=1 && python -m pip install --root-user-action=ignore --no-cache-dir pip-audit==2.9.0 >/dev/null && pip-audit -r constraints.txt"
