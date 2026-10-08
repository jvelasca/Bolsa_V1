# Evidencia `v2.88.93-beta` — `UI`: **UI 6.x — cierre de huecos del barrido global (Gate N · comodín `—`)**

**Producto:** `V2.88.93-beta` · **Package:** `2.11.93-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.93-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/copy + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Cierre de huecos del barrido de `v2.88.92`.** La [evidencia `v2.88.92`](../v2.88.92/README.md) §4 dejó abierto que el censo del gate era **acotado**; la revisión posterior a `v2.88.92-beta` detectó hallazgos **fuera de ese censo**: `Gate` crudo en el drawer de Oportunidades y «Gate preset» en Estrategias guardadas, la jerga de `Paper D` y el comodín `—` en superficies hermanas. Aquí se cierran **todos** y se añaden al gate falsable.

**Base:** [`evidence/v2.88.92/README.md`](../v2.88.92/README.md). Contrato: [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md). Auditoría de origen: [`auditoria-ui-6-x-global-2026-10-08.md`](../../auditoria-ui-6-x-global-2026-10-08.md).
**Cita POST-TAG:** pendiente (tag anotado `v2.88.93-beta` y `Release tag CI` se citan en el commit post-tag).

## 1. Huecos cerrados (fuera del censo de `v2.88.92`)

| # | Hueco | Regla | Cierre | Implementación |
| --- | --- | --- | --- | --- |
| 1 | `Gate` crudo en primer nivel | `R-G1` (H-03) | Nuevo detector `findFirstLevelGateLiterals` (`Gate` + valor crudo, `Gate ${…}`/`Gate PASS`) fuera de `TechnicalDetail`, sin marcar identificadores TS (`gateStatus`/`DecisionGate`/`AuthGate`). El drawer pasa a `gateHumanLabel`; «Gate preset» → «Condición de entrada». | [`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts); [`opportunity-drawer.tsx`](../../../../apps/web/src/features/mesa/opportunity-drawer.tsx), [`saved-strategies-panel.tsx`](../../../../apps/web/src/features/screeners/saved-strategies-panel.tsx) |
| 2 | Jerga de `Paper D` en primer nivel | `R-G1` | `PAPER_D_EXECUTE=1`/`paper_auto`/`entry_long`/«Gate cognitivo» plegados tras el disclosure único `Detalle técnico`; copy de primer nivel en lenguaje de resultado. | [`paper-d-propose-panel.tsx`](../../../../apps/web/src/features/screeners/paper-d-propose-panel.tsx) |
| 3 | Comodín `—` fuera del censo | `UI5-14` | `absentDataLabel()` en las superficies hermanas; huecos **estructurales** («no proyectado en scenario», sector dominante «Después») con `absentDataLabel("not_applicable")` → «No aplica». | [`mesa-operational-bar.tsx`](../../../../apps/web/src/features/operations/mesa-operational-bar.tsx), [`opportunity-drawer.tsx`](../../../../apps/web/src/features/mesa/opportunity-drawer.tsx), [`mesa-daily-header.tsx`](../../../../apps/web/src/features/mesa/mesa-daily-header.tsx), [`mesa-what-if-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-what-if-panel.tsx), [`operational-plan-view.tsx`](../../../../apps/web/src/features/mesa/operational-plan-view.tsx), [`f3-confirm-what-if-block.tsx`](../../../../apps/web/src/features/trading/f3-confirm-what-if-block.tsx), [`f3-trade-plan-risk-first-block.tsx`](../../../../apps/web/src/features/trading/f3-trade-plan-risk-first-block.tsx) |

## 2. Gate falsable ampliado

[`barrido-global-first-level.test.tsx`](../../../../apps/web/src/features/barrido-global-first-level.test.tsx): `opportunity-drawer`, `mesa-operational-bar`, `saved-strategies-panel` y `paper-d-propose-panel` entran en `TOKEN_SURFACES`; las superficies del barrido `—` (`mesa-operational-bar`, `mesa-daily-header`, `mesa-what-if-panel`, `operational-plan-view`, `f3-confirm-what-if-block`, `f3-trade-plan-risk-first-block`) entran en `DASH_SURFACES`; y un bloque nuevo assertea `findFirstLevelGateLiterals(...) === []` sobre todo el censo, con control de falsabilidad (`Gate ${…}` / `Gate PASS` fallan; `gateStatus`/`DecisionGate` y nivel 3 no).

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **277 ficheros / 1727 tests verdes** (+40 tests respecto a `2.11.92-beta`).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.93-beta`).
- **`Δ motor = 0`**: `git diff --name-only v2.88.92-beta -- packages/py` → **vacío**.

## 4. Qué no cambia / deuda declarada

- **Motor AUTO** de decisión/ejecución, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema. Live/XTB real sigue fuera: el canal se declara `SIMULADO`.
- **`playwright` integrado** sigue `opt-in`/`skipped`; la certificación `axe` de la serie es **con mocks**.
- **Cobertura del gate sigue siendo un censo acotado:** no sustituye una revisión humana del resto de la app. **Remediación:** ampliar el censo por oleadas con el mismo gate.
- **`Gate N` conservado** como dato de decisión (no es término prohibido): solo se humaniza su etiqueta.
- **Deuda durable backend:** `PortfolioDecision`, materialización SIM, PIT histórico, Execution Analysis.
