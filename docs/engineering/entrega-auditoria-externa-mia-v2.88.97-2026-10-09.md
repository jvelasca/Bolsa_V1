# Entrega a auditoría externa (MIA) — `v2.88.97-beta` · `UI 8.x`: **barrido `UI5-14` (primer nivel sin comodín `—`) + `S4-agregador-evidencia` (`P4`) (UI/producto · Δ motor = 0)**

> **Fecha:** 2026-10-09 · **Producto:** `V2.88.97-beta` · **Package:** `2.11.97-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.96-beta` (tag anotado objeto `74e3fcf4` → commit `de3e5222`; `Release tag CI` [`37894478961`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37894478961) **VERDE**).
> **Unidad de esta auditoría:** (a) que el **barrido `UI5-14`** deje el **primer nivel sin comodín `—`** en las superficies de `apps/web/src/**`, con un gate falsable que lo impida; y (b) que **`S4-agregador-evidencia`** quede **LANZADO** como agregador read-only de las cuatro capas de §5.2 **sin emitir nunca `CONFIRMED`**.
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. `ranking ≠ decisión` y `propuesta ≠ posición materializada` se conservan.
> **`Δ motor = 0`.** El diff vive en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.97/README.md`](./evidence/v2.88.97/README.md).
> **Cita POST-TAG:** tag anotado `v2.88.97-beta` (objeto `30bdd642` → commit `d9df6de4`); `Release tag CI` [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `frontend` `286` ficheros / `1982` passed; `python` `4596 passed / 45 skipped`; `playwright (mock E2E)` `109 passed / 21 skipped`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ `Δ motor = 0` confirmado por CI).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** un doble trabajo sellado en un único commit:

1. **Barrido `UI5-14`.** El comodín de dato ausente `—` se retira del primer nivel en **108 ficheros** de `apps/web/src/**` y se sustituye por el vocabulario Opción B de `absent-data.ts` («Sin dato todavía» / «No aplica» / «No disponible»). El detector falsable [`findFirstLevelDashes`](../src/components/first-level-gate.ts) se **endurece** (guion embebido junto a comilla/backtick y nodo JSX desnudo, además del literal) y el censo del gate se amplía. Nuevos vocabularios únicos: `auto-no-trade-labels.ts`/`auto-no-trade-explanation.ts` («Por qué AUTO no operó», `P4`) y `strategy-concept-labels.ts` (selección/validación/evidencia, `P3`).
2. **`S4-agregador-evidencia` (`P4-2`/`P4-4`) — LANZADO.** Read-model **puro** de las cuatro capas de `PROJECT_PREMISES` §5.2 —**ventana · reconciliación · evidencia OOS · evidencia PAPER**— en `dia-d-evidence-aggregate.ts`; vocabulario de primer nivel en `dia-d-evidence-aggregate-labels.ts`; superficie única `DiaDEvidenceAggregatePanel` montada una sola vez en `dia-d-auto-panel.tsx`; reuso pasivo de caché vía override `{ enabled }` en los 2 hooks. **Nunca emite `CONFIRMED`.**

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se emite la confirmación reservada: `READY ≠ CONFIRMED`, `MATCH ≠ CONFIRMED`, `OOS_SUPPORTED ≠ CONFIRMED`.
- **NO** se incluye el lens `SAME_CONFIRMED` de Trading en el agregado.
- **NO** se cierran `P4-3`, `P2-4` ni la deuda PARKED (`F2-1`…`F2-4`).

---

## 2. Cambios verificables (todo con gate)

| # | Trabajo | Fichero(s) | Qué hace |
| --- | --- | --- | --- |
| 1 | Barrido `UI5-14` | **108 ficheros** de `apps/web/src/**` | `—` de dato ausente → vocabulario Opción B en primer nivel. |
| 2 | Gate `UI5-14` | `first-level-gate.ts`, `barrido-global-first-level.test.tsx` | `findFirstLevelDashes` caza guion embebido + nodo JSX desnudo; censo ampliado. |
| 3 | Vocabulario `P4` | `auto-no-trade-labels.ts`, `auto-no-trade-explanation.ts` | Read-model puro «Por qué AUTO no operó» (6 causas, 2 capas), sin jerga. |
| 4 | Vocabulario `P3` | `strategy-concept-labels.ts` | Separa selección/validación/evidencia, sin enums crudos. |
| 5 | `S4` read-model | `dia-d-evidence-aggregate.ts`, `dia-d-evidence-aggregate-labels.ts` | Compone 4 capas y devuelve SIEMPRE `NO_CONFIRMED`. |
| 6 | `S4` superficie + wiring | `dia-d-evidence-aggregate-panel.tsx`, `dia-d-auto-panel.tsx`, `use-auto-dia-d-feedback.ts`, `use-auto-dia-d-replay.ts` | Superficie única + reuso pasivo de caché (`{ enabled }`). |
| 7 | `S4` regresión | `dia-d-evidence-aggregate.test.ts`, `dia-d-evidence-aggregate-panel.test.tsx` | Powerset → `NO_CONFIRMED`; rollup por contradicción; `UNKNOWN ≠ 0`; Trading excluido. |
| 8 | Compat contractual + `a11y` `T1`/`T2` | `decision-surface-compact.tsx` | Restaura en `sr-only` los `testid` contractuales `position-decision-t1`/`t2` (legado `absent`) **sin `<dl>`/`<dd>`** (un `<dl>` sin `<dt>` viola la regla `axe` `definition-list`), preservando `assertOperationalTruth` y el barrido `axe` de CI. |
| Bump | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.97-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio. `replay-repro` **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** confirmado por CI (`Release tag CI` [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE**).
- **Frontend local:** `typecheck` **OK** (exit 0); `eslint src` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes); **286 ficheros / 1982 tests verdes**; `contract:check` **OK**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.97-beta`).
- **`Δ motor = 0` local:** `git diff --name-only -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`P4-3` — medición por artefacto CLI, no en vivo.** **ABIERTO**: fuera del alcance de `S4` (agregador de evidencia ya medida).
- **`P2-4` — T1/T2 en `sr-only` con Journey activo.** **ABIERTO** (la duplicación de testids se conserva; el bloque `sr-only` ya no usa `<dl>`/`<dd>` — ver §2 #8).
- **`S4` no confirma.** El agregado queda **lanzado**, pero la capa PAPER (ejecución real) no se emite: el veredicto global permanece `NO_CONFIRMED` hasta que exista esa ejecución.
- **Deuda PARKED FASE 2 (`F2-1`…`F2-4`)**.
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **286 ficheros / 1982 passed** |
| `pnpm --filter @bolsa/web run contract:check` | **OK** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.97-beta`) |
| `git diff --name-only -- packages/py` | **vacío** ⇒ **`Δ motor = 0`** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** (`Release tag CI` [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE**; `frontend` `286` ficheros / `1982` passed; `python` `4596 passed / 45 skipped`) |

---

## 6. Sello

- **Producto:** `V2.88.97-beta`. **Package:** `2.11.97-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `docs/engineering/evidence/v2.88.97/README.md`, este documento; `apps/web/src/features/auto-monitor/dia-d-evidence-aggregate{,-labels,-panel,-panel.test,-test}.{ts,tsx}`; `apps/web/src/features/auto/auto-no-trade-{labels,explanation,panel}.{ts,tsx}(+test)`; `apps/web/src/features/backtests/strategy-concept-labels.{ts,test.ts}`.
- **Modificados:** `first-level-gate.ts`, `dia-d-auto-panel.tsx`, `use-auto-dia-d-feedback.ts`, `use-auto-dia-d-replay.ts`, `barrido-global-first-level.test.tsx`, `decision-surface-compact.tsx` (compat contractual + `a11y` `T1`/`T2`, ver §2 #8), ~100 superficies de `apps/web/src/**` (barrido `UI5-14`), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **Tag anotado `v2.88.97-beta`** — objeto `30bdd642` → commit `d9df6de4`. **`Release tag CI`** [`37912404394`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37912404394) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…`).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.97/README.md`.
2. **Entrega MIA.** Leer este documento.
3. **Origen.** Leer la [entrega de `v2.88.96`](./entrega-auditoria-externa-mia-v2.88.96-2026-10-09.md) (donde `S4` seguía «NO LANZADO»).
4. **`Δ motor = 0`.**
   ```bash
   git diff --name-only v2.88.96-beta -- packages/py   # vacío
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pnpm --filter @bolsa/web run contract:check
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   ```
6. **Falsabilidad barrido `UI5-14`.** `barrido-global-first-level.test.tsx` falla si reaparece un comodín literal `—` (o embebido / nodo JSX desnudo) fuera de `TechnicalDetail`; los huecos legítimos usan «Sin dato todavía» / «No aplica».
7. **Falsabilidad `S4`.** `dia-d-evidence-aggregate.test.ts` recorre el **powerset** de capas y exige `verdict === "NO_CONFIRMED"` y `/\bCONFIRMED\b/` **ausente** en el JSON; falla si el rollup OOS convierte `soportados + refutados` en `REFUTED` (debe ser `MIXED`), si un hueco se colapsa a `0`, o si el constructor conoce `SAME_CONFIRMED`. `dia-d-evidence-aggregate-panel.test.tsx` exige «NO CONFIRMADO» y la capa PAPER como hueco sin enums crudos.
8. **Qué falsaría el sello:** que el diff toque `packages/py/**`/motor/contrato/migraciones · que `S4` emita `CONFIRMED` o promocione una capa · que el barrido deje un `—` de primer nivel · que `replay-repro` no reproduzca `1E3ADAC2…`.
