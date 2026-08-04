# Panel Operativa Trading — layout, IO y Estudio (2026-08-04)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) → Product / Ops  
> **Ayuda:** [HELP.md](../HELP.md) · menú in-app «Trading y gráficos»  
> **Freeze:** Belief→Coach Fase 2/5c · `CORE_R_CRON` · `COST_MODEL_V2` · Camino D AUTO · Strategy Studio / F5  
> **Update 2026-08-04b:** Estudio = membresía explícita (no ≡ pestañas); selección masiva; gate SEMI/AUTO.

## Qué

Rediseño del rail Coach → panel **Operativa** en la mesa TRADING:

1. **Columna a altura completa** (hasta la barra de estado). Operaciones solo bajo watchlist + gráfico.
2. Tres secciones colapsables con scroll y altura redimensionable: **Recomendación** · **Info** · **Configuración**.
3. **Índice Operativo (IO) v1** en Recomendación (gauges TA / FA / IO + ranking «El n de N en Estudio»).
4. Lista virtual **Estudio** = universo operativo (membresía explícita; persistida en workspace).
5. Cabecera **Configuración** con summary derecha `Operativa: {mode}`; título del bloque = **nombre de la cuenta activa**.

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

## Estudio — membresía explícita

| Acción | Efecto |
|--------|--------|
| Abrir / enfocar gráfico | **Añade** a Estudio si faltaba |
| Cerrar pestaña | **No** saca de Estudio |
| Check membresía / «A Estudio» (bulk) | Añade o quita membresía |
| Ranking IO | Universo = IDs en `visualization-store` |
| Nombre UI | **Estudio** (id legacy `__builtin:visualization__`) |
- Preferencia: **Estudio** si el valor es miembro (universo operativo), para no saltar a catálogo (p. ej. IBEX) al cambiar de gráfico (`resolveValidSourceListIdForTab`).

Sync: `use-chart-visualization-sync.ts` solo **amplía** el store (nunca `replaceEntries` desde pestañas).

### Selección masiva (Valores)

- Check de cabecera alineado con filas; **Ctrl/Cmd** toggle · **Mayús** rango.
- Barra inferior del panel Valores (siempre visible al seleccionar): **Pasar a Estudio** · **Quitar de Estudio** · **Abrir gráficos** · Limpiar.

### Gate SEMI / AUTO

- `demoBookRequiresEstudioMembership(mode)` → true en SEMI y AUTO.
- Propose F3 (Finalistas / alarmas) falla si el instrumento no está en Estudio.
- **MANUAL** no exige Estudio.

## Índice Operativo (IO) v1

| Pieza | Regla |
|-------|--------|
| Base | Composite display 0–100 |
| Distress FA | Suelo IO ≤ 40 |
| Ranking | IO desc entre IDs en Estudio |
| Copy | `El {rank} de {total} en Estudio` |

Helpers: `operativa-index.ts` · UI: `operativa-pulse.tsx` · datos: `useInstrumentsHubScores(studyIds)`.

## Archivos clave

| Área | Path |
|------|------|
| Layout | `apps/web/src/components/layout/trading-layout.tsx` |
| Panel | `trading-operativa-panel.tsx`, `trading-operativa-section.tsx` |
| IO | `operativa-index.ts`, `operativa-pulse.tsx` |
| Prefs / gate | `demo-book-prefs.ts`, `use-demo-book-prefs.ts` |
| Sync Estudio | `lists-tab/use-chart-visualization-sync.ts` |
| Selección | `list-values-panel.tsx`, `list-column-header.tsx`, `list-item-accordion.tsx` |
| Label | `packages/shared/src/default-lists.ts` |

## Fuera de alcance

AUTO execute · Belief→Coach 5c · cambiar fórmula IO más allá de Composite+distress.

## Update 2026-08-04c — mesa SEMI vital

- Dictamen del valor activo con `positionOpen` real (portfolio).
- Banner «Fuera de Estudio» + Añadir cuando SEMI/AUTO lo exigen.
- CTAs **Proponer F3 → Confirm** y **Cola Confirm (n)** en Recomendación (Camino C).
- Chart IA propose reutiliza los mismos gates SEMI/Estudio/sizing (`propose-instrument-supervised.ts`).
- Camino D AUTO execute **sigue freeze**.
