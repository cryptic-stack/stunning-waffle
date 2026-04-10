COMPOSE_FILE=infra/compose/docker-compose.yml
DEV_COMPOSE_FILE=infra/compose/docker-compose.dev.yml

.PHONY: dev-up dev-down dev-up-live test lint typecheck build smoke

dev-up:
	docker compose -f $(COMPOSE_FILE) up --build -d

dev-up-live:
	docker compose -f $(COMPOSE_FILE) -f $(DEV_COMPOSE_FILE) up --build -d frontend api

dev-down:
	docker compose -f $(COMPOSE_FILE) down --remove-orphans

test:
	docker compose -f $(COMPOSE_FILE) run --rm api pytest

lint:
	docker compose -f $(COMPOSE_FILE) -f $(DEV_COMPOSE_FILE) run --rm --no-deps frontend pnpm lint
	docker compose -f $(COMPOSE_FILE) run --rm api python -m ruff check .

typecheck:
	docker compose -f $(COMPOSE_FILE) -f $(DEV_COMPOSE_FILE) run --rm --no-deps frontend pnpm typecheck

build:
	docker compose -f $(COMPOSE_FILE) -f $(DEV_COMPOSE_FILE) run --rm --no-deps frontend pnpm build

smoke:
	bash infra/scripts/e2e-smoke.sh
