# Modelo de configuración — v2

Documento de diseño e implementación (jul 2026). **Un ⚙ por barra** (solo su ámbito) + **inspector** para el gráfico.

Complementa [UI_PLATFORM.md](./UI_PLATFORM.md), [CHART_RESPONSIVE.md](./CHART_RESPONSIVE.md).

---

## 1. Principio rector

> **Cada superficie configura solo lo que muestra.**  
> Los atajos (iconos) **navegan**; no duplican formularios.

```
┌──────────────────────────────────────────────────────────────────┐
│  PLATAFORMA          Top bar → Configuración                     │
│  cuenta, sync, Perfil inversor (RFC-008), atajos, sonidos…       │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  BARRA GLOBAL        ⚙ → solo barra global del workspace         │
│  Indicadores, C/V, BD, toggle Inspector, fondo global            │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  BARRA DE DATOS      ⚙ → Escala · Estilo · Valor · Cursor · atajos        │
│  defaults workspace, override por tab, fondo, favoritos          │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  INSPECTOR           panel lateral + iconos de atajo             │
│  gráfico activo: capas, objetos, estilos, vela, selección        │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  LISTAS              Hub de listas (sin mezclar con gráficos)    │
└──────────────────────────────────────────────────────────────────┘
```

**Inline (estrella)** en Escala / Estilo / Valor / Cursor = configuración **frecuente** de favoritos; no sustituye al ⚙ de la barra de datos, lo complementa.

---

## 2. Estado actual (implementado)

- **Dos diálogos** independientes: `ChartGlobalBarSettingsDialog` y `ChartDataBarSettingsDialog`. Cada ⚙ abre solo su ámbito.
- **Inspector** como dueño del canvas (rejilla, colores, capas, objetos). Eliminado `ChartPropertiesDialog` y el diálogo monolítico `ChartToolbarSettingsDialog`.
- **Zona Estilo** entre Escala y Valor: tipo de barra/traza con favoritos (estrella), override por pestaña y default global para gráficos nuevos.
- **Persistencia** en `WorkspaceDocument` (servidor + backup local). Ver [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md).

---

## 3. Barra global del workspace — ⚙ propio

**Diálogo nuevo / renombrado:** `ChartGlobalBarSettingsDialog`  
**Título UI:** «Barra del workspace» o «Barra de gráficos (global)»

### Contenido exclusivo

| Bloque | Campos (tipos actuales) |
|--------|-------------------------|
| **Elementos visibles** | `visibility.indicators`, `indicatorTemplates`, `tradeButtons`, `dataStatus`, `chartInspector` |
| **Gráficos nuevos** | `preferences.newChartTemplateChartId` — icono plantilla junto a Indicadores |
| **Apariencia** | `appearance.globalBarBackground` |

### Qué NO entra aquí

- Defaults de la barra de datos (timeframe, visibilidad, wrap, fondo, favoritos) → **barra de datos ⚙**.
- Visibilidad de Escala / Valor / Cursor **de este tab** (→ barra de datos ⚙).
- Rejilla, colores del chart, capas (→ inspector).
- Favoritos de estrella (→ inline; opcionalmente «restablecer favoritos» en barra de datos).

### Botón Inspector en esta barra

Solo **abre/cierra el panel** inspector. No es configuración; la visibilidad del botón sí se configura aquí (`chartInspector`).

---

## 4. Barra de datos del gráfico — ⚙ propio

**Diálogo nuevo:** `ChartDataBarSettingsDialog`  
**Título UI:** «Barra de datos del gráfico»

Zonas: **Escala** · **Estilo** · **Plantillas** · **Valor** · **TradingView** · **Cursor** (cada una: **icono con muesca** + chips opcionales) · atajos inspector · ⚙.

Patrón UI detallado: [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

### Contenido exclusivo

| Bloque | Campos |
|--------|--------|
| **Defaults del workspace** | `defaultTimeframe`, `defaultSeriesType`, `chartVisibilityDefaults`, `chartLayoutDefaults`, `appearance.chartBarBackground`, favoritos |
| **Este gráfico — visibilidad** | `visibility.timeframe`, `timeframeZoom`, `instrumentZone`, `tradingView`, `seriesZone`, `indicatorTemplateZone`, `cursorZone`, `overlayIndicators` |
| **Este gráfico — distribución** | `layout.wrapRows` |
| **Este gráfico — apariencia** | `appearance.chartBarBackground` (override del tab) |
| **Herencia** | Checkbox «Usar valores por defecto del workspace» (`useGlobalDefaults`) |
| **Favoritos** | Vista previa + «Restaurar favoritos por defecto» (`timeframeFavorites`, `seriesTypeFavorites`, `indicatorTemplateFavorites`, `instrumentFieldFavorites`, `cursorFieldFavorites`) |

### Qué NO entra aquí

- Indicadores, C/V, BD (→ barra global).
- Enlace TradingView (→ barra de datos del gráfico activo, flag `tradingView`).
- Estilos del chart (rejilla, modo imán del cursor en canvas, colores de velas) (→ inspector).  
  *Nota:* el **cursor de la barra** (OHLC en la franja) ≠ **cursor del gráfico** (imán, tooltip).
- Capas, objetos, parámetros de indicadores (→ inspector).

### Atajos con iconos (capas, objetos, estilos…)

- **Visibilidad en barra:** solo si están en `inspectorBarShortcutFavorites` (estrella en inspector → Config).
- El botón ⚙ de la barra de datos **siempre** visible (no usa favoritos).
- **Contenido** al pulsar un atajo: inspector (navegación ya implementada).
- **Configuración** del contenido: inspector, no este ⚙.
- Opción `overlayIndicators` en visibilidad: **obsoleta** (migración automática a favoritos).

| Icono | Destino inspector | Notas |
|-------|-------------------|--------|
| Capas | Config → Capas | Badge = overlay + paneles inferiores |
| Objetos | Config → Objetos | Dibujos |
| Paleta | Config → Estilos | Rejilla, colores, márgenes del canvas |

---

## 5b. Zona Estilo (tipo de serie) — ✅ implementada

Misma familia que Escala: icono `ChartCandlestick` + muesca (menú/favoritos) + chips. Ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md).

Catálogo en `packages/shared/src/chart-series-type.ts`. Motor en `apps/web/src/features/charts/chart-main-series.ts`.

| Fase | Tipos renderizables | Estado |
|------|---------------------|--------|
| 1 | Velas, barras, línea | ✅ |
| 2 | Huecas, HLC, área, línea escalonada/marcadores, columnas, máx-mín, referencia | ✅ |
| 3 | Heikin-Ashi, velas de volumen | ✅ |
| 4 | Renko, Kagi, P&F, ruptura de línea (parámetros en inspector) | ✅ |

Inspector: subsección **Config → Estilo de barra** (distinta de **Estilos** = canvas).

Persistencia: `charts[].seriesType`, `charts[].seriesTypeParams`, `chartToolbarGlobal.defaultSeriesType`, `chartToolbarGlobal.seriesTypeFavorites`.

---

## 5c. Zona Plantillas (indicadores) — ✅ implementada

Icono `LayoutTemplate` + chips de plantillas favoritas. Menú y estrellas solo en el icono. Ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) y [CHART_INDICATORS.md](./CHART_INDICATORS.md).

| Elemento UI | Comportamiento |
|-------------|----------------|
| Icono + muesca | Menú completo; estrella = favorito en barra |
| Chips favoritos | Aplican plantilla al gráfico activo (sustituyen instancias) |
| Plantilla activa | Resaltada en menú; visible como chip si favorita o activa |

**Gestión de plantillas** (crear, renombrar, matriz preset↔plantilla): solo en catálogo **Indicadores** (barra global).

Persistencia: `chartToolbarGlobal.indicatorTemplateFavorites`, `chartVisibilityDefaults.indicatorTemplateZone`, `charts[].activeIndicatorTemplateId`, `workspace.indicatorTemplates`. Ver [CHART_INDICATORS.md](./CHART_INDICATORS.md#presets-plantillas-y-catálogo).

---

## 5d. Enlace TradingView — ✅ implementada (jul 2026)

| Aspecto | Detalle |
|---------|---------|
| **Ubicación UI** | Barra de datos del tab activo, inmediatamente **después de Valor** |
| **Visibilidad** | `ChartToolbarChartVisibility.tradingView` (⚙ barra de datos) |
| **Ya no en barra global** | Eliminado `ChartToolbarGlobalVisibility.tradingView`; migración automática al normalizar workspace |
| **Utilidad** | `apps/web/src/features/charts/chart-trading-view-url.ts` |
| **Símbolo TV** | `BME:{ticker}` desde `yahooSymbol` o label del tab |

---

## 5e. Favoritos y barra mínima — ✅ jul 2026

| Zona (select) | Default favoritos | UI sin favoritos |
|---------------|-------------------|------------------|
| Escala | `timeframeFavorites: []` | Icono `🕐` + badge `1D` |
| Estilo | `seriesTypeFavorites: []` | Icono + badge `Velas` |
| Plantillas | `indicatorTemplateFavorites: []` | Icono + nombre corto activo |
| Dibujos (vertical) | `drawToolFavorites: []` | Icono + `shortLabel` activo |

Valor y Cursor mantienen anclas y defaults de campos. Ver [CHART_DATA_BAR.md](./CHART_DATA_BAR.md) y [CHART_DRAWING_TAXONOMY.md](./CHART_DRAWING_TAXONOMY.md).

---

## 5. Inspector de gráficos

**Dueño del gráfico activo** (entidad chart + selección).

| Pestaña | Rol |
|---------|-----|
| Resumen | Lectura instrumento/gráfico; acciones (sync, catálogo) |
| Vela | OHLC bajo cursor (lectura) |
| Contexto | Indicador o dibujo **seleccionado** |
| Capas | Indicadores overlay / sub |
| Objetos | Dibujos |
| Estilos | Rejilla, cursor **del canvas**, colores, márgenes del chart |
| Estilo de barra | Tipo de serie/traza del gráfico activo (override por tab) |
| Alertas | Futuro |

### Reglas

1. **Sin** botones «Configurar barra…» que abran otros diálogos.
2. Iconos en la barra de datos = **accesos directos** al inspector (toggle + navegación).
3. Menú «Propiedades del gráfico» → redirige a **Inspector → Estilos** (deprecar diálogo suelto).

---

## 6. Jerarquía de herencia (barra de datos)

```
Workspace (barra de datos ⚙ → defaults del workspace)
        │
        ▼
Tab activo (barra de datos ⚙ → override, si no useGlobalDefaults)
        │
        ▼
Resolución en UI (resolveChartToolbarForTab — sin cambiar lógica)
```

El usuario entiende:

- **⚙ barra global** → «qué botones hay en la barra superior del workspace».
- **⚙ barra de datos** → «cómo se ve la franja Escala/Estilo/Valor/Cursor» (defaults + este gráfico).

---

## 7. Comparación con apps TOP

| Patrón TOP | Nuestra v2 |
|------------|------------|
| Timeframe / símbolo en barra + menú local | Escala / Estilo / Valor / Cursor + estrella + ⚙ barra datos |
| Barra de herramientas workspace separada | Barra global ⚙ propio |
| Panel propiedades contextual | Inspector |
| Settings de app separado | PlatformConfig |

Encaja con ProRealTime / TradingView: **chrome de barras** cerca de las barras; **propiedades del gráfico** en panel lateral.

---

## 8. Mapa de migración

### Fase A — Dividir diálogos ✅

1. `ChartGlobalBarSettingsDialog` — barra global + defaults gráficos nuevos.
2. `ChartDataBarSettingsDialog` — barra de datos + favoritos + override por tab.
3. Cada ⚙ abre **solo** su diálogo.

### Fase B — Inspector como dueño del chart ✅

1. Campos de estilos del canvas en inspector → **Estilos** (`ChartCanvasStylesPanel`).
2. Eliminados `ChartPropertiesDialog` y menú duplicado.
3. Sin `onOpenChartToolbarSettings` en el inspector.

### Fase C — Limpieza legacy ✅

1. Eliminado componente monolítico `ChartDataStrip` (sustituido por zonas Valor/Cursor + favoritos estrella).
2. Visibilidad `dataStrip` dividida en `instrumentZone` + `cursorZone` (migración automática).
3. Etiquetas `CHART_TOOLBAR_*_VISIBILITY_LABELS` alineadas con cada zona.
4. UI_PLATFORM.md + ayuda actualizados.

### Fase D — Checklist para features nuevas

```
¿Afecta a la franja Escala/Estilo/Valor/Cursor?     → barra de datos ⚙
¿Afecta a Indicadores/C/V/BD/TV/Inspector?  → barra global ⚙
¿Afecta al canvas, capas, dibujos?           → inspector
¿Uso diario del valor mostrado?              → estrella inline
¿Cuenta / app / perfil inversor?             → PlatformConfig
¿Listas?                                     → ListHub
```

**Perfil inversor (RFC-008 ART-PROFILE):** catálogo reutilizable en `investor_profiles`; cada cuenta tiene **un** `active_profile_id` (varias cuentas pueden compartir el mismo perfil). UI: **asistente Nueva demo** (paso Perfil = lista del catálogo o crear), **Configuración → Perfil inversor** (CRUD + asignar a cuenta), ficha de cuenta / Comisiones. `settings_json` solo comisiones/fiscal.

---

## 9. Glosario UI

| Nombre | Qué es |
|--------|--------|
| **Barra global** | Indicadores · Plantillas · C/V · BD · Inspector |
| **Barra de datos del gráfico** | Escala · Estilo · Plantillas · Valor · TradingView · Cursor · atajos · ⚙ |
| **Configuración** (top) | Plataforma (cuenta, sync, **BD**, **Perfil inversor**, …) |
| **Inspector** | Panel del gráfico activo |
| **Gestión de listas** | Carrusel y columnas |

---

## 10. Decisiones acordadas (jul 2026)

| # | Tema | Decisión |
|---|------|----------|
| 1 | **Favoritos** | **Ambos:** estrella inline en barra + sección en ⚙ barra de datos con vista previa y «Restaurar favoritos por defecto». |
| 2 | **Gráficos nuevos** | Heredan defaults de la **barra de datos ⚙** («Defaults del workspace»). Luego plantillas de indicadores, dibujos, etc. sobre ese tab. |
| 3 | **Flags SMA/EMA / display** | **Pendiente** — estudiar en rediseño inspector **Datos vs Config**. Probable hogar: inspector; no decidir hasta Fase B. |
| 4 | **TradingView** | Enlace en **barra de datos del tab activo** (tras Valor), no en barra global. Flag `chartVisibilityDefaults.tradingView`. |
| 5 | **Barra mínima** | Favoritos vacíos `[]` por defecto en Escala, Estilo, Plantillas y dibujos; icono muestra valor activo; chips solo con estrella. Valor/Cursor mantienen anclas fijas. |
| 6 | **Menús modales** | Backdrop `bg-black/10`, panel opaco `CHART_ZONE_DROPDOWN_PANEL_CLASS`, Escape, un menú abierto. Mismo contrato barras H y V. |
| 7 | **Dibujo continuo** | Tras colocar figura, herramienta permanece activa (`handleDrawingAdded`); puntero manual para editar. |
| 8 | **Resize paneles** | Separadores precio↔indicadores desactivados mientras herramienta de figura o regla activa. |

### Inspector (futuro — Fase B+)

Dividir conceptualmente:

- **Datos** — lo que el gráfico muestra (vela, OHLC, resumen instrumento, estado BD…).
- **Config** — lo que el usuario añade y parametriza (indicadores, líneas, figuras, estilos del canvas).

Objetivo cumplido: estilos del canvas y tipo de barra tienen hogares distintos (inspector **Estilos** vs **Estilo de barra**).

---

## 11. Estado de implementación

| Fase | Estado |
|------|--------|
| **A — Dos diálogos** | ✅ `ChartGlobalBarSettingsDialog`, `ChartDataBarSettingsDialog` |
| **B — Inspector dueño del chart** | ✅ `ChartCanvasStylesPanel`, eliminado `ChartPropertiesDialog` |
| C — Limpieza legacy | ✅ Zonas Valor/Cursor, labels, docs |
| **D — Inspector Datos / Config** | ✅ Dos modos: Datos (lectura) + Config (capas, objetos, estilos, estilo de barra, selección) |
| **E — Zona Estilo + motor de series** | ✅ Fases 1–4 renderizadas |

### Archivos (Fase A + E)

- `chart-global-bar-settings-dialog.tsx` — barra global + defaults gráficos nuevos
- `chart-data-bar-settings-dialog.tsx` — barra de datos por tab + favoritos
- `chart-toolbar-settings-fields.tsx` — `ColorField`, `FavoritesWorkspaceSection`, `DefaultSeriesTypeSelect`
- `chart-series-type-zone.tsx` — zona Estilo en la barra
- `chart-series-style-panel.tsx` — inspector Config → Estilo de barra
- `chart-advanced-series.ts` — transformaciones Renko, Kagi, P&F, ruptura de línea
- `chart-main-series.ts` — creación y datos de la serie principal
- Eliminado: `chart-toolbar-settings-dialog.tsx` (monolítico), `ChartPropertiesDialog`, `chart-data-strip.tsx` (UI)

---

## 12. Puntos abiertos (solo inspector)

1. ~~¿Pestaña **Config** agrupa Capas + Objetos + Estilos + parámetros de instancia?~~ → **Sí** (Fase D).
2. ~~¿Pestaña **Datos** agrupa Resumen + Vela + lecturas de mercado?~~ → **Sí** (Fase D).
3. ¿`display` flags (SMA/EMA legacy) pasan a instancias de indicador o a toggles de capa? — Por ahora en Config → Estilos.

---

## 13. Criterios de aceptación

- [x] Dos diálogos distintos; ningún ⚙ abre el diálogo del otro.
- [x] Barra global ⚙ sin campos de Escala/Valor/Cursor del tab ni fondo de barra de datos.
- [x] Barra de datos ⚙ con defaults del workspace (fondo, visibilidad, wrap, timeframe).
- [x] Inspector sin enlaces a configuración de barras.
- [x] Un solo lugar para estilos del canvas (inspector → Estilos).
- [x] Iconos de atajo solo navegan al inspector (modo Datos o Config).
- [x] Zona Estilo con favoritos y persistencia (`seriesType`, `defaultSeriesType`).
- [x] Tipos de serie fases 1–4 renderizados en el motor del gráfico.
- [x] Listas y barras persisten tras reinicio (ver [WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md)).

---

## 14. Persistencia (resumen)

Toda configuración de listas y barras vive en `WorkspaceDocument` y se guarda vía API. Detalle del flujo, backup local y reglas de fusión: **[WORKSPACE_PERSISTENCE.md](./WORKSPACE_PERSISTENCE.md)**.

---

## 15. Historial

| Versión | Cambio |
|---------|--------|
| v1 | Un ⚙ global unificado + inspector dueño del chart |
| **v2** | ⚙ por barra (global vs datos) + inspector para el gráfico |
| **v2.1** | Zona Estilo, `seriesType` por tab, motor fases 1–3 |
| **v2.2** | Motor fase 4: Renko, Kagi, P&F, ruptura de línea |
| **v2.3** | TradingView en barra de datos; barra mínima (favoritos `[]`); menús modales H/V; dibujo continuo; coherencia z-index |
