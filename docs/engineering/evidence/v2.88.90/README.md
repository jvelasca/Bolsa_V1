# Evidencia `v2.88.90-beta` — `UI`: **UI 6.0 — ejecución por slices (P0 · P1 · P2) + cierre del backlog UI 5.0**

**Producto:** `V2.88.90-beta` · **Package:** `2.11.90-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `apps/web/e2e/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.90-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/read-model puro (cierre del [Mapa de problemas UI 5.0](../../auditoria-ui-5-0-mapa-problemas-2026-10-08.md)) más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.

**Contrato implementado:** [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md) (`UI5-01`…`UI5-20`, con estado `DONE`/`PENDING` en §5; tras este sello **todo `DONE`**).
**Base:** [`evidence/v2.88.89/README.md`](../v2.88.89/README.md) · [`plan-ui-6-0-2026-10-08.md`](../../plan-ui-6-0-2026-10-08.md).

## 1. Cierre del backlog UI 5.0 — qué cambia

| Slice | Regla | Cambio | Implementación |
| --- | --- | --- | --- |
| **A1** | `UI5-19`, `RT-01`, `RT-02` | `operar.description` deja de prometer acción (Operar es solo lectura); `/auto/sistema` deja de re-espejar el estado+reloj de la HOME en su primer bloque (vive dentro de `AutoTechnicalDetail`); `/auto/analisis` pliega `DÍA-D · feedback OOS` tras `Detalle técnico` con rótulo humano. | [`auto-copy.ts`](../../../../apps/web/src/features/auto/auto-copy.ts), [`auto-sistema-page.tsx`](../../../../apps/web/src/features/auto/auto-sistema-page.tsx), [`auto-analisis-page.tsx`](../../../../apps/web/src/features/auto/auto-analisis-page.tsx) |
| **A2** | `UI5-09` | El peldaño `Salida final` de la escalera de la cabina deja de marcarse `active` sin evidencia: deriva de `remainingPct` medido y, sin traza, declara hueco (`"absent"` + «Sin dato todavía»). | [`operator-cabin-ui.tsx`](../../../../apps/web/src/features/trading/operator-cabin-ui.tsx) (+ test falsable) |
| **A3** | `UI5-14`, `RT-01` | La cabecera de columna `Salida` (que fundía decisión+ejecución) pasa a `Resultado`; la barra de estado abandona las abreviaturas `Pat./Disp./Ops./Pos.` y el literal `PAPER_D_EXECUTE` del primer nivel. | [`operations-panel.tsx`](../../../../apps/web/src/features/trading/operations-panel.tsx), [`trading-status-bar.tsx`](../../../../apps/web/src/features/trading/trading-status-bar.tsx) (+ tests) |
| **A4** | `UI5-01`, `UI5-17` | El primer nivel de Hoy deja la jerga `Ranking ≠ BUY` (pasa a lenguaje de resultado) y elimina la `Consola` duplicada (queda en el `AdminRail` y el menú «Ver detalles»). | [`mesa-hoy-page.tsx`](../../../../apps/web/src/features/mesa/mesa-hoy-page.tsx), [`mesa-candidates-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-candidates-panel.tsx), [`daily-desk-inbox.tsx`](../../../../apps/web/src/features/mesa/daily-desk-inbox.tsx) (+ tests) |
| **A5** | `UI5-13`, `UI5-17` | Mercado separa acción (acciones rápidas agrupadas) de información (barra de estado); vocabulario unificado `Cartera`/`Posiciones`/`Historial` (una cosa = un término; `Libro` = alias deprecado). | [`chart-workspace-page.tsx`](../../../../apps/web/src/features/charts/chart-workspace-page.tsx), [`daily-nav.ts`](../../../../apps/web/src/features/confirm/daily-nav.ts), [`mesa-positions-summary.tsx`](../../../../apps/web/src/features/mesa/mesa-positions-summary.tsx) (+ `daily-nav.test.ts`) |
| **A6** | `UI5-17`, `UI5-13` | **Verificado (no-op funcional):** la command palette ya separa por grupos (`Navegación`/`Configuración`/`Densidad`/`Tema`/`Layout`); se añade test falsable que ancla la separación. | [`command-palette.tsx`](../../../../apps/web/src/features/command-palette/command-palette.tsx) (sin cambio) + [`command-palette.test.tsx`](../../../../apps/web/src/features/command-palette/command-palette.test.tsx) |
| **B** | `UI5-01` | Nuevo barrido `axe-core` de las rutas no-AUTO tocadas a **1366×768 y 390×844**: 0 `critical`/`serious`, un único `main`+`h1`; fixes AA de contraste, `aria-label` de listbox, `<dt>` en `<dl>` `sr-only` y `tabIndex` de scroll. | [`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts) |

## 2. Invariantes de honestidad

- **`ranking ≠ decisión` / `ranking ≠ acción`.** El primer nivel de Hoy ya no dice `Ranking ≠ BUY`; lo explica en lenguaje de resultado y el término técnico queda plegado.
- **Una cosa = un término (`UI5-20`).** `Salida` deja de fundir decisión+ejecución (`Resultado`); `Pat./Disp./Ops./Pos.` dejan de ser primer nivel; `Cartera`/`Posiciones`/`Historial` unificados.
- **Ningún peldaño sin evidencia (`UI5-09`).** `Salida final` no se pinta `active` sin medición; sin traza → «Sin dato todavía».
- **`UNKNOWN ≠ 0` / sin dato = vocabulario Opción B.** Sin cambios en el cierre; se conserva el helper `absent-data.ts`.
- **`Δ motor = 0`.** Sin cambios en motor de decisión/ejecución, worker, umbrales ni Alembic; sin migración (head `052_top3_opportunities`); contrato HTTP sin cambio.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes, ajenos a este sello).
- `pnpm --filter @bolsa/web exec vitest run` → **271 ficheros / 1625 tests verdes**.
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.90-beta`).

## 4. Accesibilidad (`axe-core`)

- **AUTO** ([`gp-e2e-v28865-auto-axe-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-v28865-auto-axe-mock.spec.ts)) → **14/14** (8 rutas + teclado + responsive móvil 390×844 + carga/error/vacío).
- **Rutas tocadas no-AUTO** ([`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts)) → **9/9**: `/trading`, `/mesa`, `/mesa?view=posiciones`, `/confirm` y la command palette (Ctrl/Cmd+K) a desktop y 390×844 — **0 `critical`/`serious`**, un único `main`+`h1`.
- **Confirm LIVE VIRTUAL** ([`gp-e2e-live-virtual-confirm-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-live-virtual-confirm-mock.spec.ts)) → **2/2**.

## 5. Qué no cambia

Motor AUTO de decisión/ejecución, ledger, posiciones, settlement, contrato HTTP y esquema (head `052_top3_opportunities`). Live/XTB real no se implementa: el canal se declara `SIMULADO`.

## 6. Cita POST-TAG

**Tag anotado `v2.88.90-beta`** — mensaje `UI 5.0 backlog closure · Δ motor = 0`. Cita de `Release tag CI` **pendiente** (se anexa tras `git push origin v2.88.90-beta`). Criterio de cierre: `Release tag CI` **VERDE** con `replay-repro` **`REPRODUCIDO`** `1E3ADAC2…` ⇒ **`Δ motor = 0` confirmado por CI**.
