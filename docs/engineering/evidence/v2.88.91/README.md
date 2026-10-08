# Evidencia `v2.88.91-beta` — `UI`: **UI 6.x — lenguaje global (Confirmar · Hoy · resto de la app)**

**Producto:** `V2.88.91-beta` · **Package:** `2.11.91-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `apps/web/e2e/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.91-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/read-model puro más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Cierre parcial del backlog de la auditoría.** La [auditoría UI 6.x global](../../auditoria-ui-6-x-global-2026-10-08.md) detalla Confirmar/Hoy; las superficies de las oleadas 2-6 se corrigen aquí. Los residuos fuera de alcance quedan declarados en §6.

**Contrato implementado:** [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md) — **nuevo Bloque E** (`R-G1`, `R-G2`) en §2 y enmienda del [ADR-045](../../../adr/045-ui-contract-5-0.md) §1. En §5, `R-G1`/`R-G2` pasan a `DONE`.
**Base:** [`evidence/v2.88.90/README.md`](../v2.88.90/README.md).
**Cita POST-TAG:** `Release tag CI` [`37796847434`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37796847434) **VERDE** (`11` jobs `success` + `playwright (integrated E2E, opt-in)` `skipped`; `certify` `success`). El job `replay-repro` dio **`VEREDICTO REPRODUCIDO`** con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (misma huella que la serie; 2ª corrida idéntica) ⇒ **`Δ motor = 0` confirmado por CI**. Tag anotado `v2.88.91-beta` (objeto `a34a6094` → commit `1e832b30`).

## 1. Base compartida (Slice 0, bloqueante)

| Pieza | Regla | Implementación |
| --- | --- | --- |
| **Disclosure único** | `RT-04` | Nuevo [`technical-detail.tsx`](../../../../apps/web/src/components/technical-detail.tsx) (rótulo `Detalle técnico`, marca `data-technical-detail`); `AutoTechnicalDetail` delega en él (un solo idiom de profundidad). |
| **Gate falsable** | `R-G1` | Nuevo [`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts): `FORBIDDEN_FIRST_LEVEL_TOKENS`, `stripTechnicalDetailBlocks`, `findFirstLevelViolations`. Cada oleada ancla un test que falla si la jerga aparece fuera de nivel 3. |
| **Helper de hueco** | `UI5-14` | Se confirma [`absent-data.ts`](../../../../apps/web/src/components/absent-data.ts) como única fuente (`Sin dato todavía` / `No aplica` / `No disponible`); `—` solo nivel 3. |
| **Contrato** | `R-G1`, `R-G2` | Bloque E en `spec-ui-contract-5-0` §2 + filas §5 + falsabilidad §6; ADR-045 §1.5. |

## 2. Oleada 1 — Confirmar (`P0`) y Hoy (`P1`)

| Slice | Regla | Cambio | Implementación |
| --- | --- | --- | --- |
| **W1 Confirmar** | `R-G1`, `R-G2`, `RT-02`, `RT-04`, `UI5-09`, `UI5-20` | Bloque técnico `Recommendation`/`DecisionSession`/`Policy Gate`/`Assessment(s)`/`Prediction` plegado bajo `TechnicalDetail`; escalera **codeada en español** (`data-testid`/`data-step`), fuera los tokens ingleses; «Telegrama al broker»→«Orden propuesta»; `DE`/`A`/`REF`→`Desde`/`Para`/`Referencia`; `Libro` fuera; anti-frases de mecanismo → lenguaje de usuario; primer bloque de `confirm-content` responde «¿Qué vas a autorizar?». | [`supervised-f3-panel.tsx`](../../../../apps/web/src/features/settings/supervised-f3-panel.tsx), [`live-virtual-order-gateway.tsx`](../../../../apps/web/src/features/confirm/live-virtual-order-gateway.tsx), [`live-virtual-ladder.ts`](../../../../apps/web/src/features/confirm/live-virtual-ladder.ts), [`live-virtual-why.ts`](../../../../apps/web/src/features/confirm/live-virtual-why.ts), [`confirm-content.tsx`](../../../../apps/web/src/features/confirm/confirm-content.tsx) (+ [`confirm-first-level.test.tsx`](../../../../apps/web/src/features/confirm/confirm-first-level.test.tsx)) |
| **W1 Hoy** | `R-G1`, `R-G2`, `RT-01`, `UI5-14`, `UI5-20` | Pie de la HOME sin arquitectura interna ni `Libro`; menú «Avanzado» en lenguaje humano; `Gate {n}` → `gateHumanLabel()`; `—` → vocabulario Opción B en Oportunidades y Posiciones; «lista `estudio`» → «tu universo de análisis»; pregunta declarada = «¿Qué requiere mi atención?»; cadena en mayúsculas simplificada; `mesa-operational-header` ya no arrastra `Risk Gate`/`PAPER_D execute`. | [`mesa-hoy-page.tsx`](../../../../apps/web/src/features/mesa/mesa-hoy-page.tsx), [`mesa-hoy-view.ts`](../../../../apps/web/src/features/mesa/mesa-hoy-view.ts), [`mesa-candidates-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-candidates-panel.tsx), [`mesa-position-row.tsx`](../../../../apps/web/src/features/mesa/mesa-position-row.tsx), [`mesa-operational-header.tsx`](../../../../apps/web/src/features/mesa/mesa-operational-header.tsx) (+ [`mesa-hoy-first-level.test.tsx`](../../../../apps/web/src/features/mesa/mesa-hoy-first-level.test.tsx)) |

## 3. Oleadas 2-6

| Oleada | Regla | Cambio | Implementación |
| --- | --- | --- | --- |
| **W2 Cartera · Historial · Consola** | `UI5-13/14/20`, `R-G1` | `h1` «Historial» (ya no «Libro · Historial»); «Movimientos contables» (ya no «Ledger contable»); fuera `Libro`/`Ledger`/`fills` de primer nivel; `—` → Opción B; disclosure único en la Consola; **alias `LIBRO_*` conservados** (fijados por test). | [`history-page.tsx`](../../../../apps/web/src/features/history/history-page.tsx), [`mesa-libro-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-libro-panel.tsx), [`operations-page.tsx`](../../../../apps/web/src/features/operations/operations-page.tsx), [`operational-console-*.tsx`](../../../../apps/web/src/features/operational-console/), [`daily-nav.ts`](../../../../apps/web/src/features/confirm/daily-nav.ts) (+ [`history-first-level.test.tsx`](../../../../apps/web/src/features/history/history-first-level.test.tsx)) |
| **W3 Mercado + chrome** | `R-G1`, `R-G2`, `RT-01`, `UI5-17` | Toolbar avanzada de la barra superior a un único menú `Ajustes de vista` (nivel 2); `h1` de Mercado a tamaño de puerta; palette con grupos en español separando navegación de ajustes (divisor **decorativo**, sin `role="separator"` en el `listbox`); tooltip de la barra de estado sin lenguaje de mecanismo; `AccountVenuePreference` a lenguaje de resultado. | [`app-top-bar.tsx`](../../../../apps/web/src/components/layout/app-top-bar.tsx), [`chart-workspace-page.tsx`](../../../../apps/web/src/features/charts/chart-workspace-page.tsx), [`command-registry.ts`](../../../../apps/web/src/features/command-palette/command-registry.ts), [`command-palette.tsx`](../../../../apps/web/src/features/command-palette/command-palette.tsx), [`trading-status-bar.tsx`](../../../../apps/web/src/features/trading/trading-status-bar.tsx), [`account-venue-preference.tsx`](../../../../apps/web/src/features/accounts/account-venue-preference.tsx), [`confirm-nav.ts`](../../../../apps/web/src/features/confirm/confirm-nav.ts) |
| **W4 Asesor** | `R-G1`, `UI5-14`, `RT-04` | Jerga estadística (`Sharpe`, `campaignId`, `proposedBy`, `presetKey`, `K`, `WFE/PBO/DSR`) tras el `TechnicalDetail` único; `Sin datos.`/`—` → Opción B; `Ledger` del Diario a lenguaje de resultado; payload defensivo (una respuesta incompleta se declara ausente, no rompe). | [`research-page.tsx`](../../../../apps/web/src/features/research/research-page.tsx), [`research-trial-result-block.tsx`](../../../../apps/web/src/features/research/research-trial-result-block.tsx), [`asesor-daily-ops-panel.tsx`](../../../../apps/web/src/features/research/asesor-daily-ops-panel.tsx) (+ [`research-first-level.test.tsx`](../../../../apps/web/src/features/research/research-first-level.test.tsx)) |
| **W5 Accesibilidad** | `UI5-01` | Jerarquía `h1→h2→h3` sin saltos en las rutas L1; barrido `axe` **extendido** con la regla `heading-order` y **dos rutas nuevas** (`/research`, `/history`). | [`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts), [`mesa-positions-summary.tsx`](../../../../apps/web/src/features/mesa/mesa-positions-summary.tsx), [`history-page.tsx`](../../../../apps/web/src/features/history/history-page.tsx) |

## 4. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **276 ficheros / 1662 tests verdes** (+5 ficheros / +37 tests respecto a `2.11.90-beta`).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.91-beta`).
- **`Δ motor = 0`**: `git diff --name-only v2.88.90-beta -- packages/py` → **vacío**.

## 5. Accesibilidad (`axe-core`)

- **Rutas L1 tocadas** ([`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts)) → **13/13**: `/trading`, `/mesa`, `/mesa?view=posiciones`, `/confirm`, `/research`, `/history` × {desktop 1366×768, móvil 390×844} + command palette (Ctrl/Cmd+K). **0 `critical`/`serious`**, un único `main`+`h1`, y **0 `heading-order`** (nuevo).
- **Confirm LIVE VIRTUAL** ([`gp-e2e-live-virtual-confirm-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-live-virtual-confirm-mock.spec.ts)) → **2/2** (copy actualizado a lenguaje de resultado).
- **Consola operacional** ([`gp-e2e-02-operational-console.spec.ts`](../../../../apps/web/e2e/gp-e2e-02-operational-console.spec.ts)) → **1/1** (enlace «Posiciones»).

## 6. Qué no cambia / deuda declarada

- **Motor AUTO** de decisión/ejecución, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema. Live/XTB real sigue fuera: el canal se declara `SIMULADO`.
- **Backlog fuera de alcance:** barrido global de `—` (dashboard, instruments, journal…) y **Playwright integrado** (sigue `opt-in`/`skipped`); residuos de `Libro`/`Ledger` en superficies no auditadas (`propose-instrument-supervised.ts`, `finalist-propose-supervised.ts`, `position-exit-drawer-actions.tsx`, `app-help-menu.tsx`) y `Gate N` conservado como dato de decisión.
- **Deuda durable backend:** `PortfolioDecision`, materialización SIM, PIT histórico, Execution Analysis.
