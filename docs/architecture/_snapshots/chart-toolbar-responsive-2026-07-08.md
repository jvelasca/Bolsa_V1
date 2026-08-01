# Snapshot — barra responsive (jul 2026)

Copia de referencia **antes** del refactor responsive de la barra de datos del gráfico.

## Nombre oficial de la barra

| Nombre en UI | Nombre técnico | Componente |
|--------------|----------------|------------|
| Escala · Valor · Cursor · atajos | **Barra de datos del gráfico** (barra por tab) | `chart-toolbar-chart-bar.tsx` |
| Indicadores · C/V · BD… | **Barra global del workspace** | `chart-toolbar-global-bar.tsx` |

## Problema detectado

1. La barra por gráfico se dividió en `primary` + `actions` (`ml-auto`). El `flex-wrap` exterior solo tenía **dos hijos**, así que **no** repartía Escala / Valor / Cursor en filas distintas.
2. `wrapChips={wrapRows}` hacía que los chips **saltaran de línea dentro** de cada zona, rompiendo la altura fija (`1.375rem`) y amontonando contenido.
3. Faltaban reglas `@container` específicas para `.chart-toolbar-chart-stack` (documentadas en `CHART_RESPONSIVE.md` pero no aplicadas en CSS).
4. Las zonas usaban `shrink-0` sin modo «ancho completo» en panel estrecho.

## Archivos tocados en el refactor

- `apps/web/src/features/charts/chart-toolbar-chart-bar.tsx`
- `apps/web/src/features/charts/chart-bar-zone-styles.ts`
- `apps/web/src/features/charts/chart-bar-zone-picker.tsx`
- `apps/web/src/features/charts/chart-timeframe-bar.tsx`
- `apps/web/src/features/charts/chart-cursor-zone.tsx`
- `apps/web/src/index.css`
- `docs/RESPONSIVE_PREMISES.md` (nuevo)
- `docs/CHART_RESPONSIVE.md` (actualizado)

## Recuperar estado anterior

Usar el historial de git de los archivos listados o este snapshot como guía del diseño previo.
