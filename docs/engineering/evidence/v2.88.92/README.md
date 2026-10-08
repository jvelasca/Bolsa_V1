# Evidencia `v2.88.92-beta` — `UI`: **UI 6.x — barrido global de residuos declarados**

**Producto:** `V2.88.92-beta` · **Package:** `2.11.92-beta` · **AsOf:** 2026-10-08. **Sin migración nueva** (head `052_top3_opportunities`). **`Δ motor = 0`**: todo el diff vive en `apps/web/src/**`, `docs/**`, el `package.json` y el `meta.bump` de los 9 CLIs DÍA-D. **Contrato HTTP sin cambio.** Los 9 CLIs DÍA-D `v2_89`…`v2_97` sellan `2.11.92-beta` junto al `package.json` (guardián `test_dia_d_bump_guard`).

> **Nota de árbol (honesta).** Este sello **no** mueve `packages/py/**`: es UI/read-model puro más el bump. `replay-repro` debe seguir `REPRODUCIDO` con la huella `1E3ADAC2…` para confirmarlo por CI.
> **Cierre de la deuda declarada en `v2.88.91`.** La [entrega `v2.88.91`](../../entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md) §4 dejó abiertos: `Gate N` residual, `submitted ≠ fill`, residuos `Libro`/`Ledger` y el comodín `—` fuera de las superficies auditadas. Aquí se cierran **todos**, cada uno con gate falsable.

**Contrato implementado:** [`spec-ui-contract-5-0-2026-10-08.md`](../../spec-ui-contract-5-0-2026-10-08.md) — Bloque E (`R-G1`, `R-G2`) ya en `DONE` desde `v2.88.91`; este sello **extiende la cobertura** del gate `R-G1` a las superficies que quedaron fuera.
**Base:** [`evidence/v2.88.91/README.md`](../v2.88.91/README.md).
**Detalle de origen:** [auditoría UI 6.x global §9](../../auditoria-ui-6-x-global-2026-10-08.md).
**Cita POST-TAG:** `Release tag CI` [`37802710522`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37802710522) **VERDE** (`11` jobs `success` + `playwright (integrated E2E, opt-in)` `skipped`; `certify` `success`). El job `replay-repro` dio **`VEREDICTO REPRODUCIDO`** con `sha256 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (misma huella que la serie; 2ª corrida idéntica) ⇒ **`Δ motor = 0` confirmado por CI**. Tag anotado `v2.88.92-beta` (objeto `6bde9337` → commit `88416aff`).

## 1. Barrido (residuos declarados en `v2.88.91` §4)

| # | Residuo declarado | Regla | Cierre | Implementación |
| --- | --- | --- | --- | --- |
| 1 | `Gate N` residual | `R-G1` | Helper único `gateHumanLabel` (`PASS`→«Sin bloqueos», `VETO`→«Bloqueado», `DEFERRED`→«Aplazado»; hueco → vocabulario Opción B) aplicado a la tira de mando y a la cola de entrada. | Nuevo [`gate-label.ts`](../../../../apps/web/src/components/gate-label.ts); [`hoy-command-strip.tsx`](../../../../apps/web/src/features/trading/hoy-command-strip.tsx), [`mesa-entry-queue-panel.tsx`](../../../../apps/web/src/features/operations/mesa-entry-queue-panel.tsx) (+ [`mesa-candidates-panel.tsx`](../../../../apps/web/src/features/mesa/mesa-candidates-panel.tsx)) |
| 2 | `submitted ≠ fill` | `R-G1` | Copy unificado a «Enviar una orden no significa que se haya ejecutado» en los cuatro ficheros. | [`account-venue-preference.tsx`](../../../../apps/web/src/features/accounts/account-venue-preference.tsx), [`live-virtual-order-gateway.tsx`](../../../../apps/web/src/features/confirm/live-virtual-order-gateway.tsx), [`live-virtual-banner.tsx`](../../../../apps/web/src/features/confirm/live-virtual-banner.tsx), [`mesa-operational-bar.tsx`](../../../../apps/web/src/features/operations/mesa-operational-bar.tsx) |
| 3 | `Libro`/`Ledger` de primer nivel | `R-G1` | Retirados en dashboard, cuentas (panel/wizard/settings), fiscal, screeners, `backtesting-tracker`, ayuda y `*-propose-supervised`/`position-exit-drawer-actions`. **Identificadores de código y comentarios intactos.** | [`dashboard-page.tsx`](../../../../apps/web/src/features/dashboard/dashboard-page.tsx), [`account-detail-panel.tsx`](../../../../apps/web/src/features/accounts/account-detail-panel.tsx), [`tax-report-page.tsx`](../../../../apps/web/src/features/fiscal/tax-report-page.tsx), `screeners-*.tsx`, [`app-help-menu.tsx`](../../../../apps/web/src/features/help/app-help-menu.tsx), [`backtesting-tracker.ts`](../../../../apps/web/src/features/settings/backtesting-tracker.ts), etc. |
| 4 | Comodín `—` de primer nivel | `UI5-14`, `R-G1` | `findFirstLevelDashes` añadido al gate; fallbacks `"—"` sustituidos por `absentDataLabel()`. | [`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts) + superficies de dashboard, cuentas, instrumentos, fiscal y screeners |

## 2. Gate falsable extendido

Nuevo [`barrido-global-first-level.test.tsx`](../../../../apps/web/src/features/barrido-global-first-level.test.tsx): asevera que **no** reaparecen tokens prohibidos (jerga interna, alias `Libro`) ni el comodín `—` fuera de `[data-technical-detail="true"]` en:

- **Mercado** — `chart-workspace-page.tsx`, `app-top-bar.tsx`.
- **Laboratorio** — `backtests-page.tsx` + pestañas de run/jobs.
- **Chrome** — `command-registry.ts`, `command-palette.tsx`.
- **Superficies con `—`** — `dashboard-page`, `account-detail-panel`, `instruments-page`, `instruments-hub-detail-panel`, `instrument-detail-page`, `tax-report-page` y los paneles del screener.

El gate falla si cualquiera de esas superficies reintroduce jerga de backend, el alias `Libro` o el guion como comodín.

## 3. Verificación (local)

- `pnpm --filter @bolsa/web exec tsc --noEmit -p tsconfig.json` → **OK** (exit 0).
- `pnpm --filter @bolsa/web exec eslint src` → **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes).
- `pnpm --filter @bolsa/web exec vitest run` → **277 ficheros / 1687 tests verdes** (+1 fichero / +25 tests respecto a `2.11.91-beta`).
- `python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` → **1 passed** (`2.11.92-beta`).
- **`Δ motor = 0`**: `git diff --name-only v2.88.91-beta -- packages/py` → **vacío**.

## 4. Qué no cambia / deuda declarada

- **Motor AUTO** de decisión/ejecución, worker, umbrales, Alembic (head `052_top3_opportunities`), `contract:gen`, contrato HTTP y esquema. Live/XTB real sigue fuera: el canal se declara `SIMULADO`.
- **`playwright` integrado** sigue `opt-in`/`skipped`; la certificación `axe` de la serie es **con mocks**.
- **Residuos fuera de alcance (resto de la app), corregidos en el sello `v2.88.93-beta`:** el barrido de `—` de este sello se limita a las superficies del punto 4 de §1. La auditoría posterior detectó `—` de primer nivel en superficies hermanas (Caja/Patrimonio/Sector/Vigencia) y el rótulo `Gate` crudo en el drawer de Oportunidades; se corrigen y se añaden al gate, no se reclasifican como «nivel 3 decorativo».
- **`Gate N` conservado** como dato de decisión (no es término prohibido): solo se humaniza su etiqueta.
- **Deuda durable backend:** `PortfolioDecision`, materialización SIM, PIT histórico, Execution Analysis.
