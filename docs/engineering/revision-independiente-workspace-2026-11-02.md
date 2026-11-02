# Revisión independiente del commit de corrección — persistencia del workspace (2026-11-02)

> **AsOf:** 2026-11-02 · **Objeto:** commit **`d3236b5c`** (`fix(api,web): concurrencia optimista atómica y cierre
> de pestañas sin pérdidas`), 24 ficheros, `+2512/−69`, padre **`c50a512f`**.
> **Naturaleza:** revisión **PRE-SELLO**. No crea tag, no despliega y no reabre el dictamen del expediente
> [`evidence/auditoria-persistencia-2026-11-02`](./evidence/auditoria-persistencia-2026-11-02/README.md):
> comprueba **de forma independiente** que lo que allí se afirma es cierto sobre este árbol.
> **Veredicto:** el commit **reproduce** la evidencia comunicada. Queda apto para sellarse. Se declaran
> cuatro límites (`L-RIW-1`…`L-RIW-4`), ninguno de los cuales reabre los defectos P0/P1/P2 corregidos.

---

## 0. Qué se ha revisado y qué no

| Hecho | Cómo |
| --- | --- |
| El diff completo `c50a512f..d3236b5c`, fichero a fichero | lectura del diff, no de fragmentos citados |
| Higiene del commit (secretos, rutas absolutas, artefactos) | barrido de patrones sobre el diff |
| El CI del commit identificable (no del árbol de trabajo) | API de GitHub sobre `d3236b5c` |
| Las pruebas de persistencia contra PostgreSQL real | re-ejecutadas sobre `bolsa_v1_audit` |
| La sonda de proceso real **con reinicio** | re-ejecutada en `:8010` |
| Las suites web y de `@bolsa/shared` | re-ejecutadas **en un worktree limpio del commit** |

**No** se ha vuelto a ejecutar el E2E de Playwright (`GP-V170-02`/`GP-V170-04`): pertenecen a `c50a512f`
(columnas de listas) y no ejercen persistencia. Tampoco se ha desplegado nada en `:8000`.

La medición se hizo en dos sitios: las pruebas de backend y web «de área» sobre el árbol principal (que es
`d3236b5c` + los cambios sin commitear de GP-V190), y las **suites completas** sobre un worktree limpio del
commit (`git worktree add … d3236b5c`), que es el árbol que se sella. Cuando una cifra es del worktree se dice.

---

## 1. Diff: cada hallazgo del dictamen, anclado en código

| Hallazgo | Dónde vive la corrección | Comprobación de la revisión |
| --- | --- | --- |
| **P0-1** TOCTOU en revisión optimista | `workspace_repository.py`: el `UPDATE` condicional lleva `WHERE updated_at = :expected` en **una sola sentencia**; `rowcount == 0` ⇒ `WorkspaceVersionConflict` con la revisión vigente | no queda ningún `SELECT` + comparación en Python entre la lectura y la escritura en la ruta con revisión |
| **P0-2** keepalive sin revisión | `workspace-slice-account.ts::flushWorkspaceOnUnload`: con cierres pendientes **no** se reenvía el documento (solo `POST /charts/close`); sin ellos, el PUT de despedida lleva `expectedUpdatedAt` | el comentario del código dice explícitamente por qué no se envían ambos |
| **P1-3** comparación incompleta de snapshots | `chart-list-snapshot.ts::canonicalSnapshotJson` (claves ordenadas) sustituye la comparación por longitudes | 2 tests nuevos de parámetros/geometría con el mismo conteo |
| **P1-4** `isDirty` durante PUT | `saveToServer` compara **membresía** (`preparedInstr` vs `liveInstr`) y **contenido** (identidad de `workspace` antes del `await`) | 2 tests: cierre en vuelo y cambio de contenido en vuelo |
| **P1-7** derivación de Visualizados | `workspace-store-core.ts::deriveVisualizationEntries` se aplica en `prepareWorkspaceForSave` (orden de pestañas, sin duplicados, metadatos conservados) | test de derivación con dump obsoleto |
| **P2-5** límite de keepalive | `workspacePayloadByteLength` con `TextEncoder` (bytes UTF-8), tope `60 000` | test de acentos: bytes ≠ unidades UTF-16 |
| **P2-6** contexto huérfano y doble flush | `close_workspace_charts` anula `chartListContext` si su instrumento ya no tiene pestaña; `mergeWorkspaceChartState` poda al final; `createUnloadFlushGuard` evita el doble envío `beforeunload`+`pagehide` | 3 tests de contexto/snapshots huérfanos + 2 del guard |

Además, dos correcciones que el dictamen no enumeraba y que el diff sí incluye, ambas verificables:

- **Membresía `newest-wins`** en `mergeWorkspaceChartState`: se elimina la rama que **añadía** las pestañas del
  documento antiguo (`extrasFromOlder`). Es la causa raíz del «cierro todo y siguen apareciendo tras recargar»;
  sin ella, la poda del servidor se deshacía en la siguiente fusión.
- **Reconciliación de arranque sin reescritura** (`use-visualization-workspace-sync.ts`): solo persiste si el
  conjunto de instrumentos cambia, así que cargar la app no reinyecta las pestañas recién cerradas.

### 1.1 Contrato HTTP

Aditivo y coherente entre capas: `expectedUpdatedAt` en `UpdateWorkspaceRequestDto`, y
`POST /api/workspaces/{workspace_id}/charts/close` con `CloseWorkspaceChartsRequestDto`
(`instrumentIds` 1..500, `activeChartId`, `expectedUpdatedAt`). `openapi.json` y `schema.d.ts` viajan en el
mismo commit y `contract:check` da **OK** (medido, §3). Códigos de error: `409 workspace_conflict` (con
`currentUpdatedAt`) y `400 workspace_invalid_revision`; una revisión ilegible **no** degrada a «sin
comprobación».

### 1.2 Higiene del commit

Barrido sobre el diff completo: `ghp_…`, `sk-…`, `AKIA…`, bloques `PRIVATE KEY`, `C:\Users\…`, `/home/…`,
cadenas `postgresql://usuario:clave@`, `password = "…"` y `APP_PASSWORD =` ⇒ **0 coincidencias**. No hay
binarios, `.zip`, `.log`, `.env` ni `.pyc` en los 24 ficheros. Los únicos `postgresql://` del árbol están en la
evidencia del expediente y van con la clave **enmascarada** (`bolsa:***@`).

---

## 2. CI del commit identificable (acreditado, no inferido)

`d3236b5c` está en `origin/fix/059-060-proveedores` (el remoto apunta exactamente a ese SHA). Tres runs, ocho
checks, todos `success`:

| Run | Workflow | Jobs |
| --- | --- | --- |
| [`41482444534`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482444534) | `Python CI` | `quality`, `lifecycle-pg`, `paper-forward-pg`, `auto-v2-durable-pg`, `grammar-discovery-pg` |
| [`41482445056`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482445056) | `Optimize lab` | `battery` |
| [`41482444827`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41482444827) | `Fase 2 scientific` | `fase2-battery` |

Lo que importa para este dictamen: en `lifecycle-pg` el step **`Pytest persistencia del workspace PG`** existe
y está en `success` (no solo el job). Es decir, el gate nuevo que el commit añade al workflow **se ejecutó
sobre este mismo commit**, con PostgreSQL real y el esquema migrado por el step previo.

`git status` del worktree del commit: **limpio**. El `quality` del CI corre la suite sin
`test_workspace_persistence.py` (está en `--ignore`, con el motivo escrito) y esa exclusión es la declarada,
no una omisión silenciosa.

---

## 3. Reproducción local (medida hoy, no citada)

PostgreSQL local `localhost:5432`, `uv` con el `uv.lock` del repo, Node 22 / pnpm 10.12.1.

### 3.1 Suites completas sobre el worktree del commit

| Comando | Resultado |
| --- | --- |
| `pnpm --filter @bolsa/shared build` · `test` | **101 ficheros / 883 + 1 todo** |
| `pnpm --filter @bolsa/web test` | **364 ficheros / 2728 tests** |
| `pnpm --filter @bolsa/web typecheck` (`tsc -b --noEmit`) | limpio |
| `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `uv run python -m mypy … --follow-imports=silent` | **582 ficheros, 0 errores** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 contratos, 0 rotos** |

Las cifras **coinciden** con las del expediente (`364/2728`, `101/883`, `582`). Medido en el árbol principal
(con GP-V190 sin commitear) la suite web da `366/2737`: los 2 ficheros y 9 tests de diferencia son del trabajo
de gráficos, y por eso no se usan como cifra del sello.

### 3.2 Persistencia contra PostgreSQL real (`bolsa_v1_audit`)

```
alembic upgrade head                                  -> sin migraciones pendientes
pytest test_workspace_persistence.py test_batch_caps.py -q
14 passed in 3.68s
```

Los 10 casos del fichero cubren: poda de las tres vistas, cierre idempotente que devuelve el mismo documento,
`activeChartId` recalculado, cierre con revisión obsoleta, dos PUT con la misma revisión, revisión malformada,
y persistencia tras reiniciar la app.

### 3.3 Sonda de proceso real con reinicio (`:8010`)

Instancia levantada con `DATABASE_URL=…/bolsa_v1_audit API_PYTHON_PORT=8010`; su `/api/health/live` declara
`git_sha d3236b5c…` y `schema_revision 062_sync_settings_check_backfill`.

```
[PASS] crear workspace fixture -> 201
[PASS] PUT con revision vigente -> 200
[PASS] PUT con revision obsoleta devuelve 409
[PASS] revision malformada devuelve 400 (no fail-open)
[PASS] dos PUT concurrentes: exactamente uno gana -> [200, 409]
[PASS] cierre compacto de 2 de 3 pestanas -> 200
[PASS] respuesta del cierre: charts / visualizationEntries / snapshots podados -> ['SAN']
[PASS] respuesta del cierre: chartListContext huerfano eliminado
[PASS] respuesta del cierre: pestana activa recalculada
[PASS] cierre idempotente con revision obsoleta da 409
```

Proceso **matado** y **arrancado de nuevo** (PID distinto, health de nuevo con `d3236b5c`), y entonces:

```
[PASS] releer tras reiniciar la API -> 200
[PASS] la revision sobrevive al reinicio -> (20:29:44.279212, 20:29:44.279212)
[PASS] post-reinicio: charts / visualizationEntries / snapshots podados -> ['SAN']
[PASS] post-reinicio: chartListContext huerfano eliminado
[PASS] post-reinicio: pestana activa recalculada
[PASS] borrar fixture -> 204
```

Puerto `8010` queda **libre** y el fichero de estado temporal eliminado. La instancia de `:8000` no se tocó.

---

## 4. Aislamiento respecto a los datos reales

Medido por consulta read-only a `pg_database` + `workspaces` antes y después de toda la batería.

| Comprobación | Antes (20:28Z) | Después (20:36Z) |
| --- | --- | --- |
| Workspaces en `bolsa_v1` | 1 (`7e503dd5…`) | 1 (`7e503dd5…`) |
| Pestañas (`charts`) de ese workspace | 1 | 1 |
| `visualizationEntries` | 1 | 1 |
| Fixture de la sonda (`e35cf5fd…`) en `bolsa_v1` | ausente | ausente |
| Instancia `:8000` | escuchando (PID 18508) | escuchando (PID 18508) |

Todas las órdenes de pytest se ejecutaron con `DATABASE_URL` apuntando a `bolsa_v1_audit` porque el
`conftest.py` de `apps/api-python/tests` **purga residuos contra la BD vigente** en el teardown de sesión: una
variable heredada apuntando a `bolsa_v1` habría borrado cuentas e instrumentos reales.

### 4.1 Lo que este apartado **no** puede certificar retroactivamente

`L-RIW-1`. El expediente declara que `bolsa_v1` conservaba **214 pestañas** en `updated_at
2026-11-02 16:10:57.976+00`. Hoy, **antes** de que esta revisión escribiera nada, la fila ya tenía **1**
pestaña y `updated_at` en continuo movimiento (`20:28:17`, `20:31:15`…), coherente con la instancia de `:8000`
guardando la sesión viva del navegador. No se puede reconstruir el estado de las 16:10; lo que sí queda medido
es que el workspace, su id y su nombre no han cambiado durante esta revisión y que ninguna escritura de la
sonda cayó en `bolsa_v1`.

`L-RIW-2`. En `bolsa_v1_audit` persiste un workspace `493f5875…` («Visualizados», 1 pestaña, `activeChartId
t1`, `updated_at 15:50:57Z`) con la forma exacta de un fixture de la sonda anterior (`t0/t1/t2`). Es residuo de
la sesión de auditoría de las 15:50, no aparece en ninguna otra base y **no** está en `bolsa_v1`; se deja
intacto para no borrar estado ajeno a esta revisión. Matiza el «fixture eliminado con 204» del expediente: el
borrado ocurrió, pero no fue el único fixture creado.

`L-RIW-3`. En esta máquina el binario `mypy` del entorno está bloqueado por el control de aplicaciones de
Windows (`os error 4551`); el gate se ejecutó como `uv run python -m mypy`, mismo módulo y mismas rutas. El CI
usa el entry point normal y está en verde.

`L-RIW-4`. No se ha re-ejecutado el E2E de navegador. `GP-V170-02`/`GP-V170-04` pertenecen a `c50a512f` y su
evidencia no se usa aquí como prueba de persistencia (el propio expediente lo advierte).

---

## 5. Veredicto

1. Las seis correcciones del dictamen **existen en el árbol** y están en el sitio que se les supone; no hay
   ninguna que se apoye en un fragmento citado sin código detrás.
2. El **CI verde es del commit**, no del árbol de trabajo, e incluye el gate nuevo de persistencia ejecutado.
3. Las cifras comunicadas **se reproducen** sobre el commit: `14 passed` de persistencia, `364/2728` web,
   `101/883` shared, `582` ficheros de mypy, ruff limpio, contrato OK, y la sonda con reinicio en `PASS`.
4. La concurrencia real se comporta como se declaró: dos PUT con la misma revisión dan **exactamente**
   `[200, 409]`; una revisión ilegible da **400**; el cierre idempotente con revisión obsoleta da **409**.

Queda por tanto **autorizado el sellado** de `d3236b5c` como `v2.88.177-beta`. Lo que este documento **no**
autoriza es llamar «desplegada» a la corrección: `:8000` sigue ejecutando código anterior, y el despliegue no
forma parte de este sello.
