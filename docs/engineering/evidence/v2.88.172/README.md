# Evidencia `v2.88.172-beta` — la ventana BD estrena su única acción de mantenimiento

## 1. Qué publica este sello

Sello de **funcionalidad de mantenimiento** sobre `2.11.171-beta`. **Configuración → BD** deja de ser
solo informativa y añade **una** acción —**crear una copia ahora**— con confirmación escrita, un solo
trabajo a la vez, rol `admin` cuando la auth está activa, producción prohibida y auditoría. El resto del
mantenimiento (VACUUM/ANALYZE, restaurar, podar sin crear, aplicar migraciones) sigue **en CLI**.

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **AUTO OFF**.
- **Contrato HTTP ADITIVO**: `GET /api/database/maintenance` y `POST /api/database/backup`;
  `openapi.json` y `schema.d.ts` regenerados, `contract:check` verde.
- **SIN migración**: `head` sigue `060_provider_check_policy`.
- **Bump** `2.11.171-beta` → `2.11.172-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard` **2 passed**).
- **Publicación decidida**: empujar la rama y **auditar en CI**; **sin tag y sin GitHub Release** en
  este acto.

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Rentabilidad** | Crear copias no añade evidencia operativa. AUTO **OFF**, PAPER **`INCONCLUSIVE`**. |
| **Un backup inmune a fallos del host** | El volcado exige `node` y `pg_dump`/Docker **en la máquina de la API**; si faltan, la ruta responde **503** con código, no simula. |
| **Exclusión frente a un dump manual** | El cerrojo es `pg_try_advisory_lock(774104254)`: cubre la ruta HTTP entre procesos, **no** un `pnpm db:dump` lanzado a mano en paralelo (el manifest y `O_EXCL` evitan colisiones de fichero). |
| **Restaurar desde la UI** | No existe y no se añade aquí: sobrescribe datos. |
| **La auditoría 2 (D-1–D-4)** | Sus cambios siguen **sin commitear** en el árbol y quedan **fuera** de este sello. |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Script | `scripts/db-dump.mjs` (`--dir`) |
| Aplicación | `database_backup.py` (nuevo), `database_maintenance.py` (`summarize_backup_snapshot`) |
| Infraestructura | `database/backup_runner.py`, `database/backup_inventory.py`, `database/schema_contract.py` |
| API | `routes/database.py`, `schemas/database_maintenance.py`, `api/dependencies.py`, `auth/roles.py` |
| Web | `features/config/database-maintenance-panel.tsx` (+ test), `features/config/database-config-panel.tsx`, `lib/api.ts`, `features/help/*` |
| Contrato | `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `packages/shared/src/types.ts` |
| Bump | `package.json` + `meta.bump` de `v2_87`, `v2_89`…`v2_100` (el literal congelado `2.11.0-beta` de `v2_87` **no** se toca) |
| Docs | `CHANGELOG.md`, `PROJECT_STATE.md`, `handoff-061`, `handoff-062`, este README |

## 4. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest packages/py/application/tests` | **3 034 passed** |
| `pytest packages/py/infrastructure/tests` | **238 passed** |
| `pytest apps/api-python/tests/test_database_backup_api.py test_database_maintenance_api.py` | **14 passed** |
| `vitest src/features/config/database-maintenance-panel.test.tsx` | **5 passed** |
| `ruff` + `mypy` (strict) sobre los ficheros tocados | **0 errores** |
| `pnpm --filter @bolsa/web typecheck` | **OK** |
| `pnpm contract:check` | **OK** |
| `pytest tests/test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm window:freeze` | **`freeze OK`** tras re-anclar el pin |

Las suites completas (`web`, `shared`, `pytest` de API) las mide el **CI de la rama**; este documento
**no** adelanta cifras que no se hayan medido.

## 5. Verificación en vivo (stack local, 2026-10-29)

| Paso | Evidencia |
| --- | --- |
| `POST /api/database/backup` con `{"confirm":"no"}` | **422** `confirmation_required` |
| `POST /api/database/backup` con `{"confirm":"COPIAR"}` | **200** — `bolsa_v1-20261029-145347-232.sql`, **14 963 887 B**, `sha256 dcb9c49b…`, `schemaRevision 060_provider_check_policy`, **780 ms**, `pruned 0` |
| Artefactos | fichero + `.sha256` en `db-backups/` y entrada nueva en `backups-manifest.json` |
| Auditoría | línea en `logs/agent/db-maintenance.jsonl` con `action`, `actor`, `ok`, `file`, `bytes`, `durationMs` |
| Tarjeta | `GET /api/database/maintenance` → `backups.status` pasa de `warning` a **`ok`**, `ageHours ≈ 0` |
| `--dir` | volcado en un directorio temporal: escribe ahí y **no** en `db-backups/` |
| UI real (`:5173` → Configuración → BD) | 6 bloques de diagnóstico + botón «Crear copia ahora» con su campo `COPIAR`; el proxy de Vite devuelve **422** con confirmación inválida (ruta viva) |

## 6. Límites declarados

- La copia abre **su propia conexión** con `pg_dump`: el diagnóstico puede mostrar una conexión más
  mientras dura.
- La UI **no** reintenta sola; el timeout del script es de **600 s**.
- AUTO **OFF**; PAPER virtual; ventana **`INCONCLUSIVE`**. Crear copias **no** demuestra rentabilidad ni
  corrige hallazgos abiertos (`R-170-1`, `P2-03`, `P2-11`…).
- No hay tag ni Release en este acto: el objeto publicable se decide con el CI de la rama.

## 7. Publicación (POST-PUSH)

| Dato | Valor |
| --- | --- |
| Rama | `fix/059-060-proveedores` (nueva en `origin`; **no** existía antes de este acto) |
| HEAD del sello de código | `45246d86` (`chore(window)`: segundo re-anclaje del pin) |
| Cierre documental | viaja en un commit **posterior** de la misma rama (docs-only; este texto) |
| Commit funcional | `9bd7625c` (`feat(bd)`: diagnóstico, copia bajo demanda y bump `2.11.172-beta`) |
| Tag / Release / PR | **no emitidos** |

### 7.1 Commits de la rama (5, en orden)

| Commit | Qué hace |
| --- | --- |
| `afeeda9b` | `style(imports)`: ordena los imports que dejaban rojo el gate Ruff de 059/060 |
| `9bd7625c` | `feat(bd)`: diagnóstico, copia bajo demanda y sello `2.11.172-beta` |
| `76cf9598` | `chore(window)`: primer re-anclaje del pin |
| `3c40deaf` | `fix(bd)`: CHECK de 060 en el modelo + allowlist en `alembic/env.py` |
| `45246d86` | `chore(window)`: segundo re-anclaje del pin |

### 7.2 Runs de CI medidos

Un `git push` solo dispara `push` para el **tip** del envío, así que hay dos tandas, no cinco.

| Run | Workflow | Commit | Resultado |
| --- | --- | --- | --- |
| [`40902287501`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40902287501) | `Frontend CI` | `76cf9598` | **success** — job `quality` (build/typecheck/test de `shared`, typecheck/lint/test/build de `web`) |
| [`40902287451`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40902287451) | `Fase 2 scientific` | `76cf9598` | **success** |
| [`40902287549`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40902287549) | `Optimize lab` | `76cf9598` | **success** |
| [`40902287372`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40902287372) | `Python CI` | `76cf9598` | **failure** — ver §7.3 |
| [`40903120830`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40903120830) | `Python CI` | `3c40deaf` | **success** — `quality`, `grammar-discovery-pg`, `lifecycle-pg`, `paper-forward-pg`, `auto-v2-durable-pg` |
| [`40903120882`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40903120882) | `Fase 2 scientific` | `3c40deaf` | **success** |

`45246d86` **no dispara ningún workflow**: toca solo `scripts/lib/window-forward.mjs`, que no está en
los `paths` de ningún workflow (en particular no está en `.github/workflows/python-ci.yml`). El pin, en
cambio, **sí** se verifica en el `Release tag CI`; por eso el re-anclaje se comprobó en local
(§7.4). `3c40deaf` no dispara `Frontend CI` porque no toca `apps/web/**`, `packages/shared/**` ni
`package.json`: el estado del frontend lo fija `40902287501`, medido sobre el mismo árbol de `web` y
`shared` que el sello publica (el único commit posterior es Python y el pin).

### 7.3 El rojo intermedio, y por qué no es del sello

`Python CI` [`40902287372`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40902287372) salió
`failure` con **5 747 passed, 57 skipped, 2 failed**, y los dos fallos eran de
`packages/py/infrastructure/tests/test_schema_contract.py`:

- `test_sync_settings_declares_the_060_check` → `KeyError: 'sync_settings_provider_check_interval_check'`
- `test_contract_snapshot_covers_metadata` → la allowlist no declaraba el constraint

**Causa medida:** dos ficheros de la **061** se quedaron **sin commitear** al sellar, aunque su test sí
viajó. El árbol local pasaba; el checkout limpio de CI no. `git diff` los tenía en ` M` mientras el
commit del sello solo llevaba el test.

**Corrección:** `3c40deaf` añade exactamente esos dos ficheros —
`packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` (declaración del
`CheckConstraint`, solo metadatos) y `packages/py/infrastructure/alembic/env.py`
(`include_object=alembic_include_object()` en las dos ramas de `configure`)—, y es el run que queda
**verde** con los cinco jobs. Como `packages/` cambia, `45246d86` re-ancla después el pin PAPER, que es
lo único que toca ese último commit.

**Lo que esto deja dicho:** el rojo se detectó **solo** porque la rama se empujó; los commits
`52f12334` (059/060) y `9bd7625c` nunca habían pasado por CI. Un sello local verde no es un sello
verificado.

### 7.4 Verificación local del sello (`45246d86`)

| Comprobación | Resultado |
| --- | --- |
| `pnpm window:freeze` | **`freeze OK`** — coinciden `appsHash` (`35cd320f…`) y `packagesHash` (`3df714c5…`) |
| `git status -sb` | `## fix/059-060-proveedores...origin/fix/059-060-proveedores` (sin `ahead`/`behind`) |

El cierre documental que contiene este texto **no** toca `apps/` ni `packages/`, así que no mueve el pin:
el `freeze` sigue siendo el mismo tras él.

La etiqueta `commit` del pin dice `3c40deaf` mientras HEAD es `45246d86`; el propio
`scripts/window-pin.mjs` declara que **el freeze real son los dos tree hashes**, y `45246d86` solo
cambia ese fichero, así que el aviso es cosmético y no se re-ancla otra vez (re-anclarlo movería el
mismo fichero en bucle).

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La copia no escribe en la BD | el único SQL nuevo es `pg_try_advisory_lock`/`pg_advisory_unlock`; `pg_dump` abre su propia conexión en modo lectura |
| 2 | Un fallo no es un éxito | los tests de runner fijan `DUMP_FAILED`/`TIMEOUT`/`OUTPUT_MISSING` y la API solo devuelve 200 desde el camino `ok=True` |
| 3 | No hay dos copias a la vez | `test_lock_reports_busy_without_holding_connection` + 409 en `test_database_backup_api.py` |
| 4 | Producción no ejecuta | `production=True` no llama al runner ni toma el cerrojo (`test_production_is_refused_before_touching_lock_or_disk`) |
| 5 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 6 | El pin casa con el árbol | `pnpm window:freeze` ⇒ `freeze OK` |
