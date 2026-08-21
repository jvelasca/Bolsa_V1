# Barra de datos del gráfico

Documentación del patrón **Escala · Estilo · Plantillas · Valor · TradingView · Cursor · (i) · IA** en la barra por pestaña (`chart-toolbar-chart-bar.tsx`). Diseño cerrado **jul 2026**, alineado con la barra vertical de dibujos.

Ver también: [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md) (layout adaptable), [CONFIGURATION_MODEL.md](./CONFIGURATION_MODEL.md) (⚙ por barra), [CHART_INDICATORS.md](./CHART_INDICATORS.md) (plantillas), [CHART_DRAWING_TAXONOMY.md](./CHART_DRAWING_TAXONOMY.md) (barra vertical — patrón espejo).

---

## Alcance

| Barra                           | Componente                     | Contenido                                                                                                 |
| ------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Workspace** (global)          | `chart-toolbar-global-bar.tsx` | Indicadores, C/V, sync BD, inspector, ⚙ global                                                            |
| **Datos del gráfico** (por tab) | `chart-toolbar-chart-bar.tsx`  | Escala, Estilo, Plantillas, Valor, **TradingView**, Cursor, **(i) ficha**, **IA F3**, atajos inspector, ⚙ |

Esta guía cubre solo la **barra de datos del gráfico**.

---

## Concepto: familias y separadores

Una **familia** (zona) agrupa todo lo relacionado con un mismo aspecto del gráfico activo:

```
┌─ Escala ──┐ │ ┌─ Estilo ─┐ │ ┌─ Valor ─┐ │ ┌─ Cursor ──┐ │ ┌─ (i) ─┐ │ ┌─ IA ─┐
│ 1D ▾ …    │ │ │ Velas ▾  │ │ │ símbolo │ │ │ O H L C Δ │ │ │ Info  │ │ │ F3   │
└───────────┘ │ └──────────┘ │ └─────────┘ │ └───────────┘ │ └───────┘ │ └──────┘
```

- **(i)** → mismo `InstrumentInfoDialog` que la lista (hechos / perfil / Nuestra BD).
- **IA** (`BrainCircuit`) → `proposeRecommendation` del valor activo → cola Supervisado F3 → Confirmar (`/confirm`) (`chart-instrument-ai-button.tsx`). No mezcla juicios en la ficha (i).

Reglas:

1. **Dentro de una familia** no hay separadores: timeframes (`1m`, `1h`, `1D`), estilos (`Velas`, `Línea`), campos OHLC, etc. van en **una sola fila** de chips.
2. **Entre familias** sí hay divisor vertical grueso (`CHART_TOOLBAR_SECTION_DIVIDER` en `chart-bar-zone-styles.ts`).
3. En el **menú desplegable** (muesca del icono) sí pueden existir líneas entre subgrupos (p. ej. minutos | horas | días en Escala) para orientar al elegir opciones.

---

## Patrón UI: icono + chips + menú único

Cada familia sigue el mismo contrato que la barra vertical de dibujos, adaptado a horizontal:

| Elemento               | Rol                                                                                     | Menú (muesca)                      |
| ---------------------- | --------------------------------------------------------------------------------------- | ---------------------------------- |
| **Icono de familia**   | Identifica la zona; en modo `select` muestra el **valor activo** (p. ej. `1D`, `Velas`) | **Sí** — menú completo y estrellas |
| **Chips de favoritos** | Acceso directo opcional (solo si los fijas con estrella)                                | **No**                             |
| **Controles inline**   | Solo en Escala: zoom − / + / ajustar a ventana                                          | **No**                             |

### Interacción

| Acción                                      | Efecto                                                                     |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| Clic en **icono** o **muesca**              | Abre/cierra menú con todas las opciones + estrellas                        |
| Clic en **opción** del menú (modo `select`) | Aplica valor; no requiere favorito previo                                  |
| Clic en **chip** (modo `select`)            | Aplica valor (solo chips fijados con estrella)                             |
| Clic en **chip** (modo `display`)           | Informativo (Valor, Cursor); no cambia selección                           |
| **Estrella** en menú                        | Añade/quita chip opcional en la barra                                      |
| Ancla bloqueada                             | Símbolo (Valor) y Cierre (Cursor) siempre en barra; estrella deshabilitada |

### Componentes

| Componente                        | Archivo                          | Uso                                               |
| --------------------------------- | -------------------------------- | ------------------------------------------------- |
| `ChartBarZonePicker`              | `chart-bar-zone-picker.tsx`      | Orquestador: icono, chips, menú portal, favoritos |
| `ChartBarZoneIconAnchor`          | `chart-bar-zone-rail-button.tsx` | Icono + muesca inferior derecha                   |
| `ChartBarZoneChipButton`          | `chart-bar-zone-rail-button.tsx` | Chip sin muesca                                   |
| `resolveBarZoneDisplayIds`        | `chart-bar-zone-rail-button.tsx` | Orden de chips; solo favoritos en modo `select`   |
| `CHART_ZONE_DROPDOWN_PANEL_CLASS` | `chart-bar-zone-styles.ts`       | Panel opaco compartido con barra vertical         |

Estilos compartidos: `chart-bar-zone-styles.ts` (`CHART_BAR_ZONE_ROW_CLASS`, altura fija `1.375rem`, scroll horizontal en chips).

### Barra mínima (jul 2026)

En zonas **select** (Escala, Estilo, Plantillas):

- **Default de favoritos:** `[]` — sin chips en barra al instalar.
- El **icono muestra el valor activo** como badge (`1D`, `Velas`, nombre corto de plantilla…) vía `ChartBarZoneIconAnchor.badgeLabel`.
- Elegir una opción en el menú **no requiere** marcarla con estrella antes.
- Los chips solo aparecen si el usuario fija accesos con **estrella** (opcionales).
- `resolveBarZoneDisplayIds(..., { includeActive: false })` en modo `select`; en modo `display` (Valor, Cursor) sigue incluyendo anclas.

En zonas **display** (Valor, Cursor) el comportamiento no cambia: ancla fija (`symbol`, `close`) + chips de campos favoritos.

### Enlace TradingView

| Aspecto         | Detalle                                                                                               |
| --------------- | ----------------------------------------------------------------------------------------------------- |
| **Ubicación**   | Barra de datos del gráfico activo, **después de Valor** y antes de Cursor                             |
| **Visibilidad** | `ChartToolbarChartVisibility.tradingView` (⚙ barra de datos, no barra global)                         |
| **Migración**   | `visibility.tradingView` legacy en barra global → `chartVisibilityDefaults.tradingView` al normalizar |
| **URL**         | `chart-trading-view-url.ts` → `BME:{símbolo}` (Yahoo sin `.MC`)                                       |
| **Props**       | `symbol`, `yahooSymbol` desde `chart-workspace-page.tsx`                                              |

Razonamiento: el enlace es del **instrumento del tab activo**, no del workspace entero.

### Menús emergentes modales

Todos los desplegables de familias (horizontal y vertical) comparten el mismo contrato desde **jul 2026**:

| Capa               | z-index | Clase / rol                                      |
| ------------------ | ------- | ------------------------------------------------ |
| Backdrop           | `200`   | `fixed inset-0 bg-black/10` — clic cierra        |
| Zona / rail activa | `202`   | `relative z-[202]` mientras el menú está abierto |
| Panel del menú     | `203`   | `CHART_ZONE_DROPDOWN_PANEL_CLASS`                |

**Panel opaco** (`CHART_ZONE_DROPDOWN_PANEL_CLASS`):

```ts
"rounded-lg border border-border bg-card text-foreground shadow-2xl ring-1 ring-black/20";
```

> **Importante:** no usar `bg-popover` — no está definido en el tema (`index.css`) y el menú queda transparente.

**Comportamiento:**

- Un solo menú abierto por picker / flyout (estado local).
- **Escape** cierra.
- Portal en `document.body` (`createPortal`).
- Reposicionamiento en `scroll` / `resize` (barra horizontal).
- Barra vertical de dibujos: rail lateral sigue clickable encima del backdrop para cambiar de familia sin cerrar a mano.

Implementación horizontal: `chart-bar-zone-picker.tsx`. Vertical: `DrawingToolFlyout` en `chart-drawing-sidebar.tsx`.

---

## Familias implementadas

| Familia        | Icono (Lucide)     | Componente                          | Modo      | Chips típicos                          |
| -------------- | ------------------ | ----------------------------------- | --------- | -------------------------------------- |
| **Escala**     | `Clock`            | `chart-timeframe-bar.tsx`           | `select`  | Icono `1D` + zoom; chips opcionales    |
| **Estilo**     | `ChartCandlestick` | `chart-series-type-zone.tsx`        | `select`  | Icono `Velas`; chips opcionales        |
| **Plantillas** | `LayoutTemplate`   | `chart-indicator-template-zone.tsx` | `select`  | Icono + nombre corto; chips opcionales |
| **Valor**      | `Landmark`         | `chart-instrument-zone.tsx`         | `display` | Símbolo (fijo), nombre, lista…         |
| **Cursor**     | `Crosshair`        | `chart-cursor-zone.tsx`             | `display` | O, H, L, C (C fijo), Δ, Vol            |

### Escala y zoom

Los controles **Alejar**, **Acercar** y **Ajustar a ventana** (`ZoomOut`, `ZoomIn`, `Maximize2`) forman parte de la familia Escala (`inlineTail` del picker), **sin** divisor interno. Disparan `requestChartZoom()` en `chart-utils.ts`.

Visibilidad independiente: `visibility.timeframe` (chips) y `visibility.timeframeZoom` (zoom) en `ChartToolbarChartVisibility`.

### Etiquetas abreviadas (shared)

| Dominio    | Campo                                  | Ejemplos                     |
| ---------- | -------------------------------------- | ---------------------------- |
| Timeframes | `shortLabel` en `chart-timeframes.ts`  | `1m`, `1h`, `1D`, `1W`, `1M` |
| Estilo     | `shortLabel` en `chart-series-type.ts` | `Velas`, `Línea`, `P&F`      |
| Valor      | `CHART_INSTRUMENT_FIELD_SHORT_LABELS`  | Sym, Nom, Lista…             |
| Cursor     | `CHART_CURSOR_FIELD_SHORT_LABELS`      | O, H, L, C, Δ, Vol           |

### Cursor — semántica OHLC

- Los valores O/H/L/C/Δ/Vol son de la **vela bajo el cursor** (timeframe activo del gráfico).
- Sin cursor sobre el gráfico: se muestra la **última vela** disponible.
- **Δ vela** = cierre − apertura de esa vela (no confundir con % intradía de listas/tablas).
- Chips con **ancho fijo** por campo para evitar parpadeo al mover el ratón (`CURSOR_FIELD_BUTTON_CLASS` en `chart-cursor-zone.tsx`).

### Plantillas

- Menú agrupa plantillas **builtin** vs **custom** (solo en desplegable).
- Plantilla vacía: no aplica; aviso efímero ~2,5 s en barra.
- Favoritos: `chartToolbarGlobal.indicatorTemplateFavorites`.

---

## Favoritos y persistencia

| Zona       | Campo workspace              | Default (shared)                           | Hook                                        |
| ---------- | ---------------------------- | ------------------------------------------ | ------------------------------------------- |
| Escala     | `timeframeFavorites`         | `[]` (barra mínima)                        | `use-chart-timeframe-favorites.ts`          |
| Estilo     | `seriesTypeFavorites`        | `[]`                                       | `use-chart-series-type-favorites.ts`        |
| Plantillas | `indicatorTemplateFavorites` | `[]`                                       | `use-chart-indicator-template-favorites.ts` |
| Valor      | `instrumentFieldFavorites`   | `DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES` | `use-chart-bar-zone-favorites.ts`           |
| Cursor     | `cursorFieldFavorites`       | `DEFAULT_CHART_CURSOR_FIELD_FAVORITES`     | `use-chart-bar-zone-favorites.ts`           |

Normalización y toggles: `packages/shared/src/chart-data-bar-zones.ts`, `chart-timeframes.ts`, `chart-series-type.ts`, `indicator-templates.ts`. Merge en `mergeChartToolbarGlobalConfig` (`chart-toolbar.ts`).

Regla común: en zonas **select** (Escala, Estilo, Plantillas) los favoritos son **opcionales** — lista vacía válida; el icono muestra el valor activo. En zonas **display** (Valor, Cursor), las anclas (`symbol`, `close`) siguen siempre visibles (`toggleBarZoneFavoriteList` no quita la ancla).

---

## Visibilidad y configuración

Flags en `ChartToolbarChartVisibility` (`packages/shared/src/chart-toolbar.ts`):

| Flag                            | Zona                                                            |
| ------------------------------- | --------------------------------------------------------------- |
| `timeframe`                     | Chips de Escala                                                 |
| `timeframeZoom`                 | Zoom en Escala                                                  |
| `seriesZone`                    | Estilo                                                          |
| `indicatorTemplateZone`         | Plantillas                                                      |
| `instrumentZone`                | Valor                                                           |
| `tradingView`                   | Enlace externo TradingView (tras Valor)                         |
| `cursorZone`                    | Cursor                                                          |
| `instrumentInfo`                | Botón (i) tras Cursor → ficha del valor                         |
| `instrumentAi`                  | Botón IA tras (i) → propose / Supervisado F3                    |
| `overlayIndicators`             | _(obsoleto)_ — usar `inspectorBarShortcutFavorites`             |
| `inspectorBarShortcutFavorites` | Atajos al inspector en barra (estrella en Config del inspector) |

### Atajos al inspector (favoritos)

Por defecto **ningún** icono de Capas/Objetos/Canvas aparece en la barra. En el inspector → **Config**, cada pestaña tiene **estrella** para fijar un acceso directo a la derecha de la barra (junto a ⚙ de configuración, que siempre permanece).

Persistencia: `chartToolbarGlobal.inspectorBarShortcutFavorites` (`layers`, `series`, `objects`, `styles`, `context`). Lista vacía `[]` es válida (barra sin atajos; el inspector sigue disponible).

⚙ de la barra de datos → `ChartDataBarSettingsDialog` / campos en `chart-toolbar-settings-fields.tsx`.

---

## Responsive

- Apilado por **zonas** (no por chips): `layout.wrapRows` — ver [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md).
- Chips: scroll horizontal (`chart-bar-zone-scroll`), altura fija.
- Separadores entre familias se mantienen al apilar; dentro de cada fila de zona no hay sub-separadores.

---

## Añadir una zona nueva

1. Definir opciones, grupos de menú y defaults en `@bolsa/shared` si aplica.
2. Crear `chart-*-zone.tsx` que use `ChartBarZonePicker` con `zoneIcon`, `zoneTitle`, `zoneHint`.
3. Registrar en `chart-toolbar-chart-bar.tsx` (`dataZones` + flag en `ChartToolbarChartVisibility`).
4. Persistir favoritos en `chartToolbarGlobal` + store si hace falta.
5. **No** poner muesca en chips; **no** separadores entre chips de la misma familia.
6. Usar `selectionMode: 'select' | 'display'` según aplique valor o solo muestre datos.

Ejemplo mínimo:

```tsx
<ChartBarZonePicker
  zoneIcon={MyIcon}
  zoneTitle="Mi zona"
  zoneHint="Tooltip largo"
  activeId={active}
  favorites={favorites}
  menuGroups={MENU_GROUPS}
  options={OPTIONS}
  isFavorite={isFavorite}
  onToggleFavorite={toggleFavorite}
  onSelectOption={onSelect}
  getButtonLabel={(id) => LABELS[id]}
/>
```

---

## Mapa de archivos

| Área                 | Ruta                                                                                              |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| Orquestador barra    | `apps/web/src/features/charts/chart-toolbar-chart-bar.tsx`                                        |
| Picker + icono/chips | `apps/web/src/features/charts/chart-bar-zone-picker.tsx`                                          |
| Botones              | `apps/web/src/features/charts/chart-bar-zone-rail-button.tsx`                                     |
| Estilos              | `apps/web/src/features/charts/chart-bar-zone-styles.ts`                                           |
| Escala               | `apps/web/src/features/charts/chart-timeframe-bar.tsx`                                            |
| Estilo               | `apps/web/src/features/charts/chart-series-type-zone.tsx`                                         |
| Plantillas           | `apps/web/src/features/charts/chart-indicator-template-zone.tsx`                                  |
| Valor                | `apps/web/src/features/charts/chart-instrument-zone.tsx`                                          |
| Cursor               | `apps/web/src/features/charts/chart-cursor-zone.tsx`                                              |
| TradingView          | `apps/web/src/features/charts/chart-trading-view-url.ts`, enlace en `chart-toolbar-chart-bar.tsx` |
| Timeframes           | `packages/shared/src/chart-timeframes.ts`                                                         |
| Tipos de serie       | `packages/shared/src/chart-series-type.ts`                                                        |
| Campos Valor/Cursor  | `packages/shared/src/chart-data-bar-zones.ts`                                                     |
| Toolbar config       | `packages/shared/src/chart-toolbar.ts`                                                            |

### Obsoleto

`chart-bar-zone-anchor.tsx` — **eliminado** (2026-07-31). Usar icono + muesca inferior en `ChartBarZoneIconAnchor`.

---

## Relación con la barra vertical de dibujos

| Aspecto          | Barra vertical (dibujos)          | Barra horizontal (datos)                     |
| ---------------- | --------------------------------- | -------------------------------------------- |
| Identificador    | Icono herramienta / grupo         | Icono familia (`Clock`, `ChartCandlestick`…) |
| Muesca           | Esquina inferior derecha          | Igual                                        |
| Accesos directos | Favoritos en rail                 | Chips en fila                                |
| Separadores      | Entre familias de herramientas    | Entre zonas Escala \| Estilo \| …            |
| Menú             | Flyout modal + estrellas          | Portal modal + estrellas                     |
| Fondo menú       | `CHART_ZONE_DROPDOWN_PANEL_CLASS` | Igual                                        |
| Backdrop         | `bg-black/10`                     | Igual                                        |

Misma filosofía: **un solo menú por familia**, favoritos opcionales como botones compactos, persistencia en `chartToolbarGlobal`. Detalle barra vertical: [CHART_DRAWING_TAXONOMY.md](./CHART_DRAWING_TAXONOMY.md).

---

## Changelog (jul 2026)

### 11 jul — sesión cierre barras

| Cambio                      | Descripción                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| TradingView en barra activa | Movido desde barra global; flag `tradingView` en `ChartToolbarChartVisibility`              |
| Barra mínima                | Favoritos `[]` por defecto (Escala, Estilo, Plantillas); badge de valor activo en icono     |
| Chips opcionales            | `resolveBarZoneDisplayIds` sin forzar activo en modo `select`; toggles permiten lista vacía |
| Menús modales H             | Backdrop `bg-black/10`, Escape, panel opaco `bg-card`                                       |
| Coherencia V/H              | `CHART_ZONE_DROPDOWN_PANEL_CLASS` compartida con barra de dibujos                           |

### 10 jul — rail unificado

| Cambio                   | Descripción                                                         |
| ------------------------ | ------------------------------------------------------------------- |
| Rail unificado           | `ChartBarZonePicker` para todas las zonas de datos                  |
| Iconos vs texto          | Etiquetas «Escala», «Estilo»… sustituidas por iconos con tooltip    |
| Menú solo en icono       | Chips sin muesca; favoritos solo desde menú del icono               |
| Sin separadores internos | Solo entre familias (zonas), no entre `1m`/`1D` ni minutos/horas    |
| Zoom en Escala           | − / + / ajustar en la misma familia, sin borde lateral              |
| Cursor estable           | Anchos fijos por chip OHLC/Δ/Vol                                    |
| Plantillas               | Migradas al mismo patrón que Escala/Estilo                          |
| Atajos inspector         | Solo favoritos (`inspectorBarShortcutFavorites`); ⚙ siempre visible |
| `shortLabel`             | Timeframes `1D`, `1W`, `1M`; defaults incluyen `1mo`                |
