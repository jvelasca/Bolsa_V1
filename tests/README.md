# Tests — Bolsa V1



Fixtures y guía de tests del monorepo.



## Tests principales



```bash

pnpm test:py       # Backend Python — pytest

pnpm typecheck     # Frontend TypeScript

pnpm test          # Tests unitarios @bolsa/web

```



| Área | Ubicación |

|------|-----------|

| API FastAPI | `apps/api-python/tests/` |

| Analytics | `packages/py/analytics/tests/` |

| Market | `packages/py/market/tests/` |

| Application | `packages/py/application/tests/` |

| Frontend | `apps/web/src/**/*.test.ts(x)` |



Instalar deps Python: `pnpm test:py:install`



## Fixtures



- `fixtures/ohlcv-ibe-sample.json` — barras OHLCV IBE



## Legacy archivado



Tests de paridad TS↔Python y suite `@bolsa/api` están en `archive/legacy-tests/` y `archive/legacy-ts/`. Ver [LEGACY.md](../docs/LEGACY.md).

