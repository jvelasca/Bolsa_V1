# Evidencia `v2.88.177-beta` — guardar el espacio de trabajo deja de perder pestañas

## 1. Qué publica este sello

Sello de **corrección** posterior a `2.11.176-beta`, que cierra la auditoría de persistencia del workspace
del 2026-11-02. No mueve motor ni decisión:

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **SIN migración** (`head` sigue `062_sync_settings_check_backfill`).
- **Contrato HTTP aditivo**: `expectedUpdatedAt` en `PUT /api/workspaces/{id}` y endpoint nuevo
  `POST /api/workspaces/{id}/charts/close` (`openapi.json`/`schema.d.ts` regenerados en el mismo commit;
  `contract:check` **OK**).
- **Bump** `2.11.176-beta` → `2.11.177-beta` (13 `meta.bump`, **14 literales**; `test_dia_d_bump_guard`
  **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` no se toca).
- **Pin PAPER re-anclado** después del bump: `apps` `246edde7…` / `packages` `0f8efb9b…` (`freeze OK`).

El objeto que se publica es el commit de corrección **`d3236b5c`** (24 ficheros, `+2512/−69`), revisado de
forma independiente en [`revision-independiente-workspace-2026-11-02.md`](../../revision-independiente-workspace-2026-11-02.md).

### 1.1 Los seis defectos y su ancla

| Id | Defecto | Ancla en el árbol |
| --- | --- | --- |
| P0-1 | TOCTOU entre comparar y escribir la revisión | `workspace_repository.py`: `UPDATE … WHERE updated_at = :expected` en una sentencia |
| P0-2 | `keepalive` de cierre sin revisión | `workspace-slice-account.ts::flushWorkspaceOnUnload` |
| P1-3 | snapshots «iguales» por longitud | `chart-list-snapshot.ts::canonicalSnapshotJson` |
| P1-4 | `isDirty` perdía cambios en vuelo | `workspace-slice-account.ts::saveToServer` (membresía + contenido) |
| P1-7 | Visualizados obsoleto respecto a pestañas | `workspace-store-core.ts::deriveVisualizationEntries` |
| P2-5 | tope de keepalive en caracteres | `workspace-store-core.ts::workspacePayloadByteLength` |
| P2-6 | contexto huérfano y doble flush | `close_workspace_charts` (poda) + `unload-flush-guard.ts` |

Y la causa raíz del síntoma visible («cierro pestañas y reaparecen»): `mergeWorkspaceChartState` dejó de
**añadir** las pestañas del documento antiguo; la membresía la dicta el documento más reciente.

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Que el entorno habitual (`:8000`) ya ejecute la corrección** | la instancia de desarrollo no se reinició; este sello no despliega |
| **El E2E de navegador de esta incidencia** | `GP-V170-02`/`GP-V170-04` son de `c50a512f` (columnas de listas) y no ejercen persistencia; no se re-ejecutaron |
| **La cifra de 214 pestañas del expediente** | no es reproducible a posteriori: la fila de `bolsa_v1` tenía **1** pestaña antes de empezar esta revisión (`L-RIW-1`) |
| **Que el cierre al salir funcione con cualquier tamaño de documento** | por encima de `60 000` bytes UTF-8 el flush **no** se envía (decisión explícita: mejor no enviar que perder la petición); lo que se acredita es que ese camino ya no miente |
| **Rentabilidad ni operativa** | AUTO **OFF**; PAPER **`INCONCLUSIVE`** |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Corrección (`d3236b5c`) | `apps/api-python/src/bolsa_api/api/v1/routes/workspaces.py`, `.../schemas/workspaces.py`, `apps/api-python/tests/test_workspace_persistence.py` (**nuevo**), `packages/py/application/src/bolsa_application/workspaces.py`, `packages/py/infrastructure/.../workspace_repository.py`, `apps/web/src/lib/{api,chart-list-snapshot,unload-flush-guard}.ts` (+ 4 tests), `apps/web/src/stores/{workspace-store-core,workspace-slice-account,workspace-slice-charts,workspace-store}.ts` (+ 1 test), `apps/web/src/features/workspace/*`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/lib/api-keepalive.test.ts`, `docs/WORKSPACE_PERSISTENCE.md`, `docs/engineering/evidence/auditoria-persistencia-2026-11-02/*`, `.github/workflows/python-ci.yml` |
| Revisión independiente (`70edc251`) | `docs/engineering/revision-independiente-workspace-2026-11-02.md` |
| Bump (`7119e9bc`) | `package.json`, `CHANGELOG.md`, 13 `meta.bump` de `apps/api-python/scripts` |
| Pin (`4ba03ed6`) | `scripts/lib/window-forward.mjs` |

## 4. Verificación medida (local, 2026-11-02)

Cada fila es una ejecución distinta; no se suman. Las suites completas se midieron en un **worktree limpio del
commit** (`git worktree add … d3236b5c`), no en el árbol con trabajo sin commitear.

| Comprobación | Comando | Salida | Código |
| --- | --- | --- | --- |
| Persistencia PG | `pytest apps/api-python/tests/test_workspace_persistence.py apps/api-python/tests/test_batch_caps.py` (BD `bolsa_v1_audit`) | **14 passed** (`3,68 s`) | `0` |
| Sonda real + reinicio | `probe_integration.py setup` → kill/arranque → `verify` → `cleanup` (`:8010`) | **12 `PASS`** + **7 `PASS`** post-reinicio + **204** | `0` |
| Suites web | `pnpm --filter @bolsa/web test` | **364 ficheros / 2728 tests** | `0` |
| Suites shared | `pnpm --filter @bolsa/shared test` | **101 / 883** + 1 todo | `0` |
| Typecheck | `pnpm --filter @bolsa/web typecheck` | limpio | `0` |
| Contrato | `pnpm contract:check` | **OK** | `0` |
| Ruff | `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** | `0` |
| mypy | `uv run python -m mypy … --follow-imports=silent` | **582 ficheros, 0 errores** | `0` |
| Import-linter | `uv run lint-imports --config packages/py/.importlinter` | **4 contratos, 0 rotos** | `0` |
| Bump guard | `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** | `0` |
| Pin | `node scripts/window-pin.mjs --check` | **`freeze OK`** | `0` |
| Runner del pin | `pnpm window:test` | **50 / 50** | `0` |

Cadena del pin, medida en cada paso:

| Commit | `appsHash` | `packagesHash` | `window:freeze` |
| --- | --- | --- | --- |
| `d3236b5c` (corrección) | `5ab3cf5b…` | `0f8efb9b…` | `TREE_MOVED` respecto del pin `.176` (previsto) |
| `7119e9bc` (bump) | `246edde7…` | `0f8efb9b…` (sin cambio) | **`freeze OK`** tras el re-anclaje |
| `4ba03ed6` (pin) | `246edde7…` | `0f8efb9b…` | **`freeze OK`** |

Solo `appsHash` se movió, que es lo que produce tocar `apps/api-python/scripts`; `packages/py` no cambió en el
bump.

## 5. CI del commit de corrección (acreditado)

`d3236b5c` en `origin/fix/059-060-proveedores`; **8 checks `success`** en tres runs:

| Run | Workflow | Jobs |
| --- | --- | --- |
| [`41482444534`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482444534) | `Python CI` | `quality`, `lifecycle-pg`, `paper-forward-pg`, `auto-v2-durable-pg`, `grammar-discovery-pg` |
| [`41482445056`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482445056) | `Optimize lab` | `battery` |
| [`41482444827`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482444827) | `Fase 2 scientific` | `fase2-battery` |

El step **`Pytest persistencia del workspace PG`** del job `lifecycle-pg` figura en `success`: el gate que el
propio commit añade al workflow **se ejecutó** sobre este commit, con PostgreSQL real y esquema migrado.

## 6. Publicación

| Paso | Estado |
| --- | --- |
| Corrección `d3236b5c` + CI | hecho |
| Revisión independiente `70edc251` | hecho |
| Bump `2.11.177-beta` `7119e9bc` | hecho |
| Re-anclaje del pin `4ba03ed6` | hecho |
| Tag anotado `v2.88.177-beta` | sobre el commit de este documento |
| `Release tag CI` del tag | **§6.1** (POST-TAG) |
| GitHub Release | **§6.1** (POST-TAG) |
| Despliegue en `:8000` | **no realizado** y fuera de este sello |

## 7. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Dos PUT con la misma revisión no pueden ganar ambos | `test_two_updates_from_the_same_revision_do_not_both_win` y la sonda (`[200, 409]`) |
| 2 | Una revisión malformada no desactiva la comprobación | `test_invalid_revision_is_rejected_instead_of_fail_open` |
| 3 | El cierre poda las tres vistas y el contexto huérfano | `test_close_workspace_charts_prunes_all_three_views` + 3 asserts de la sonda |
| 4 | El estado podado sobrevive al reinicio | `test_pruned_charts_survive_an_api_restart` + `verify` de la sonda |
| 5 | La fusión no resucita pestañas cerradas | `mergeWorkspaceChartState` membresía newest-wins (9 tests) |
| 6 | El tope de keepalive se mide en bytes | `workspacePayloadByteLength` con acentos |
| 7 | El flush no se envía dos veces | `createUnloadFlushGuard` (2 tests) |
| 8 | El bump es coherente en los 14 literales | `test_dia_d_bump_guard` (`2 passed`) |
| 9 | El pin casa con el árbol del sello | `pnpm window:freeze` ⇒ `freeze OK`; rojo en el step del CI del tag |
| 10 | El motor no cambió | el diff no toca `packages/py/domain`, analytics ni workers AUTO; el `replay-repro` del CI del tag lo mide byte a byte (§6.1) |

## 8. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | `d3236b5c`: corrección + tests + evidencia del expediente en un solo commit; CI verde por commit. |
| 2 | `70edc251`: revisión independiente (diff, higiene, CI, reproducción, aislamiento). |
| 3 | `7119e9bc`: bump `2.11.177-beta`; bump guard `2 passed`. |
| 4 | `4ba03ed6`: re-anclaje del pin; `freeze OK` y `window:test` 50/50. |
| 5 | Este documento y el tag anotado `v2.88.177-beta` sobre él. |
| 6 | `Release tag CI` y GitHub Release: **§6.1**, anotados POST-TAG. |
