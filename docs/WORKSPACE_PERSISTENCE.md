# Persistencia del workspace

> Documento operativo (jul 2026). Complementa [CONFIGURATION_MODEL.md](./CONFIGURATION_MODEL.md) y [UI_PLATFORM.md](./UI_PLATFORM.md).  
> **Unicidad de pestañas:** una por `instrumentId` (§2b) · sync Ayuda `HELP_CONTENT_AS_OF` = **2026-07-24**.  
> **UI:** chip superior (nombre del espacio) → gestor; arranque = último activo local.  
> **Chrome por dispositivo:** dock + anchos de columnas (`localStorage`); contenido del espacio en servidor.  
> **Premisa global UI:** todo lo configurable de layout/chrome → `localStorage` — ver [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md).

---

## 0. Producto / UI

| Acción | Comportamiento |
|--------|----------------|
| Arrancar app | Carga `activeWorkspaceId` local → si no, espacio `isDefault` (preferido) → si no, el primero |
| Chip barra superior | Abre gestor de espacios |
| Nuevo (blanco) | Documento vacío (`DEFAULT_WORKSPACE`) |
| Duplicar activo | Clona documento + dock del espacio actual con nuevo nombre |
| Preferido al arrancar | Marca `isDefault` en servidor (reserva si no hay último activo) |
| Autoguardado | Debounce ~1 s al servidor |

Cabecera derecha (orden): **chip espacio** · Ayuda · Config · **sesión**.  
Guardar: autoguardado + «Guardar actual» en el gestor. Exportar JSON también en el gestor. Sin menú ⋯ ni botón Guardar suelto.

---

## 1. Capas de persistencia

| Capa | Clave / API | Qué guarda |
|------|-------------|------------|
| **Servidor** | `PUT /api/workspaces/:id` | Documento (`WorkspaceDocument`). `dockLayout` en API es legado (no se aplica al cargar) |
| **Backup local** | `bolsa-workspace-meta` → `chartPersistBackup` | Gráficos, listas, barras, inspector, snapshots de dibujos |
| **Metadatos locales** | `bolsa-workspace-meta` | `activeWorkspaceId`, `recents` |
| **Dock (por dispositivo)** | `bolsa-trading-layout-v1` | Abierto/ancho watchlist y operaciones |
| **Anchos columnas (por dispositivo)** | `bolsa-list-chrome-layout-v1` | Anchos Valores/Hub + columnas de acciones |

El servidor es la **fuente de verdad del contenido** del espacio (gráficos, listas, orden/visibilidad de columnas, dibujos…).  
El **chrome de layout** (tamaños de paneles y anchos de columna) es **por dispositivo** (`localStorage`): escritorio y portátil no se pisan al cambiar de PC.

Esto es instancia de la **premisa de app**: preferencias/UI configurables → `localStorage` del navegador — [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md).

---

## 2. Mapa de configuración → campo en `WorkspaceDocument`

| Ámbito UI | Campo(s) |
|-----------|----------|
| Barra global del workspace | `chartToolbarGlobal` |
| Barra de datos (defaults workspace) | `chartToolbarGlobal` (`chartVisibilityDefaults`, `chartLayoutDefaults`, `defaultTimeframe`, favoritos…) |
| Barra de datos (override por pestaña) | `charts[].toolbar` |
| Estilos del canvas (inspector) | `charts[].chart` |
| Tipo de barra / traza | `charts[].seriesType`, `charts[].seriesTypeParams` |
| Default tipo de barra (gráficos nuevos) | `chartToolbarGlobal.defaultSeriesType` |
| Favoritos estilo en barra | `chartToolbarGlobal.seriesTypeFavorites` (default `[]`) |
| Favoritos escala en barra | `chartToolbarGlobal.timeframeFavorites` (default `[]`) |
| Favoritos plantillas barra | `chartToolbarGlobal.indicatorTemplateFavorites` (default `[]`) |
| Favoritos herramientas dibujo | `chartToolbarGlobal.drawToolFavorites` (default `[]`) |
| Enlace TradingView (barra tab) | `chartToolbarGlobal.chartVisibilityDefaults.tradingView` |
| Atajos inspector en barra | `chartToolbarGlobal.inspectorBarShortcutFavorites` (default `[]`) |
| Listas: carrusel, columnas (orden/visibilidad), ordenación | `list.carouselListIds`, `list.carouselHiddenListIds`, `list.columnLayoutsByListId`, `list.sortByListId` — **anchos** en `bolsa-list-chrome-layout-v1` |
| Lista Visualización | `list.visualizationEntries` (espejo de pestañas de gráfico abiertas) |
| Inspector abierto/cerrado | `layout.chartInspectorOpen` |
| Tamaño panel listas / inspector | `layout.listPanelSizePct`, `layout.rightPanelSizePct` |
| Dibujos e indicadores (solo pestañas abiertas) | `charts[]` |
| Copia efímera al guardar (misma sesión) | `chartStateByListInstrument` — solo instrumentos con pestaña abierta |
| Presets de indicadores | `indicatorPresets` |
| Plantillas de indicadores | `indicatorTemplates`, `defaultIndicatorTemplateId` |
| Columna Personal (matriz) | `indicatorTemplates[builtin-personal].presetIds` |
| Herencia en gráficos nuevos | `preferences.newChartTemplateChartId` (pestaña plantilla anclada) |
| Favoritos plantillas en barra | `chartToolbarGlobal.indicatorTemplateFavorites` |
| Visibilidad zona plantillas | `chartToolbarGlobal.chartVisibilityDefaults.indicatorTemplateZone` |

---

## 2b. Ciclo de vida de las pestañas (modelo «solo abiertas»)

**Principio:** el estado gráfico (indicadores, dibujos, overrides de barra, layout de sub-paneles) **solo existe mientras la pestaña está abierta**. Cerrar la pestaña = descartar ese instrumento del workspace persistido, como si nunca se hubiera visualizado.

Esto es coherente con terminales profesionales (Bloomberg, muchas estaciones de bróker): las listas son **navegación**; el layout del gráfico vive en las ventanas/pestañas activas. Lo que se guarda a largo plazo son presets, plantillas y defaults del workspace — no cada símbolo visitado.

| Acción | Efecto |
|--------|--------|
| **Abrir desde lista / rastreador / ficha** | **Crea o activa** la pestaña de ese `instrumentId` (nunca una segunda). Actualiza `sourceListId` / `chartListContext` si viene de lista. |
| **Reabrir el mismo valor desde otra lista** | Activa la pestaña ya abierta; el valor puede estar en varias listas, pero solo hay **una** pestaña de gráfico. |
| **Quitar de una lista** (pertenencia en Valores / hub) | Si el valor tenía pestaña abierta → se **cierra** y desaparece de Visualización (`closeOpenChartsForInstrument`). |
| **Cerrar pestaña** | Quita `charts[]`, purga snapshots, desancla plantilla si era esa pestaña, guarda backup local. |
| **Cambiar de pestaña** | El estado del tab anterior sigue en `charts[]` mientras permanezca abierto. |

### Unicidad: una pestaña por instrumento

**Regla de producto:** `workspace.charts[]` no puede contener dos entradas con el mismo `instrumentId`.

| Pieza | Comportamiento |
|-------|----------------|
| `openChartTab` / `focusInstrumentFromList` | Si ya existe → `activeChartId` = esa pestaña |
| `normalizeWorkspace` / `finalizeChartWorkspace` | `dedupeChartTabsByInstrument` colapsa duplicados legacy (p. ej. «Duplicar gráfico» antiguo) |
| Menú ⋯ «Usar gráfico activo como plantilla…» | Ancla plantilla de gráficos **nuevos**; **no** clona pestaña |
| Lista virtual Visualización | Espejo 1:1 de instrumentos con pestaña abierta |

Motivo: OHLCV/sync, snapshots `listId::instrumentId` y dibujos canónicos por instrumento asumen identidad 1:1; dos pestañas del mismo valor provocaban sync a medias y estado cruzado.

Implementación: `apps/web/src/lib/chart-tab-uniqueness.ts`.

`chartStateByListInstrument` es una **copia derivada** de las pestañas abiertas al sincronizar/guardar; no debe contener instrumentos cerrados. Al cargar un workspace antiguo, `pruneOrphanChartSnapshots` elimina entradas huérfanas.

**Fusión servidor ↔ backup:** la lista de pestañas abiertas la dicta el documento más reciente; snapshots huérfanos se descartan en la fusión.

---

## 3. Flujo de guardado

```
Cambio en store (isDirty: true)
        │
        ├─► Listas / barras → scheduleWorkspaceSettingsPersist (500 ms)
        │       ├─ backup local inmediato (chartPersistBackup)
        │       └─ saveToServer si autoSave
        │
        ├─► Dibujos → flushDrawingAutoSave (450 ms)
        │
        └─► WorkspaceAutoSave → saveToServer (1200 ms) si isDirty + autoSave

beforeunload / pagehide → flushWorkspaceOnUnload (keepalive al servidor + backup)
```

Los diálogos ⚙ llaman `save()` al confirmar (guardado inmediato al servidor).

---

## 4. Arranque (bootstrap)

1. Cargar workspace del servidor (`GET /api/workspaces/:id`).
2. Si existe `chartPersistBackup` en localStorage, fusionar con `mergeWorkspaceChartState`:
   - **Listas y barras**: gana el documento con `updatedAt` más reciente.
   - **Dibujos**: unión por id entre servidor y backup.
   - **Overrides de barra por pestaña**: se conservan si alguna fuente los personalizó.
3. Normalizar con `normalizeWorkspace` (valores por defecto + migraciones legacy).

El backup incluye desde jul 2026: `chartToolbarGlobal`, `list`, gráficos, snapshots, catálogo de indicadores (`indicatorTemplates`, `indicatorPresets`) y estado del inspector.

---

## 4b. Migraciones al normalizar (`normalizeWorkspace`)

Al cargar un workspace antiguo, `mergeChartToolbarGlobalConfig` en `chart-toolbar.ts` aplica:

| Legacy | Destino | Notas |
|--------|---------|-------|
| `chartToolbarGlobal.visibility.tradingView` | `chartVisibilityDefaults.tradingView` | Eliminado de visibilidad global; el enlace vive en la barra del tab |
| Favoritos pre-rellenados | Se conservan tal cual | Workspaces existentes **no** se vacían automáticamente |
| Nuevo workspace / «Restaurar favoritos por defecto» | `[]` en Escala, Estilo, Plantillas, dibujos | Barra mínima con badge en icono |

Para probar barra mínima en un workspace ya usado: ⚙ barra de datos → **Restaurar favoritos por defecto**, o quitar chips manualmente con estrella.

---

## 5. Reglas de fusión de listas

`mergeListConfig` evita que arrays vacíos del servidor pisen configuración válida del backup:

- Carrusel: solo se aplica `carouselListIds` / `carouselHiddenListIds` del servidor si `carouselInitialized` o hay datos de carrusel.
- `visualizationEntries`: se prefiere la fuente con entradas.
- `columnLayoutsByListId`: unión por clave de lista.

El carrusel **no** re-sembrará IBEX 35 si ya hay listas ocultas persistidas (`carouselHiddenListIds`), ni si ya existen `carouselListIds` / `carouselPinnedListNames` (p. ej. pin desde la vista **Listas**).

**Selección de lista:** clic en una lista (hub o carrusel) fija `apiListId` y un guard manual (`list-selection-guard.ts`) para que `chartListContext` no vuelva a forzar IBEX 35 / la lista del gráfico hasta cambiar de pestaña de gráfico.

**Misma operativa de carrusel:** checkbox columna Carrusel en Listas = menú ⋯ del carrusel en Valores → `patchToggleCarouselList` (`list-carousel-config.ts`).

Ayuda en app: **Ayuda → Watchlist (Listas / Valores)**.

---

## 6. Comprobación manual

1. Cambiar visibilidad en ⚙ barra global → recargar → debe mantenerse.
2. Cambiar favoritos de timeframe (estrella) → recargar → debe mantenerse.
3. Override por pestaña en ⚙ barra de datos → recargar → debe mantenerse.
4. Reordenar columnas de una lista → recargar → debe mantenerse.
5. Pin/ocultar listas en el carrusel → recargar → debe mantenerse.
6. Cambiar tipo de barra (Estilo) en un gráfico → recargar → debe mantenerse.
7. Añadir símbolos a Visualización → recargar → debe mantenerse.
8. Inspector abierto/cerrado → recargar → debe recordar el último estado.
9. Abrir valor desde lista, añadir indicadores/dibujos, cerrar pestaña, recargar → **no** debe reaparecer la pestaña ni su estado.
10. Reabrir el mismo valor tras cerrar → gráfico limpio o heredado según conmutador «Nuevo», sin restaurar la sesión anterior.
11. Chip superior → gestor → **Nuevo (blanco)** → sin pestañas del anterior; **Duplicar activo** → misma configuración con otro nombre.
12. Cerrar app y reabrir → se restaura el último espacio activo (no el «preferido», salvo que no haya activo local).

---

## 7. Archivos relevantes

| Archivo | Rol |
|---------|-----|
| `apps/web/src/stores/workspace-store.ts` | Store, bootstrap, create/duplicate/rename, save |
| `apps/web/src/features/workspace/workspace-picker-dialog.tsx` | Gestor UI (chip / Config → General) |
| `apps/web/src/components/layout/app-top-bar.tsx` | Chip + Guardar + ⋯ |
| `apps/web/src/lib/chart-list-snapshot.ts` | `mergeWorkspaceChartState`, `mergeListConfig` |
| `apps/web/src/lib/workspace-payload.ts` | Payload API |
| `apps/web/src/features/workspace/workspace-auto-save.tsx` | Debounce global + flush al cerrar |
| `packages/shared/src/chart-toolbar.ts` | `mergeChartToolbarGlobalConfig` |
| Ayuda → Trading / Guía | Textos de producto (barra superior + espacio) |
