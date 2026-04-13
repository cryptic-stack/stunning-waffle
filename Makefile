COMPOSE_FILE=infra/compose/docker-compose.yml
DEV_COMPOSE_FILE=infra/compose/docker-compose.dev.yml

.PHONY: prebuild-workers dev-up dev-down dev-up-live test lint typecheck build audit smoke test-e2e rc-validate

prebuild-workers:
	bash infra/scripts/prebuild-workers.sh

dev-up:
	bash infra/scripts/dev-up.sh

dev-up-live:
	bash infra/scripts/dev-up-live.sh

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

audit:
	bash infra/scripts/dependency-audit.sh

smoke:
	bash infra/scripts/e2e-smoke.sh

test-e2e:
	bash infra/scripts/e2e-viewer.sh

rc-validate:
	bash infra/scripts/rc-validate.sh
