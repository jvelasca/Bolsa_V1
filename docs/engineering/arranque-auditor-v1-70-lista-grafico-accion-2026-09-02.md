# Arranque auditor — V1.70 LISTA→GRÁFICO→ACCIÓN (2026-09-02)

> **Padre:** [`spec-v170-lista-grafico-accion-2026-09-02.md`](./spec-v170-lista-grafico-accion-2026-09-02.md) · partida **V1.69** (`e3e1ca40`).

## Punta de partida

- Producto: **V1.69** CI Playwright Release-tag
- Brecha: V1.67 certifica cockpit con gráfico pre-seedeado; falta journey **lista → gráfico → DECISIÓN** sin tab inicial

## Qué auditar

| GP         | Evidencia                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------- |
| GP-V170-01 | `gp-v170-list-mercado-integrated.spec.ts` — workspace vacío · click `list-instrument-open-*` · fase lista = cockpit |
| GP-V170-02 | `instrument-operational-facts.ts` usado por lista + `useInstrumentOperationalContext`                               |
| GP-V170-03 | `focus-instrument-in-mercado.ts` + `ensureOperativaOpen` / `ensureChartsOpen` en layout store                       |
| GP-V170-04 | Journal / alerts / scan → `focusInstrumentInMercado`                                                                |
| GP-V170-05 | `use-position-operational-view.ts` fail-closed · test GP-V170-05                                                    |

**Hardening E2E mock Mercado (colateral audit):**

- `list-recommendation-scores-context.tsx` — contexto layout opcional en hidratación
- `fixtures.ts` — instrumentos mock con `meta.lastClose`

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v170-list
# → 3 passed (1 mock + 2 integrated)

E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v170-list
# → requiere API :8000 + PG; misma suite

pnpm --filter @bolsa/web exec vitest run src/features/trading/use-position-operational-view.test.ts
# → 10 passed

pnpm --filter @bolsa/web exec tsc --noEmit
```

## Run integrado (opt-in)

```bash
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v170-list
```

## OUT explícito

- HUD chart placement redesign
- bump package
- LIVE

## Next aparcado

Bump package · HUD unification residual · **NO LIVE**
