# PENDIENTE DE BORRAR — inventario (2026-07-31)

Zona de auditoría: código / aliases **obsoletos** que aún no se eliminan porque pueden tener
callers, tests o compat de persistencia. Revisar antes de borrar en frío.

## Ya eliminado en esta pasada

| Ítem                                                                                                                                                                                                                                                               | Motivo                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `apps/web/src/features/charts/chart-bar-zone-anchor.tsx`                                                                                                                                                                                                           | Orphan; sustituido por `ChartBarZoneIconAnchor` (docs CHART\_\*)                                                         |
| `scripts/pre-dev.mjs`                                                                                                                                                                                                                                              | Deprecated wrapper → `db-ensure.mjs --ping`; sin referencias                                                             |
| `DCF_METHOD_FIXED_R` en `valuation.py`                                                                                                                                                                                                                             | Alias muerto `dcf_fcf_2stage_v1`; canónico `DCF_METHOD`                                                                  |
| `apps/web/src/features/charts/chart-bar-zone-rail-button.tsx` — `ChartBarZoneRailButton`                                                                                                                                                                           | R-8D · 0 callers; alias → `ChartBarZoneChipButton` (bajo riesgo)                                                         |
| `apps/web/src/features/charts/chart-scale-wheel.ts` — `attachChartScaleWheel`                                                                                                                                                                                      | R-8D · 0 callers; alias → `attachChartScaleInteraction`                                                                  |
| `apps/web/src/features/charts/chart-time-sync.ts` — `attachChartTimeWheelSync`                                                                                                                                                                                     | R-8D · 0 callers; alias → `attachChartHorizontalWheel`                                                                   |
| `apps/web/src/features/charts/chart-drawing-tools.ts` — `resolveDisplayToolForGroup` / `resolveActivateToolForGroup`                                                                                                                                               | R-8D · 0 callers; → `resolveGroupRailIconTool` / `resolveGroupRailActivateTool`                                          |
| `apps/web/src/features/charts/indicator-compute.ts` — `resolveOverlayLineSeries`                                                                                                                                                                                   | R-8D · 0 callers; → `resolveOverlayRenderSeries`                                                                         |
| `apps/web/src/features/backtests/backtest-assistant-steps.ts` — `inferAssistantStep` (+ `backtest-assistant-steps.test.ts` huérfano)                                                                                                                               | R-8D · solo tests legacy; → `resolveAssistantActiveStep`                                                                 |
| `apps/web/src/features/backtests/backtest-explore-value.ts` — `EXPLORE_PRESET_BATTERY` / `matrixPresetRowsToExploreRows`                                                                                                                                           | R-8D · 0 callers; → `ALL_PRESET_COACH_KEYS` / `matrixRowsToExploreRows`                                                  |
| `apps/web/src/features/backtests/backtest-optimize-seed.ts` — `isSmaGridOptimizable`                                                                                                                                                                               | R-8D · 0 callers; alias → `optimizeFamilyForStrategy` (canónico, se mantiene)                                            |
| `packages/shared/src/chart-strategy-bridge.ts` — `presetFromHybridStrategyScore`                                                                                                                                                                                   | R-8D · 0 callers; → `presetFromStrategyScore`                                                                            |
| `apps/web/src/features/trading/lists-tab/watchlist-panel.tsx` — `ListsTab` (+ re-export en barrel `lists-tab.tsx`)                                                                                                                                                 | R-8D · 0 callers; → `WatchlistPanel`                                                                                     |
| `apps/web/src/stores/ui-store.ts` — aliases `chartToolbarSettingsOpen` / `chartToolbarSettingsTab` / `openChartToolbarSettings` / `closeChartToolbarSettings` / `openListProperties` / `closeListProperties` (+ tipo `ChartToolbarSettingsTab` huérfano)           | R-8D · 0 callers, no persistidos; → `chartGlobalBarSettings` / `chartDataBarSettings` / `openListHub`                    |
| Cargo de custodia **retirado del GET** (R-10 F4b, `e12a125`) — `ApplyCustodyFees` ya **NO se invoca** en `GetAccountSummary`/`GetTaxReport` (`accounts.py`); solo queda en su propia definición (`accounts.py:553`) y en el job `RunCustodyJob` (`custody_job.py`) | R-10 F4b · GET de solo lectura (D4/D4.1); el cobro pasa al job periódico. Verificado en código (información, no borrado) |

## Pendiente (no borrar aún)

### Web / stores

| Path                                                                                                                    | Notas                                                                               |
| ----------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `apps/web/src/features/charts/chart-inspector-nav.ts`                                                                   | Tabs legacy → secciones                                                             |
| `apps/web/src/features/trading/use-pending-orders.ts` — `readLegacyPendingOrders`                                       | RIESGO ALTO · gate `bolsa-trading-ui` → no tocar hasta purge storage                |
| `apps/web/src/stores/workspace-store.ts` — lectura legacy `chartDataStrip` / `chartNewTabSeed` / `newChartConfigSource` | RIESGO ALTO · migración workspaces → no tocar hasta purge storage                   |
| `readLegacyTimeframeFavorites`                                                                                          | RIESGO ALTO · gate `bolsa-chart-timeframe-favorites` → no tocar hasta purge storage |

### Shared

| Path                                                                                               | Notas                                                                                                 |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `packages/shared` — re-export `presetRuleGroups` desde `strategy-rules`                            | RIESGO ALTO · requiere repuntar imports shared → fuera de alcance                                     |
| `packages/shared` — otros `@deprecated` en chart-defaults / strategy-rules / chart-strategy-bridge | Compat dist; borrar tras bump consumers (salvo `presetFromHybridStrategyScore`, ya eliminado en R-8D) |

### Docs / copy

| Path                                                       | Notas                                                     |
| ---------------------------------------------------------- | --------------------------------------------------------- |
| Referencias a `chart-bar-zone-anchor` en `docs/CHART_*.md` | **RESUELTO** — ya actualizadas a “eliminado”              |
| Launch configs legacy TS `:3001` en `.vscode` (si quedan)  | **RESUELTO** — ya eliminadas; `auth-gate` apunta a F5 Dev |

## Criterio de borrado

1. Cero imports en `apps/` + `packages/` (excl. tests que solo validan el alias).
2. No hay lectura de storage/localStorage que dependa del nombre.
3. Battery / typecheck verdes tras quitar.

## Resuelto en R-8D (ya no aplica)

| Ítem                                                             | Nota                                        |
| ---------------------------------------------------------------- | ------------------------------------------- |
| `requestWorkspaceSave` alias en `workspace-store.ts`             | **No existe** — no hay alias con ese nombre |
| Launch `:3001` en `.vscode`                                      | **RESUELTO** — ya eliminado                 |
| «Actualizar referencias chart-bar-zone-anchor en docs CHART\_\*» | **RESUELTO** — ya actualizadas              |

## Relacionado FA

Verificación operativa: `pnpm test:fa` · `pnpm test:fa:ops` · `pnpm test:fa:boot`.

Próximas UX: botón IA informativo — **hecho** ([`NEXT-IA-BUTTON.md`](./NEXT-IA-BUTTON.md)). Unificación Research→Radar: [`research-radar-unification-2026-07-31.md`](../research-radar-unification-2026-07-31.md).

**R-12 A5 inventario (sin purge):** [`inventory-r12-2026-08-21.md`](./inventory-r12-2026-08-21.md). `presetRuleGroups` es API viva, no candidato de borrado.
