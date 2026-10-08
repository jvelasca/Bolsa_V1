# Entrega a auditoría externa (MIA) — `v2.88.91-beta` · `UI`: **UI 6.x — lenguaje global (Confirmar · Hoy · resto de la app)**

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.91-beta` · **Package:** `2.11.91-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.90-beta` (tag anotado objeto `c220df76` → commit `c15873fd`; `Release tag CI` [`37774540104`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37774540104) **VERDE**).
> **Unidad de esta auditoría:** llevar a **toda la app** (no solo AUTO) las dos reglas de lenguaje que `v2.88.90` solo había cerrado en su backlog: `R-G1` (**el primer nivel se entiende sin el backend**) y `R-G2` (**una pantalla = una pregunta**). Se plegó la jerga interna tras un **único** mecanismo de profundidad, se purgó el alias deprecado `Libro` y se unificó el vocabulario de hueco. Auditoría de origen: [`auditoria-ui-6-x-global-2026-10-08.md`](./auditoria-ui-6-x-global-2026-10-08.md); contrato: [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md) (nuevo **Bloque E**; §5 ahora `R-G1`/`R-G2` a `DONE`).
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde. El guion `—` queda **prohibido** en nivel 1.
> **`Δ AUTO decision/execution motor = 0`.** Todo el sello es UI/read-model y tests en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.91/README.md`](./evidence/v2.88.91/README.md).
> **Cita POST-TAG:** _pendiente_ — se rellenará al confirmar el `Release tag CI` del tag anotado `v2.88.91-beta`.

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo en el primer nivel**. No se añaden funciones ni se toca el motor: se re-corta la superficie ya existente y se hace **falsable** cada afirmación con un gate (`first-level-gate.ts`) que falla si la jerga reaparece fuera del nivel 3.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el corte de lenguaje global en seis oleadas:

1. **Slice 0 · Base compartida (bloqueante).** Nuevo [`technical-detail.tsx`](../../apps/web/src/components/technical-detail.tsx) como **único** mecanismo de profundidad (`RT-04`: rótulo `Detalle técnico`, marca `data-technical-detail="true"`; `AutoTechnicalDetail` delega en él) + [`first-level-gate.ts`](../../apps/web/src/components/first-level-gate.ts) (gate **falsable**: `FORBIDDEN_FIRST_LEVEL_TOKENS`, `stripTechnicalDetailBlocks`, `findFirstLevelViolations`) + enmienda del contrato (`R-G1`/`R-G2`, reglas falsables 9–11) y del [ADR-045](../../adr/045-ui-contract-5-0.md).
2. **W1 · Confirmar (`P0`).** Bloque técnico (`Recommendation`/`DecisionSession`/`Policy Gate`/`Assessment(s)`/`Prediction`) plegado bajo el disclosure; escalera **codeada en español**; fuera tokens ingleses del DOM; `Libro` fuera; el primer bloque responde «¿Qué vas a autorizar?».
3. **W1 · Hoy (`P1`).** Pie sin arquitectura interna ni `Libro`; menú «Avanzado» en lenguaje humano; `Gate {n}` → `gateHumanLabel()`; `—` → vocabulario Opción B; pregunta declarada = «¿Qué requiere mi atención?».
4. **W2 · Cartera · Historial · Consola.** `h1` «Historial» (ya no «Libro · Historial»); «Movimientos contables» (ya no «Ledger contable»); fuera `Ledger`/`fills` de primer nivel; disclosure único en la Consola.
5. **W3 · Mercado + chrome.** Toolbar avanzada a un único menú `Ajustes de vista` (nivel 2); palette con grupos en español; tooltip de la barra de estado sin lenguaje de mecanismo; `AccountVenuePreference` a lenguaje de resultado.
6. **W4 · Asesor.** Jerga estadística (`Sharpe`, `campaignId`, `proposedBy`, `presetKey`, `K`, `WFE`/`PBO`/`DSR`) tras el `TechnicalDetail` único; `Sin datos.`/`—` → Opción B; payload defensivo.
7. **W5 · Accesibilidad.** Jerarquía `h1→h2→h3` sin saltos en rutas L1; barrido `axe` **extendido** con la regla `heading-order` y **dos rutas nuevas** (`/research`, `/history`).

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y `skipped`. La certificación `axe` de este sello es **con mocks**.
- **NO** se cierra el **barrido global** de `—` (dashboard, instruments, journal…) ni los residuos de `Libro`/`Ledger` en superficies fuera de alcance (§4).
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, traza de materialización SIM, PIT histórico institucional y Execution Analysis.

---

## 2. Cambios verificables (todo con gate)

| Oleada | Regla | Hallazgo de origen | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| Slice 0 | `RT-04`, `R-G1` | Auditoría UI 6.x §2 | `technical-detail.tsx`, `first-level-gate.ts`, `absent-data.ts` (+ `technical-detail.test.tsx`) | Un solo disclosure; gate falsable; helper de hueco único. |
| W1 Confirmar | `R-G1`, `R-G2`, `RT-02`, `RT-04`, `UI5-09`, `UI5-20` | Auditoría UI 6.x (Confirmar) | `supervised-f3-panel.tsx`, `live-virtual-order-gateway.tsx`, `live-virtual-ladder.ts`, `live-virtual-why.ts`, `confirm-content.tsx` (+ test) | Jerga de backend plegada; escalera en español; `Libro` fuera; primer bloque = «¿Qué vas a autorizar?». |
| W1 Hoy | `R-G1`, `R-G2`, `RT-01`, `UI5-14`, `UI5-20` | Auditoría UI 6.x (Hoy) | `mesa-hoy-page.tsx`, `mesa-hoy-view.ts`, `mesa-candidates-panel.tsx`, `mesa-position-row.tsx`, `mesa-operational-header.tsx` (+ test) | Pie sin arquitectura interna; menú Avanzado; `Gate N` humano; `—` → Opción B. |
| W2 Cartera/Historial/Consola | `UI5-13/14/20`, `R-G1` | Auditoría UI 6.x §3 | `history-page.tsx`, `mesa-libro-panel.tsx`, `operations-page.tsx`, `operational-console-*.tsx` (+ test) | Fuera `Libro`/`Ledger`/`fills` del primer nivel; disclosure único. |
| W3 Mercado + chrome | `R-G1`, `R-G2`, `RT-01`, `UI5-17` | Auditoría UI 6.x §4 | `app-top-bar.tsx`, `chart-workspace-page.tsx`, `command-registry.ts`, `command-palette.tsx`, `trading-status-bar.tsx`, `account-venue-preference.tsx` | Toolbar a nivel 2; palette en español; tooltip sin mecanismo. |
| W4 Asesor | `R-G1`, `UI5-14`, `RT-04` | Auditoría UI 6.x §5 | `research-page.tsx`, `research-trial-result-block.tsx`, `asesor-daily-ops-panel.tsx` (+ test) | Jerga estadística plegada; hueco unificado; payload defensivo. |
| W5 Accesibilidad | `UI5-01` | Auditoría UI 6.x §6 | `gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`, `mesa-positions-summary.tsx`, `history-page.tsx` | `heading-order` a 0; dos rutas L1 nuevas en el barrido. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.91-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en §6 tras el CI).
- **Frontend local:** `typecheck` **OK** (exit 0); `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); **276 ficheros / 1662 tests verdes** (+5 ficheros / +37 tests respecto a `2.11.90-beta`).
- **`axe` (mocks):** rutas L1 tocadas **13/13** (incl. `heading-order` 0) · `gp-e2e-live-virtual-confirm-mock` **2/2** · `gp-e2e-02-operational-console` **1/1**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.91-beta`).
- **`Δ motor = 0` local:** `git diff --name-only v2.88.90-beta -- packages/py` → **vacío**.

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **Backlog global fuera de alcance:** el barrido de `—` (dashboard, instruments, journal…) y los residuos de `Libro`/`Ledger` en superficies no auditadas (`propose-instrument-supervised.ts`, `finalist-propose-supervised.ts`, `position-exit-drawer-actions.tsx`, `app-help-menu.tsx`). **Remediación:** siguiente corte de lenguaje global con el mismo gate.
- **`Gate N` conservado** como dato de decisión (no es término prohibido).
- **`F-A2` — barrido `axe` en vivo.** Este sello certifica **con mocks**; la variante en vivo (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **`UI52-02` — `PortfolioDecision` durable**; **traza de materialización SIM**; **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **276 ficheros / 1662 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.91-beta`) |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` | **13/13** (desktop + 390×844; `heading-order` 0) |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-live-virtual-confirm-mock.spec.ts` | **2/2** |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-02-operational-console.spec.ts` | **1/1** |
| `replay-repro` — CI | _pendiente_ (`REPRODUCIDO` `1E3ADAC2…` ⇒ **`Δ motor = 0`**) |

---

## 6. Sello

- **Producto:** `V2.88.91-beta`. **Package:** `2.11.91-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `apps/web/src/components/technical-detail.tsx` (+ `.test.tsx`), `apps/web/src/components/first-level-gate.ts`, tests falsables de primer nivel (`confirm-first-level`, `mesa-hoy-first-level`, `history-first-level`, `research-first-level`), `docs/engineering/evidence/v2.88.91/README.md`, este documento.
- **Modificados:** `apps/web/src/**` (confirm + mesa + history + operations + operational-console + charts + command-palette + trading + research + layout), `apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`, `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/spec-ui-contract-5-0-2026-10-08.md`, `docs/adr/045-ui-contract-5-0.md`.
- **Tag anotado `v2.88.91-beta`** — _objeto/commit pendientes de crear_; mensaje propuesto `UI 6.x global language · Δ motor = 0`. **`Release tag CI` _pendiente_** (_cita en el commit `docs(seal)` posterior_).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.91/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` (Bloque E + §5) y `docs/adr/045-ui-contract-5-0.md`. Deuda de origen: `docs/engineering/auditoria-ui-6-x-global-2026-10-08.md`.
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.90-beta v2.88.91-beta -- packages/py   # vacío
   git rev-parse v2.88.90-beta:packages v2.88.91-beta:packages      # iguales
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   E2E_RUN=1 pnpm --filter @bolsa/web exec playwright test e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts e2e/gp-e2e-live-virtual-confirm-mock.spec.ts e2e/gp-e2e-02-operational-console.spec.ts
   ```
6. **Falsabilidad del primer nivel (`R-G1`).** Comprobar que fuera de `[data-technical-detail="true"]` **no** aparece `Recommendation`, `DecisionSession`, `Policy Gate`, `runId`, `cycleId`, `ledger`, `fills`, `DÍA-D`, `WFE`, `PBO`, `DSR`, ni el alias `Libro`, ni el guion `—`. El gate `first-level-gate.ts` + los cuatro tests `*-first-level.test.tsx` fallan si reaparecen.
7. **Falsabilidad de «una pantalla, una pregunta» (`R-G2`).** Confirmar que el primer bloque visible de cada pantalla responde su pregunta declarada y no describe el mecanismo.
8. **Falsabilidad del disclosure único (`RT-04`).** Confirmar que solo existe un `data-technical-detail` por bloque y que el rótulo es «Detalle técnico».
9. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que el primer nivel reintroduzca jerga interna, `—` o el alias `Libro` · que aparezca un segundo mecanismo de profundidad · que el barrido `axe` de rutas L1 devuelva `critical`/`serious` o `heading-order` · que el diff toque `packages/py/**`/motor/contrato/migraciones · que `replay-repro` no reproduzca `1E3ADAC2…`.
