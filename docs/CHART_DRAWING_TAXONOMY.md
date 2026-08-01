# Taxonomía de dibujos y herramientas (fase 0–2)

Documento de referencia (jul 2026). IDs técnicos estables para órdenes, estudios y reportes futuros.

## Principios

1. **`semanticId`** en cada dibujo persistido (`cursor.dot`, `line.trend`, …).
2. **Herramienta** (`ChartDrawTool`) ≠ **tipo persistido** (`ChartDrawing.type`).
3. **Favoritos** en workspace (`drawToolFavorites`) — acceso directo en barra; persistidos en `chartToolbarGlobal`.
4. **Controles globales** por pestaña: imán, ocultar capa, bloquear capa.

---

## Barra vertical de dibujos — UX (jul 2026)

### Interacción por botón

| Zona del botón | Acción |
|----------------|--------|
| **Icono principal** | Activa la herramienta (acción directa) |
| **Triángulo inferior derecho** | Abre menú de la familia (elegir herramienta, marcar/desmarcar favorito con estrella) |

**Regla:** el triángulo **solo aparece** si la familia tiene **más de una herramienta implementada** (`availableToolsInGroup > 1`). Familias con una sola opción (Fibonacci, Gann, texto, figuras, medida, tridente por ahora) → botón limpio, clic = activar.

### Bloques por familia

La barra se organiza en **bloques unificados** (una familia = un bloque), no en “extras arriba / grupos abajo”.

Cada familia muestra siempre:

1. **Slot principal** — icono de familia; muestra la **herramienta activa** abreviada (p. ej. `Lín`, `H`) cuando pertenece a esa familia.
2. **Slots extra** — solo herramientas marcadas con estrella (chips opcionales).

**Acotado visual** (clase `chart-drawing-family-group` en `index.css`):

- Si la familia tiene **2 o más slots** en barra (principal + extras) → contenedor con fondo suave, bordes laterales y **separadores gruesos** arriba y abajo.
- Si solo hay **1 slot** → botón suelto, sin caja (barra más limpia).

**Orden en barra:**

- Familias en orden canónico (`DRAWING_TOOL_GROUP_ORDER`: cursor → líneas → … → medida).
- Cursor fijado arriba; resto en zona con scroll.
- Dentro de cada familia: principal primero, extras en orden de la lista de favoritos.

### Favoritos — modelo de datos

Persistencia: `workspace.chartToolbarGlobal.drawToolFavorites` (`ChartDrawTool[]`).

| Concepto | Definición |
|----------|------------|
| **Favorito principal** | Primera herramienta de la familia en la lista ordenada (solo si hay favoritos) |
| **Favorito extra** | Cualquier otra favorita de la misma familia → slot adicional en barra |
| **Default** | `[]` — barra mínima (un botón por familia, sin chips extra) |
| **Inserción** | Al marcar estrella, la herramienta se inserta **junto a sus hermanos**, no al final |
| **Normalización** | `organizeDrawToolFavorites()` reordena por familia y catálogo al cargar/guardar |

Funciones clave (`packages/shared/src/chart-drawing-taxonomy.ts`):

- `organizeDrawToolFavorites` — orden canónico por familia
- `insertDrawToolFavorite` — insertar junto a la familia
- `toggleDrawToolFavoriteList` — añadir/quitar + reorganizar
- `primaryFavoriteForGroup` / `isExtraDrawToolFavorite`

Funciones de barra (`apps/web/src/features/charts/chart-drawing-tools.ts`):

- `drawingRailFamilyBlocks` — bloques `{ groupId, extraTools, slotCount, bracketed, showMenu }`
- `resolveGroupRailIconTool` / `resolveGroupRailActivateTool` — el slot principal **no duplica** un extra activo
- `isGroupRailToolActive` — solo un botón resaltado por familia

### Menú flyout (familia)

- Clic en fila = usar herramienta
- Estrella = añadir/quitar chip opcional en barra
- **Sin texto de ayuda** en cabecera (solo título de familia en mayúsculas)
- **Modal:** portal en `document.body`, backdrop `bg-black/10` (`z-[200]`), panel `z-[203]`
- **Escape** o clic en backdrop → cierra
- **Un solo flyout** abierto; abrir otro sustituye al anterior
- Rail lateral `z-[202]` mientras hay flyout → sigue clickable para cambiar familia
- Sidebar contenedor `z-40` para no quedar bajo el stack del gráfico

Panel visual: `CHART_ZONE_DROPDOWN_PANEL_CLASS` en `chart-bar-zone-styles.ts` (mismo que barra horizontal — fondo `bg-card` opaco).

### Etiquetas abreviadas en rail (`shortLabel`)

Mapa en `chart-drawing-tools.ts` (`DRAWING_TOOL_SHORT_LABELS`). El botón principal muestra icono + etiqueta cuando la herramienta activa pertenece a esa familia (p. ej. `Pin` / `Res` para pincel/resaltador).

### Dibujo continuo

Tras colocar una figura (línea, rectángulo, pincel, etc.), la **herramienta sigue activa** para repetir sin volver a seleccionarla. Implementación:

- `chart-workspace-page.tsx` → `handleDrawingAdded`
- Si `isShapeDrawTool(activeTool)`: no llama a `focusDrawing`; limpia selección (`setSelectedDrawingId(null)`)
- Si no (p. ej. navegación): `focusDrawing` → puntero + dibujo seleccionado

Comportamiento tipo TradingView. Para editar: activar **Puntero** o inspector → Objetos.

### Separadores precio / indicadores vs herramientas

Los `PanelResizeHandle` entre panel de precio e indicadores inferiores se **desactivan** mientras una herramienta de dibujo o la regla está activa (`shouldDisablePanelResize` en `chart-draw-tool-utils.ts` → `blocksChartPointerPan`).

Motivo: la zona de agarre amplia (`before:-top-1.5 -bottom-1.5`) interceptaba el cursor al mover el ratón hacia el flyout de herramientas.

Archivo: `chart-indicator-stack.tsx` + `panel-resize-handle.tsx` (`disabled` → `pointer-events-none`).

### Capas z-index (referencia)

| Elemento | z-index |
|----------|---------|
| Backdrop menús H/V | 200 |
| Separadores panel (activos) | 30 |
| Separadores panel (dibujo activo) | 10, sin pointer-events |
| Rail dibujos / zona barra abierta | 202 |
| Panel menú flyout / picker | 203 |
| Sidebar dibujos (contenedor) | 40 |

### Criterio unificado con barras horizontales

Misma **filosofía**, distinto widget:

| Barra | Patrón |
|-------|--------|
| **Vertical (dibujos)** | Icono + etiqueta activa; triángulo = menú; estrella = chip opcional |
| **Horizontal (Escala, Estilo, Plantillas…)** | Icono + valor activo; muesca = menú; estrella = chip opcional |

No se parte cada chip horizontal en “acción + esquina” — el espacio es demasiado reducido. Regla común: **menú solo si hay más de una opción**.

Ver también [CONFIGURATION_MODEL.md](./CONFIGURATION_MODEL.md) (favoritos estrella en barra de datos) y [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md).

### Tests

`apps/web/src/features/charts/chart-drawing-rail.test.ts` — favoritos, bloques familiares, activación de slots, inserción y normalización.

---

## Categorías de la barra vertical

| Grupo | ID | Estado fase 2 |
|-------|-----|----------------|
| Cursor | `cursor` | Puntero, cruz, punto, punto resaltado, flecha |
| Líneas | `lines` | 9 tipos implementados |
| Canales | `channels` | Paralelo, regresión; plano/disjunto próximamente |
| Tridentes | `pitchforks` | Tridente estándar (3 clics); variantes Schiff próximamente |
| Fibonacci | `fibonacci` | **Retroceso**, **extensión tendencia**, **zona temporal** (2 clics) |
| Gann | `gann` | **Abanico**, **cuadrícula 8×8**, **cuadrado 1×1** (2 clics); cuadrado fijo próximamente |
| Pinceles | `brushes` | Pincel y resaltador (trazo libre) |
| Flechas | `arrows` | Flecha en círculo, marcadores arriba/abajo |
| Figuras | `shapes` | Rectángulo |
| Texto | `text` | Etiqueta anclada en el gráfico |
| Medida | `measure` | Regla / cruce medidor |

---

## Fibonacci (`fibonacci`)

- Herramienta: `fibonacci` → tipo `fibonacci`
- Dos clics: extremo → extremo
- Niveles estándar: 0, 23.6 %, 38.2 %, 50 %, 61.8 %, 78.6 %, 100 % (`FIBONACCI_LEVELS`)
- `semanticId`: `fibonacci.retracement`
- Vista previa al dibujar muestra niveles (no una línea simple)

## Abanico Gann (`gann-fan`)

- Herramienta: `gann-fan` → tipo `gann-fan`
- Dos clics: origen → línea 1×1 de referencia
- Nueve rayos clásicos (1×8 … 8×1) respecto a la referencia
- `semanticId`: `gann.fan`

## Cuadrícula Gann (`gann-grid`)

- Herramienta: `gann-grid` → tipo `gann-grid`
- Dos clics: esquinas del área; rejilla 8×8 con relleno opcional
- `semanticId`: `gann.grid`

## Cuadrado Gann (`gann-square`)

- Herramienta: `gann-square` → tipo `gann-square`
- Dos clics: origen → esquina; el segundo punto se ajusta a cuadrado 1×1 en pantalla
- `semanticId`: `gann.square`

## Fibonacci extensión (`fib-trend-ext`)

- Dos clics como retroceso; niveles incluyen extensiones (127.2 %, 161.8 %, 261.8 %…)
- `semanticId`: `fibonacci.trend_extension`

## Fibonacci zona temporal (`fib-time-zone`)

- Dos clics: define periodo base; líneas verticales en multiplicadores Fibonacci (0, 1, 1, 2, 3, 5…)
- `semanticId`: `fibonacci.time_zone`

## Iconos de líneas (barra)

Cada herramienta de líneas tiene icono propio en catálogo (`Info`, `UnfoldHorizontal`, `Compass`, `ArrowRight`, etc.) para distinguir favoritos en barra.

## Barras horizontales — criterio unificado

Patrón **icono de familia + muesca + chips** documentado en [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

Resumen: solo el **icono** (`ChartBarZoneIconAnchor`) abre el menú de opciones y favoritos; los **chips** (`ChartBarZoneChipButton`) son acceso directo sin muesca. Orquestador: `ChartBarZonePicker`. Separadores **solo entre familias** (Escala | Estilo | …), no entre chips de la misma zona.

`chart-bar-zone-anchor.tsx` **eliminado** (2026-07-31); sustituido por `ChartBarZoneIconAnchor`.

## Punto resaltado (`dot-halo`)

Sustituye el concepto ambiguo de «demostración»: mismo uso que el punto, con **halo circular semitransparente** para mayor visibilidad.

- Herramienta: `dot-halo`
- Tipo: `dot-halo-marker`
- `semanticId`: `cursor.dot_halo`

## Canal con relleno (fase 2)

El canal paralelo admite `fillOpacity` (como el rectángulo). La plantilla «Zona» aplica relleno por defecto.

## Texto anclado (`text`)

- Herramienta: `text` → tipo `text-label`
- `semanticId`: `text.plain`
- Clic coloca etiqueta; se abre el editor para editar el texto.

## Tridente (`pitchfork`)

- Herramienta: `pitchfork` → tipo `pitchfork`
- Tres clics: extremos de la base → punto de la mediana
- `semanticId`: `pitchfork.standard`

## Pincel / resaltador

- Herramientas: `brush`, `highlighter` → tipo `brush-stroke`
- Trazo libre; el resaltador usa trazo ancho semitransparente.

## Edición de dibujos

- **Seleccionar** (`select`) o **Cruz** (`cross`): clic = seleccionar; doble clic = editor; arrastre de anclajes
- Herramienta activa y última por grupo persisten en sesión UI (`bolsa-chart-draw-tool-session`)
- Borrado individual y «Limpiar todos» sincronizan snapshots por pestaña/lista

---

## Archivos

| Área | Ruta |
|------|------|
| Taxonomía + favoritos | `packages/shared/src/chart-drawing-taxonomy.ts` |
| Tipos persistidos | `packages/shared/src/chart-drawings.ts` |
| Catálogo UI + bloques barra | `apps/web/src/features/charts/chart-drawing-tools.ts` |
| Barra vertical | `apps/web/src/features/charts/chart-drawing-sidebar.tsx` |
| Dibujo continuo | `apps/web/src/features/charts/chart-workspace-page.tsx` (`handleDrawingAdded`) |
| Utilidades herramienta | `apps/web/src/features/charts/chart-draw-tool-utils.ts` |
| Stack precio/indicadores | `apps/web/src/features/charts/chart-indicator-stack.tsx` |
| Separadores panel | `apps/web/src/components/layout/panel-resize-handle.tsx` |
| Estilos menú compartido | `apps/web/src/features/charts/chart-bar-zone-styles.ts` |
| Estilos agrupación familia | `apps/web/src/index.css` (`.chart-drawing-family-group`) |
| Render / interacción | `apps/web/src/features/charts/chart-drawings-layer.tsx` |
| Geometría / hit-test | `apps/web/src/features/charts/chart-drawing-utils.ts` |
| Hook favoritos | `apps/web/src/features/charts/use-draw-tool-favorites.ts` |
| Tests barra | `apps/web/src/features/charts/chart-drawing-rail.test.ts` |

## Controles globales

| Control | Ubicación | Campo |
|---------|-----------|--------|
| Imán OHLC | Barra vertical + inspector Estilos | `chart.cursor.mode` |
| Ocultar dibujos | Barra vertical | `charts[].drawingsLayerHidden` |
| Bloquear edición | Barra vertical | `charts[].drawingsLayerLocked` |

## Persistencia relacionada

| Dato | Ubicación |
|------|-----------|
| Favoritos herramientas dibujo | `chartToolbarGlobal.drawToolFavorites` |
| Último estilo por herramienta | `chartToolbarGlobal.lastDrawStyleByTool` |
| Panel estilo herramienta activa | `chart-draw-tool-style-bar.tsx` (edición antes de dibujar) |
| Herramienta activa / última por grupo | UI store persist `bolsa-chart-draw-tool-session` |
| Dibujos por pestaña | `workspace.charts[].drawings` + snapshots por lista |

Ver [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md).

---

## Changelog barra de dibujos (jul 2026)

### 11 jul — sesión cierre

| Cambio | Descripción |
|--------|-------------|
| Barra mínima | `drawToolFavorites: []` por defecto; badge `shortLabel` en botón familia |
| Flyout modal | Backdrop, Escape, portal, panel opaco compartido con barra H |
| Sin leyenda flyout | Eliminado texto «Clic = usar · …» |
| Dibujo continuo | Herramienta permanece activa tras colocar figura |
| Resize paneles | Desactivado durante herramientas de figura / regla |
| z-index sidebar | `z-40` + flyout `203` para no quedar bajo gráfico |

### 10 jul — bloques y estilos

| Cambio | Descripción |
|--------|-------------|
| Acción vs menú | Clic principal activa; triángulo abre configuración |
| Sin chevron mono-opción | Familias con 1 herramienta implementada |
| Bloques familiares | Principal + extras en un bloque; acotado visual si ≥2 slots |
| Favoritos ordenados | Inserción junto a hermanos; normalización al persistir |
| Sin duplicados | Un solo slot activo por familia; icono principal no repite extra |
| Gann | Abanico Gann implementado |
| Fib/Gann ext | Extensión Fib, zona temporal, cuadrícula y cuadrado Gann |
| Iconos líneas | Iconos distintos por herramienta en catálogo |
| Barras horizontales | Icono + muesca + chips (`ChartBarZonePicker`) — ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) |
| Memoria de estilo | `lastDrawStyleByTool` + panel lateral por herramienta; brush/highlighter separados |
| Estado jul 2026 | **Barra de dibujos cerrada** (favoritos, familias, estilos, Fib/Gann, barras H) |

### Memoria de estilo por herramienta

Al activar una herramienta de dibujo (p. ej. resaltador, línea, canal), el panel **Estilo herramienta** muestra el último color/grosor/opacidad usado. Los cambios se persisten en `chartToolbarGlobal.lastDrawStyleByTool` y se aplican a:

- Vista previa al dibujar (borradores en el gráfico)
- Nuevos objetos colocados
- Cursor de marcadores (cruz, punto, flecha)

`brush` y `highlighter` mantienen memoria **independiente** (mismo tipo `brush-stroke` en disco, distinto tool en UI).

Implementación: `packages/shared/src/chart-draw-style-memory.ts`, `chart-draw-tool-style-bar.tsx`, `resolveDrawToolStyle()` en la capa de dibujos.
