# Entrega a auditoría externa (MIA) — `v2.88.93-beta` · `UI`: **UI 6.x — cierre de huecos del barrido global (Gate N · comodín `—`)**

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.93-beta` · **Package:** `2.11.93-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.92-beta` (tag anotado objeto `6bde9337` → commit `88416aff`; `Release tag CI` [`37802710522`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37802710522) **VERDE**).
> **Unidad de esta auditoría:** cerrar los **huecos del censo** que la revisión posterior a `v2.88.92-beta` detectó **fuera del gate** —`Gate` crudo en el drawer de Oportunidades (H-03) y en Estrategias guardadas, la jerga de `Paper D` y el comodín `—` en superficies hermanas— y **ampliar el censo** del gate falsable para que no reaparezcan. Evidencia de origen: [`evidence/v2.88.92/README.md`](./evidence/v2.88.92/README.md) §4.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. Los tres rótulos de ausencia (`Sin dato todavía` / `No aplica` / `No disponible`) **no son intercambiables**; el guion `—` queda **prohibido** en el primer nivel de las superficies **cubiertas por el gate**.
> **`Δ AUTO decision/execution motor = 0`.** Todo el sello es UI/copy y tests en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.93/README.md`](./evidence/v2.88.93/README.md).
> **Cita POST-TAG:** pendiente (tag anotado `v2.88.93-beta` y `Release tag CI` se citan en el commit post-tag).

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo en el primer nivel, sin residuos**. No se añaden funciones ni se toca el motor: se cierra el censo del gate y se hace **falsable** cada afirmación con el gate (`first-level-gate.ts`, ahora con `findFirstLevelGateLiterals`) que falla si la jerga o el comodín reaparecen fuera del nivel 3.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre de los huecos del censo de `v2.88.92`:

1. **`Gate` crudo.** Nuevo detector `findFirstLevelGateLiterals` ([`first-level-gate.ts`](../../apps/web/src/components/first-level-gate.ts)): `Gate` + valor crudo (`Gate ${…}`/`Gate PASS`) fuera de `TechnicalDetail`, sin marcar identificadores TS. [`opportunity-drawer.tsx`](../../apps/web/src/features/mesa/opportunity-drawer.tsx) pasa a `gateHumanLabel(row.gate)`; [`saved-strategies-panel.tsx`](../../apps/web/src/features/screeners/saved-strategies-panel.tsx) relabela «Gate preset» → «Condición de entrada».
2. **`Paper D` a nivel 3.** La jerga técnica (`PAPER_D_EXECUTE=1`, `paper_auto`, `entry_long`, «Gate cognitivo») de [`paper-d-propose-panel.tsx`](../../apps/web/src/features/screeners/paper-d-propose-panel.tsx) se pliega tras el disclosure único `Detalle técnico`.
3. **Comodín `—`.** `absentDataLabel()` en `mesa-operational-bar`, `opportunity-drawer`, `mesa-daily-header`, `mesa-what-if-panel`, `operational-plan-view` y los bloques `f3-confirm-what-if`/`f3-trade-plan-risk-first`; los huecos **estructurales** usan `absentDataLabel("not_applicable")` → «No aplica».
4. **Censo del gate.** [`barrido-global-first-level.test.tsx`](../../apps/web/src/features/barrido-global-first-level.test.tsx) amplía `TOKEN_SURFACES`/`DASH_SURFACES` y añade el bloque del rótulo `Gate`.
5. **Honestidad.** Se acota la afirmación sobreabarcante de `v2.88.92` («el guion `—` queda prohibido en nivel 1») a «en las superficies **cubiertas por el gate**».

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y `skipped`. La certificación `axe` de la serie es **con mocks**.
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, traza de materialización SIM, PIT histórico institucional y Execution Analysis.

---

## 2. Cambios verificables (todo con gate)

| # | Hueco de origen | Regla | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| 1 | `Gate` crudo | `R-G1` (H-03) | `first-level-gate.ts`, `opportunity-drawer.tsx`, `saved-strategies-panel.tsx` | Nuevo detector + etiqueta humanizada. |
| 2 | Jerga `Paper D` | `R-G1` | `paper-d-propose-panel.tsx` | Copy técnico tras `Detalle técnico`. |
| 3 | Comodín `—` | `UI5-14`, `R-G1` | 7 superficies (mesa/operaciones/trading) | `absentDataLabel()`; «No aplica» en huecos estructurales. |
| 4 | Censo del gate | `R-G1`, `R-G2` | `barrido-global-first-level.test.tsx` | Falsabilidad ampliada + bloque del rótulo `Gate`. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.93-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en el commit post-tag).
- **Frontend local:** `typecheck` **OK** (exit 0); `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); **277 ficheros / 1727 tests verdes** (+40 tests respecto a `2.11.92-beta`).
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.93-beta`).
- **`Δ motor = 0` local:** `git diff --name-only v2.88.92-beta -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **Cobertura del gate sigue siendo un censo acotado.** `barrido-global-first-level.test.tsx` cubre las superficies declaradas; **no** sustituye una revisión humana del resto de la app. **Remediación:** ampliar el censo de superficies por oleadas con el mismo gate.
- **`Gate N` conservado** como dato de decisión (no es término prohibido): solo se humaniza su etiqueta.
- **`F-A2` — barrido `axe` en vivo.** Este sello certifica **con mocks**; la variante en vivo (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **`UI52-02` — `PortfolioDecision` durable**; **traza de materialización SIM**; **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **277 ficheros / 1727 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.93-beta`) |
| `replay-repro` — CI | pendiente (**esperado `REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`**) |

---

## 6. Sello

- **Producto:** `V2.88.93-beta`. **Package:** `2.11.93-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.93/README.md`, este documento.
- **Modificados:** `apps/web/src/**` (components, mesa, operations, screeners, trading), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/evidence/v2.88.92/README.md` y `docs/engineering/entrega-auditoria-externa-mia-v2.88.92-2026-10-08.md` (acotado de la afirmación de alcance).
- **Tag anotado `v2.88.93-beta`** — mensaje `UI 6.x close of global sweep gaps (Gate literal, paper-d jerga, dash wildcard) - Delta motor = 0`. **`Release tag CI` pendiente** de cita.

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.93/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` (Bloque E + §5) y el `§9` de `docs/engineering/auditoria-ui-6-x-global-2026-10-08.md`.
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.92-beta v2.88.93-beta -- packages/py   # vacío
   git rev-parse v2.88.92-beta:packages v2.88.93-beta:packages      # iguales
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad del primer nivel (`R-G1`).** Comprobar que fuera de `[data-technical-detail="true"]` **no** aparece `Recommendation`, `DecisionSession`, `Policy Gate`, `runId`, `cycleId`, `ledger`, `fills`, `DÍA-D`, `WFE`, `PBO`, `DSR`, el alias `Libro`, el guion `—` ni `Gate` + valor crudo. El gate `first-level-gate.ts` + `barrido-global-first-level.test.tsx` falla si reaparecen.
7. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que el primer nivel reintroduzca jerga interna, `—`, el alias `Libro` o `Gate` crudo · que un hueco estructural se rote como «Sin dato todavía» en vez de «No aplica» · que el diff toque `packages/py/**`/motor/contrato/migraciones · que `replay-repro` no reproduzca `1E3ADAC2…`.
