# RELEVO — v2.15 backups/prevención + apertura V2.15 hardening — 2026-09-08

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) · gatillado por [incidente pérdida de listas](./traspaso-incidente-perdida-list-2026-09-08.md) (BD `bolsa_v1` quedó seed-only sin copia) · base de cobro de deuda V2.15 [`respuesta-auditor-externo-v2-14-2-2026-09-08.md`](./respuesta-auditor-externo-v2-14-2-2026-09-08.md) §4 + [`audit-interno-lectura-v2-14-2026-09-08.md`](./audit-interno-lectura-v2-14-2026-09-08.md).
> **Estado:** **RELEVO PREPARADO (solo documento).** El agente siguiente ejecuta la faena a partir de este texto. No se ha implementado código todavía.
> **AsOf:** `main` = `2a98886c` · package `1.43.2-beta` · Alembic `023_ohlcv_bars_unique_reconcile` · V2.14.2 Release-tag CI GREEN (run `34224783087`).

---

## 1. Propósito y alcance de esta faena (para el agente QUE EJECUTE)

Dos objetivos acordados por el usuario:

1. **PREVENCIÓN — copias de seguridad automáticas de la BD `bolsa_v1`** y su recuperación (pg_dump a carpeta local gitignored + scripts `pnpm db:*` + punto de cron).
2. **VERSIONAJE — abrir y ejecutar el primer ciclo de la V2.15 (hardening)** en GitHub para auditoría externa.

> Nota metodológica: este fichero es el **handover** (relevo). El código NO se ha escrito. Un agente siguiente lo toma y ejecuta. Mantener el foco: primero BACKUPS (bajo riesgo, cierre operativo), luego abrir V2.15 con el catálogo de deuda del informe A-ext V2.14.2.

---

## 2. Contexto del incidente que motiva la prevención (referencia)

El 2026-09-08 la BD `bolsa_v1` quedó en estado bootstrap/seed sin las listas propias ni la membresía 'estudio' del usuario; no había backup y las filas eran estado runtime no versionado → **pérdida no recuperable**. Detalle completo en [`traspaso-incidente-perdida-list-2026-09-08.md`](./traspaso-incidente-perdida-list-2026-09-08.md). La prevención y el versionaje de V2.15 nacen de esa lección: **sin copia automática, cualquier reset/re-drift es irrecuperable**.

---

## 3. BLOQUE A — PREVENCIÓN: copias de seguridad automáticas de `bolsa_v1`

### 3.1 Base técnica ya verificada (no re-investigar)

- **Credenciales/DB/contenedor:** `bolsa` / `bolsa_dev`, DB `bolsa_v1`, contenedor `bolsa-postgres`, PostgreSQL 16 en `localhost:5432`, volumen docker `bolsa_pg_data` ([docker-compose.yml](./../docker-compose.yml) línea 6-22).
- **Idea del backup:** volcar POR FUERA del contenedor a un fichero local bajo `/workspace/db-backups/`:
  - dump: `docker exec bolsa-postgres pg_dump -U bolsa -d bolsa_v1` con salida redirigida a `db-backups/bolsa_v1-<estampa>.sql` (o `.sql.gz` vía pipe a `gzip -c`).
  - restore: `docker exec -i bolsa-postgres psql -U bolsa -d bolsa_v1` recibiendo el fichero por STDIN (`Get-Content -Raw` o `cmd /c type` en Windows), y posterior `alembic upgrade head` (023) si procede.
- **Helpers a reutilizar:** `scripts/lib/docker.mjs` → `findDockerExe()`, `isPostgresReady(docker, {container,user,db})`; `scripts/lib/db.mjs` → `runDbMigrateDeploy()` (Alembic head), `runDbScript`; `scripts/lib/logger.mjs` → `logInfo`, `logError`, `ROOT`, `writeAgentLog`; existe un patrón de **prune por retención** ya implementado en `pruneStampedLogs` ([scripts/lib/logger.mjs](./../scripts/lib/logger.mjs)) que sirve de modelo para podar backups.
- **Estilo CLI** de los scripts existentes: un `.mjs` en la raíz de `scripts/` que lee `process.argv.includes('--flag')`, usa top-level `await`, y hace `process.exit(1)` ante error + `logInfo`/`writeAgentLog`. Ver [scripts/db-check.mjs](./../scripts/db-check.mjs) y [scripts/db-ensure.mjs](./../scripts/db-ensure.mjs) como plantilla.

### 3.2 Ficheros a crear por el agente que ejecute

1. **[scripts/lib/backup.mjs](./../scripts/lib/backup.mjs)** — helpers:
   - `BACKUP_DIR = join(ROOT, 'db-backups')` (carpeta local, fuera del contenedor).
   - `resolveBackupDir() / ensureBackupHostDir()` → `mkdirSync(recurse)`.
   - `buildFileStamp()` → sello local `YYYYMMDD-HHMMSS`.
   - `pgDumpToFile({ docker, db='bolsa_v1', gzip=true, keep })` → ejecuta el dump con salida a fichero en `BACKUP_DIR`, devuelve `{file, bytes}`.
   - `listBackups()` → lecturas ordenadas por mtime de `db-backups/*.sql*`.
   - `retentionPrune(keep)` → borra los `> keep` más antiguos (modelado en `pruneStampedLogs`).
   - `readBackupForRestore()`/`requireFile(file)` para el restore.
2. **[scripts/db-dump.mjs](./../scripts/db-dump.mjs)** — genera un volcado en `db-backups/bolsa_v1-<estampa>.sql(.gz)`, `logInfo` del resultado, prune por retención (default `--keep 14`), `writeAgentLog('db-dump', {...})`. Si Postgres no está listo → inicia Docker/Postgres (reutiliza `ensureProjectDatabase`).
3. **[scripts/db-restore.mjs](./../scripts/db-restore.mjs)** — interfaz `--file <path.sql|path.sql.gz> [--yes] [--target-db bolsa_v1]`. Sin `--yes` pide confirmación (destructivo). Restaura vía psql STDIN y, opcionalmente `--alembic` para re-aplicar head 023.
4. **Ganchos en [../package.json](./../package.json)** (scripts):
   - `"db:dump": "node scripts/db-dump.mjs"`
   - `"db:backup": "node scripts/db-dump.mjs"` (alias)
   - `"db:restore": "node scripts/db-restore.mjs"`
   - `"db:backup:list": "node scripts/db-backup-list.mjs"` (listado + retención)
   - `"db:backup:cron:win": "node scripts/db-backup-cron-win.mjs"` (genera/registra la tarea programada de Windows o da las instrucciones `schtasks`, con la cadencia de arranque/diaria).
5. **`.gitignore`**: añadir la línea `db-backups/` (que no versiona) (el gitignore ya ignora `*.sql.gz`, `*.dump`, `pgdata`).
6. **Retención configurable**: añadir a `.env.example` `# DB_BACKUP_KEEP=14` (sobreescribible) y que el script lea env antes del default.
7. **Documentación**: añadir una sección "Copias de seguridad y recuperación" en [docs/DEV_STARTUP.md](./../docs/DEV_STARTUP.md) o un doc hermana (mismo lugar donde se explican `db:ensure`, `pnpm doctor`).

### 3.3 Comportamiento esperado (criterio de aceptación)

- `pnpm db:dump` deja al menos 1 fichero en `db-backups/`, no comitete, reporta bytes/rutas, no borra más de la retención.
- `pnpm db:backup:list` lista los backups ordenados.
- `pnpm db:restore --file <backup> --yes` deja la BD restaurada y Alembic en head 023 (o avisa si no).
- Al cabo de N d�as (o al arrancar un `pnpm db:dump` programado) se conservan `DB_BACKUP_KEEP` y se podan el resto.
- NADA de `db-backups/` debe aparecer en `git status`.

> Riesgo/nota: un dump de una BD abierta puede no ser transaccionalmente coherente si hay writes concurrentes; para esta app local single-writer está bien (aceptar por ahora). Si se quiere más robustez se usaría `pg_dump --no-owner` + restauración en parado; decidirlo en la faena.

---

## 4. BLOQUE B — CIERRE Y APERTURA DE LA V2.15 (HARDENING) EN GITHUB

### 4.1 Estado previo (ya cerrado, NO re-hacer)

- `main` = `2a98886c` = `1.43.2-beta` = tag `v2.14.2-beta`, **Release-tag CI GREEN** (run `34224783087`, `certify` success). Documentado en la certificación V2.14.2.
- NO hay que volver a etiquetar V2.14.2. La V2.14.2 queda cerrada.

### 4.2 Qué es la V2.15

Ciclo **de HARDENING / CERTIFICATION**, NO nueva funcionalidad de trading. El catálogo de deuda sale de:

- [`respuesta-auditor-externo-v2-14-2-2026-09-08.md`](./respuesta-auditor-externo-v2-14-2-2026-09-08.md) **§4**:
  - P1-01 account-less→global (`require_owned_account_if_present` deja pasar `account_id=None`; repos consultan global) — posponer a soporte multi-owner real.
  - Readiness operacional / separar `/health` en `/live`+`/ready`.
  - Provenance: `PRODUCT_VERSION`/`API_CONTRACT_VERSION` obligatorias en build.
  - Columnas muertas `claim_expires_at`/`attempt_count`/`last_error` (migración 022) — darles o no semántica de lease real.
  - T1/T2 (`position_state._advance_target_leg`, lifecycle `open→T1_EXECUTED` sin `T1_TRIGGERED`).
  - FSM declarativa + cobertura de transiciones.
  - Matriz de cobertura CI (test_account_isolation/auth/health no corren en ningún job del tag-trigger).
  - Baterías `[runtime]` (multi-worker/SKIP LOCKED real-PG, broker real, crash recovery, kill/unlock).
- [`audit-interno-lectura-v2-14-2026-09-08.md`](./audit-interno-lectura-v2-14-2026-09-08.md) (observaciones P2: FSM mantenimiento, divergencias Paper/live, guardas).

### 4.3 Ciclo de faena V2.15 recomendado (lo ejecutará el agente siguiente)

1. Elegir **1–2 items** prioritarios V2.15 (sugerencia para primer ciclo: **provenance obligatoria + readiness** o el **limpieza/semántica de lease**), describiéndolos en un plan corto.
2. Rama `stage/v2.15-<nombre>-YYYY-MM-DD` desde `main`, commits con mensajes claros, **sin** `git add -A`.
3. PR a `main`; CI del PR verde (quality + tests) antes de merge.
4. Al cerrar el primer ciclo: **bump de package** a **`1.44.x-beta`** (batch) y actualizar `docs/CURRENT_SYSTEM.md`, `CHANGELOG/README` (re-apuntar el tip de SHA al que sea HEAD del bump), y registrar en `engineering-index`.
5. **Etiquetar `v2.15-beta`** → dispara el **Release-tag CI**. **Observar el run real GREEN** (job `certify` success) antes de afirmar nada (disciplina interna: no inventar GREEN).
6. Commitear/actualizar la documentación pendiente del worktree en una actualización coherente de versión antes de etiquetar V2.15 (no dejar docs sueltas sin rama).

### 4.4 Checklist de apertura de versión (V2.14.x cerrada → V2.15)

- [ ] Confirmado que `main`/tag V2.14.2 están GREEN (sí, run 34224783087).
- [ ] Commit de cierre/documentación pendiente V2.14.x subido (relevos del 2026-09-08) — permitir que quede auditable antes de la nueva versión.
- [ ] Actualizar `docs/CURRENT_SYSTEM.md`, `CHANGELOG`/`README` (tip SHA actual), `engineering-index`.
- [ ] Definir el 1-2 items de V2.15 (hardening) y el plan de la faena.
- [ ] Etiquetar V2.15 con CI GREEN real y registro de auditoría.

---

## 5. BLOQUE C — LÍNEA ROJA (reglas para el agente que ejecute)

- No `git add -A`. Stage por paths explícitos. El worktree contiene doc pendiente de esta tanda (relevos/incidente) y trabajo preexistente (`apps/web/e2e/*`, `playwright.config.ts`, `lists-tab/*`, `open-instrument-in-trading.ts`, `packages/shared/src/cognitive/live-order.ts`) que NO es de la faena de backups; no tocarlo.
- **No afirmar GREEN sin ver el run real** (`gh run view <id> --json conclusion`).
- No subir ramas/tags sueltas en paralelo a `main` hasta que el ciclo lo exija.
- **Congelado / NO tocar agresivamente:** FSM live, live_orders, ExecutionEvent, ledger, outbox, reconciliación, arquitectura de capas. La V2.15 endurece alrededor, no reescribe el núcleo (salvo decisión explícita en el item elegido, p. ej. lease columns).
- El backup/restore NUNCA debe ejecutarse automáticamente contra una BD productiva compartida; es solo entorno local `bolsa_v1`.

---

## 6. Texto de traspaso (pegar en el hilo del agente siguiente)

> **AGENTE SIGUIENTE — continúa el RELEVO v2.15 backups/prevención (2026-09-08).**
> Repo `c:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1`, `main` en `2a98886c` (=`1.43.2-beta`, V2.14.2, Release-tag CI GREEN). Documento de relevo: `docs/engineering/traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md`.
> **Faena 1 (PREVENCIÓN/backups, PRIMERO):** crear `scripts/lib/backup.mjs`, `scripts/db-dump.mjs`, `scripts/db-restore.mjs`, `scripts/db-backup-list.mjs`, `scripts/db-backup-cron-win.mjs`; añadir a `package.json` los scripts `db:dump`, `db:backup`, `db:restore`, `db:backup:list`, `db:backup:cron:win`; añadir `db-backups/` a `.gitignore`; añadir `DB_BACKUP_KEEP` a `.env.example`; documentar en DEV_STARTUP. Criterio: `pnpm db:dump` deja backup local no versionado y `pnpm db:restore --file … --yes` restaura + Alembic head 023.
> **Faena 2 (VERSIONAJE V2.15):** cerrar/subir la doc pendiente V2.14.x de forma coherente; abrir el 1er ciclo de hardening V2.15 (elegir 1-2 items del §4.2: sugerido provenance obligatoria+readiness o limpieza/semántica de lease), rama `stage/v2.15-*`, bump a `1.44.x-beta`, y al cerrar **etiquetar `v2.15-beta` y confirmar Release-tag CI GREEN real** (run `certify` success) antes de afirmarlo.
> **Reglas:** sin `git add -A`; no tocar núcleo congelado (FSM/live_orders/ExecutionEvent/ledger/outbox/recon); no afirmar GREEN sin ver el run real; backups solo entorno local `bolsa_v1`.

---

FIN DEL RELEVO — 2026-09-08. Handover preparado; ejecución pendiente de un agente siguiente.
