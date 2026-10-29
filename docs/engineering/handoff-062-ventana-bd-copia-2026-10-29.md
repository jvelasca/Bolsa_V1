# Handoff 062 — Ventana BD: copia bajo demanda (2026-10-29)

## Qué se pidió

Tras el diagnóstico read-only de la ventana BD (handoff 061) la pregunta fue: *«¿desde dónde
hacemos el mantenimiento y control de la BD?»*. Decisión: **una sola acción en la UI** —
crear una copia ahora. Todo lo demás (VACUUM/ANALYZE, restaurar, podar sin crear, aplicar
migraciones, programar la tarea diaria) sigue en CLI o en tareas automáticas.

## Qué se implementó

| Capa | Pieza | Fichero |
| --- | --- | --- |
| Script | `--dir <ruta>` para que el volcado escriba donde la API mira | `scripts/db-dump.mjs` |
| Aplicación | `CreateDatabaseBackup`, `BackupRunner` / `MaintenanceLock` / `MaintenanceAudit` | `packages/py/application/src/bolsa_application/database_backup.py` |
| Aplicación | `summarize_backup_snapshot` compartido por diagnóstico y copia | `packages/py/application/src/bolsa_application/database_maintenance.py` |
| Infraestructura | `NodeBackupRunner`, `PostgresMaintenanceLock`, `JsonlMaintenanceAudit` | `packages/py/infrastructure/src/bolsa_infrastructure/database/backup_runner.py` |
| API | `POST /api/database/backup`, DTOs y guardas | `apps/api-python/src/bolsa_api/api/v1/routes/database.py`, `schemas/database_maintenance.py` |
| API | `require_admin_when_auth_enabled` | `apps/api-python/src/bolsa_api/auth/roles.py` |
| Web | Botón «Crear copia ahora» con confirmación `COPIAR` | `apps/web/src/features/config/database-maintenance-panel.tsx` |
| Web | `createDatabaseBackup` y `detail` estructurado legible | `apps/web/src/lib/api.ts` |
| Contrato | Tipos y OpenAPI regenerados | `packages/shared/src/types.ts`, `apps/web/api/openapi.json` |

## Blindaje (lo que impide que esto sea «un botón que rompe cosas»)

1. **Confirmación escrita**: el body debe traer `COPIAR`; si no, 422. No hay clic accidental.
2. **Un trabajo a la vez**: `pg_try_advisory_lock(774104254)` sobre una conexión dedicada.
   Si está ocupado → 409 `backup_in_progress`. La clave es distinta de la de migraciones
   (`774104253`), así que migrar y copiar no se bloquean entre sí.
3. **Rol**: con `APP_PASSWORD` activo se exige claim `role=admin` (403). Sin auth (local) no
   se bloquea: no hay usuario que suplantar.
4. **Producción fuera**: el entorno se evalúa con `is_production_environment`; en producción
   la ruta responde 403 y **no** se toma el cerrojo ni se toca el disco.
5. **Auditoría**: cada intento (éxito o fallo) escribe una línea en
   `logs/agent/db-maintenance.jsonl` con `at`, `action`, `actor`, `ok`, `file`, `bytes`,
   `durationMs` y `errorCode`. Un fallo al escribir la auditoría no oculta la copia.
6. **Honestidad del resultado**: `DUMP_FAILED`, `TIMEOUT`, `OUTPUT_MISSING`, `NODE_MISSING`,
   `SCRIPT_MISSING` y `DIR_ERROR` son respuestas de error con código; nunca un 200 sin
   fichero. `pruned` se calcula por diferencia de listado, no parseando logs.

## Doctrina intacta

- El **diagnóstico** no escribe en PostgreSQL.
- La **copia** tampoco escribe en PostgreSQL: `pg_dump` solo lee. Lo que escribe es un
  fichero con su `.sha256`, el `backups-manifest.json` y la poda por `DB_BACKUP_KEEP`.
- **Restaurar** no está en la UI y no se debe poner: sobrescribe datos.

## Límites conocidos

- La acción exige `node` y `pg_dump`/Docker en la máquina donde corre la API. Si no están,
  se dice con un código (503), no se simula.
- `pg_dump` abre su propia conexión: el diagnóstico puede mostrar una conexión más mientras
  dura el volcado.
- El cerrojo es global por BD, pero **no** cubre un `pnpm db:dump` lanzado a mano en
  paralelo; el manifest y `O_EXCL` evitan colisiones de fichero, no el trabajo duplicado.
- La UI no reintenta sola: si el volcado tarda, hay que esperar a la respuesta (timeout del
  script: 600 s).

## Evidencia

- `packages/py/application/tests/test_database_backup.py` — éxito, `busy`, producción,
  fallo del runner, excepción, auditoría y actor acotado.
- `apps/api-python/tests/test_database_backup_api.py` — 200, 422, 409, 403 (producción y
  rol), 503 y 500 por código.
- `packages/py/infrastructure/tests/test_backup_runner.py` — `--dir` y `shell=False`,
  detección del fichero nuevo, podados, sidecar/manifest, `NODE_MISSING`, `TIMEOUT`.
- `apps/web/src/features/config/database-maintenance-panel.test.tsx` — el botón no dispara
  hasta `COPIAR`, muestra el fichero y el error sin verde.
- Sello `2.11.172-beta` / `v2.88.172-beta` (rama empujada, sin tag): expediente en
  [`evidence/v2.88.172`](./evidence/v2.88.172/README.md).
- En vivo (2026-10-29): `POST /api/database/backup` con `COPIAR` → **200**,
  `bolsa_v1-20261029-145347-232.sql`, **14 963 887 B**, `sha256 dcb9c49b…`, 780 ms; la
  tarjeta de copias pasa de `warning` a **`ok`**.

## Siguiente paso natural

Programar la copia diaria en el sistema operativo (ya existe `pnpm db:backup:cron:win`) y
vigilar `DB_BACKUP_STALE_HOURS`: la tarjeta pasa a `warning` cuando la copia más reciente
supera ese umbral. La copia bajo demanda es para «quiero una antes de tocar algo», no un
sustituto del calendario.
