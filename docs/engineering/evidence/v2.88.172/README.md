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
| Rama | `fix/059-060-proveedores` |
| Commit del sello | _pendiente de medición POST-PUSH_ |
| CI de la rama | _pendiente de medición POST-PUSH_ |
| Tag / Release | **no emitidos** |

## 8. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | La copia no escribe en la BD | el único SQL nuevo es `pg_try_advisory_lock`/`pg_advisory_unlock`; `pg_dump` abre su propia conexión en modo lectura |
| 2 | Un fallo no es un éxito | los tests de runner fijan `DUMP_FAILED`/`TIMEOUT`/`OUTPUT_MISSING` y la API solo devuelve 200 desde el camino `ok=True` |
| 3 | No hay dos copias a la vez | `test_lock_reports_busy_without_holding_connection` + 409 en `test_database_backup_api.py` |
| 4 | Producción no ejecuta | `production=True` no llama al runner ni toma el cerrojo (`test_production_is_refused_before_touching_lock_or_disk`) |
| 5 | El bump es coherente | `test_dia_d_bump_guard` falla si un `meta.bump` difiere de `package.json` |
| 6 | El pin casa con el árbol | `pnpm window:freeze` ⇒ `freeze OK` |
