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
| Duplicar activo | Clona documento + dock del espacio actual con nombre libre (`(copia)`, `(copia 2)`, …) |
| Preferido al arrancar | `PUT { isDefault }` inmediato (reserva si no hay último activo local) |
| Autoguardado | Debounce ~1 s al servidor; apagarlo también se guarda al momento |

Cabecera derecha (orden): **chip espacio** · Ayuda · Config · **sesión**.  
Guardar: autoguardado + «Guardar actual» en el gestor. Exportar JSON también en el gestor. Sin menú ⋯ ni botón Guardar suelto.

### 0b. Reparto de superficies (oct 2026)

`Configuración → General` y el gestor de espacios no se solapan:

| Superficie | Qué contiene |
|------------|--------------|
| **General** | `Tema` y `Densidad de UI` (app/dispositivo), toggle **Panel/Gráfico** del HUD Mercado (dispositivo) y un **resumen de solo lectura** del espacio activo + botón «Gestionar espacios…» |
| **Gestor de espacios** (única superficie de edición del espacio) | Catálogo (cambiar / renombrar / borrar) · preferencias de servidor (autoguardado, preferido, plantilla de gráficos nuevos) · chrome del dispositivo (diseño de Mercado, restablecer paneles) · nuevo/duplicar/exportar/guardar |

Motivo: `Tema` y `Densidad` son globales por dispositivo; si vivieran en el espacio el usuario creería que cambian al cambiar de espacio. `Diseño de Mercado` y `Restablecer paneles` sí son chrome del espacio, aunque por dispositivo.

---

## 1. Capas de persistencia

| Capa | Clave / API | Qué guarda |
|------|-------------|------------|
| **Servidor** | `PUT /api/workspaces/:id` | Documento (`WorkspaceDocument`). `dockLayout` en API es legado (no se aplica al cargar) |
| **Servidor (cierre de pestañas)** | `POST /api/workspaces/:id/charts/close` | Solo `instrumentIds` (+ `activeChartId`, `expectedUpdatedAt`): poda pestañas, snapshots, `visualizationEntries` y `chartListContext` huérfano sin reenviar el documento |
| **Backup local** | `bolsa-workspace-meta` → `chartPersistBackup` | Gráficos, listas, barras, inspector, snapshots de dibujos |
| **Metadatos locales** | `bolsa-workspace-meta` | `activeWorkspaceId`, `recents` |
| **Dock (por dispositivo)** | `bolsa-trading-layout-v1` | Abierto/ancho watchlist y operaciones, `namedLayoutId` |
| **Anchos columnas (por dispositivo)** | `bolsa-list-chrome-layout-v1` | Anchos Valores/Hub + columnas de acciones |
| **Tema / densidad (por dispositivo)** | `bolsa-ui-prefs-v1` | Solo `uiTheme` y `uiDensity` — ver [UI_PREFS_LOCALSTORAGE.md](./UI_PREFS_LOCALSTORAGE.md) |
| **Sesión de dibujo** | `bolsa-chart-draw-tool-session` | `chartDrawTool` + `lastDrawToolByGroup` (comparte prefijo pero **no** claves con la UI) |

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
| Tamaño panel inspector | `layout.rightPanelSizePct` |
| Tamaño panel listas | `bolsa-trading-layout-v1` (`listsWidthPct`, por dispositivo). `layout.listPanelSizePct` es **legado**: solo se usa como semilla si no hay preferencia local |
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

`syncSnapshotsFromCharts` compara los snapshots con **serialización canónica** (claves ordenadas), no por longitudes. Comparar solo `timeframe`, `seriesType` y el número de dibujos/indicadores dejaba snapshots obsoletos cuando cambiaban los parámetros de un indicador o la geometría de un dibujo sin cambiar el conteo. La fusión termina con `pruneOrphanChartSnapshots`, así un `chartListContext` de un instrumento cerrado no revive desde el documento antiguo.

`list.visualizationEntries` se **deriva de `charts`** al guardar (`deriveVisualizationEntries` en `prepareWorkspaceForSave`), además del espejo con debounce de `useVisualizationWorkspaceSync`. Cerrar y salir antes del debounce ya no puede escribir `charts` podado junto a un `visualizationEntries` obsoleto.

**Fusión servidor ↔ backup (newest-wins):** la **membresía** de pestañas la dicta el documento con `updatedAt` más reciente — nunca se unen pestañas de documentos distintos. Del documento antiguo solo se reutiliza el estado interno de las pestañas que existen en ambos (dibujos, overrides de barra, etc.); los snapshots de instrumentos cerrados se descartan.

Motivo: unir pestañas hacía que un documento viejo del servidor con 200+ pestañas resucitara las que el usuario ya había cerrado en «Visualizados» tras recargar. `docs` y código actual lo cubren con `apps/web/src/lib/chart-list-snapshot.merge.test.ts`.

**Persistencia fiable del cierre** (una pestaña cerrada no debe volver):

| Mecanismo | Comportamiento |
|-----------|----------------|
| Guardado al cerrar | `closeChartTab` / `closeChartTabsForInstruments` guardan **al momento** (sin esperar el debounce). |
| Reintentos | Si el PUT falla (API reiniciándose, red), se reintenta con backoff 2 s → 5 s → 15 s → 30 s mientras `isDirty` y autoguardado sigan activos. |
| Concurrencia optimista | El PUT envía `expectedUpdatedAt` (el `updatedAt` del servidor que se leyó). Si otro cliente guardó antes, el servidor responde **409** `workspace_conflict` + `currentUpdatedAt`; el cliente relee, refusiona y reintenta una vez. La comprobación y la escritura son **una sola sentencia** (`UPDATE … WHERE id = :id AND updated_at = :expected`): comparar en Python entre `SELECT` y `UPDATE` dejaba una ventana TOCTOU en la que dos PUT con la misma revisión ganaban los dos. Una revisión malformada se rechaza con **400** `workspace_invalid_revision` (antes se degradaba a `null` y desactivaba la comprobación). |
| Cierre al salir | `beforeunload`/`pagehide` → `POST /charts/close` con los ids pendientes y `expectedUpdatedAt`; en ese caso **no** se reenvía el documento completo (podría resucitar las pestañas que el cierre está podando). Sin cierres pendientes, el PUT keepalive también lleva `expectedUpdatedAt`. El tope de `keepalive` (~64 KiB en Chromium) se mide en **bytes UTF-8** (`TextEncoder`), no en unidades de `String#length`; por encima se omite el PUT (queda el último guardado). Un guard de reentrada evita que `beforeunload` + `pagehide` envíen el flush dos veces. |
| Carrera con el PUT | `isDirty` se recalcula comparando el **conjunto** de `instrumentId` enviado con el vivo **y la identidad del documento** (`get().workspace !== workspaceBeforeSave`): cerrar pestañas, cambiar indicadores, dibujos, orden o pestaña activa durante el `await` deja el workspace pendiente y encola otro guardado. |

---

## 3. Flujo de guardado

```
Cambio en store (isDirty: true)
        │
        ├─► Listas / barras → scheduleWorkspaceSettingsPersist (500 ms)
        │       ├─ backup local inmediato (chartPersistBackup)
        │       └─ saveToServer si autoSave
        │
        ├─► Cerrar pestaña → guardado inmediato (sin debounce)
        │
        ├─► Dibujos → flushDrawingAutoSave (450 ms)
        │
        └─► WorkspaceAutoSave → saveToServer (1200 ms) si isDirty + autoSave

saveToServer falla → reintento con backoff (2/5/15/30 s); 409 → relee + refusiona
beforeunload / pagehide → flushWorkspaceOnUnload (charts/close + backup + keepalive acotado)
```

Los diálogos ⚙ llaman `save()` al confirmar (guardado inmediato al servidor).

### 3b. Semántica de `isDefault` (oct 2026)

`is_default` es la **única** autoridad del «preferido al arrancar».

| Camino | ¿Envía `isDefault`? |
|--------|---------------------|
| `saveToServer` (autoguardado, «Guardar actual», `setAutoSave`) | **No** |
| `flushWorkspaceOnUnload` (keepalive) | **No** |
| `setPreferred(enabled)` (checkbox del gestor) | **Sí**: `PUT { isDefault }` y refresca el catálogo |
| `applyServerWorkspace` (bootstrap / cambiar / recargar / borrar) | — lo **lee** y fija `preferences.openOnStartup` |

Antes cada guardado enviaba `isDefault: preferences.openOnStartup` (default `true`), así que la estrella saltaba al último espacio guardado. `preferences.openOnStartup` sigue en el documento por compatibilidad, pero ya no decide nada en la UI.

En el servidor, `WorkspaceRepository.update` solo toca `is_default` cuando el campo llega en el body, así que un guardado normal nunca lo desmarca.

### 3c. Exportar JSON ≠ guardar

`exportJson` serializa `prepareWorkspaceForSave(workspace)` pero **no** limpia `isDirty`: exportar no cambia el estado del servidor, y marcar el espacio como limpio permitía que el siguiente pull pisara cambios sin guardar.

### 3d. Cambio de espacio y backup local

`chartPersistBackup` no guarda id de espacio. Al cambiar/crear/duplicar/recargar/borrar se reescribe con el documento nuevo (`workspaceBackupPatch` + `writeChartPersistBackupSync`); sin eso, el bootstrap siguiente fusionaba pestañas y dibujos del espacio anterior. Al borrar también se purga el id de `recents`.

---

## 4. Arranque (bootstrap)

1. Cargar workspace del servidor (`GET /api/workspaces/:id`).
2. Si existe `chartPersistBackup` en localStorage, fusionar con `mergeWorkspaceChartState`:
   - **Membresía de pestañas**: la dicta el documento con `updatedAt` más reciente (no se unen pestañas).
   - **Listas y barras**: gana el documento con `updatedAt` más reciente.
   - **Dibujos**: se conservan los del documento autoritativo; los de instrumentos cerrados se descartan.
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
- `visualizationEntries`: gana el documento más reciente, **incluido `[]`** (permite podar el dump legacy con el Estudio de 100+). En cada arranque, `useVisualizationWorkspaceSync` reconcilia el store con las pestañas abiertas y solo reescribe el workspace si el conjunto cambió.
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
10. Vaciar **Visualizados** (Quitar / cerrar todas las pestañas) → recargar y **reiniciar el servidor** → sigue vacío (o solo con la pestaña que quede).
11. Reabrir el mismo valor tras cerrar → gráfico limpio o heredado según conmutador «Nuevo», sin restaurar la sesión anterior.
12. Chip superior → gestor → **Nuevo (blanco)** → sin pestañas del anterior; **Duplicar activo** → misma configuración con otro nombre (`(copia 2)`, `(copia 3)` si repites).
13. Cerrar app y reabrir → se restaura el último espacio activo (no el «preferido», salvo que no haya activo local).
14. **Autoguardado** en el gestor: desactivarlo → recargar → sigue desactivado (se persiste al momento).
15. **Preferido al arrancar**: marcarlo en el espacio A, guardar el espacio B → la estrella sigue en A.
16. **Exportar JSON**: con cambios sin guardar, descargar → el punto ámbar (`isDirty`) permanece.
17. Cambiar de espacio → no reaparecen pestañas ni dibujos del espacio anterior al recargar.
18. **Concurrencia**: dos pestañas del navegador en espacios distintos con el mismo id; guardar en ambas → ninguna pierde su cierre (la segunda recibe 409, relee y reintenta).
19. **Tema**: Claro → cambiar de herramienta de dibujo → recargar → sigue Claro (el tema ya no comparte clave con la sesión de dibujo).

---

## 7. Archivos relevantes

| Archivo | Rol |
|---------|-----|
| `apps/web/src/stores/workspace-store.ts` | Store, bootstrap, create/duplicate/rename, save |
| `apps/web/src/stores/workspace-store-core.ts` | `applyServerWorkspace`, `nextCopyName`, `workspaceBackupPatch`, payloads |
| `apps/web/src/stores/workspace-slice-account.ts` | Acciones de espacio (`setPreferred`, `setAutoSave`, `exportJson`, borrado) |
| `apps/web/src/features/workspace/workspace-picker-dialog.tsx` | Gestor UI (chip / Config → General) |
| `apps/web/src/features/settings/general-settings-section.tsx` | General por ámbitos + resumen del espacio |
| `apps/web/src/components/ui/dialog.tsx` | `Dialog` (título con `useId`, pila de Escape) + `DialogTabs` accesibles |
| `apps/web/src/components/layout/app-top-bar.tsx` | Chip + Guardar + ⋯ |
| `apps/web/src/lib/chart-list-snapshot.ts` | `mergeWorkspaceChartState` (newest-wins), `mergeListConfig` |
| `apps/web/src/lib/unload-flush-guard.ts` | Guard de reentrada `beforeunload` + `pagehide` (un solo flush) |
| `apps/web/src/features/workspace/use-visualization-workspace-sync.ts` | Visualizados = espejo de pestañas; solo reescribe si cambia |
| `apps/api-python/src/bolsa_api/api/v1/routes/workspaces.py` | Rutas del espacio + `POST /charts/close` + 409 de conflicto |
| `packages/py/application/src/bolsa_application/workspaces.py` | `close_workspace_charts` (poda charts/snapshots/visualizationEntries/context) |
| `packages/py/infrastructure/src/.../workspace_repository.py` | `update` con escritura condicional atómica + `parse_timestamp` estricto |
| `apps/web/src/lib/workspace-payload.ts` | Payload API |
| `apps/web/src/features/workspace/workspace-auto-save.tsx` | Debounce global + flush al cerrar |
| `packages/shared/src/chart-toolbar.ts` | `mergeChartToolbarGlobalConfig` |
| Ayuda → Trading / Guía | Textos de producto (barra superior + espacio) |

---

## 8. Auditoría profunda de persistencia (2026-11-02)

Rama `fix/059-060-proveedores`. La auditoría se ejecutó sobre el árbol de trabajo cuando HEAD
era `5012361f` (commit **solo de documentación**, no contiene ninguna corrección): las
correcciones que describe esta sección se publican en el commit que introduce este texto.
Comandos y resultados reproducibles: `docs/engineering/evidence/auditoria-persistencia-2026-11-02/README.md`.

BD de auditoría aislada `bolsa_v1_audit` (`DATABASE_URL` solo para las pruebas): `bolsa_v1`
no se tocó (1 workspace, 214 pestañas).

| Hallazgo | Corrección | Prueba |
|----------|------------|--------|
| TOCTOU: dos PUT con la misma revisión ganaban ambos | `UPDATE … WHERE updated_at = :expected` + `rowcount` (una sola sentencia) | `test_two_updates_from_the_same_revision_do_not_both_win` (mutación del `WHERE` → falla) |
| Flush de cierre sin `expectedUpdatedAt` | El keepalive envía la revisión y, con cierres pendientes, **solo** `/charts/close` | `workspace-save-reliability.test.ts` + `api-keepalive.test.ts` |
| Snapshot obsoleto con el mismo conteo | Comparación canónica profunda | `chart-list-snapshot.merge.test.ts` (parámetros y geometría) |
| `isDirty` limpio con cambios en vuelo | Identidad del documento + membresía | `workspace-save-reliability.test.ts` (cambio de contenido) |
| `visualizationEntries` no derivado al guardar | `deriveVisualizationEntries` en `prepareWorkspaceForSave` | `workspace-save-reliability.test.ts` |
| Keepalive medido en caracteres | `TextEncoder().encode(...).length` | `workspacePayloadByteLength` (UTF-8) |
| Doble flush `beforeunload`+`pagehide` | `createUnloadFlushGuard` | `unload-flush-guard.test.ts` |
| `chartListContext` huérfano tras cierre/fusión | Poda en `close_workspace_charts` y en `mergeWorkspaceChartState` | `test_close_workspace_charts_prunes_chart_list_context` + merge |
| Cierre idempotente sin comprobar revisión | 409 también cuando no hay nada que podar | `test_noop_close_with_stale_revision_still_conflicts` |
| Revisión malformada = fail-open | 400 `workspace_invalid_revision` | `test_invalid_revision_is_rejected_instead_of_fail_open` |

Ejecutado: `pytest` (workspace/batch), `vitest` completo, `pnpm typecheck`, `ruff`, `mypy`
(3 módulos), y la sonda de integración
`docs/engineering/evidence/auditoria-persistencia-2026-11-02/probe_integration.py`
(PUT vigente/obsoleto, dos PUT concurrentes → `[200, 409]`, cierre de 2 de 3 pestañas,
reinicio real de la API y relectura, borrado del fixture).

Los E2E `GP-V170-02` y `GP-V170-04` (verde con Chromium) son evidencia del trabajo de
**columnas y panel de listas** que viaja en otro commit: `GP-V170-04` mide pistas de columna
y scroll horizontal del panel, no persistencia. No se usan como prueba de esta sección.
