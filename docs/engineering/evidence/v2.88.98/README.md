# Evidencia `v2.88.98-beta` — `UI 8.x`: **respuesta a la auditoría externa de `v2.88.97` (`P1` rollup OOS · `P2-4` `T1`/`T2` visibles · `P4` validación E2E · contrato durable PAPER) (UI/producto · Δ motor = 0)**

**Producto:** `V2.88.98-beta` · **Package:** `2.11.98-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `packages/shared/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.98-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI + read-model de UI (`packages/shared/src/cognitive`) + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Re-sello.** El primer `Release tag CI` de este sello ([`37922388038`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37922388038)) salió **ROJO** en `playwright (mock E2E)`: el anidado inicial de `position-decision-t1/t2` en peldaños **solo visibles si el legado ya se ha disparado** dejaba `position-decision-t2` ausente en `T1_READY` (6 specs `mock E2E`). Corregido haciendo **incondicional** el peldaño-objetivo `T1`/`T2` en el plan de la posición (ver §1 #3).
> **Origen.** Responde, en orden, a la auditoría externa sobre el sello [`v2.88.97-beta`](../v2.88.97/README.md): (a) **`P1`** — el rollup OOS del agregador `S4` colapsaba contadores `null` a `0`; (b) **`P2-4`** — los `testid` contractuales `T1`/`T2` vivían en un bloque `sr-only`; (c) **`P4`** — «Por qué AUTO no operó» no tenía validación E2E; (d) **contrato PAPER** — faltaba especificar la evidencia durable de confirmación.

**Base:** [`evidence/v2.88.97/README.md`](../v2.88.97/README.md).
**Cita POST-TAG:** **PENDIENTE** (se añade en el commit siguiente al push del tag `v2.88.98-beta` tras CI VERDE).

## 1. Cambios (por hallazgo)

| # | Hallazgo | Qué hace | Implementación |
| --- | --- | --- | --- |
| 1 | **`P1` — rollup OOS (`null ≠ 0`)** | `buildOosLayer` exige que `oosSupported`, `mixed`, `refuted` sean estrictamente no nulos **y** `notMeasured === 0` antes de afirmar `OOS_SUPPORTED` / `MIXED` / `REFUTED`. Si el dato es parcial o ausente ⇒ capa `gap` («Sin dato todavía») conservando la línea de medición parcial. | [`dia-d-evidence-aggregate.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.ts), [`dia-d-evidence-aggregate-labels.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-labels.ts) |
| 2 | **Regresión `P1`** | Contadores ausentes ⇒ hueco; un contador ausente ⇒ hueco; `notMeasured > 0` ⇒ hueco; `UNKNOWN ≠ 0`; la UI renderiza el hueco sin afirmar veredicto. | [`dia-d-evidence-aggregate.test.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.test.ts), [`dia-d-evidence-aggregate-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-panel.test.tsx) |
| 3 | **`P2-4` — `T1`/`T2` visibles** | El peldaño-objetivo `T1`/`T2` del plan se monta **siempre** (no solo si el legado ya se disparó): `buildOperatorPositionPlan` deja de filtrar por `status !== "absent"`; el detalle lleva el precio objetivo (`trigger`) o «Sin dato todavía». Se retira el bloque `sr-only` duplicado y los `data-testid` contractuales `position-decision-t1`/`position-decision-t2` se anidan en los **peldaños visibles** vía `LevelTestIds` (alias `journey-t1`/`journey-t2`), preservando `assertOperationalTruth` y `axe`. | [`operator-cabin-view.ts`](../../../../packages/shared/src/cognitive/operator-cabin-view.ts), [`decision-surface-compact.tsx`](../../../../apps/web/src/features/trading/decision-surface-compact.tsx), [`decision-surface-journey.test.tsx`](../../../../apps/web/src/features/trading/decision-surface-journey.test.tsx) |
| 4 | **`P4` — validación E2E** | 10 tests sobre el contenedor real `AutoNoTradePanel`: causa↔registro (`/auto/operar/operacion/{cycleId}`), filtro por día, `absent` vs `unknown`, fallback ante error de lectura, `estudioStatus: unavailable` vs `empty`. | [`auto-no-trade-panel.integration.test.tsx`](../../../../apps/web/src/features/auto/auto-no-trade-panel.integration.test.tsx) |
| 5 | **Contrato durable PAPER** | Doc + read-model puro de 7 criterios falsables; `verdict` literal `"NO_CONFIRMED"`; `UNKNOWN ≠ 0`. | [`contrato-evidencia-paper-confirmacion-2026-10-09.md`](../../contrato-evidencia-paper-confirmacion-2026-10-09.md), [`paper-confirmation-contract.ts`](../../../../apps/web/src/features/auto-monitor/paper-confirmation-contract.ts), [`paper-confirmation-contract-labels.ts`](../../../../apps/web/src/features/auto-monitor/paper-confirmation-contract-labels.ts), [`paper-confirmation-contract.test.ts`](../../../../apps/web/src/features/auto-monitor/paper-confirmation-contract.test.ts) |
| Bump | — | `package.json` (`2.11.98-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **No promoción.** `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`. Ninguna capa confirma la siguiente.
- **Confirmación reservada.** La capa PAPER (ejecución real) sigue siendo un hueco por contrato: el agregado **nunca** emite `CONFIRMED` (el `verdict` es un tipo literal `"NO_CONFIRMED"`; rótulo «NO CONFIRMADO»).
- **Rollup OOS con contradicción (y con dato completo).** `soportados + refutados` a la vez ⇒ `MIXED`; solo `refutados` ⇒ `REFUTED`; solo `mixtos` ⇒ `MIXED`; si no ⇒ `OOS_SUPPORTED`. **Pero** estas ramas solo se alcanzan con los tres contadores completos y `notMeasured === 0`; en cualquier otro caso ⇒ `gap`.
- **`UNKNOWN ≠ 0`.** Un dato no medido se declara hueco («Sin dato todavía»); jamás se colapsa a `0` ni a un veredicto afirmado.
- **Trading fuera del agregado.** El lens `SAME_CONFIRMED` de `dia-d-reconciliation.ts` **no** entra en el agregado.
- **Motor intacto.** `Δ motor = 0`: sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **288 ficheros / 2007 tests verdes** (+2 ficheros / +25 tests sobre `v2.88.97`).
- `pnpm --filter @bolsa/shared build` + `pnpm --filter @bolsa/shared test` → **OK** / **817 passed** (+1 todo).
- E2E local de los specs que fallaron en CI (`gp-v177|gp-v178|gp-v179|gp-v181|gp-v183`) → **18 passed** (el `GP-V178-03` intermitente pasó en aislamiento; flake de servidor local, no reproduce en CI).
- `pnpm --filter @bolsa/web run contract:check` → **OK** (`openapi.json` y `schema.d.ts` coinciden).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.98-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py` → **vacío** (sin contrato HTTP, sin Alembic).

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema.
- **`S4` no confirma:** el rollup OOS queda blindado, pero el veredicto global sigue `NO_CONFIRMED` mientras la capa PAPER no se emita. El nuevo [contrato PAPER](../../contrato-evidencia-paper-confirmacion-2026-10-09.md) especifica **qué** evidencia durable haría falta, sin afirmarla.
- **`P4-3`** (medición por artefacto CLI, no en vivo) sigue **abierto**.
- **Deuda PARKED (`F2-1`…`F2-4`)**: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
