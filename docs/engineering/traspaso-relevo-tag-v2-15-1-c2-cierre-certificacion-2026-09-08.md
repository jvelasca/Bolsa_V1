# RELEVO — V2.15.1 C2 (cierre de certificación: restore seguro, readiness schema-aware, batería DR) — 2026-09-08

> **Padre:** [índice #103+](./engineering-index-2026-08-03.md) · tag previo [`traspaso-relevo-tag-v2-15-beta-2026-09-08.md`](./traspaso-relevo-tag-v2-15-beta-2026-09-08.md) · auditoría que abre este ciclo: (informe externo V2.15 en transcript sesión 2026-09-08 20:0x).
> **Estado:** trabajo C2 implementado y verificado en local (GREEN battery DR + tests health). **Pendiente de elevar** (bump `1.45.0-beta`, tag `v2.15.1-beta`, CI GREEN real) — NO afirmar GREEN hasta ver el run.
> **Núcleo congelado (intacto):** FSM / live_orders / ExecutionEvent / ledger / outbox / reconciliation. Este ciclo solo endurece infraestructura de backup/restore y health-readiness.

## 1. Objetivo (cierre de certificación V2.15 C2)

Sin nuevas funciones de trading. Cierra los hallazgos P1/P2 del auditor externo en **infraestructura**:

| Hallazgo auditor                                              | Estado                                                   |
| ------------------------------------------------------------- | -------------------------------------------------------- |
| V2.15-01 `db:restore --target-db` NO propaga target a Alembic | RESUELTO — reescritura de `DATABASE_URL` al destino      |
| V2.15-02 psql restore sin `ON_ERROR_STOP=1`                   | RESUELTO — `-v ON_ERROR_STOP=1` en restore + drop/create |
| V2.15-03 `/health/ready` no valida Alembic current            | RESUELTO — readiness fail-closed schema-aware            |
| V2.15-09/-11 checksum + manifest backup                       | RESUELTO — sidecar `.sha256` + `backups-manifest.json`   |
| V2.15-10 colisión nombre (timestamp)                          | RESUELTO — ms en sello + escritura O_EXCL                |
| V2.15-13 `DB_BACKUP_KEEP=0` peligroso                         | RESUELTO — mínimo seguro ≥1                              |
| Test automático restore+checksum · restore no toca `bolsa_v1` | RESUELTO — `pnpm db:dr:test` (batería DR)                |

## 2. Archivos (faena C2)

- `scripts/lib/backup.mjs` — sello `-mmm`, escritura `wx` (O_EXCL), `sha256Hex`, sidecar `.sha256`, `backups-manifest.json`, `reconcileManifest`, mínimo `DB_BACKUP_KEEP`≥1.
- `scripts/lib/db.mjs` — `runAlembicUpgrade({databaseUrl})`, `redirectDatabaseUrlTo(db)`.
- `scripts/db-restore.mjs` — `ON_ERROR_STOP=1`; Alembic dirigido a `--target-db`; aborta si sidecar no coincide.
- `scripts/db-dr-verify.mjs` (**nuevo**) + `package.json` `db:dr:test` — batería DR.
- `apps/api-python/.../database/session.py` — `read_db_schema_current(engine)`.
- `apps/api-python/.../api/v1/routes/health.py` — `/health/ready` schema-aware; campo `schema_status`.
- `apps/api-python/tests/test_health.py` — ready 200-at-head / 503-mismatch / 503-unmigrated.
- `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` — regenerados (contrato).

## 3. Verificación realizada en local (2026-09-08)

- `node scripts/db-dr-verify.mjs` → **GREEN**: `dump-hash · sidecar-checksum OK · db-restore-cli-exit0 · scratch-al-alineado-head(023) · scratch-esquema-consultable(66 tablas) · principal-intacta` — la SCRATCH se elimina en `finally`.
- `pytest apps/api-python/tests/test_health.py` (PG local) → **9 passed** (incl. 3 nuevos schema-aware).
- `ruff` + `py_compile` limpios en `health.py`/`session.py`/`test_health.py`; `node --check` OK en los `.mjs`.
- `uv run mypy` (entorno real) sobre `health.py` → **Success** (el aviso local Redis `aclose` es falso positivo fuera del venv).
- `pnpm db:backup:list` OK con el nuevo sello `-mmm`.

## 4. Estados / decisión de elevación (A EJECUTAR tras OK)

- Bump candidato: `1.44.0-beta` → **`1.45.0-beta`** (ciclo de hardening, no menor).
- Tag candidato: **`v2.15.1-beta`**.
- No subir rama/tag ni afirmar "GREEN" hasta ver run real del Release-tag CI (`certify=success`).

FIN DEL RELEVO — faena **V2.15 C2** implementada y verificada en local. Pendiente de bump/tag/CI para quedar **auditable externamente**.
