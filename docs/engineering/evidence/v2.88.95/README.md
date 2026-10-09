# Evidencia `v2.88.95-beta` — `FASE 3`: **reorden — slices `S1`–`S3` (entrada/salida · objetivos con precio · estrategia→indicadores→razón) (UI-only · Δ motor = 0)**

**Producto:** `V2.88.95-beta` · **Package:** `2.11.95-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: el diff funcional vive en `apps/web/src/**` y `packages/shared/src/**`; el resto es `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.95-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/producto + `packages/shared` + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Origen.** Implementa los slices que el auditor externo **aceptó** en el [reorden de la FASE 3](../../entrega-auditoria-externa-mia-v2.88.94-reorden-fase-3-2026-10-08.md); dictamen en la [respuesta del auditor](../../respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md). El cuarto slice (`S4-agregador-evidencia`) **no se lanza**.

**Base:** [`evidence/v2.88.94/README.md`](../v2.88.94/README.md). Auditoría de origen: [`auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`](../../auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md) §5.
**Cita POST-TAG:** tag anotado `v2.88.95-beta` (objeto pendiente → commit pendiente); `Release tag CI` **pendiente**.

## 1. Cambios (por slice)

| # | Slice | Regla | Cierre | Implementación |
| --- | --- | --- | --- | --- |
| 1 | `S1-exit-precio` | `P2-2` | El Plan de salida declara `Objetivo T1`/`Objetivo T2` con **precio** de backend (`position.operational.target1/2` vía `OperativaExitMetaV1`); si falta → «Sin dato todavía» (`ABSENT_DATA_NOT_MEASURED`). **No** se fabrica desde la UI ni desde un porcentaje. | [`f3-exit-plan-block.tsx`](../../../../apps/web/src/features/trading/f3-exit-plan-block.tsx), [`propose-position-exit.ts`](../../../../apps/web/src/features/operations/propose-position-exit.ts) |
| 2 | `S2-entrada-literal` | `P2-3` | En `phase = "prepared"` + `focusMode = "simple"`, `Entrada` (fill) y `Trigger` (activación) coexisten **solo** si el precio difiere; si coinciden, una única línea `Trigger` representa ambos y **no** se duplica. | [`operational-plan-chart-levels.ts`](../../../../apps/web/src/features/charts/operational-plan-chart-levels.ts) |
| 3 | `S3-indicadores-razon` | `P3-1`/`P3-3`/`P3-4` | Primer nivel de Finalistas muestra **Estrategia → indicadores → razón**. Indicadores de `definition.indicatorSpecs` → `presetIndicatorSpecs(strategyType)` (`strategySlotToIndicatorLabels`), **nunca** del catálogo del gráfico. Razón de `coachFacts.recommendations[].reasons` (ahora **persistidas**). Sin evidencia → «Sin dato todavía». | [`instrument-strategy-top-panel.tsx`](../../../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx), [`strategy-top1-chart-indicators.ts`](../../../../packages/shared/src/strategy-top1-chart-indicators.ts), [`coach-facts-api.ts`](../../../../packages/shared/src/coach-facts-api.ts), [`backtest-deep-coach.ts`](../../../../apps/web/src/features/backtests/backtest-deep-coach.ts) |
| — | `S4-agregador-evidencia` | `P4-2`/`P4-4` | **NO LANZADO.** No se emite `CONFIRMED` ni `OOS_SUPPORTED + MATCH → CONFIRMED`. `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`. | — |
| Bump | — | — | `package.json` (`2.11.95-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Tests añadidos/actualizados

- [`f3-exit-plan-block.test.tsx`](../../../../apps/web/src/features/trading/f3-exit-plan-block.test.tsx) — `S1`: objetivo con precio y «Sin dato todavía» cuando falta.
- [`operational-plan-chart-levels.test.ts`](../../../../apps/web/src/features/charts/operational-plan-chart-levels.test.ts) — `S2`: `Entrada`≠`Trigger` coexisten; iguales → una sola línea.
- [`finalist-indicators-reason.test.ts`](../../../../apps/web/src/features/backtests/finalist-indicators-reason.test.ts) — `S3`: cadena indicadores + razón y hueco declarado.
- [`propose-position-exit.test.ts`](../../../../apps/web/src/features/operations/propose-position-exit.test.ts) — `S1`: `target1`/`target2` propagados a `OperativaExitMetaV1`.

## 3. Verificación (local)

- `pnpm --filter @bolsa/shared build` → **OK**.
- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **281 ficheros / 1750 tests verdes**.
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.95-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py` → **vacío** (sin contrato HTTP, sin Alembic).

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema. Live/XTB real sigue fuera: el canal se declara `SIMULADO`.
- **`S4-agregador-evidencia` NO LANZADO.** El veredicto DÍA-D sigue fragmentado y `CONFIRMED` sigue reservado; la medición sigue siendo por artefacto CLI, no en vivo (`P4-3` abierto).
- **`P2-4`** (con Journey activo, T1/T2 en `sr-only`) queda **abierto**: fuera del alcance de `S1`–`S3`.
- **Deuda PARKED (`F2-1`…`F2-4`)**: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
