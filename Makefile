.PHONY: dev-api lint typecheck test install

install:
	uv sync

dev-api:
	cd apps/api-python && uv run bolsa-api

lint:
	# --config explícito: sin él, ruff NO encuentra el pyproject raíz al recibir
	# directorios y pierde `known-first-party`, reportando cientos de I001 falsos
	# (medido: 2 reales con --config frente a 828 sin él en el árbol integrado).
	uv run ruff check --config pyproject.toml packages/py apps/api-python
	uv run ruff format --check --config pyproject.toml packages/py apps/api-python

typecheck:
	uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src

test:
	uv run pytest packages/py/market/tests apps/api-python/tests -q

test-parity:
	uv run pytest apps/api-python/tests/integration/test_parity_instruments.py -m integration -q

alembic-upgrade:
	cd packages/py/infrastructure && uv run alembic upgrade head
