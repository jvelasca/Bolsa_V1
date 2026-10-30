# Seguimiento — General y espacios de trabajo (2026-10-30)

> Alcance: pestaña **Configuración → General**, gestor **Espacio de trabajo**, store de espacios y primitivas de diálogo.
> Docs de referencia: [WORKSPACE_PERSISTENCE.md](../WORKSPACE_PERSISTENCE.md), [UI_PREFS_LOCALSTORAGE.md](../UI_PREFS_LOCALSTORAGE.md), [CONFIGURATION_MODEL.md](../CONFIGURATION_MODEL.md).
> Evidencia: [`evidence/general-espacios-2026-10-30/`](./evidence/general-espacios-2026-10-30/).

---

## 1. Decisión de estructura

No se añade pestaña nueva. El modal **«Espacio de trabajo»** (chip de la barra superior y botón «Gestionar espacios…» de General) es la **única** superficie de edición de lo que pertenece al espacio. `General` se queda con lo de la app/dispositivo y un **resumen de solo lectura**.

| Ámbito | Superficie | Persistencia |
|--------|------------|--------------|
| Tema, Densidad | General → Apariencia | `bolsa-ui-prefs-v1` |
| HUD Mercado (panel/gráfico) | General → Mercado | `bolsa-mercado-decision-surface-v1` |
| Diseño de Mercado, Restablecer paneles | Gestor → Diseño en este dispositivo | `bolsa-trading-layout-v1` |
| Autoguardado, Preferido, Plantilla de gráficos nuevos | Gestor → Preferencias del espacio activo | `PUT /api/workspaces/:id` |
| Gráficos, listas, dibujos, plantillas | Gestor → catálogo | `/api/workspaces` |

Motivo de no mover Tema/Densidad al espacio: son globales por dispositivo; si vivieran en el espacio el usuario creería que cambian al cambiar de espacio.

---

## 2. Defectos corregidos

| ID | Síntoma real | Causa | Corrección | Test |
|----|--------------|-------|------------|------|
| **WS-D1** | Exportar JSON quitaba el punto ámbar y el siguiente pull pisaba cambios sin guardar | `exportJson` hacía `set({ isDirty: false })` sin guardar | Exporta `prepareWorkspaceForSave(workspace)` y **no** toca `isDirty`; el gestor muestra «JSON descargado… los cambios siguen sin guardar» | `workspace-preferences.test.ts` · `workspace-picker-dialog.test.tsx` |
| **WS-D2** | La estrella «preferido al arrancar» saltaba al último espacio guardado | `saveToServer` y `flushWorkspaceOnUnload` enviaban `isDefault: preferences.openOnStartup` (default `true`) | Se deja de enviar `isDefault` al guardar; nueva acción `setPreferred(enabled)` → `PUT { isDefault }`; `applyServerWorkspace` fija `openOnStartup` desde `is_default` | `workspace-preferences.test.ts` (3 casos) |
| **WS-D3** | Desactivar el autoguardado no persistía | Al apagarlo se saltaba el debounce de autoguardado | `setAutoSave` guarda de inmediato (`saveToServer`) tras el `set` | `workspace-preferences.test.ts` · `workspace-picker-dialog.test.tsx` |
| **WS-D4** | Al cambiar de espacio reaparecían pestañas y dibujos del anterior | `chartPersistBackup` no guarda id de espacio y no se reescribía | Helper `workspaceBackupPatch` + `writeChartPersistBackupSync` en `switchWorkspace`, `createWorkspace`, `duplicateWorkspace`, `reloadActiveFromServer`, `deleteWorkspaceById`; el borrado además purga `recents` | `workspace-preferences.test.ts` |
| **WS-D5** | Duplicar generaba nombres idénticos `(copia)` | Nombre fijo sin comprobar el catálogo | `nextCopyName(name, summaries)` → `(copia)`, `(copia 2)`, `(copia 3)`… | `workspace-preferences.test.ts` (4 casos) |
| **WS-D6** | Checkboxes de autoguardado y preferido duplicados entre General y el gestor | Ambas superficies editaban lo mismo | General pasa a resumen de solo lectura; edición solo en el gestor | `general-settings-section.test.tsx` |
| **WS-D7** | Escape en el input de renombrar cerraba también el diálogo padre | Cada `Dialog` escuchaba Escape en `document` sin orden | Pila de diálogos en `dialog.tsx`: solo el superior se cierra; el input hace `stopPropagation` y cancela solo el renombrado | `workspace-picker-dialog.test.tsx` |
| **WS-D8** | `id="dialog-title"` fijo → ids duplicados con dos modales abiertos | Constante en el JSX | `useId()` + `aria-labelledby` único por instancia | (cubierto por los tests de modal anidado) |
| **WS-D9** | Fallo de bootstrap se mostraba como «Aún no hay espacios» | No había estado de error separado | `loadError` en el store + «No se pudieron cargar los espacios» con `Reintentar` (`bootstrapWorkspaces`) y `role="alert"` | `workspace-picker-dialog.test.tsx` |
| **WS-D10** | Cambiar de cuenta activa silenciaba el error del servidor | `void activate.mutateAsync(id)` sin `catch` | `handleActivate` con estado de error (`role="alert"`) y aviso de que el cambio es de toda la app | — (manual) |
| **WS-D11** | Cambiar de herramienta de dibujo borraba el tema; al recargar volvía el oscuro | `uiTheme`/`uiDensity` se persistían en `bolsa-chart-draw-tool-session`, y `writeDrawToolSessionLocal` reescribe esa clave sin ellos | Clave propia `bolsa-ui-prefs-v1` con `partialize` de solo `{uiTheme, uiDensity}`; migración de una vez desde el blob antiguo; la sesión de dibujo sigue en su clave | `ui-store-persistence.test.ts` (5 casos) |

---

## 3. Cambios por archivo

| Archivo | Cambio |
|---------|--------|
| `apps/web/src/stores/ui-store.ts` | `UI_PREFS_STORAGE_KEY = "bolsa-ui-prefs-v1"`; `partialize` solo tema/densidad; `merge` con migración desde `bolsa-chart-draw-tool-session`; `"sounds"` fuera de `PlatformConfigTab` |
| `apps/web/src/lib/draw-tool-session-storage.ts` | Sin cambios de contrato: ya no comparte clave con el tema |
| `apps/web/src/stores/workspace-store-core.ts` | `applyServerWorkspace` lee `isDefault`; `loadError` en el estado; `workspaceBackupPatch`; `nextCopyName` |
| `apps/web/src/stores/workspace-slice-account.ts` | `saveToServer`/`flushWorkspaceOnUnload` sin `isDefault`; `setPreferred`; `setAutoSave` guarda; backup al cambiar/crear/duplicar/recargar/borrar; `exportJson` mantiene `isDirty`; `loadError` en bootstrap |
| `apps/web/src/stores/workspace-store.ts` | `loadError: null` en el estado inicial |
| `apps/web/src/features/settings/general-settings-section.tsx` | Reescrito: Apariencia / Mercado / resumen del espacio + «Gestionar espacios…» |
| `apps/web/src/features/config/platform-config-dialog.tsx` | Fuera el `case "sounds"`; Cuenta activa con error visible y copy de alcance global |
| `apps/web/src/features/workspace/workspace-picker-dialog.tsx` | Reescrito: catálogo, preferencias del servidor, diseño del dispositivo, pie de acciones, estados de carga/error, `aria-busy`/`aria-label`/`role="alert"` |
| `apps/web/src/components/ui/dialog.tsx` | Pila de Escape, `useId` para el título, `DialogTabs` con `role="tablist"/"tab"`, `aria-selected`, roving tabindex y flechas |
| `apps/web/src/features/settings/chart-platform-section.tsx` | Texto de ayuda sin «sonidos» y con el reparto nuevo |

---

## 4. Tests

Nuevos (32 casos):

| Archivo | Casos |
|---------|-------|
| `apps/web/src/stores/workspace-preferences.test.ts` | 12 — `saveToServer` sin `isDefault`; keepalive sin `isDefault`; `setPreferred`; `applyServerWorkspace`; `setAutoSave`; backup al cambiar; borrado purga `recents`; export sin limpiar dirty; `nextCopyName` ×4 |
| `apps/web/src/features/workspace/workspace-picker-dialog.test.tsx` | 8 — estructura; plantilla; autoguardado; preferido; export sin dirty; error de carga + reintento; Escape en renombrado; borrado con confirmación y error |
| `apps/web/src/features/settings/general-settings-section.test.tsx` | 7 — ámbitos; sin diseño de Mercado; sin checkboxes duplicados; tema; densidad; resumen; abrir gestor |
| `apps/web/src/stores/ui-store-persistence.test.ts` | 5 — clave nueva; sin herramienta de dibujo; tema sobrevive a la escritura legacy; migración; la clave nueva gana |

Gates (evidencia en `evidence/general-espacios-2026-10-30/`):

| Gate | Resultado | Fichero |
|------|-----------|---------|
| `vitest run` (área) | 4 archivos / 32 tests ✅ | `vitest-area.txt` |
| `vitest run` (web completo) | 351 archivos / 2636 tests ✅ (antes: 347 / 2604) | `vitest-web-full.txt` |
| `tsc -b --noEmit` | ✅ | `tsc.txt` |
| `eslint` (web) | 0 errores, 23 warnings preexistentes ✅ | `eslint.txt` |
| `pnpm contract:check` | ✅ sin cambios de DTO | `contract-check.txt` |
| Python | `test_dia_d_bump_guard.py` ← **2 passed** (bump `2.11.173-beta`); sin cambios en `packages/py` ni `apps/api-python` salvo los `meta.bump` | — |

---

## 5. Verificación en vivo (stack local)

Capturas: `ui-general.png` (General), `ui-general-light.png` (tema claro aplicado), `ui-modal-espacio.png` (gestor con preferencias y diseño).

| Caso | Cómo | Resultado |
|------|------|-----------|
| **WS-D11** separación de claves | Tema → Claro; leer `localStorage` | `bolsa-ui-prefs-v1 = {uiDensity:"comfortable", uiTheme:"light"}`; `bolsa-chart-draw-tool-session` solo `chartDrawTool` + `lastDrawToolByGroup` (con datos reales previos) ✅ |
| **WS-D11** el tema sobrevive a la escritura legacy | Reescribir `bolsa-chart-draw-tool-session` con `chartDrawTool:"hline"` y recargar | `data-theme="light"` tras recargar ✅ |
| **WS-D3** autoguardado persiste | Desmarcar en el gestor → `GET /api/workspaces/{id}` | `autoSave=True → False` de inmediato ✅ (antes no se guardaba) |
| **WS-D2** guardar no mueve la estrella | Desmarcar preferido → «Guardar actual» → `GET` | `isDefault=False` antes y después del guardado ✅ |
| **WS-D2** `is_default` es la autoridad | Volver a marcar preferido (clic real) → `GET` | `isDefault=True`; `preferences.openOnStartup` sigue en el documento como campo legado ✅ |
| **WS-D7** Escape por capas | Escape con el gestor abierto encima de Configuración | Cierra solo el gestor; Configuración sigue montada ✅ |
| Estado del operador | Tras las pruebas | `isDefault=True`, `autoSave=True`, tema `dark` (restaurado) ✅ |

Detalle de las transiciones de API: `evidence/general-espacios-2026-10-30/api-isdefault-autosave.txt`.

---

## 6. Límites y pendientes

- **Fuera de alcance** (no elegido): importar JSON, buscador de espacios, deshacer borrado, focus trap completo en los diálogos.
- `preferences.openOnStartup` se mantiene en el documento por compatibilidad, pero la UI y el arranque usan `is_default`.
- El contador «Listas en el carrusel» del resumen cuenta `list.carouselListIds`; con carrusel no inicializado muestra `Ninguna` (no distingue «sin datos» de «vacío»).
- Los 23 warnings de ESLint son preexistentes (hooks con expresiones lógicas en otros módulos).
- Cambiar de cuenta activa se validó por lectura de código + `role="alert"`; no se forzó un fallo del servidor en vivo para no dejar la cuenta inconsistente.
