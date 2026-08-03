# Chart TOP#1 indicator switch (2026-08-03)

## Qué

Overlay Finalista TOP #1 en Trading, con política workspace + override por gráfico.

| Control | Dónde | Efecto |
|---------|--------|--------|
| **Finalista #1 · todos** | Barra general · zona Indicadores | `preferences.finalistTop1DefaultOn` + flag en todas las pestañas abiertas; gráficos nuevos heredan ON |
| **Finalista #1** | Barra del gráfico en uso · junto a Plantillas | Solo esa pestaña (opt-out / opt-in sin cambiar la política «todos») |

ON aplica specs del Finalista #1 del instrumento+TF; OFF quita solo `origin: 'finalist-top1'`.

## Resolución de specs

1. `strategyDefinition.indicatorSpecs` si hay `strategyDefinitionId` y specs.
2. Si no: `presetIndicatorSpecs(strategyType)`.
3. Sin TOP / sin specs → switch por gráfico deshabilitado (salvo que ya estuviera ON, para poder apagar).

Las pestañas inactivas solo marcan el flag; al enfocarlas se sincronizan los overlays.

## Archivos

- `packages/shared`: `strategy-top1-chart-indicators.ts`, `preferences.finalistTop1DefaultOn`, `ChartTabState.showFinalistTop1Indicators`
- `workspace-store`: `setShowFinalistTop1Indicators`, `setFinalistTop1DefaultForAll`, `syncFinalistTop1Indicators`
- UI: `chart-finalist-top1-switch.tsx` (`scope: 'all' | 'chart'`)

## Fuera de alcance

AUTO / Belief / mandato / execute. Plantilla de indicadores apaga el flag de **ese** gráfico (opt-out), no la política «todos».

## Relacionado

- [trading-operativa-panel-2026-08-04.md](./trading-operativa-panel-2026-08-04.md) — panel Operativa / En estudio / IO
- [HELP.md](../HELP.md) — sync Ayuda
