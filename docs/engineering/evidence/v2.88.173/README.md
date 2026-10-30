# Evidencia `v2.88.173-beta` — la configuración se ordena por ámbito y el espacio deja de falsear su estado

## 1. Qué publica este sello

Sello **UI-only** sobre `2.11.172-beta`. No mueve motor, decisión ni contrato HTTP:

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`contract:check` **OK**; sin
  `contract:gen`).
- **SIN migración**: `head` sigue `060_provider_check_policy`.
- **Bump** `2.11.172-beta` → `2.11.173-beta` (+ los **13** `meta.bump`; `test_dia_d_bump_guard`
  **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` **no** se toca).
- **Publicación**: rama + **tag anotado `v2.88.173-beta`** (dispara `Release tag CI`).

Dos cambios de producto:

1. **`Configuración → General`** deja de mezclar ámbitos. Queda en **Apariencia** (tema y densidad),
   **Mercado** (colocación de la superficie de decisión) y **Espacio de trabajo** (resumen de solo
   lectura + «Gestionar espacios…»).
2. **Modal «Espacio de trabajo»** separa **catálogo**, **preferencias del servidor** (`autoSave`,
   `is_default`, `newChartTemplateChartId`), **diseño del dispositivo** (`namedLayoutId`, reset de
   paneles) y acciones de pie.

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Rentabilidad** | Un sello de UI no añade evidencia operativa. AUTO **OFF**; PAPER **`INCONCLUSIVE`**. |
| **Sync del *chrome* del espacio** | `namedLayoutId` y el reset de paneles siguen en `localStorage` (`bolsa-trading-layout-v1`), por dispositivo; no viajan al servidor. |
| **Workspace multiusuario / cuentas compartidas** | El dueño sigue siendo la cuenta activa; no se añade modelo de permisos. |
| **La página `/fiscal`, las cuentas y auto ops** | Ese trabajo sigue **sin commitear** en el árbol y queda **fuera** de este sello. |
| **La suite completa del frontend** | La mide el CI de la rama y del tag; este documento no adelanta cifras no medidas sobre el árbol exacto del sello. |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Store | `stores/ui-store.ts`, `stores/workspace-store-core.ts`, `stores/workspace-slice-account.ts`, `stores/workspace-store.ts` |
| UI | `components/ui/dialog.tsx`, `features/settings/general-settings-section.tsx`, `features/workspace/workspace-picker-dialog.tsx`, `features/config/platform-config-dialog.tsx`, `features/settings/chart-platform-section.tsx` |
| Tests | `stores/ui-store-persistence.test.ts`, `stores/workspace-preferences.test.ts`, `features/workspace/workspace-picker-dialog.test.tsx`, `features/settings/general-settings-section.test.tsx` |
| Docs | `docs/CONFIGURATION_MODEL.md`, `docs/UI_PREFS_LOCALSTORAGE.md`, `docs/WORKSPACE_PERSISTENCE.md`, `docs/engineering/seguimiento-ui-general-espacios-2026-10-30.md`, `CHANGELOG.md`, `PROJECT_STATE.md`, este README |
| Bump | `package.json` + `meta.bump` de `v2_87`, `v2_89`…`v2_100` (el literal congelado `2.11.0-beta` de `v2_87` **no** se toca) |

## 4. Verificación medida (local)

| Comprobación | Resultado |
| --- | --- |
| `vitest run` (área nueva) | **4 archivos / 32 tests** |
| `tsc -b --noEmit` | **OK** |
| `eslint` (web) | **0 errores**, 23 avisos preexistentes |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` sin diff |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:freeze` | **`freeze OK`** tras re-anclar el pin |

Evidencia capturada en [`evidence/general-espacios-2026-10-30/`](../general-espacios-2026-10-30/):
`vitest-area.txt`, `vitest-web-full.txt`, `tsc.txt`, `eslint.txt`, `contract-check.txt`,
`api-isdefault-autosave.txt` y las capturas `ui-general.png`, `ui-general-light.png`,
`ui-modal-espacio.png`.

## 5. Verificación en vivo (stack local, 2026-10-30)

| Caso | Cómo | Resultado |
| --- | --- | --- |
| Separación de claves (`WS-D11`) | Tema → Claro; leer `localStorage` | `bolsa-ui-prefs-v1 = {uiDensity:"comfortable", uiTheme:"light"}`; `bolsa-chart-draw-tool-session` solo `chartDrawTool` + `lastDrawToolByGroup` |
| El tema sobrevive a la escritura legacy (`WS-D11`) | Reescribir la clave de dibujo y recargar | `data-theme="light"` tras recargar |
| Autoguardado persiste (`WS-D3`) | Desmarcar en el gestor → `GET /api/workspaces/{id}` | `autoSave=True → False` de inmediato |
| Guardar no mueve la estrella (`WS-D2`) | Desmarcar preferido → «Guardar actual» → `GET` | `isDefault=False` antes y después |
| `is_default` es la autoridad (`WS-D2`) | Volver a marcar preferido (clic real) → `GET` | `isDefault=True`; `preferences.openOnStartup` sigue como campo legado |
| Escape por capas (`WS-D7`) | Escape con el gestor encima de Configuración | Cierra solo el gestor; Configuración sigue montada |
| Estado del operador | Tras las pruebas | `isDefault=True`, `autoSave=True`, tema `dark` (restaurado) |

## 6. Límites declarados

- **Fuera de alcance** (no elegido): importar JSON, buscador de espacios, deshacer borrado, focus trap
  completo en los diálogos.
- `preferences.openOnStartup` se mantiene en el documento por compatibilidad, pero la UI y el arranque
  usan `is_default`.
- El contador «Listas en el carrusel» del resumen cuenta `list.carouselListIds`; con carrusel no
  inicializado muestra «Ninguna» (no distingue «sin datos» de «vacío»).
- Los 23 avisos de ESLint son preexistentes (hooks con expresiones lógicas en otros módulos).
- Cambiar de cuenta activa se validó por lectura de código + `role="alert"`; no se forzó un fallo del
  servidor en vivo para no dejar la cuenta inconsistente.

## 7. Publicación (POST-PUSH)

| Dato | Valor |
| --- | --- |
| Rama | `fix/059-060-proveedores` |
| Commit del sello | _pendiente de rellenar tras el commit_ |
| Re-anclaje del pin | _pendiente_ |
| Tag | `v2.88.173-beta` (anotado) |
| Runs de CI | _pendiente de medir_ |

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Tema y densidad no dependen de la sesión de dibujo | `ui-store-persistence.test.ts` reescribe la clave legacy y exige que `bolsa-ui-prefs-v1` gane |
| 2 | Guardar el espacio no cambia `is_default` | `workspace-preferences.test.ts` inspecciona el cuerpo de `saveToServer` y del `keepalive` |
| 3 | `is_default` es la única autoridad del arranque | `applyServerWorkspace` fija `openOnStartup` desde `isDefault` |
| 4 | El autoguardado se persiste al cambiarlo | `setAutoSave` llama a `saveToServer`; test dedicado |
| 5 | El backup del gráfico no sobrevive al cambio de espacio | `workspaceBackupPatch` + test de cambio y de borrado con purga de `recents` |
| 6 | Exportar no limpia el estado sucio | test de `exportJson`: `isDirty` sigue `true` |
| 7 | Escape cierra solo el diálogo superior | test de modal anidado en `workspace-picker-dialog.test.tsx` |
| 8 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 9 | El pin casa con el árbol | `pnpm window:freeze` ⇒ `freeze OK` |
