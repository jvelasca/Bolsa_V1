# Chart TOP#1 indicator switch (2026-08-03)

## Qué

Switch **TOP#1** en la barra global del gráfico Trading (junto a Indicadores). ON aplica los indicadores del Finalista TOP #1 del instrumento + TF del gráfico; OFF quita solo instancias `origin: 'finalist-top1'`.

## Resolución de specs

1. `strategyDefinition.indicatorSpecs` si hay `strategyDefinitionId` y specs.
2. Si no: `presetIndicatorSpecs(strategyType)`.
3. Sin TOP / sin specs → switch deshabilitado (salvo que ya estuviera ON, para poder apagar).

## Archivos

- `packages/shared/src/strategy-top1-chart-indicators.ts`
- `apps/web/src/features/charts/chart-finalist-top1-switch.tsx`
- `workspace-store`: `setShowFinalistTop1Indicators` / `syncFinalistTop1Indicators` (idempotente)
- Wiring: `chart-workspace-page.tsx` → `ChartToolbarGlobalBar`

## Fuera de alcance

AUTO / Belief / mandato / execute. Plantilla de indicadores apaga el flag TOP#1.
