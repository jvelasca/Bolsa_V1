# PENDIENTE DE BORRAR — inventario (2026-07-31)

Zona de auditoría: código / aliases **obsoletos** que aún no se eliminan porque pueden tener
callers, tests o compat de persistencia. Revisar antes de borrar en frío.

## Ya eliminado en esta pasada

| Ítem | Motivo |
|------|--------|
| `apps/web/src/features/charts/chart-bar-zone-anchor.tsx` | Orphan; sustituido por `ChartBarZoneIconAnchor` (docs CHART_*) |
| `scripts/pre-dev.mjs` | Deprecated wrapper → `db-ensure.mjs --ping`; sin referencias |
| `DCF_METHOD_FIXED_R` en `valuation.py` | Alias muerto `dcf_fcf_2stage_v1`; canónico `DCF_METHOD` |

## Pendiente (no borrar aún)

### Web / stores

| Path | Notas |
|------|-------|
| `apps/web/src/stores/ui-store.ts` — `openChartSettings` / `closeChartSettings` / `openListHub` aliases | `@deprecated`; migrar callers y quitar |
| `apps/web/src/features/trading/lists-tab/watchlist-panel.tsx` — `ListsTab` | Alias de `WatchlistPanel`; barrel `lists-tab.tsx` solo reexporta |
| `apps/web/src/features/charts/chart-bar-zone-rail-button.tsx` — `ChartBarZoneRailButton` | `@deprecated` → `ChartBarZoneChipButton` |
| `apps/web/src/features/charts/chart-scale-wheel.ts` / `chart-time-sync.ts` | Helpers `@deprecated` (attach* nuevos) |
| `apps/web/src/features/charts/chart-drawing-tools.ts` | `resolveGroupRail*` / rail family aliases |
| `apps/web/src/features/charts/indicator-compute.ts` | `resolveOverlayRenderSeries` / sub-series deprecated |
| `apps/web/src/features/charts/chart-inspector-nav.ts` | Tabs legacy → secciones |
| `apps/web/src/features/backtests/backtest-assistant-steps.ts` — `inferAssistantStep` | Solo tests legacy; prefer `resolveAssistantActiveStep` |
| `apps/web/src/features/backtests/backtest-explore-value.ts` | Presets/batería corta histórica |
| `apps/web/src/features/backtests/backtest-optimize-seed.ts` — `optimizeFamilyForStrategy` alias | Migrar |
| `apps/web/src/stores/workspace-store.ts` — `requestWorkspaceSave` alias + lectura legacy localStorage | Mantener hasta purge storage |
| `apps/web/src/features/trading/use-pending-orders.ts` — `readLegacyPendingOrders` | Migración one-shot |

### Shared

| Path | Notas |
|------|-------|
| `packages/shared` — varios `@deprecated` en chart-defaults / strategy-rules / chart-strategy-bridge | Compat dist; borrar tras bump consumers |

### Docs / copy

| Path | Notas |
|------|-------|
| Referencias a `chart-bar-zone-anchor` en `docs/CHART_*.md` | Actualizar a “eliminado” en próxima pasada docs |
| Launch configs legacy TS `:3001` en `.vscode` (si quedan) | Confirmar no se usan; `auth-gate` ya apunta a F5 Dev |

## Criterio de borrado

1. Cero imports en `apps/` + `packages/` (excl. tests que solo validan el alias).
2. No hay lectura de storage/localStorage que dependa del nombre.
3. Battery / typecheck verdes tras quitar.

## Relacionado FA

Verificación operativa: `pnpm test:fa` · `pnpm test:fa:ops` · `pnpm test:fa:boot`.

Próximas UX: botón IA informativo — **hecho** ([`NEXT-IA-BUTTON.md`](./NEXT-IA-BUTTON.md)). Unificación Research→Radar: [`research-radar-unification-2026-07-31.md`](../research-radar-unification-2026-07-31.md).
