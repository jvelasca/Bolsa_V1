# Responsive del entorno de gráficos y trading

Documentación de referencia para el comportamiento adaptativo del workspace de trading (jul 2026).  
Complementa [UI_PLATFORM.md](./UI_PLATFORM.md) y [ADR-004](./adr/004-prorealtime-ui-platform.md).

---

## Principio de diseño

### Container queries, no solo viewport

El gráfico puede quedar **estrecho en un monitor grande** (watchlist al 45 %, inspector abierto, panel de operaciones, etc.). Por eso la mayoría de reglas responsive del chart **no usan** `sm:` / `md:` del viewport.

| Enfoque | Cuándo se usa | Ejemplo |
|---------|---------------|---------|
| **Container query** `@container chart-workspace` | Barras del gráfico, inspector, etiquetas abreviadas de indicadores | Apilar barra en 2 filas cuando el **panel** &lt; 576 px |
| **Media query** `@media (max-width: 640px)` | Chrome global fuera del contenedor del gráfico | Barra de estado inferior (patrimonio, P&L…) |
| **Flex + `min-w-0` + scroll** | Siempre | Paneles acoplables, listas, pestañas de gráficos |

### Contenedor raíz

El elemento con clase `chart-workspace-shell` define el contenedor CSS:

```css
.chart-workspace-shell {
  container-type: inline-size;
  container-name: chart-workspace;
}
```

**Ubicación:** raíz de `ChartWorkspacePage` (`apps/web/src/features/charts/chart-workspace-page.tsx`).

Todo hijo puede usar selectores `@container chart-workspace (…)` en `apps/web/src/index.css`.

---

## Umbrales (breakpoints del panel)

Valores en **rem** (1 rem ≈ 16 px con fuente por defecto).

| Umbral | Ancho aprox. | Efecto |
|--------|--------------|--------|
| **28 rem** | 448 px | Etiquetas cortas («Ind.», «S/gráf.»); ocultar ↑↓ en paneles inferiores de indicadores; barra de dibujos más estrecha (2 rem) |
| **30 rem** | 480 px | Barra **global** pasa de 2 filas → 1 fila |
| **36 rem** | 576 px | Barra de datos: atajos en segunda rail si &lt; 48 rem |
| **32 rem** | 512 px | Barra de datos: zonas Escala/Estilo/Valor/Cursor al 100 % de ancho |
| **42 rem** | 672 px | Inspector: dock lateral fijo ↔ panel flotante con backdrop |

Para cambiar cuándo se apilan las barras, editar estos valores en `apps/web/src/index.css` (bloque «Responsive del workspace de gráficos»).

---

## Arquitectura de barras del gráfico

Hay **dos niveles** claramente separados (modelo tipo ProRealTime / plataformas profesionales):

```
┌─ Barra 1 · WORKSPACE (global) ─────────────────────────────────────────┐
│  Indicadores │ Plantillas │ C/V │ BD │ TV │ Inspector │ ⚙            │
│  → parámetros y acciones del entorno (todos los gráficos)              │
└────────────────────────────────────────────────────────────────────────┘
┌─ Barra 2 · GRÁFICO ACTIVO (por tab) ───────────────────────────────────┐
│  [🕐 Escala] │ [🕯 Estilo] │ [📐 Plantillas] │ [🏛 Valor] │ [⊕ Cursor]  │
│  → icono + chips + menú en icono; separadores solo ENTRE familias        │
└────────────────────────────────────────────────────────────────────────┘
```

Detalle del patrón: [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

| Barra | Alcance | Ejemplos |
|-------|---------|----------|
| **1 · Workspace** | Catálogo, plantillas, operativa, datos, inspector | Indicadores, C/V, sync BD, inspector |
| **2 · Gráfico activo** | Timeframe, estilo de barra, OHLC, cursor, overlays del tab | 1h, Velas, Valor, TradingView, Cursor |

Ambas usan el mismo patrón responsive: zonas con separadores verticales; si no caben, **flex-wrap** a la siguiente fila (`wrapRows`, por defecto `true`).

| Barra | Componente |
|-------|------------|
| Workspace | `chart-toolbar-global-bar.tsx` |
| Gráfico activo | `chart-toolbar-chart-bar.tsx` |

La gestión de indicadores superpuestos (SMA, volumen, etc.) está en la zona **«Sobre gráfico»** de la barra 2, no en una franja bajo el precio.

---

## Barra por gráfico — layout adaptable (`layout.wrapRows`)

**Nombre:** barra de **datos del gráfico** (Escala · Estilo · Plantillas · Valor · Cursor). Ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) y [RESPONSIVE_PREMISES.md](./RESPONSIVE_PREMISES.md).

### Estructura (modo adaptativo, `wrapRows: true`)

```
┌─ Panel ancho (≥ 48 rem) ─────────────────────────────────────────────┐
│  Escala │ Estilo │ Valor │ Cursor              [atajos inspector] │ ⚙   │
└──────────────────────────────────────────────────────────────────────┘

┌─ Panel medio (32–48 rem) ────────────────────────────────────────────┐
│  Escala │ Estilo │ Valor                                              │
│  Cursor                                                              │
│  ─────────────────────────────────────────────────────────────────  │
│                                    [atajos inspector] │ ⚙            │
└──────────────────────────────────────────────────────────────────────┘

┌─ Panel estrecho (&lt; 32 rem) ────────────────────────────────────────┐
│  Escala  (100 % ancho, chips con scroll interno)                     │
│  Estilo                                                              │
│  Valor                                                               │
│  Cursor                                                              │
│  ─────────────────────────────────────────────────────────────────  │
│                                    [atajos inspector] │ ⚙            │
└──────────────────────────────────────────────────────────────────────┘
```

A la **izquierda**: Escala, Estilo, Valor y Cursor (rail `chart-toolbar-chart-data`). A la **derecha**: atajos al inspector y ⚙ (`chart-toolbar-chart-actions`). Los umbrales usan **container queries** sobre `chart-workspace-shell`, no el viewport.

### Modo scroll (`wrapRows: false`)

Una fila con `overflow-x: auto` (`chart-toolbar--scroll`) en toda la barra.

### Regla importante

Los **chips dentro de cada zona** usan scroll horizontal (`chart-bar-zone-scroll`), **no** `flex-wrap`, para mantener la altura fija de `1.375rem`. El apilado en varias filas ocurre a nivel de **zonas**, no de chips.

### Configuración

| Ubicación | Campo |
|-----------|--------|
| ⚙ global → **Global** | `chartLayoutDefaults.wrapRows` |
| ⚙ del gráfico → **Este gráfico** | `toolbar.layout.wrapRows` |

Checkbox: «Apilar zonas en varias filas si no caben (sin scroll horizontal)».

---

## Barra global — layout

Usa el mismo `chartLayoutDefaults.wrapRows` del workspace. Todas las zonas (indicadores, C/V, BD, etc.) comparten **una sola fila lógica** con separadores `|`, igual que la barra del gráfico; solo pasan a la fila siguiente cuando el panel es estrecho.

```
[ Indicadores · Plantillas ] | [ C ] [ V ] | [ BD ] | [ Insp. ] | [ ⚙ ]
```

TradingView ya **no** está en esta barra — ver barra de datos del tab activo ([CHART_DATA_BAR.md](./CHART_DATA_BAR.md#enlace-tradingview)).

---

## Menús emergentes y capas z-index (jul 2026)

Desplegables de **Escala / Estilo / Plantillas / Valor / Cursor** y **flyouts de dibujos** comparten:

| Capa | z-index | Notas |
|------|---------|-------|
| Backdrop | 200 | `bg-black/10`, clic cierra |
| Separador precio↔indicadores | 30 | Desactivado (`pointer-events-none`) al dibujar |
| Rail / zona con menú abierto | 202 | Barra H: fila del picker; barra V: `aside` del sidebar |
| Panel menú | 203 | `CHART_ZONE_DROPDOWN_PANEL_CLASS` — **bg-card opaco** |
| Sidebar dibujos | 40 | Contenedor; evita solapamiento con stack del gráfico |

Detalle: [CHART_DATA_BAR.md](./CHART_DATA_BAR.md#menús-emergentes-modales), [CHART_DRAWING_TAXONOMY.md](./CHART_DRAWING_TAXONOMY.md#menú-flyout-familia).

---

## Separadores entre paneles de indicadores

`PanelResizeHandle` horizontal entre precio e indicadores (`chart-indicator-stack.tsx`).

- Zona de agarre invisible ±6 px (`before:-top-1.5 -bottom-1.5`).
- Con herramienta de **figura** o **regla** activa: `disabled` — no captura puntero ni muestra cursor `row-resize`.
- Implementación: `shouldDisablePanelResize(chartDrawTool)` leído desde `useUiStore`.

---

## Patrón de scroll en zonas (`chart-bar-zone-scroll`)

Cuando hay muchos favoritos (timeframes, campos OHLC, chips de overlay), el contenido **no empuja** el layout: se desplaza horizontalmente.

### Clases

| Clase | Uso |
|-------|-----|
| `chart-bar-zone-scroll` | Contenedor con `overflow-x: auto`, `min-width: 0` |
| `CHART_BAR_ZONE_SCROLL_ROW_CLASS` | Constante TS equivalente para filas de chips |

### Dónde está aplicado

- Favoritos de **Escala** (`chart-timeframe-bar.tsx`)
- Favoritos de **Estilo** (`chart-series-type-zone.tsx`)
- Favoritos de **Valor** y **Cursor** (`chart-bar-zone-picker.tsx`)
- Chips de **Sobre gráfico** (`chart-overlay-indicators-zone.tsx`)
- Barra global (indicadores y acciones)
- Fila 2 de la barra por gráfico en modo compacto

### Modelo a seguir al añadir zonas nuevas

Ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) — sección «Añadir una zona nueva». Resumen:

```tsx
<ChartBarZonePicker
  zoneIcon={Clock}
  zoneTitle="Escala"
  zoneHint="…"
  activeId={…}
  favorites={…}
  menuGroups={…}
  options={…}
  …
/>
```

Cada zona: icono con muesca + fila `CHART_BAR_ZONE_SCROLL_ROW_CLASS` de chips. Sin separadores entre chips de la misma familia.

---

## Etiquetas abreviadas (panel muy estrecho, &lt; 28 rem)

Pares de spans; CSS muestra uno u otro según el contenedor:

| Clase completa | Clase corta | Texto |
|----------------|-------------|-------|
| `chart-indicators-label-text` | `chart-indicators-label-short` | Indicadores → **Ind.** |
| `chart-overlay-zone-label-full` | `chart-overlay-zone-label-short` | Sobre gráfico → **S/gráf.** |

Los chips mantienen `truncate` y `max-width` (`chart-bar-zone-styles.ts`: hasta `11rem` en chips genéricos, `9rem` en overlays).

---

## Inspector de gráficos

Comportamiento según **ancho del panel del gráfico**, no del viewport.

| Ancho panel | Modo | Comportamiento |
|-------------|------|----------------|
| ≥ 42 rem | **Dock** | Columna fija `14rem` a la derecha del área chart; sin botón cerrar |
| &lt; 42 rem | **Flotante** | `position: absolute` sobre el gráfico; ancho `min(14rem, 88%)`; sombra |
| &lt; 42 rem + abierto | **Backdrop** | Capa semitransparente; clic cierra el inspector |

### Clases y props

- Panel: `chart-inspector-panel` + `is-open` cuando está visible
- Backdrop: `chart-inspector-backdrop is-open` (botón en `chart-workspace-page.tsx`)
- Cerrar flotante: botón con clase `chart-inspector-close` (solo visible en modo flotante)

| Archivo | Rol |
|---------|-----|
| `chart-inspector-panel.tsx` | UI del inspector; props `isOpen`, `onClose` |
| `chart-workspace-page.tsx` | Backdrop + panel siempre montado (visibilidad vía CSS) |

---

## Paneles inferiores de indicadores (RSI, MACD…)

### Divisor vertical precio / sub-paneles

Entre el gráfico de precio y la franja «Paneles inferiores» hay un **asa de redimensionado horizontal** (`PanelResizeHandle`).

| Campo | Rango | Default |
|-------|-------|---------|
| `ChartTabState.pricePanelHeightPct` | 25–85 % | 55 % |

- Arrastrar ajusta en vivo; al soltar se persiste en el workspace (`updateChartPricePanelHeight`).
- Componente: `chart-indicator-stack.tsx`.

### Chrome de cada panel

- Chrome: `indicator-panel-chrome.tsx`
- En panel &lt; 28 rem: botones **Subir/Bajar** ocultos (`.indicator-panel-move-btns`)
- Clic en el panel selecciona el indicador (zoom vertical en escala Y con pulsación + arrastre)

---

## Sincronización temporal (vinculación horizontal)

Todos los paneles de un tab comparten el mismo `chartSyncId` (= id del tab).

| Interacción | Comportamiento |
|-------------|----------------|
| Rueda sobre **área del gráfico de precio** (cuerpo, velas, volumen) | Zoom **horizontal** sincronizado (precio + todos los sub-paneles) |
| Botones +/- en barra Escala | Mismo zoom horizontal unificado |
| **Pulsar y arrastrar** en la **escala Y derecha** | Zoom **vertical** de ese panel (precio, volumen o sub-panel) |
| Rueda con **botón izquierdo pulsado** sobre la escala Y | Mismo zoom vertical que arrastrar |
| Botones lupa +/- en chrome del indicador | Mismo zoom vertical que la escala |

### Reglas de zoom (todas las capas iguales)

1. **Horizontal (rueda):** rueda en el cuerpo del gráfico de precio **o de un panel inferior** → `attachChartHorizontalWheel` (hub de sync).
2. **Arrastre (estilo XTB)** en el gráfico de precio o en un panel inferior con botón pulsado:
   - Movimiento **horizontal** → desplaza el tiempo en **todos** los paneles (precio + indicadores).
   - Movimiento **vertical** en el cuerpo del precio → desplaza solo el eje de precio.
   - Movimiento **vertical** en la escala derecha → zoom Y (precio o volumen / indicador).
3. **Vertical (escala):** rueda con botón pulsado en escala Y → zoom vertical (solo ese panel).
4. Los sub-paneles comparten el rango temporal vía `chart-time-sync.ts` (sync bidireccional).
5. El zoom vertical usa `scaleMargins` / `scaleZoom` persistido.

Ver también **[CHART_INDICATORS.md](./CHART_INDICATORS.md)**.

### Implementación

| Archivo | Rol |
|---------|-----|
| `chart-price-pan.ts` | Arrastre XTB: pan temporal / pan precio / zoom en escala |
| `chart-scale-wheel.ts` | Zoom en escala Y (rueda) + drag en sub-paneles |
| `chart-time-sync.ts` | Hub: zoom/pan horizontal sincronizado entre paneles |
| `chart-time-pan.ts` | Arrastre horizontal solo tiempo (sub-paneles) |
| `chart-stable-resize.ts` | `ResizeObserver` con debounce (anti-vibración) |
| `ohlcv-chart.tsx` | `handleScroll` horizontal; escala Y custom |
| `sub-indicator-panel.tsx` | Rueda/pan temporal + escala Y; serie ancla temporal |

### Anti-vibración (paneles múltiples)

- Reparto precio/indicadores con **CSS grid** (`Nfr auto Mfr`), no `%` ni flex con ratios dinámicos.
- `autoSize: false` en todos los charts LW; el resize actualiza el chart por **ref** sin `setState` en modo `fillContainer`.
- Un solo `observeStableSize` por contenedor (umbral 2 px, debounce 48 ms).
- Divisor en fila `auto` propia (sin márgenes negativos que invadan el volumen).
- `overflow-y: scroll` + `scrollbar-gutter: stable` en paneles inferiores.
- `contain: strict` en el panel de precio.
- `rightPriceScale.minimumWidth` (76 px) para evitar parpadeo de la escala al mover el crosshair.

---

## Resto del shell de trading

### Barra de estado (`trading-status-bar.tsx`)

- **Viewport** &lt; 640 px: etiquetas cortas (Pat., Disp., Ops., P&L…)
- Clases: `trading-status-label-full` / `trading-status-label-short`
- Footer con `overflow-x-auto` + `scroll-area`

### Badge de datos (`chart-data-status-badge.tsx`)

- Estados de sincronización/flash: texto corto en viewport `sm` (`Sync BD…`, `BD OK`)
- Popover BD: ancho `min(20rem, calc(100vw - 1rem))` para no salirse de pantalla

### Layout acoplable (`trading-layout.tsx`)

- Zona gráficos: `min-w-0 flex-1` (imprescindible para que el contenedor mida bien)
- Watchlist: `minWidth: min(240px, 40vw)` — en ventanas muy estrechas cede espacio al gráfico

### Zona de gráficos (`charts-zone.tsx`)

- Padding responsive: `p-1 sm:p-2`
- Pestañas inferiores: scroll horizontal existente (`max-w-[140px] truncate`)

### Panel operaciones (`operations-panel.tsx`)

- Pestañas con `overflow-x-auto` en cabecera

### Barra superior (`app-top-bar.tsx`)

- Ya usaba `hidden sm:inline` / `md:` / `lg:` para labels — **no** forma parte del contenedor `chart-workspace`; es responsive por viewport (correcto para chrome global).

---

## Mapa de archivos

```
apps/web/src/
├── index.css                          # ★ Reglas @container y utilidades responsive
├── components/layout/
│   ├── trading-layout.tsx             # min-w-0, watchlist flexible
│   └── platform-shell.tsx             # Shell h-screen
├── features/charts/
│   ├── chart-workspace-page.tsx       # ★ chart-workspace-shell
│   ├── chart-toolbar-global-bar.tsx   # ★ Barra global 1/2 filas
│   ├── chart-toolbar-chart-bar.tsx    # ★ Barra por gráfico 1/2 filas
│   ├── chart-bar-zone-styles.ts       # Tokens de zona
│   ├── chart-bar-zone-picker.tsx      # Scroll en favoritos
│   ├── chart-timeframe-bar.tsx
│   ├── chart-overlay-indicators-zone.tsx
│   ├── chart-inspector-panel.tsx      # Dock / flotante
│   ├── chart-time-sync.ts             # Sync temporal entre paneles
│   ├── chart-scale-wheel.ts           # attachChartScaleInteraction (escala Y)
│   ├── chart-stable-resize.ts         # ResizeObserver con debounce
│   └── indicator-panel-chrome.tsx     # Botones ↑↓ condicionales
└── features/trading/
    ├── charts-zone.tsx
    ├── trading-status-bar.tsx
    └── operations-panel.tsx
```

---

## Barra del gráfico e inspector (atajos)

La zona inline **«Sobre gráfico»** (chips con SMA, volumen, etc.) se **retiró de la barra** por defecto para ganar espacio al gráfico, sobre todo en pantallas estrechas.

En su lugar, la barra por gráfico incluye **iconos compactos** que abren el **inspector** en la pestaña adecuada:

| Icono | Destino en inspector |
|-------|----------------------|
| Regla | **Resumen** → sección «Gráfico» (escala / timeframe) |
| Etiqueta | **Resumen** → sección «Instrumento» |
| Capas (badge) | **Capas** → sección «Sobre gráfico» |
| Paneles (badge) | **Capas** → sección «Paneles inferiores» |
| Objetos (badge) | **Objetos** |
| Paleta | **Estilos** |

**Orden en barra:** izquierda — Escala → Estilo → Valor → Cursor; derecha — atajos al inspector → ⚙

### API de navegación

- `chart-inspector-nav.ts` — tipos `ChartInspectorNavigateInput`, `ChartInspectorTab`, `ChartInspectorLayerSection`, `ChartInspectorSummarySection`, `inspectorNavigateKey()`.
- `workspace-store.toggleChartInspectorShortcut(target)` — abre el inspector en el destino; si ya está abierto en el **mismo** atajo, lo **colapsa**.
- `workspace-store.openChartInspector(target)` — abre sin toggle (p. ej. desde otros puntos de la UI).
- `ui-store.chartInspectorNav` — petición consumida por `ChartInspectorPanel`.
- `ui-store.chartInspectorActiveShortcutKey` — atajo que abrió el inspector (para resaltar y toggle).

### Cerrar / colapsar inspector

- **Mismo icono de atajo otra vez** — colapsa el inspector si ya estaba abierto en ese destino.
- Botón **colapsar** (`PanelRightClose`) en la cabecera del inspector — visible en **todas** las anchuras (antes solo móvil).
- En panel estrecho: clic en el **backdrop** sigue cerrando el inspector.
- La barra global conserva el toggle **Inspector** para mostrar/ocultar el panel acoplado.

### Configuración de visibilidad

En ajustes de barra del gráfico, la opción `overlayIndicators` controla ahora los **atajos al inspector** (no la franja de chips antigua). Valor por defecto: **activado** (iconos visibles).

### Extender con nuevos atajos

1. Añadir `ChartInspectorShortcutButton` en `chart-toolbar-chart-bar.tsx`.
2. Llamar `toggleChartInspectorShortcut({ tab: '…' })`.
3. Si hace falta ancla de scroll, añadir `id` en la sección del inspector y opcional `layerSection` o `summarySection` en `chart-inspector-nav.ts`.

---

1. **Apilado barra por gráfico**  
   Estrechar solo el panel del gráfico → **Escala** + **Valor** + iconos de inspector + **Cursor** al final; sin franja «Sobre gráfico».

2. **Atajos inspector**  
   Clic en icono Capas → inspector abierto en pestaña Capas, sección «Sobre gráfico»; **mismo icono otra vez** o colapsar con ✕ en cabecera.

3. **Apilado barra global**  
   Con panel &lt; ~480 px → indicadores arriba, acciones abajo; ningún botón recortado sin scroll.

3. **Favoritos**  
   Añadir varios timeframes/campos favoritos → scroll horizontal en la zona, sin desbordar la ventana.

4. **Inspector**  
   Panel ancho: dock lateral + botón colapsar en cabecera. Panel estrecho: flotante + backdrop.

5. **Monitor grande, panel estrecho**  
   Verificar que **no** depende de redimensionar la ventana del navegador (container query).

6. **Móvil / ventana estrecha**  
   Barra de estado con abreviaturas; badge BD con textos cortos.

7. **Sub-paneles**  
   Con panel &lt; 448 px: sin botones ↑↓; título truncado; gráfico del indicador sigue visible.

---

## Cómo extender sin romper el responsive

1. **Nueva zona en la barra por gráfico**  
   - Añadir componente de zona y registrarlo en `chart-toolbar-chart-bar.tsx`  
   - Usar `CHART_BAR_ZONE_ROW_CLASS` + `CHART_BAR_ZONE_SCROLL_ROW_CLASS`  
   - No usar `shrink-0` en la fila completa de la zona

2. **Nuevo umbral**  
   - Añadir bloque `@container chart-workspace` en `index.css`  
   - Documentar el valor en la tabla de umbrales de este archivo

3. **Evitar**  
   - `overflow-hidden` en barras con contenido dinámico (recorta en silencio)  
   - `hidden sm:flex` para paneles del gráfico (usa container query o el patrón inspector)  
   - Filas con solo `shrink-0` sin `min-w-0` en padres flex

4. **Visibilidad en configuración**  
   - Flags en `ChartToolbarChartVisibility` (`packages/shared/src/chart-toolbar.ts`): `timeframe`, `instrumentZone`, `seriesZone`, `cursorZone`, `overlayIndicators`, etc.

---

## Relación con otras docs

| Documento | Relación |
|-----------|----------|
| [UI_PLATFORM.md](./UI_PLATFORM.md) | Shell trading, zonas acoplables, archivos clave |
| [adr/006-chart-platform-and-settings.md](./adr/006-chart-platform-and-settings.md) | Modelo de configuración global vs por gráfico |
| [adr/004-prorealtime-ui-platform.md](./adr/004-prorealtime-ui-platform.md) | Visión UI estilo terminal |

---

## Historial

| Fecha | Cambio |
|-------|--------|
| Jul 2026 | Container queries, inspector flotante, auditoría shell |
| Jul 2026 | Barra de datos: rails adaptativas 48/32 rem; chips con scroll interno; RESPONSIVE_PREMISES.md |
