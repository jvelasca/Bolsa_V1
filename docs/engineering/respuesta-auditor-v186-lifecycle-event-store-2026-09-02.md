# Respuesta auditor — V1.86 (Lifecycle Event Store) (2026-09-02)

> **Padre:** [`arranque-auditor-v1-86-beta-2026-09-02.md`](./arranque-auditor-v1-86-beta-2026-09-02.md) · [`traspaso-relevo-tag-v1-86-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-86-beta-2026-09-02.md).  
> **Tip auditado:** `v1.86-beta` → [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · CI GREEN [run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402).  
> **Partida:** V1.85 PASS modelo mock [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3) · [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md).

## Veredicto

**V1.86 = 9,0 / 10 como arquitectura beta · 7,5 / 10 como servicio explotable.**

**NO** beta estable / explotable PAPER. El salto de dominio + PostgreSQL es correcto y cierra los cinco P1 de V1.85. Lo que bloquea es operacional: **auth del endpoint nuevo**, **serialización del event store** y **certificación real de Alembic 015**.

P0 = 1 (superficie HTTP sin identidad) · P1 = 5 · P2 = 6.

## Qué está bien

- Dominio `bolsa_domain.lifecycle` puro (sin FastAPI / SQLAlchemy / PostgreSQL); Import-Linter intacto.
- `LifecycleIdentity` + `event_id` / `payload_hash` / `schema_version` / causation / correlation.
- Cerrados: `event_id_conflict` · `identity_mismatch` · `invalid_payload` · `trail_relaxation` · `invalid_timestamp` · ENTRY fill.
- Accounting OPEN/T1/T2/CLOSE + invariante `initial + realized + unrealized = totalEquity`.
- Idempotencia por hash (incl. CLOSE con remaining dependiente). Job `lifecycle-pg` obligatorio en certify.

## P0 / P1 abiertos (next = V1.87)

1. **P0 Auth HTTP** — `POST /api/lifecycle/events` y `GET .../snapshot` no exigen JWT ni ownership. `accountId` del cliente no es autoridad.
2. **P1 Concurrencia** — SELECT → validate → INSERT sin lock/sequence. Dos transiciones legales sobre el mismo snapshot pueden colisionar.
3. **P1 Orden del log** — `ORDER BY at, created_at` no es secuencia de agregado. Hace falta `sequence_no` + `UNIQUE(position_id, sequence_no)`.
4. **P1 CI Alembic** — el fixture crea la tabla con SQLAlchemy metadata; el job no certifica `015` desde cero.
5. **P1 Migración 015** — `if table_exists: return` omite índices/constraints si la tabla ya existe.
6. **P1 DTO** — `extra="allow"` tragaría typos (`quanity`) en un evento financiero.

## P2 (no bloquean V1.87 obligatorio)

- `float` dominio ↔ `Numeric` PG. Congelar `Decimal` domain→DB.
- Lifecycle accounting no es autoridad de equity de cartera (ledger/portfolio).
- `last_price_for_stage()` sintético: no llevar a producción.
- `venueOrderId` vs broker/client/execution ids.
- `IntegrityError` de `fill_id` UNIQUE mal clasificado como `event_id_conflict`.
- Integrated E2E sigue opt-in (correcto ahora; V1.88 golden operativo).

## Freeze verificado

Confirm = firma · `PAPER_D_EXECUTE` off · **no LIVE** · package `1.35.0-beta` · mesa `/portfolio` mock · sin Playwright en `frontend-ci` · integrated opt-in.

## Next

**V1.87 — Operational Integration & Concurrency Certification:** JWT → principal → account/position ownership · `sequence_no` + lock · `alembic upgrade head` en CI · `extra="forbid"` · Decimal domain→DB. **Sin** nuevas features de negocio. **V1.88** = golden integrado + restart proceso + recon.
