# Indicadores en el gráfico

Documentación de indicadores técnicos en Bolsa V1: paneles, datos y **sincronización temporal** con el precio.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│  OhlcvChart (main)          chartSyncId = chartTab.id       │
│  · Velas / línea / área                                     │
│  · Volumen (histograma)                                     │
│  · Indicadores «sobre gráfico» (SMA, Bollinger, …)          │
│  · Dibujos                                                  │
├─────────────────────────────────────────────────────────────┤
│  ChartIndicatorStack                                        │
│  └─ SubIndicatorPanel × N (RSI, MACD, ATR, …)               │
└─────────────────────────────────────────────────────────────┘
```

| Capa | Componente | Panel |
|------|------------|-------|
| Precio + overlays | `ohlcv-chart.tsx` | Principal |
| Sub-paneles | `sub-indicator-panel.tsx` | Inferior (scroll) |
| Orquestación | `chart-indicator-stack.tsx` | Grid precio / indicadores |
| Cómputo series | `indicator-compute.ts` | — |
| Catálogo UI | `indicators-catalog-dialog.tsx` | Modal |

## Coherencia temporal (requisito)

**Todos los indicadores comparten el mismo rango temporal visible que el precio.** Si haces zoom o pan horizontal en cualquier panel, el resto debe moverse al unísono.

### Grupo de sincronización

Cada pestaña de gráfico usa `chartSyncId` (= `chartTab.id`). Todos los paneles del mismo gráfico se registran en un `ChartSyncHub` (`chart-time-sync.ts`).

| Pane | `id` | `kind` |
|------|------|--------|
| Precio | `main` | `main` |
| RSI, MACD, … | `instance.instanceId` | `sub` |

### Interacciones sincronizadas

| Acción | Dónde | Efecto |
|--------|-------|--------|
| Rueda (zoom horizontal) | Precio o panel indicador | Acerca/aleja tiempo en **todos** los paneles, **anclado al cursor** |
| Crosshair | Precio ↔ sub-paneles | Misma barra temporal (`setCrosshairPosition`) |
| Arrastre horizontal (botón pulsado) | Precio o panel indicador | Desplaza tiempo en todos |
| Botones +/- zoom barra | `chart-timeframe-bar.tsx` | Mismo hub (`CHART_ZOOM_EVENT`; centro del rango) |
| `fitContent` tras cargar datos | Solo main | `broadcastFrom('main')` actualiza sub-paneles |

El zoom **vertical** (eje Y precio o escala del indicador) es **independiente** por panel.

### Alineación de datos

- Barras OHLCV e indicadores usan `barTimeToChartTime()` (`chart-utils.ts`) para las mismas claves temporales.
- Sub-paneles incluyen una **serie ancla** invisible con todos los timestamps de las velas, para que lightweight-charts comparta el mismo dominio temporal.
- Tras actualizar series, se llama `broadcastFrom('main')` para alinear el rango visible.

### Archivos clave

| Archivo | Rol |
|---------|-----|
| `chart-time-sync.ts` | Hub: rango lógico, zoom/pan, **crosshair sync**, zoom anclado |
| `chart-time-pan.ts` | Arrastre horizontal solo tiempo (sub-paneles) |
| `chart-price-pan.ts` | Pan precio: tiempo + eje Y + zoom escala |
| `ohlcv-chart.tsx` | Registro `main`, rueda, pan |
| `sub-indicator-panel.tsx` | Registro sub, rueda, pan, serie ancla |

## Indicadores sobre el gráfico vs paneles inferiores

| Ubicación | `panel` en definición | Render |
|-----------|----------------------|--------|
| Sobre precio | `overlay` | Series en `ohlcv-chart` (mismo timeScale) |
| Panel inferior | `sub` | `SubIndicatorPanel` propio |

Los overlays **no necesitan sync hub** para el tiempo: comparten el gráfico principal.

### Paneles inferiores — reparto vertical

Los indicadores con `panel: 'sub'` (RSI, MACD, ATR…) se apilan bajo el precio en `chart-indicator-stack.tsx`.

| Comportamiento | Detalle |
|----------------|---------|
| Primer sub-panel | Ocupa todo el espacio bajo el precio (menos la franja «Paneles inferiores») |
| Varios sub-paneles | Reparten altura según `subPanelWeight` (por defecto partes iguales) |
| Redimensionar | Asa horizontal entre paneles visibles adyacentes |
| Panel oculto | Solo barra de título (~28 px); no participa en el reparto |
| Persistencia | `instance.subPanelWeight`; reequilibrio al añadir / quitar / mostrar |
| Poco espacio vertical | Scroll vertical en la zona de indicadores; cada panel conserva altura mínima legible |

Helpers: `packages/shared/src/sub-panel-layout.ts`.

## Persistencia (resumen)

| Dato | Campo | Ámbito |
|------|-------|--------|
| Instancias en el gráfico | `charts[].indicatorInstances` | Por pestaña |
| Preset de cada instancia | `instance.presetId` | Por instancia |
| Reparto vertical sub-paneles | `instance.subPanelWeight` | Por instancia |
| Alto precio vs inferiores | `charts[].pricePanelHeightPct` | Por pestaña |
| Plantilla activa | `charts[].activeIndicatorTemplateId` | Por pestaña |
| Catálogo de presets | `workspace.indicatorPresets` | Workspace |
| Catálogo de plantillas | `workspace.indicatorTemplates` | Workspace |
| Plantilla por defecto (gráficos nuevos) | `workspace.defaultIndicatorTemplateId` | Workspace |
| Herencia al abrir valor nuevo | `preferences.newChartTemplateChartId` | Workspace |
| Favoritos de barra (plantillas) | `chartToolbarGlobal.indicatorTemplateFavorites` | Workspace |
| Visibilidad zona plantillas | `chartVisibilityDefaults.indicatorTemplateZone` | Workspace / override tab |

Detalle en [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md).

### Plantilla para gráficos nuevos (icono junto a Indicadores)

Activa el icono **plantilla** (`LayoutTemplate`) en el gráfico que quieras usar como referencia. Mientras esté activo en ese gráfico:

- Los valores nuevos copian **en vivo** indicadores, barra de datos, estilo, timeframe, sub-paneles, etc. (sin dibujos).
- Si cambias la config del gráfico plantilla, los siguientes valores nuevos ya llevan esos cambios.

Desactiva el icono (segundo clic) para que los gráficos nuevos usen los **defaults del workspace** (timeframe/serie globales + `defaultIndicatorTemplateId` si existe).

Al **cerrar** la pestaña plantilla, el anclaje se quita automáticamente.

| Campo | Uso |
|-------|-----|
| `preferences.newChartTemplateChartId` | Id de la pestaña plantilla; `null` = defaults |

---

## Presets, plantillas y catálogo

Documentación operativa completa del sistema de indicadores guardados (jul 2026).

### Terminología

| Término UI | Tipo en código | Qué es |
|------------|----------------|--------|
| Indicador (motor) | `IndicatorDefinition` | Tipo técnico (`sma`, `rsi`…). Código fijo, no editable por el usuario. |
| Preset / variante | `IndicatorPreset` | Configuración guardada: parámetros + nombre + color/grosor. Vive en el catálogo del workspace. |
| Plantilla | `IndicatorTemplate` | Conjunto ordenado de `presetIds` que se aplica de golpe a un gráfico. Antes «grupo». |
| Instancia | `ChartIndicatorInstance` | Preset (o spec suelto) **montado** en una pestaña de gráfico. Tiene `instanceId` y `visible`. |

**Regla clave:** editar un preset en el catálogo actualiza todas las instancias del gráfico que comparten su `presetId`. Aplicar una plantilla **sustituye** la lista completa de instancias de esa pestaña.

### Modelo de tres capas

```
IndicatorDefinition (motor)
        │
        ▼
IndicatorPreset (variante guardada: SMA 35 azul)
        │
        ▼
IndicatorTemplate (plantilla: Swing = [vol, sma50, rsi])
        │
        ▼ applyIndicatorTemplate
ChartIndicatorInstance[] (lo que renderiza el gráfico)
```

### Semillas de sistema

**Presets** (`packages/shared/src/indicator-presets.ts`):

- Un preset por cada indicador builtin + variantes (p. ej. SMA 50).
- `source: 'builtin'`, `locked: true` → no borrables; se pueden **fork** a personal.

**Plantillas** (`packages/shared/src/indicator-templates.ts`):

| id | Nombre | Contenido |
|----|--------|-----------|
| `builtin-swing` | Swing | Volumen, SMA 50, RSI 14 |
| `builtin-day` | Intradía | Volumen, EMA 20, RSI 14 |
| `builtin-personal` | Personal | Vacía (locked); receptáculo de presets propios |

### Superficies de la UI

```
┌─────────────────────────────────────────────────────────────────┐
│ BARRA GLOBAL (workspace)                                        │
│  [Indicadores] → abre catálogo matricial (presets + plantillas) │
├─────────────────────────────────────────────────────────────────┤
│ BARRA DEL GRÁFICO (por pestaña)                                 │
│  Escala │ Estilo │ [📐] Swing Intradía [Swing▾] │ Valor │ Cursor │
│                      ↑ zona Plantillas                          │
├─────────────────────────────────────────────────────────────────┤
│ GRÁFICO + paneles inferiores + inspector                        │
│  Doble clic → config instancia                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Superficie | Archivo | Función |
|------------|---------|---------|
| Botón Indicadores | `chart-indicators-bar.tsx` | Abre catálogo; badge = nº instancias |
| Zona Plantillas | `chart-indicator-template-zone.tsx` | Aplicar / reaplicar plantillas; favoritos de barra |
| Catálogo | `indicators-catalog-dialog.tsx` | Matriz presets×plantillas; CRUD presets/plantillas |
| Editor preset | `indicator-preset-editor-panel.tsx` | Edición de presets personales |
| Config instancia | `indicator-instance-config-dialog.tsx` | Params, estilo, gestión (ocultar, duplicar, orden, eliminar) |

La visibilidad de la zona Plantillas se configura en **Barra de datos → ⚙** (`indicatorTemplateZone`). El botón Indicadores, en **Barra global → ⚙** (`visibility.indicators`).

---

### Catálogo matricial

Modal único para presets y plantillas. Filas = **presets**; columnas = **plantillas**.

#### Columnas fijas (izquierda)

| Col | Significado | Acción |
|-----|-------------|--------|
| ★ | Preset en el gráfico activo | Clic = añadir / quitar instancia (toggle) |
| 👁 | Visible en gráfico | Solo si ★ activo; toggle `visible` |
| Indicador | Nombre, origen, soporte API | Clic en engranaje → config si está en gráfico |
| Panel | `overlay` / `sub` | Informativo |
| Origen | Sistema / Personal / IA | Filtro arriba |
| Datos | Si el backend calcula la serie | Informativo |

#### Cabecera de cada plantilla (columna)

| Control | Acción |
|---------|--------|
| ▶ | Aplicar plantilla al gráfico (**sin confirmación**; sustituye instancias) |
| ★ | Favorito de barra (mismo estado que estrella en menú ▾ de la zona Plantillas) |
| 📌 | Marcar como plantilla por defecto en gráficos nuevos (`defaultIndicatorTemplateId`) |
| ✏ / 🗑 | Renombrar / eliminar (solo plantillas no `locked`) |

#### Celda matriz (preset × plantilla)

Clic = toggle pertenencia del preset a esa plantilla (`togglePresetInTemplate`).

#### Filtros

- **Sistema / IA** — filtra filas por `preset.source`.
- **Personal** — filtra por membresía en la plantilla `builtin-personal` (columna Personal de la matriz), no solo por `source: custom`.
- **Solo en gráfico** — solo presets con instancia en la pestaña activa.

#### Otras acciones del catálogo

| Acción | Dónde |
|--------|-------|
| Fork preset sistema → personal | Icono copiar en fila |
| Editar preset personal | Panel lateral |
| Crear plantilla vacía | Botón «Nueva plantilla» |
| Guardar gráfico como plantilla | Botón «Desde gráfico» |
| Eliminar preset personal | Icono papelera (no en sistema) |

**Plantillas vacías:** no se aplican (ni ▶ ni zona Plantillas). El catálogo muestra mensaje en panel; la barra muestra aviso efímero ~2,5 s.

---

### Zona Plantillas (barra del gráfico)

Componente: `ChartIndicatorTemplateZone`. Mismo patrón que el resto de familias — ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

```
[📐]  [Swing]  [Intradía]     ← icono con muesca + chips favoritos
 muesca
```

| Elemento | Comportamiento |
|----------|----------------|
| Icono `LayoutTemplate` + muesca | Menú de todas las plantillas; estrella = favorito en barra |
| Chips favoritos | Clic → `applyIndicatorTemplate` inmediato |
| Plantilla activa | Resaltada en menú; visible en el icono (nombre corto) |
| Plantilla vacía | No aplica; mensaje efímero ~2,5 s en barra |

**Favoritos de barra** (`chartToolbarGlobal.indicatorTemplateFavorites`):

- Default en workspaces nuevos: `[]` (sin chips; icono muestra plantilla activa).
- Se gestionan con estrella en menú ▾ o en cabecera del catálogo.
- **Son quitables** (incluso Swing e Intradía): lista vacía `[]` es válida y persistente.
- El chip ancla no se duplica en favoritos (se excluye del listado de chips).

Hook: `use-chart-indicator-template-favorites.ts` → `toggleIndicatorTemplateFavorite` en workspace store.

Documentación completa del patrón de barra: [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

---

### Aplicar plantilla vs. toggle preset

| Operación | Efecto en `indicatorInstances` | `activeIndicatorTemplateId` |
|-----------|--------------------------------|---------------------------|
| ★ preset en catálogo | Añade o quita **una** instancia | Se pone a `null` (gráfico «suelto») |
| ▶ plantilla / zona Plantillas | **Reemplaza** toda la lista | Se guarda el id de plantilla |
| Editar instancia suelta | Solo esa instancia | Sin cambio (sigue `null` o plantilla previa*) |
| Gráfico nuevo con default | Lista desde plantilla default | Id de plantilla default |

\*Tras aplicar plantilla, los cambios puntuales en instancias no actualizan la plantilla hasta «Guardar gráfico como plantilla».

Flujo interno de `applyIndicatorTemplate`:

1. Resolver `IndicatorTemplate` por id.
2. Abortar si `!templateHasIndicators(template)`.
3. `instancesFromTemplate(template, indicatorPresets)` → `ChartIndicatorInstance[]`.
4. Sustituir `charts[].indicatorInstances` y fijar `activeIndicatorTemplateId`.

---

### Configuración de instancia (doble clic)

| Zona | Acción |
|------|--------|
| Barra de título del panel inferior | Doble clic → diálogo |
| Área del gráfico del panel inferior | Doble clic → diálogo |
| Chip «Sobre gráfico» en la barra | Doble clic → config overlay |
| Línea overlay sobre precio (~10 px) | Doble clic → config |

Diálogo (`indicator-instance-config-dialog.tsx`):

- **Parámetros** y **Estilo** (color, grosor).
- **Gestión:** ocultar, duplicar, subir/bajar (sub-paneles), eliminar.
- **Guardar como personal:** fork del preset vinculado; opción de reemplazar instancia.

Archivos: `indicator-panel-chrome.tsx`, `sub-indicator-panel.tsx`, `chart-overlay-indicators-zone.tsx`, `chart-indicator-hit.ts`, `ohlcv-chart.tsx`.

---

### API del workspace store

| Método | Descripción |
|--------|-------------|
| `togglePresetOnChart` | ★ catálogo: añade/quita instancia por `presetId` |
| `togglePresetVisibilityOnChart` | 👁 catálogo |
| `togglePresetInTemplate` | Celda matriz preset↔plantilla |
| `applyIndicatorTemplate` | Sustituye instancias; fija plantilla activa |
| `setDefaultIndicatorTemplate` | 📌 plantilla por defecto |
| `forkPresetToPersonal` | Copia preset sistema → personal |
| `updateIndicatorPreset` | Edita personal; sync instancias con mismo `presetId` |
| `removeIndicatorPreset` | Borra personal |
| `duplicateUserIndicatorPreset` | Duplica personal |
| `addIndicatorTemplate` / `updateIndicatorTemplate` / `removeIndicatorTemplate` | CRUD plantillas |
| `createIndicatorTemplateFromChart` | Snapshot de instancias actuales → nueva plantilla |
| `duplicateIndicatorTemplate` | Copia plantilla |
| `toggleIndicatorTemplateFavorite` | Estrella favorito de barra |
| `addIndicatorInstance` / `updateIndicatorInstance` / `removeIndicatorInstance` | Instancias sueltas (inspector, etc.) |

---

### Archivos clave (presets / plantillas)

| Área | Ruta |
|------|------|
| Tipos y semillas presets | `packages/shared/src/indicator-presets.ts` |
| Tipos y semillas plantillas | `packages/shared/src/indicator-templates.ts` |
| Runtime / normalización | `packages/shared/src/indicators-runtime.ts` |
| Toolbar / favoritos / visibilidad | `packages/shared/src/chart-toolbar.ts` |
| Catálogo | `apps/web/src/features/charts/indicators-catalog-dialog.tsx` |
| Zona barra plantillas | `apps/web/src/features/charts/chart-indicator-template-zone.tsx` |
| Favoritos hook | `apps/web/src/features/charts/use-chart-indicator-template-favorites.ts` |
| Store | `apps/web/src/stores/workspace-store.ts` |

---

### Migración y compatibilidad

| Legado | Comportamiento actual |
|--------|----------------------|
| `IndicatorTemplate.items[]` | Se migra a `presetIds` al normalizar; `instancesFromTemplate` soporta ambos |
| `indicatorGroupZone` en visibilidad | Lee como `indicatorTemplateZone` |
| `visibility.indicatorTemplates` en barra global | Obsoleto para UI; solo queda botón **Indicadores** |
| Workspaces sin `indicatorTemplateFavorites` | Semilla Swing + Intradía |
| `indicatorTemplateFavorites: []` | Lista vacía respetada (sin re-sembrar defaults) |

---

## Catálogo unificado (`IND-*`) — estrategia

No copiamos ProRealTime (>100) ni nos limitamos a XTB (~39). Mantenemos **un universo canónico** en:

`packages/shared/src/indicator-universe.ts`

Separación (ML-style) y **dirección de dependencias**:

```text
IndicatorUniverse (IND-*, familyId, outputKeys, origin)
        │
        ▼
Chart Catalog (chartDefinitionId)

Feature Registry
        │  indicator_id = IND-RSI
        ▼
FeatureDef (feat_rsi_14_close, …)
```

| Capa | Ejemplo | Dueño |
|------|---------|-------|
| Familia | `MOVING_AVERAGE` / `MACD` | `familyId` |
| Indicator (impl.) | `IND-RSI` | IndicatorUniverse |
| Feature (instancia) | `feat_rsi_14_close` | Feature Registry |
| Chart UI | `rsi` | `chartDefinitionId` legacy |

| Campo | Uso |
|-------|-----|
| `familyId` | Agrupa implementaciones (SMA/EMA/WMA → `MOVING_AVERAGE`) |
| `canonicalId` | `IND-RSI`, … estable; no cambia nunca |
| `chartDefinitionId` | Id legacy UI (`rsi`, `willr`, …) |
| `origin` | Filtros xtb / prt / taLib / pandasTa / vectorbt |
| `status` | Lifecycle RFC-001: `draft`…`production` / `deprecated` |
| `inputTypes` | `ohlcv`, `price`, `volume`, `indicator`, … |
| `outputType` / `outputKeys` / `outputShape` | Semántica + claves + geometría de render |
| `scaleType` / `displayPrecision` | Eje UI (oscillator/price/volume…) y decimales |
| `supportedPanels` / `defaultPanel` | overlay/sub sin limitar el futuro (`chartPanel` alias) |
| `dependencies` | p. ej. StochRSI → `IND-RSI` |
| `complexity` / `supports` | Coste cómputo + superficies (chart/screener/feature/…) |
| `defaultParams` | Semilla UI / Feature Registry / docs |

**Prohibido en el universo:** `featureParityRefs`, `featureFamilyId`.  
La UI pregunta al Feature Registry (`list_by_indicator_id("IND-RSI")`) si hay features / soporte screener.

**Paridad Py ↔ TS:** un único golden `packages/py/analytics/tests/fixtures/indicator_golden.json` consumido por pytest y `indicator-compute-parity.test.ts`.

**Prioridad:** (1) set XTB operable, (2) Oleada 3 cuant (OBV/MFI/Aroon/ROC + Ichimoku/PSAR…), (3) DSL/custom, (4) UX.

**Oleada 1:** WILLR, MOM, SD, DC.  
**Oleada 2:** ADX, Stoch RSI, SuperTrend, VWAP.  
**Oleada 3 (implementada):** OBV, MFI, Aroon, ROC, Ichimoku, PSAR, Bears/Bulls, Alligator, Fractals.

Helpers: `summarizeIndicatorUniverse()`, `indicatorUniverseByFamily()`, `indicatorUniverseByOrigin()`, `indicatorUniverseByChartId()`.

---

## Changelog (jul 2026)

| Cambio | Descripción |
|--------|-------------|
| UX sync | Crosshair multi-panel + zoom horizontal anclado al cursor |
| Oleada 3 | OBV/MFI/Aroon/ROC + ICH/SAR/Bears/Bulls/ALI/FR (Py+TS+Features+golden) |
| Metadatos UI/IA | `outputShape`, `scaleType`, `displayPrecision`, `supportedPanels`, `dependencies`, `complexity`, `supports` |
| Golden Oleadas 1–2 | Fixture compartido Py+TS (willr/mom/sd/dc/adx/srsi/st/vwap) |
| Arquitectura catálogo | `familyId` + `outputKeys`; sin refs a Features; lookup Feature→IND |
| Oleada 2 XTB | ADX, Stoch RSI, SuperTrend, VWAP en Py+TS+Feature Registry+validators |
| Oleada 1 XTB | WILLR, MOM, SD, DC en Py+TS+Feature Registry+validators |
| Sync bidireccional | Rueda y pan horizontal en sub-paneles propagan al precio |
| Hub multi-pane | Todos los paneles suscritos a `visibleLogicalRangeChange` |
| `rightOffset` sub | Mismo margen derecho que el gráfico principal |
| Doble clic → config | Paneles inferiores y líneas overlay sobre precio |
| Capa presets | `IndicatorPreset` + catálogo por variantes |
| Capa plantillas | `IndicatorTemplate` con matriz en catálogo |
| Zona Plantillas | Barra del gráfico: icono + favoritos + menú (sin confirmación) |
| Favoritos quitables | Swing/Intradía removibles de la barra |
| Renombre interno | `indicatorGroupZone` → `indicatorTemplateZone` |

## Próximos pasos (no implementados)

- Indicadores custom (DSL / scripts de usuario)
- Zoom vertical anclado al cursor en el eje Y (hoy es independiente por panel)
