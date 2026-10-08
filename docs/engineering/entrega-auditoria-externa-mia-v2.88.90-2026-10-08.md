# Entrega a auditoría externa (MIA) — `v2.88.90-beta` · `UI`: **UI 6.0 — ejecución por slices (P0 · P1 · P2) + cierre del backlog UI 5.0**

> **Fecha:** 2026-10-08 · **Producto:** `V2.88.90-beta` · **Package:** `2.11.90-beta` · **Alembic head:** `052_top3_opportunities` (**sin migración**).
> **Base:** `v2.88.89-beta` (tag anotado objeto `ab26aeba` → commit `b9557c21`; `Release tag CI` [`37766767402`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37766767402) **VERDE**).
> **Unidad de esta auditoría:** cerrar **todo** el backlog que el [Mapa de problemas UI 5.0](./auditoria-ui-5-0-mapa-problemas-2026-10-08.md) dejó abierto tras la oleada UI 6.0 (no solo los `PENDING` declarados), y certificar el nivel 1 (jerga, duplicidades, una cosa por término) y la accesibilidad de las rutas tocadas. El plan es [`plan-ui-6-0-2026-10-08.md`](./plan-ui-6-0-2026-10-08.md); el contrato es [`spec-ui-contract-5-0-2026-10-08.md`](./spec-ui-contract-5-0-2026-10-08.md) (`UI5-01`…`UI5-20`, §5 ahora **todo `DONE`**).
> **Regla del hueco:** una regla que no se puede afirmar se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente o `UNKNOWN` se rotula «Sin dato todavía»; **jamás** se rellena con `0` ni con verde.
> **`Δ AUTO decision/execution motor = 0`.** Todo el sello es UI/read-model y tests en `apps/web/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D: **sin motor, sin worker, sin umbrales, sin Alembic, sin `contract:gen`, sin tocar `packages/py/**`**. **El contrato HTTP NO cambia.**
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.90/README.md`](./evidence/v2.88.90/README.md).
> **Cita POST-TAG:** `Release tag CI` [`37774540104`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37774540104) **VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**). Tag anotado `v2.88.90-beta` (objeto `c220df76` → commit `c15873fd`).

**Sello dirigido (declarado).** Mandato: **una sola aplicación, un único lenguaje operativo en el primer nivel**. No se añaden funciones ni se toca el motor: se re-corta la superficie ya existente (fuera jerga, fuera duplicidades, una cosa por término, ningún peldaño sin evidencia) y se hace **falsable** cada afirmación con un test. El barrido `axe` de rutas no-AUTO queda **con mocks** (el `playwright` integrado sigue `opt-in`).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** el cierre del backlog UI 5.0 sobre UI/read-model (Oleada A) más la certificación `axe` de las rutas tocadas (Oleada B):

1. **A1 · AUTO lenguaje/densidad (`UI5-19`).** `operar.description` deja de prometer acción (Operar es solo lectura); el primer bloque de `/auto/sistema` deja de re-espejar el estado+reloj de la HOME (vive dentro de `AutoTechnicalDetail`); `/auto/analisis` pliega `DÍA-D · feedback OOS` tras `Detalle técnico` con rótulo humano.
2. **A2 · tercera escalera (`UI5-09`).** El peldaño `Salida final` de la escalera de la cabina deja de marcarse `active` sin evidencia: deriva de `remainingPct` medido y, sin traza, declara hueco (`"absent"` + «Sin dato todavía»).
3. **A3 · columna y barra (`UI5-14`, `RT-01`).** La cabecera de columna `Salida` (que fundía decisión+ejecución) pasa a `Resultado`; la barra de estado abandona `Pat./Disp./Ops./Pos.` y el literal `PAPER_D_EXECUTE` del primer nivel.
4. **A4 · Hoy L1 (`UI5-01`, `UI5-17`).** El primer nivel de Hoy deja la jerga `Ranking ≠ BUY` (pasa a lenguaje de resultado) y elimina la `Consola` duplicada (queda en el `AdminRail` y el menú «Ver detalles»).
5. **A5 · Mercado + Cartera (`UI5-13`, `UI5-17`).** Mercado separa acción (acciones rápidas agrupadas) de información (barra de estado); vocabulario unificado `Cartera`/`Posiciones`/`Historial` (`Libro` = alias deprecado).
6. **A6 · command palette (`UI5-17`).** **Verificado (no-op funcional):** ya separa por grupos; se ancla con test falsable de render.
7. **Oleada B · `UI5-01`.** Nuevo barrido `axe-core` de `/trading`, `/mesa`, `/mesa?view=posiciones`, `/confirm` y la command palette a **1366×768 y 390×844**: 0 `critical`/`serious`, un único `main`+`h1`; fixes AA de contraste, `aria-label` de listbox, `<dt>` en `<dl>` `sr-only` y `tabIndex` de scroll.

**NO se entrega**, y se declara:

- **NO** se toca el motor de decisión/ejecución, el ledger, las posiciones, el settlement, el worker ni los umbrales (`Δ motor = 0`; lo confirma `replay-repro` en CI).
- **NO** cambia el contrato HTTP ni el esquema (head Alembic intacto `052_top3_opportunities`).
- **NO** se toca `packages/py/**`.
- **NO** se implementa el canal `LIVE` real: el canal se declara `SIMULADO`.
- **NO** se ejecuta el `playwright` **integrado** (E2E contra stack real): sigue `opt-in` y `skipped`. La certificación `axe` de este sello es **con mocks**.
- **NO** se cierran las deudas estructurales de la serie: `PortfolioDecision` durable, traza de materialización SIM, PIT histórico institucional y Execution Analysis.
- **NO** se re-mide el motor: las cifras de la serie se **heredan y citan**.

---

## 2. Cambios verificables (todo con gate)

| Slice | Regla | Hallazgo de origen | Fichero(s) | Qué hace |
| --- | --- | --- | --- | --- |
| A1 | `UI5-19`, `RT-01`, `RT-02` | Mapa UI 5.0 §5.6 | `auto-copy.ts`, `auto-sistema-page.tsx`, `auto-analisis-page.tsx` (+ tests) | Operar sin promesa de acción; Sistema sin espejar la HOME; `DÍA-D · feedback OOS` plegado. |
| A2 | `UI5-09` | Mapa UI 5.0 §4.3.2/.3 | `operator-cabin-ui.tsx` (+ `.test.tsx`) | `Salida final` derivado de evidencia; sin traza → hueco («Sin dato todavía»). |
| A3 | `UI5-14`, `RT-01` | Mapa UI 5.0 §4.3.4, §2.3 | `operations-panel.tsx`, `trading-status-bar.tsx` (+ tests) | Columna `Resultado`; barra sin abreviaturas ni `PAPER_D_EXECUTE`. |
| A4 | `UI5-01`, `UI5-17` | Mapa UI 5.0 §2.5, §5.1 | `mesa-hoy-page.tsx`, `mesa-candidates-panel.tsx`, `daily-desk-inbox.tsx` (+ tests) | Fuera jerga `Ranking ≠ BUY`; fuera `Consola` duplicada. |
| A5 | `UI5-13`, `UI5-17` | Mapa UI 5.0 §2.5, §5.5 | `chart-workspace-page.tsx`, `daily-nav.ts`, `mesa-positions-summary.tsx` (+ tests) | Acción ≠ información; `Cartera`/`Posiciones`/`Historial` unificados. |
| A6 | `UI5-17`, `UI5-13` | Mapa UI 5.0 §2.4 | `command-palette.tsx` (sin cambio) + `command-palette.test.tsx` | Verificado: grupos ya separados; test ancla la separación. |
| B | `UI5-01` | Mapa UI 5.0 §6 | `gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` + fixes AA | `axe` 0 `critical`/`serious` en rutas tocadas, desktop + móvil. |
| Bump | — | — | `package.json` + `apps/api-python/scripts/v2_89`…`v2_97` | `2.11.90-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |
| Contrato | — | — | `spec-ui-contract-5-0-2026-10-08.md` §5, `045-ui-contract-5-0.md` | `UI5-19`/`UI5-01` a `DONE`; `UI5-19`/`UI5-01`/resto cerrado con evidencia. |

---

## 3. Medición

- **Motor:** sin cambio esperado. `replay-repro` debe seguir **`REPRODUCIDO`** (`sha256 1E3ADAC2…`) ⇒ **`Δ motor = 0`** (cita en §6 tras el CI).
- **Frontend local:** `typecheck` **OK** (exit 0); `lint` **0 errores** (`23` avisos `react-hooks/exhaustive-deps` preexistentes); **271 ficheros / 1625 tests verdes**.
- **`axe` (mocks):** `gp-e2e-v28865` AUTO **14/14** · `gp-e2e-ui5-0-axe-touched-routes-mock` rutas tocadas **9/9** · `gp-e2e-live-virtual-confirm-mock` **2/2**.
- **Bump guard:** `pytest apps/api-python/tests/test_dia_d_bump_guard.py` **1 passed** (`2.11.90-beta`).

---

## 4. Hallazgos abiertos (declarados, con remediación)

- **`heading-order` (best-practice) en 11 rutas L1** — abierto desde `v2.88.54`; preexistente y fuera del alcance de este sello.
- **`F-A2` — barrido `axe` en vivo.** Este sello certifica **con mocks**; la variante en vivo (stack real, `playwright` integrado) sigue `opt-in` y `skipped`. **Remediación:** activar el `playwright` integrado en el `Release tag CI`.
- **`mesa-candidates-panel` conserva `Gate N`** como dato de decisión (no es término prohibido de §5.6).
- **`account-venue-preference.tsx`** conserva un literal `submitted ≠ fill` fuera de los slices.
- **Cierre `COMPLETE` → `Posición cerrada`** sigue sin exigir traza intermedia (coherente con el modelo durable y el contrato backend).
- **`UI52-02` — `PortfolioDecision` durable**; **traza de materialización SIM**; **PIT histórico institucional** y **Execution Analysis**: abiertos (spine/backend).
- **`23` warnings `react-hooks/exhaustive-deps`** (`eslint`, **0 errores**): preexistentes, ajenos a este sello.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` | **OK** |
| `pnpm --filter @bolsa/web exec eslint src` | **0 errores** (23 avisos preexistentes) |
| `pnpm --filter @bolsa/web exec vitest run` | **271 ficheros / 1625 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** (`2.11.90-beta`) |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-v28865-auto-axe-mock.spec.ts` | **14/14** (0 `critical`/`serious`) |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` | **9/9** (desktop + 390×844) |
| `E2E_RUN=1 … playwright test e2e/gp-e2e-live-virtual-confirm-mock.spec.ts` | **2/2** |
| `replay-repro` — CI | **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0`** |

---

## 6. Sello

- **Producto:** `V2.88.90-beta`. **Package:** `2.11.90-beta`. **Sin migración** (Alembic head `052_top3_opportunities`). **Contrato HTTP sin cambio.** `packages/py/**` **sin mover**.
- **Añadidos:** `apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`, `apps/web/src/features/trading/trading-status-bar.test.tsx`, `apps/web/src/features/command-palette/command-palette.test.tsx`, `docs/engineering/evidence/v2.88.90/README.md`, este documento.
- **Modificados:** `apps/web/src/**` (AUTO + trading + mesa + charts + confirm + command-palette), `package.json`, `apps/api-python/scripts/v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `docs/engineering/spec-ui-contract-5-0-2026-10-08.md`, `docs/adr/045-ui-contract-5-0.md`.
- **Tag anotado `v2.88.90-beta`** (objeto `c220df76` → commit `c15873fd`) — mensaje `UI 5.0 backlog closure · Δ motor = 0`. **`Release tag CI` [`37774540104`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37774540104) VERDE** (`11` jobs `success` + `playwright` integrado `skipped`; `certify` `success`; `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir `docs/engineering/evidence/v2.88.90/README.md` en el árbol del commit del sello.
2. **Entrega MIA.** Leer este documento: qué se entrega/NO, cambios verificables, medición, hallazgos abiertos y gates.
3. **Contrato.** Leer `docs/engineering/spec-ui-contract-5-0-2026-10-08.md` §5 (todo `DONE`) y `docs/adr/045-ui-contract-5-0.md`. La deuda de origen: `docs/engineering/auditoria-ui-5-0-mapa-problemas-2026-10-08.md` y `docs/engineering/plan-ui-6-0-2026-10-08.md`.
4. **`Δ motor = 0`.** Verificar que el diff del sello **no toca** `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`:
   ```bash
   git diff --name-only v2.88.89-beta v2.88.90-beta -- packages/py   # vacío
   git rev-parse v2.88.89-beta:packages v2.88.90-beta:packages      # iguales
   ```
5. **Reproducción local.**
   ```bash
   pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json
   pnpm --filter @bolsa/web exec eslint src
   pnpm --filter @bolsa/web exec vitest run
   pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   E2E_RUN=1 pnpm --filter @bolsa/web exec playwright test e2e/gp-e2e-v28865-auto-axe-mock.spec.ts e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts e2e/gp-e2e-live-virtual-confirm-mock.spec.ts
   ```
6. **Falsabilidad del nivel 1.** Comprobar que el DOM de primer nivel no contiene `Salida` (columna fundida), `Pat.`/`Disp.`/`Ops.`/`Pos.`, `PAPER_D_EXECUTE`, `Ranking ≠ BUY`, ni una `Consola` duplicada en Hoy.
7. **Falsabilidad de la escalera (`UI5-09`).** Confirmar en `operator-cabin-ui.tsx` que sin `remainingPct` medido el peldaño `Salida final` **no** se pinta `active` (test dedicado).
8. **Qué falsaría el sello:** que un dato ausente se pinte `0` o en verde · que `Salida final` (u otro peldaño) afirme estado sin evidencia · que el primer nivel reintroduzca jerga prohibida o abreviatura · que Cartera/Posiciones/Historial se vuelvan a mezclar · que aparezca `critical`/`serious` en `axe` de las rutas tocadas · que el diff toque `packages/py/**`/motor/contrato/migraciones · que `replay-repro` no reproduzca `1E3ADAC2…`.
