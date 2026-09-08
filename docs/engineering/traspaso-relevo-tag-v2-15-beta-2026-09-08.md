# RELEVO — v2.15-beta elevado a `main` (PREVENCIÓN backups `bolsa_v1` + 1er ciclo hardening provenance/readiness) — 2026-09-08

> **Padre:** [índice #99–102](./engineering-index-2026-08-03.md) · apertura [`traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md`](./traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md) · certificación V2.14.2 [`respuesta-auditor-externo-v2-14-2`](./respuesta-auditor-externo-v2-14-2-2026-09-08.md) (deuda que abrió este ciclo).
> **Estado:** **CERRADO.** V2.15 (1er ciclo hardening) elevado a `main` con **bump de package `1.44.0-beta`**.
> **Tag:** [`v2.15-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.15-beta) → `7c6d624e` (commit de elevación/bump; contiene el merge PR #59 como ancestro).
> **CI GREEN confirmado con run real:** run [`34256252001`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34256252001) · tag `v2.15-beta` `7c6d624e` · event `push` · `conclusion=success` · job **`certify (aggregate + artifact)` = `completed`/`success`** (gate: falla si security/shared/spine/frontend/python/playwright-mock/lifecycle-pg no son success).

## 1. Elevación V2.15 (auditable desde GitHub)

| Pieza                 | Valor                                                                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Base                  | `main` en `2a98886c` (V2.14.2, `1.43.2-beta`)                                                                    |
| Rama                  | `stage/v2.15-backups-prevencion-2026-09-08` (desde `2a98886c`)                                                   |
| Commits de trabajo    | `d628d8ab` backups · `23fcfb48` cierre doc V2.14.x · `51db5c4e` hardening · `01778a8d` C1 fix ruff I001 (config) |
| PR                    | **#59** → merge `808432aa` (CI PR verde)                                                                         |
| Commit elevación/bump | `7c6d624e` (este tag)                                                                                            |
| Bump                  | `1.43.2-beta` → **`1.44.0-beta`**                                                                                |
| Tag                   | [`v2.15-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.15-beta) → `7c6d624e`                        |
| Previo                | `main` `808432aa` (merge PR #59) == contenido de trabajo antes del bump                                          |
| Alembic head          | `023_ohlcv_bars_unique_reconcile` (no hay migración nueva en V2.15.1)                                            |

## 2. Qué incluye V2.15 (1er ciclo hardening)

### Faena 1 — PREVENCIÓN (copias de seguridad de `bolsa_v1` local)

- **`scripts/lib/backup.mjs`** + **`db-dump.mjs`/`db-restore.mjs`/`db-backup-list.mjs`/`db-backup-cron-win.mjs`**.
- Ganchos `pnpm db:dump` · `db:backup` · `db:restore` · `db:backup:list` · `db:backup:cron:win`.
- `.gitignore db-backups/` · `.env.example DB_BACKUP_KEEP` (default **14**) · sección en `docs/DEV_STARTUP.md`.
- **Criterio aceptación cumplido**: `pnpm db:dump` deja backup local no versionado (gilab `db-backups/`) y reporta bytes; `db:restore --file … --yes` re-aplica Alembic head. Verificado contra BD scratch `bolsa_v1_restore_test` (35 instruments duplicados) sin tocar la `bolsa_v1` real (que quedó intacta en schema `023`). Backup real de sanity: `db-backups/bolsa_v1-20260908-164709.sql` (8.8 MB, gitignored).

### Faena 2 — hardening V2.15·1 (item §4.2: provenance + readiness)

- **Readiness operacional**: `GET /api/health/live` (liveness **sin** tocar BD) y `GET /api/health/ready` (readiness: PostgreSQL requerido → `200/ready` o `503/not_ready`). Redis/worker_arq informativos (optional). `/api/health` agregado compatible.
- **Provenance obligatoria en producción**: `provenance.require_release_identity_env()` eleva en `create_app` cuando `PRODUCT_VERSION`/`API_CONTRACT_VERSION` faltan en `ENVIRONMENT=production` (`is_production_environment`). En dev/test/staging (allowlist) permanecen opcionales → no rompe CI ni arranque local.
- **Tests**: `test_provenance_gate.py` (offline, corre en python job del tag CI) + 3 nuevos en `test_health.py` (`live` 200, `ready` 200/DB-up, `ready` 503/DB-down mock).
- **Contrato regenerado** (openapi.json + schema.d.ts, diff solo aditivo).

## 3. Estado / riesgos abiertos (no bloquean la elevación)

- **Cierre V2.14.x**: certificación V2.14.2 (run 34224783087 GREEN real) + incidente listas 2026-09-08 y apertura V2.15 quedan auditable en engineering-index **#99–102**.
- Deuda V2.15 restante del §4 (no cerrada en este ciclo): P1-01 account-less→global (single-owner, no urgente), columnas muertas `claim_expires_at/attempt_count/last_error`, T1/T2, FSM declarativa, limpieza/semántica de lease, matriz cobertura CI, baterías `[runtime]` LIVE.
- Núcleo congelado (FSM/live_orders/ExecutionEvent/ledger/outbox/recon) **intacto** — V2.15.1 no reescribe esas piezas.
- Backups/rutinas `db:*` lanzan contra el contenedor local; en entornos productivos compartidos no deben ejecutarse automáticamente (documentado en DEV_STARTUP).

FIN DEL RELEVO — V2.15 (backups/prevención + hardening provenance/readiness) elevado a `main`, **CI GREEN real certificado**, auditable desde GitHub.
