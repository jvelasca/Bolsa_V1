# Spec — V1.70 LISTA→GRÁFICO→ACCIÓN

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v169-ci-playwright-release-tag-2026-09-02.md`](./spec-v169-ci-playwright-release-tag-2026-09-02.md) · partida **V1.69** (`e3e1ca40`). **No** LIVE.

Unifica el journey **lista → gráfico → panel DECISIÓN** en Mercado: click en fila abre pestaña, fuerza paneles visibles y alinea fase lista/cockpit con un resolver compartido.

```text
P0  GP-V170-01 — E2E integrado: click Cartera → gráfico activo → cockpit mismo símbolo/fase
P0  GP-V170-02 — Badge/fila lista y cockpit usan `resolveInstrumentOperationalFacts`
P0  GP-V170-03 — Click lista abre panel DECISIÓN (`operativaOpen`) + gráfico
P1  GP-V170-04 — Journal/Hoy/alerts usan `focusInstrumentInMercado` (+ lista cuando aplica)
P1  GP-V170-05 — POV fail-closed: sin fallback cliente si falta wire/blob
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.69 intacto.

## 1. IN

| ID         | Comportamiento                                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| GP-V170-01 | Playwright integrado: workspace sin gráfico · click `list-instrument-open-*` → `chart-indicators-zone` + cockpit |
| GP-V170-02 | `instrument-operational-facts.ts` compartido lista ↔ cockpit                                                     |
| GP-V170-03 | `ensureOperativaOpen` + `ensureChartsOpen` en click lista                                                        |
| GP-V170-04 | `focusInstrumentInMercado` desde Journal (Estudio), alerts, open-hit-in-trading                                  |
| GP-V170-05 | `buildPositionOperationalViewFromDto` → `null` sin wire; test GP-V170-05                                         |

## 2. OUT

HUD chart placement redesign · bump package · LIVE.

## 3. Pre-flight

**Resultados local 2026-09-02:** GP-V170 mock 1/1 · integrado 2/2 · vitest 10/10 · `tsc` OK.

```bash
# Mock
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v170-list

# Integrado (API :8000 + PG)
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v170-list

pnpm --filter @bolsa/web exec vitest run src/features/trading/use-position-operational-view.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```
