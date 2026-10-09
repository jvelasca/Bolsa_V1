# Entrega a auditoría externa (MIA) — `v2.88.98-beta` · `UI 8.x`: **respuesta a la auditoría externa de `v2.88.97` (`P1` rollup OOS · `P2-4` `T1`/`T2` visibles · `P4` validación E2E · contrato durable PAPER) (UI/producto · Δ motor = 0)**

> **Fecha:** 2026-10-09 · **Producto:** `V2.88.98-beta` · **Package:** `2.11.98-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.97-beta` (tag anotado objeto `30bdd642` → commit `d9df6de4`; `Release tag CI` [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE**).
> **Unidad de esta auditoría:** responder, en orden, a los hallazgos del auditor externo sobre el sello `v2.88.97`: **`P1`** (el rollup OOS colapsaba `null` a `0`), **`P2-4`** (`T1`/`T2` en `sr-only`, no visibles), **`P4`** (validación E2E de «Por qué AUTO no operó») y el **contrato durable de evidencia PAPER**.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** El diff vive en `apps/web/**`, `packages/shared/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.98/README.md`](./evidence/v2.88.98/README.md).
> **Re-sello.** El primer `Release tag CI` ([`37922388038`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37922388038)) salió **ROJO** en `playwright (mock E2E)`; se corrige el anidado de `T1`/`T2` haciendo **incondicional** el peldaño-objetivo en el plan de la posición (ver §1 #2). El resto del run (frontend, python, shared, lifecycle-pg, decision-spine, a7-gate, dr-verify, `replay-repro` `REPRODUCIDO` `1E3ADAC2…`) fue **VERDE**.
> **Cita POST-TAG:** **PENDIENTE** (se añade en el commit siguiente al push del tag `v2.88.98-beta` con CI VERDE).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la respuesta verificable a la revisión externa de `v2.88.97`, en un único commit:

1. **`P1` — rollup OOS sin colapso de `null` a `0`.** [`buildOosLayer`](../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.ts) exige los tres contadores (`oosSupported`, `mixed`, `refuted`) estrictamente no nulos **y** `notMeasured === 0` **antes** de afirmar `OOS_SUPPORTED` / `MIXED` / `REFUTED`; en cualquier otro caso devuelve la capa `gap` («Sin dato todavía») conservando la línea de medición parcial. Razones de hueco tipadas en `dia-d-evidence-aggregate-labels.ts`.
2. **`P2-4` — `T1`/`T2` visibles en la escalera.** El peldaño-objetivo `T1`/`T2` del plan de la posición se monta **siempre** (no solo si el legado ya se ha disparado): `buildOperatorPositionPlan` deja de filtrar por `status !== "absent"` y el detalle lleva el precio objetivo (`trigger`) o «Sin dato todavía». Se retira el bloque `sr-only` duplicado; los `data-testid` contractuales `position-decision-t1`/`position-decision-t2` se anidan en esos **peldaños visibles** vía `LevelTestIds` (alias `journey-t1`/`journey-t2`).
3. **`P4` — validación E2E.** Nuevo `auto-no-trade-panel.integration.test.tsx` (10 tests) sobre el contenedor real `AutoNoTradePanel`.
4. **Contrato durable PAPER.** Doc `docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md` + read-model puro `paper-confirmation-contract.ts` (7 criterios falsables) con `verdict` literal `"NO_CONFIRMED"`.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se emite la confirmación reservada: `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`.
- **NO** se cierra `P4-3` ni la deuda PARKED (`F2-1`…`F2-4`).

---

## 2. Cambios verificables (todo con gate)

| # | Trabajo | Fichero(s) | Qué hace |
| --- | --- | --- | --- |
| 1 | `P1` rollup OOS | `dia-d-evidence-aggregate.ts`, `dia-d-evidence-aggregate-labels.ts` | `null ≠ 0`: exige 3 contadores no nulos + `notMeasured === 0`; si no ⇒ `gap`. |
| 2 | Regresión `P1` | `dia-d-evidence-aggregate.test.ts`, `dia-d-evidence-aggregate-panel.test.tsx` | Ausente / uno ausente / `notMeasured > 0` ⇒ hueco; `UNKNOWN ≠ 0`; UI sin veredicto afirmado. |
| 3 | `P2-4` `T1`/`T2` visibles | `operator-cabin-view.ts`, `decision-surface-compact.tsx`, `decision-surface-journey.test.tsx` | Peldaño-objetivo siempre visible; retira `sr-only`; `testid` en peldaños visibles vía `LevelTestIds`; `assertOperationalTruth` + `axe` intactos. |
| 4 | `P4` validación E2E | `auto-no-trade-panel.integration.test.tsx` | 10 tests: causa↔registro, filtro por día, `absent` vs `unknown`, error de lectura, `unavailable` vs `empty`. |
| 5 | Contrato PAPER | `contrato-evidencia-paper-confirmacion-2026-10-09.md`, `paper-confirmation-contract.ts`, `paper-confirmation-contract-labels.ts`, `paper-confirmation-contract.test.ts` | 7 criterios falsables; `verdict` literal `"NO_CONFIRMED"`; `UNKNOWN ≠ 0`. |
| Bump | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.98-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio. `replay-repro` **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (ya confirmado en el run [`37922388038`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37922388038), donde ese job fue **VERDE**; se re-confirma al re-sellar el tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); **288 ficheros / 2007 tests verdes** (+2 ficheros / +25 sobre `v2.88.97`); `contract:check` **OK**.
- **Read-model UI local:** `pnpm --filter @bolsa/shared build` **OK**; `pnpm --filter @bolsa/shared test` **817 passed** (+1 todo).
- **E2E local (specs que fallaron en CI):** `gp-v177|gp-v178|gp-v179|gp-v181|gp-v183` → **18 passed** (fix confirmado; `GP-V178-03` pasó en aislamiento — flake de servidor local).
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.98-beta`).
- **`Δ motor = 0` local:** `git diff --name-only -- packages/py` → **vacío**.

---

## 4. Hallazgos y estado tras esta entrega

- **`P1` — cerrado.** El rollup OOS ya no convierte `null` en `0`; con dato incompleto se declara hueco.
- **`P2-4` — cerrado.** `T1`/`T2` viven en nodos visibles de la escalera; test que verifica «visible y fuera de `.sr-only`».
- **`P4` — cerrado.** «Por qué AUTO no operó» queda blindado por 10 tests de integración sobre el contenedor real.
- **Contrato PAPER — entregado como contrato.** Especifica la evidencia durable exigible sin afirmar `CONFIRMED`; `S4` permanece `NO_CONFIRMED` mientras no exista esa ejecución.
- **`P4-3` — medición por artefacto CLI, no en vivo.** **ABIERTO** (fuera del alcance de `S4`).
- **Deuda PARKED FASE 2 (`F2-1`…`F2-4`)**.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **288 ficheros / 2007 passed** |
| `pnpm --filter @bolsa/web run contract:check` | **OK** |
| `pnpm --filter @bolsa/shared build` + `test` | **OK** / **817 passed** |
| E2E local `gp-v177|gp-v178|gp-v179|gp-v181|gp-v183` | **18 passed** (fix del `Release tag CI` ROJO) |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.98-beta`) |
| `git diff --name-only -- packages/py` | **vacío** ⇒ **`Δ motor = 0`** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` en el run [`37922388038`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37922388038) ⇒ **`Δ motor = 0`** |

---

## 6. Sello

- **Producto:** `V2.88.98-beta`. **Package:** `2.11.98-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.98/README.md`, este documento, `docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md`; `apps/web/src/features/auto/auto-no-trade-panel.integration.test.tsx`; `apps/web/src/features/auto-monitor/paper-confirmation-contract{,-labels}.ts` y `paper-confirmation-contract.test.ts`.
- **Modificados:** `packages/shared/src/cognitive/operator-cabin-view.ts`, `dia-d-evidence-aggregate.ts`, `dia-d-evidence-aggregate-labels.ts`, `dia-d-evidence-aggregate.test.ts`, `dia-d-evidence-aggregate-panel.test.tsx`, `decision-surface-compact.tsx`, `decision-surface-journey.test.tsx`, `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **Tag anotado `v2.88.98-beta`:** creado y empujado sobre `d18e0e30`; su primer `Release tag CI` ([`37922388038`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37922388038)) salió **ROJO** en `playwright (mock E2E)`. Se **re-ancla** al commit del fix (`P2-4` incondicional) y se re-lanza; la cita POST-TAG se añade al quedar CI VERDE.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.98/README.md`.
2. **Entrega MIA.** Leer este documento.
3. **Origen.** Leer la [entrega de `v2.88.97`](./entrega-auditoria-externa-mia-v2.88.97-2026-10-09.md) (donde el auditor abrió `P1`, `P2-4`, `P4` y el contrato PAPER).
4. **`Δ motor = 0`.**
   ```bash
   git diff --name-only v2.88.97-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pnpm --filter @bolsa/web run contract:check
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad `P1`.** `dia-d-evidence-aggregate.test.ts` falla si un contador `null` se colapsa a `0`, si `notMeasured > 0` aún produce `OOS_SUPPORTED`, o si el rollup por contradicción deja de ser `MIXED`.
7. **Falsabilidad `P2-4`.** `decision-surface-journey.test.tsx` falla si `position-decision-t1`/`t2` no están visibles o quedan dentro de `.sr-only`.
8. **Falsabilidad PAPER.** `paper-confirmation-contract.test.ts` falla si el JSON contiene `/\bCONFIRMED\b/` o si el `verdict` deja de ser `"NO_CONFIRMED"`.
9. **Qué falsaría el sello:** que el diff toque `packages/py/**`/motor/contrato/migraciones · que `S4` emita `CONFIRMED` o promocione una capa · que un contador ausente vuelva a colapsarse a `0` · que `replay-repro` no reproduzca `1E3ADAC2…`.
