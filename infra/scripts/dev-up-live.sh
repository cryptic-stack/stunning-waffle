#!/usr/bin/env bash
set -euo pipefail

export AUTH_MODE="${AUTH_MODE:-dev}"
bash infra/scripts/prebuild-workers.sh
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.dev.yml up --build -d frontend api "$@"
