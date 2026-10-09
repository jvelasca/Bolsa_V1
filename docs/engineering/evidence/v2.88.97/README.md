# Evidencia `v2.88.97-beta` — `UI 8.x`: **barrido `UI5-14` (primer nivel sin comodín `—`) + `S4-agregador-evidencia` (`P4`) (UI-only · Δ motor = 0)**

**Producto:** `V2.88.97-beta` · **Package:** `2.11.97-beta` · **AsOf:** 2026-10-09. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.97-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI + tests más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Origen.** Es el sello de un doble trabajo: (a) el **barrido `UI5-14`** que retira el comodín de dato ausente `—` del primer nivel; (b) **`S4-agregador-evidencia`**, que **pasa a LANZADO** como agregador read-only de las cuatro capas de §5.2 y que **nunca emite `CONFIRMED`**. Proviene del estado de `v2.88.96-beta`, donde `S4` seguía «NO LANZADO».

**Base:** [`evidence/v2.88.96/README.md`](../v2.88.96/README.md).
**Cita POST-TAG:** tag anotado `v2.88.97-beta` (objeto `30bdd642` → commit `d9df6de4`); `Release tag CI` [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `286` ficheros / `1982` passed; `python` `4596 passed / 45 skipped`; `playwright (mock E2E)` `109 passed / 21 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

## 1. Cambios (por trabajo)

| # | Trabajo | Qué hace | Implementación |
| --- | --- | --- | --- |
| 1 | **Barrido `UI5-14`** | Retira el comodín `—` de dato ausente del primer nivel en **108 ficheros** de `apps/web/src/**` y lo sustituye por el vocabulario Opción B («Sin dato todavía» / «No aplica» / «No disponible»). El guion queda reservado al nivel 3. | `apps/web/src/**` (superficies de trading/mesa/auto-monitor/charts/instruments/research/journal/screeners/settings/config/alerts/accounts/backtests) |
| 2 | **Gate `UI5-14` endurecido** | `findFirstLevelDashes` caza además el guion **embebido** junto a comilla/backtick (`"Velas · —"`) y el **nodo JSX desnudo** (`<span>—</span>`, multilínea); el guion de prosa no se marca y cada guion cuenta ≤1 coincidencia. Censo ampliado. | [`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts), [`barrido-global-first-level.test.tsx`](../../../../apps/web/src/features/barrido-global-first-level.test.tsx) |
| 3 | **Vocabulario `P4` («Por qué AUTO no operó»)** | Read-model puro de dos capas rotuladas (descubrimiento 1–3 · motor 4–6), con `UNKNOWN ≠ 0` y enlace de cada causa a su registro; primer nivel sin enums crudos. | [`auto-no-trade-labels.ts`](../../../../apps/web/src/features/auto/auto-no-trade-labels.ts), [`auto-no-trade-explanation.ts`](../../../../apps/web/src/features/auto/auto-no-trade-explanation.ts) |
| 4 | **Vocabulario `P3` (embudo)** | Separa SELECCIÓN / VALIDACIÓN / EVIDENCIA, sin devolver nunca el enum crudo (`active`, `in_sample_only`, `lab_validated`). | [`strategy-concept-labels.ts`](../../../../apps/web/src/features/backtests/strategy-concept-labels.ts) |
| 5 | **`S4-agregador-evidencia` (LANZADO)** | Read-model puro de las 4 capas de `PROJECT_PREMISES` §5.2 —**ventana · reconciliación · evidencia OOS · evidencia PAPER**— que compone y devuelve SIEMPRE `NO_CONFIRMED`. | [`dia-d-evidence-aggregate.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.ts), [`dia-d-evidence-aggregate-labels.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-labels.ts) |
| 6 | **Superficie + wiring `S4`** | Una sola superficie (`DiaDEvidenceAggregatePanel`) montada una sola vez sobre el toolbar de sub-vistas; reuso pasivo de caché vía override `{ enabled }` en los 2 hooks. | [`dia-d-evidence-aggregate-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-panel.tsx), [`dia-d-auto-panel.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx), [`use-auto-dia-d-feedback.ts`](../../../../apps/web/src/features/auto-monitor/use-auto-dia-d-feedback.ts), [`use-auto-dia-d-replay.ts`](../../../../apps/web/src/features/auto-monitor/use-auto-dia-d-replay.ts) |
| 7 | **Regresión `S4`** | Powerset completo → `NO_CONFIRMED`; word-boundary `/\bCONFIRMED\b/`; rollup OOS por contradicción; `UNKNOWN ≠ 0`; exclusión del lens `SAME_CONFIRMED`. | [`dia-d-evidence-aggregate.test.ts`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate.test.ts), [`dia-d-evidence-aggregate-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-panel.test.tsx) |
| 8 | **Compat contractual + `a11y` `T1`/`T2`** | Restaura en `sr-only` los `data-testid` contractuales `position-decision-t1`/`position-decision-t2` (cuando la escalera visible no monta el peldaño, legado `absent`) **sin `<dl>`/`<dd>`** — un `<dl>` sin `<dt>` viola la regla `axe` `definition-list` — preservando el `getByTestId` de `assertOperationalTruth` y sin romper el barrido `axe` de CI. | [`decision-surface-compact.tsx`](../../../../apps/web/src/features/trading/decision-surface-compact.tsx) |
| Bump | — | `package.json` (`2.11.97-beta`) + `meta.bump` de `v2_89`…`v2_97`. | [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) |

## 2. Reglas que NO cambian

- **No promoción.** `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`. Ninguna capa confirma la siguiente.
- **Confirmación reservada.** La capa PAPER (ejecución real) es un hueco por contrato: el agregado **nunca** emite `CONFIRMED` (el `verdict` es un tipo literal `"NO_CONFIRMED"`; rótulo «NO CONFIRMADO»).
- **Rollup OOS con contradicción.** `soportados + refutados` a la vez ⇒ `MIXED`; solo `refutados` ⇒ `REFUTED`; solo `mixtos` ⇒ `MIXED`; si no ⇒ `OOS_SUPPORTED`.
- **`UNKNOWN ≠ 0`.** Un dato no medido se declara hueco («Sin dato todavía»); jamás se colapsa a `0` ni a un veredicto afirmado.
- **Trading fuera del agregado.** El lens `SAME_CONFIRMED` de `dia-d-reconciliation.ts` **no** entra en el agregado (test que lee el fuente y comprueba que no lo conoce).
- **Motor intacto.** `Δ motor = 0`: sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **286 ficheros / 1982 tests verdes**.
- `pnpm --filter @bolsa/web run contract:check` → **OK** (`openapi.json` y `schema.d.ts` coinciden).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.97-beta`).
- **`Δ motor = 0`**: `git diff --name-only -- packages/py` → **vacío** (sin contrato HTTP, sin Alembic).

## 4. Qué no cambia / deuda declarada

- **Motor de decisión/ejecución**, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema.
- **`S4` no confirma:** queda **lanzado como agregador**, pero **no** promociona a `CONFIRMED` mientras la capa PAPER no se emita.
- **`P4-3`** (medición por artefacto CLI, no en vivo) y **`P2-4`** (T1/T2 en `sr-only` con Journey) siguen **abiertos**.
- **Deuda PARKED (`F2-1`…`F2-4`)**: `PortfolioDecision` durable, posición por operación, P&L agregado, motivo de ranking por ciclo.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.
