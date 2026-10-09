# Entrega a auditoría externa (MIA) — `v2.88.95-beta` · `FASE 3`: **reorden — slices `S1`–`S3` (UI/producto · Δ motor = 0)**

> **Fecha:** 2026-10-09 · **Producto:** `V2.88.95-beta` · **Package:** `2.11.95-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.94-beta` (tag anotado objeto `0671ae15` → commit `20fd538c`; `Release tag CI` [`37823112083`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37823112083) **VERDE**). Sobre esa base: [reorden de la FASE 3](./entrega-auditoria-externa-mia-v2.88.94-reorden-fase-3-2026-10-08.md) (docs-only, commit `1a2ce597`) y sus correcciones (`65f69e2c`, `fcb38c29`).
> **Unidad de esta auditoría:** que los tres slices que el auditor **aceptó** —`S1-exit-precio`, `S2-entrada-literal`, `S3-indicadores-razon`— estén **realmente implementados** contra el código, sin fabricar datos y sin mover el motor; y que `S4-agregador-evidencia` siga **no lanzado** (sin emitir `CONFIRMED`).
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** El diff funcional vive en `apps/web/src/**` y `packages/shared/src/**`; el resto es `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.95/README.md`](./evidence/v2.88.95/README.md).
> **Cita POST-TAG:** tag anotado `v2.88.95-beta` (objeto `778c5ec9` → commit `52ba2a26`); `Release tag CI` [`37892237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37892237594) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `281` ficheros / `1750` passed; `python` `4596 passed / 45 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).
> **Continuación (2026-10-09):** las 2 observaciones menores del self-review quedan cerradas en [`v2.88.96-beta`](./entrega-auditoria-externa-mia-v2.88.96-2026-10-09.md) (cobertura `S2` en `completo` + `indicatorSpecs` reales en `S3`), sin cambiar la semántica de los slices.

**Sello dirigido (declarado).** Mandato: cerrar los hallazgos `P2-2`, `P2-3`, `P3-1`/`P3-3`/`P3-4` **solo con presentación** sobre datos ya existentes, y **no** cerrar `P4`. No se añaden funciones al motor ni se inventa ningún dato ausente.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la implementación de `S1`–`S3`:

1. **`S1-exit-precio` (`P2-2`).** El Plan de salida del ticket declara `Objetivo T1`/`Objetivo T2` con **precio** leído de backend (`position.operational.target1/2`, propagado por `OperativaExitMetaV1`). Si el backend no aporta el dato, la UI declara «Sin dato todavía» (`ABSENT_DATA_NOT_MEASURED`); **no** lo calcula desde la UI ni desde un porcentaje.
2. **`S2-entrada-literal` (`P2-3`).** En `phase = "prepared"` + `focusMode = "simple"`, `Entrada` (fill) y `Trigger` (activación) se dibujan como **dos** niveles **solo** si el precio difiere; si coinciden, una sola línea `Trigger` los representa y **no** se duplica.
3. **`S3-indicadores-razon` (`P3-1`/`P3-3`/`P3-4`).** El primer nivel de Finalistas muestra la cadena **Estrategia → indicadores → razón**: indicadores de `definition.indicatorSpecs` → `presetIndicatorSpecs(strategyType)` (`strategySlotToIndicatorLabels`), **nunca** del catálogo del gráfico; razón de `coachFacts.recommendations[].reasons` (ahora **persistidas** en el read-model de coach). Sin evidencia → «Sin dato todavía».

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa `S4-agregador-evidencia`: no hay veredicto único que emita `CONFIRMED` (`READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`).
- **NO** se cierra `P2-4` (con Journey activo, T1/T2 siguen en `sr-only`): fuera del alcance de `S1`–`S3`.
- **NO** se cierran las deudas PARKED de FASE 2 (`F2-1`…`F2-4`).

---

## 2. Cambios verificables (todo con gate)

| # | Slice | Regla | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| 1 | `S1-exit-precio` | `P2-2` | `f3-exit-plan-block.tsx`, `propose-position-exit.ts` | `Objetivo T1`/`T2` con precio de backend; hueco → «Sin dato todavía»; no se fabrica. |
| 2 | `S2-entrada-literal` | `P2-3` | `operational-plan-chart-levels.ts` | `Entrada`≠`Trigger` coexisten en `simple`+`prepared`; iguales → una sola línea. |
| 3 | `S3-indicadores-razon` | `P3-1`/`P3-3`/`P3-4` | `instrument-strategy-top-panel.tsx`, `strategy-top1-chart-indicators.ts`, `coach-facts-api.ts`, `backtest-deep-coach.ts` | Cadena estrategia→indicadores→razón; indicadores del preset, razón persistida; hueco declarado. |
| Tests | — | — | `f3-exit-plan-block.test.tsx`, `operational-plan-chart-levels.test.ts`, `finalist-indicators-reason.test.ts`, `propose-position-exit.test.ts` | Cobertura falsable de cada slice. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.95-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en el commit post-tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); **281 ficheros / 1750 tests verdes**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.95-beta`).
- **`Δ motor = 0` local:** `git diff --name-only -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`P2-4` — T1/T2 en `sr-only` con Journey activo.** **ABIERTO**: fuera del alcance de `S1`–`S3`. **Remediación:** diseño de primer nivel del ticket con Journey.
- **`P4-2`/`P4-4` — veredicto DÍA-D fragmentado y `CONFIRMED` reservado.** **NO LANZADO**: materia de `S4-agregador-evidencia` (read-only, sin emitir `CONFIRMED`).
- **`P4-3` — medición por artefacto CLI, no en vivo.** **ABIERTO**: diseño, no código, en este ciclo.
- **Deuda PARKED FASE 2 (`F2-1`…`F2-4`)**: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/shared build` | **OK** |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **281 ficheros / 1750 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.95-beta`) |
| `git diff --name-only -- packages/py` | **vacío** ⇒ **`Δ motor = 0`** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** (`Release tag CI` [`37892237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37892237594) **VERDE**) |

---

## 6. Sello

- **Producto:** `V2.88.95-beta`. **Package:** `2.11.95-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.95/README.md`, este documento.
- **Modificados:** `apps/web/src/features/trading/f3-exit-plan-block.tsx`, `apps/web/src/features/operations/propose-position-exit.ts`, `apps/web/src/features/charts/operational-plan-chart-levels.ts`, `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx`, `apps/web/src/features/backtests/backtest-deep-coach.ts`, `packages/shared/src/strategy-top1-chart-indicators.ts`, `packages/shared/src/coach-facts-api.ts` (+ tests), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.94-reorden-fase-3-2026-10-08.md`, `docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`, `docs/engineering/arranque-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`, `docs/engineering/respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md`.
- **Tag anotado `v2.88.95-beta`** — objeto `778c5ec9` → commit `52ba2a26`; mensaje `FASE 3 reorder slices S1-S3 (entry/exit literal, targets with price, strategy->indicators->reason) - Delta motor = 0`. **`Release tag CI`** [`37892237594`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37892237594) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.95/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Origen.** Leer el [reorden de la FASE 3](./entrega-auditoria-externa-mia-v2.88.94-reorden-fase-3-2026-10-08.md) y la [respuesta del auditor](./respuesta-auditor-operativa-diaria-entrada-salida-dia-d-2026-10-08.md).
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.94-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/shared build
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad `S1`.** Comprobar que `f3-exit-plan-block.test.tsx` falla si T1/T2 se pintan sin precio de backend (fabricado o por porcentaje).
7. **Falsabilidad `S2`.** Comprobar que `operational-plan-chart-levels.test.ts` falla si la línea `Entrada` se duplica cuando `Entrada == Trigger`.
8. **Falsabilidad `S3`.** Comprobar que `finalist-indicators-reason.test.ts` falla si los indicadores se deducen del catálogo del gráfico o si la razón se inventa sin `reasons` persistidas.
9. **`S4` no lanzado.** Confirmar que no existe un veredicto único que emita `CONFIRMED` y que no hay `OOS_SUPPORTED + MATCH → CONFIRMED`.
10. **Qué falsaría el sello:** que el diff toque `packages/py/**`/motor/contrato/migraciones · que `S1` calcule el precio en la UI · que `S2` duplique la línea cuando los precios coinciden · que `S3` deduzca indicadores del catálogo o invente razones ausentes · que `S4` se haya lanzado o emita `CONFIRMED` · que `replay-repro` no reproduzca `1E3ADAC2…`.
