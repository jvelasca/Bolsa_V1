# Evidencia `v2.88.96-beta` — `FASE 3`: **cierre de las 2 observaciones de `S1`–`S3` (cobertura `S2` completo + `indicatorSpecs` reales en `S3`) (UI-only · Δ motor = 0)**

**Producto:** `V2.88.96-beta` · **Package:** `2.11.96-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.96-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Origen.** Cierra las dos observaciones menores del self-review del sello [`v2.88.95-beta`](../v2.88.95/README.md); no cambia la semántica de `S1`–`S3`, refuerza cobertura y fuente de datos. `S4-agregador-evidencia` **no se lanza**.

**Base:** [`evidence/v2.88.95/README.md`](../v2.88.95/README.md).
**Cita POST-TAG:** tag anotado `v2.88.96-beta` (objeto `74e3fcf4` → commit `de3e5222`); `Release tag CI` [`37894478961`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37894478961) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `281` ficheros / `1753` passed; `python` `4596 passed / 45 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

## 1. Cambios (por observación)

| # | Observación (de `v2.88.95`) | Cierre | Implementación |
| --- | --- | --- | --- |
| 1 | `S2`: sin test explícito del caso `focusMode = "completo"` + `prepared` con `Entrada ≠ Trigger` | Test nuevo que fija la coexistencia en `completo` igual que en `simple` (rama compartida, ahora blindada) | [`operational-plan-chart-levels.test.ts`](../../../../apps/web/src/features/charts/operational-plan-chart-levels.test.ts) |
| 2 | `S3`: `definitionByStrategyId` pasaba `indicatorSpecs: []` (la rama «definition» nunca se cableaba) | El panel resuelve hasta ~3 `strategyDefinitionId` vía `GET /api/strategies/{id}` y usa `definition.indicatorSpecs` como fuente preferida; fallback a `presetIndicatorSpecs(strategyType)`. Extraído a helper puro `buildStrategyDefinitionRefMap` | [`instrument-strategy-top-panel.tsx`](../../../../apps/web/src/features/backtests/instrument-strategy-top-panel.tsx), [`finalist-indicators-reason.test.ts`](../../../../apps/web/src/features/backtests/finalist-indicators-reason.test.ts) |
| Bump | — | `package.json` (`2.11.96-beta`) + `meta.bump` de `v2_89`…`v2_97` | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- `S1`–`S3` conservan su semántica: objetivos con precio de backend (`S1`), `Entrada`≠`Trigger` sin duplicar (`S2`), cadena estrategia→indicadores→razón sin deducir del catálogo del gráfico (`S3`).
- Indicadores: fuente = `definition.indicatorSpecs` → `presetIndicatorSpecs(strategyType)` → `[]`; sin evidencia → «Sin dato todavía».
- `S4-agregador-evidencia` **NO LANZADO**: `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`; no se emite `CONFIRMED`.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **281 ficheros / 1753 tests verdes** (+3 respecto a `2.11.95-beta`).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.96-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py` → **vacío** (sin contrato HTTP, sin Alembic).

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema.
- **`S4-agregador-evidencia` NO LANZADO** (`P4-2`/`P4-4`); `P4-3` (medición por artefacto CLI) y `P2-4` (T1/T2 en `sr-only` con Journey) siguen **abiertos**.
- **Deuda PARKED (`F2-1`…`F2-4`)**: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
