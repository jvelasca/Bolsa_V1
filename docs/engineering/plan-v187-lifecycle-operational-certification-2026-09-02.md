# Plan — V1.87 Lifecycle Operational Integration & Concurrency Certification

> **Padre:** [`spec-v187-lifecycle-operational-certification-2026-09-02.md`](./spec-v187-lifecycle-operational-certification-2026-09-02.md).  
> **Estado:** **CERRADA** · **stamp CI GREEN remoto DONE** — [`v1.87-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.87-beta) → [`646b97ac`](https://github.com/jvelasca/Bolsa_V1/commit/646b97ac) · [run 33689747400](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400) **success**. Partida V1.86 [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · auditoría [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md).

| ID  | Entrega                                                                   | Estado   |
| --- | ------------------------------------------------------------------------- | -------- |
| D0  | respuesta auditor V1.86 + spec/plan V1.87                                 | **DONE** |
| P0  | JWT principal + account/position ownership en POST/GET lifecycle          | **DONE** |
| P1  | `sequence_no` + `lifecycle_aggregates` + FOR UPDATE + UNIQUE              | **DONE** |
| P1  | Alembic 015 ensure-indexes + 016; CI `upgrade head` (sin metadata.create) | **DONE** |
| P1  | DTO `extra="forbid"` + Decimal domain→DB + classify IntegrityError        | **DONE** |
| P1  | Tests: auth 401/403 · concurrent append · migration-from-zero             | **DONE** |
| —   | Docs CURRENT_SYSTEM · index §56 · relevo                                  | **DONE** |
| —   | Tag `v1.87-beta` / CI remoto GREEN                                        | **DONE** |

## Secuencia

1. Stamp auditoría V1.86 (no beta estable).
2. Decimal + `sequence_no` en dominio (hash sin sequence).
3. Alembic 015/016 + modelo SQLAlchemy.
4. Store lock/append/order + use-case bajo lock.
5. Rutas FastAPI: JWT, ownership, forbid.
6. Tests PG + HTTP + CI.
7. Freeze NO LIVE.

## OUT (plan)

- LIVE · `PAPER_D_EXECUTE` on · scheduler · bump · V1.88 integrated obligatorio
- Commitear `**/logs/`
