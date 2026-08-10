# Python packages — Bolsa V1 backend

Capas del backend activo. Ver [ADR-003](../../docs/adr/003-python-backend-ai-platform.md) y [ONBOARDING.md](../../docs/ONBOARDING.md).

| Paquete | Módulo pip | Responsabilidad |
|---------|------------|-----------------|
| `domain/` | `bolsa_domain` | Entidades, enums, protocolos de repositorio |
| `application/` | `bolsa_application` | Casos de uso (sync, import, portfolio, lists…) |
| `infrastructure/` | `bolsa_infrastructure` | SQLAlchemy, config, repos concretos, Alembic |
| `analytics/` | `bolsa_analytics` | SMA, EMA, RSI, motor backtest |
| `market/` | `bolsa_market` | Yahoo provider, ingest OHLCV, símbolos XTB |
| `ai/` | `bolsa-ai` | AI Governance (RFC-007): Proxy, Prompt Registry, adapters LLM (Ollama/OpenAI) |

App HTTP: `apps/api-python` (`bolsa_api`).

## Instalación (recomendada desde raíz)

```bash
pnpm test:py:install
```

Equivalente manual:

```bash
pip install -e packages/py/domain -e packages/py/analytics -e packages/py/market \
  -e packages/py/infrastructure -e packages/py/application -e packages/py/ai \
  -e "apps/api-python[dev]"
```

Alternativa con uv (opcional): `uv sync` + `make dev-api` si usas el Makefile de raíz.

## Tests

```bash
pnpm test:py
# o: python -m pytest packages/py/market/tests packages/py/application/tests \
#         packages/py/analytics/tests packages/py/ai/tests apps/api-python/tests -q
```

## Casos de uso clave (`bolsa_application/`)

| Archivo | Descripción |
|---------|-------------|
| `sync_instrument.py` | Sync OHLCV Yahoo → PostgreSQL |
| `import_instrument.py` | Importar activo externo + sync opcional |
| `search_instruments.py` | Búsqueda catálogo + Yahoo |
| `lists.py` | Listas personalizadas |
| `alerts.py` | Alertas de precio |
| `backtests.py` | Ejecutar backtests |
| `fx.py` | Tipo de cambio Yahoo |

Cada módulo incluye docstring de módulo; las clases exponen `execute()`.
