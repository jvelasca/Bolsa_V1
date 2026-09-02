# Relevo — V1.87 Lifecycle Operational Integration & Concurrency

> **AsOf:** 2026-09-02 · **Estado:** **CÓDIGO LISTO** · pendiente stamp CI GREEN / tag.  
> **Partida:** V1.86 auditoría NO beta estable · tip [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md).  
> **Spec/plan:** [`spec-v187-lifecycle-operational-certification-2026-09-02.md`](./spec-v187-lifecycle-operational-certification-2026-09-02.md) · [`plan-v187-lifecycle-operational-certification-2026-09-02.md`](./plan-v187-lifecycle-operational-certification-2026-09-02.md).

## Hecho

- P0: JWT obligatorio en POST/GET `/api/lifecycle/*` · account/position ownership → 401/403/404
- P1: `sequence_no` + `lifecycle_aggregates` + `SELECT … FOR UPDATE` + `UNIQUE(position_id, sequence_no)`
- P1: Alembic 015 ensure-indexes · 016 sequence · CI `lifecycle-pg` hace `alembic upgrade head` (sin `metadata.create`)
- P1: DTO `extra="forbid"` · Decimal domain→DB · `IntegrityError` clasificado (`fill_id` ≠ `event_id`)
- Tests: DTO offline · in-memory concurrent T1 · PG alembic/schema + concurrent + auth (job PG)

## Reservas

- Mesa `/portfolio` sigue mock Playwright
- V1.88 integrated golden + kill/restart API + recon real **OUT**
- Tag / CI GREEN remoto pendiente

## OUT (intactos)

- LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger
- Playwright en `frontend-ci` · integrated E2E obligatorio · thaw estricto
- Lifecycle accounting ≠ autoridad de equity de cartera (ledger)

## Next

Stamp CI GREEN + tag `v1.87-beta`. **No** LIVE · **no** V1.88 aún.
