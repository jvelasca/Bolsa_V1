# Panel Operativa Trading — layout, IO y En estudio (2026-08-04)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) → Product / Ops  
> **Ayuda:** [HELP.md](../HELP.md) · menú in-app «Trading y gráficos»  
> **Freeze:** Belief→Coach Fase 2/5c · `CORE_R_CRON` · `COST_MODEL_V2` · Camino D AUTO · Strategy Studio / F5

## Qué

Rediseño del rail Coach → panel **Operativa** en la mesa TRADING:

1. **Columna a altura completa** (hasta la barra de estado). Operaciones solo bajo watchlist + gráfico.
2. Tres secciones colapsables con scroll y altura redimensionable: **Recomendación** · **Info** · **Configuración**.
3. **Índice Operativo (IO) v1** en Recomendación (gauges TA / FA / IO + ranking «El n de N en estudio»).
4. Lista virtual **En estudio** = conjunto de pestañas de gráfico abiertas (misma identidad).
5. Resumen cabecera **Configuración** a la derecha: `Operativa: manual|semi|auto`; título del bloque = **nombre de la cuenta activa**.

## Layout

```text
┌ Watchlist │ Gráfico ─┐┌ Operativa (full height) ┐
├ Operaciones ─────────┤│ Recomendación / Info /  │
└──────────────────────┘│ Configuración           │
                        └─────────────────────────┘
TradingStatusBar (fuera de TradingLayout)
```

- Store: `bolsa-trading-layout-v1` (`operativaOpen`, `operativaWidthPct`, `operativaSections`, `operativaSectionHeights`, …).
- Código: `trading-layout.tsx`, `trading-layout-store.ts`.

## En estudio ≡ pestañas

| Acción | Efecto |
|--------|--------|
| Abrir pestaña de gráfico | Entra en lista **En estudio** |
| Cerrar pestaña | Sale de **En estudio** |
| Ranking IO | Universo = IDs únicos de pestañas abiertas |

Sync: `use-chart-visualization-sync.ts` → `visualization-store` · label `VIRTUAL_LIST_VISUALIZATION` = «En estudio» (`default-lists.ts`).

## Índice Operativo (IO) v1

| Pieza | Regla |
|-------|--------|
| Base | Composite display 0–100 (`technicalDisplay100` / composite chip) |
| Distress FA | Suelo IO ≤ 40 |
| Ranking | IO desc entre IDs en estudio; empate por `instrumentId` |
| Copy | `El {rank} de {total} en estudio` |

Helpers puros: `operativa-index.ts` (+ tests). UI: `operativa-pulse.tsx`. Datos: `useInstrumentsHubScores(studyIds)`.

## Configuración / modos

| UI | Detalle |
|----|---------|
| Cabecera sección | summary derecha: `Operativa: {mode}` |
| Título bloque | Nombre cuenta activa (`useActiveAccount`) |
| Prefs | `bolsa-demo-book-prefs-v1` · `useDemoBookPrefs` (reactivo misma pestaña) |
| Modos | MANUAL / SEMI / AUTO (AUTO UI disabled — freeze Camino D) |

Docs producto modos: [demo-operating-modes-brief-2026-08-03.md](./demo-operating-modes-brief-2026-08-03.md) · [semi-demo-book-impl-slice1-2026-08-03.md](./semi-demo-book-impl-slice1-2026-08-03.md).

## Archivos clave

| Área | Path |
|------|------|
| Layout | `apps/web/src/components/layout/trading-layout.tsx` |
| Panel | `trading-operativa-panel.tsx`, `trading-operativa-section.tsx` |
| IO | `operativa-index.ts`, `operativa-pulse.tsx` |
| Prefs libro | `demo-book-prefs.ts`, `use-demo-book-prefs.ts`, `demo-book-mode-panel.tsx` |
| Sync estudio | `lists-tab/use-chart-visualization-sync.ts` |
| TOP#1 gráfico | [chart-top1-indicator-switch-2026-08-03.md](./chart-top1-indicator-switch-2026-08-03.md) (misma rama) |

## Fuera de alcance

AUTO execute · Belief→Coach 5c · cambiar fórmula IO más allá de Composite+distress · persistir «en estudio» sin pestaña.
