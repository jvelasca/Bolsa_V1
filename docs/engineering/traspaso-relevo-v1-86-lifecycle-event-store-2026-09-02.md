# Relevo — V1.86 Lifecycle Event Store (FastAPI + PostgreSQL)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA (código)** · pendiente tag CI remoto.  
> **Partida:** V1.85 PASS modelo mock · tip [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3) · auditoría [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md).  
> **Spec/plan:** [`spec-v186-lifecycle-event-store-2026-09-02.md`](./spec-v186-lifecycle-event-store-2026-09-02.md) · [`plan-v186-lifecycle-event-store-2026-09-02.md`](./plan-v186-lifecycle-event-store-2026-09-02.md).

## Hecho

- P1-01…05: ENTRY accounting · `event_id_conflict` · identity envelope · payload · trail LONG
- Domain kernel `bolsa_domain.lifecycle` + espejo TS `lifecycle-events.ts`
- Alembic `015_lifecycle_events` · `PostgresLifecycleEventStore` · POST/GET FastAPI `/api/lifecycle/*`
- Vitest 22 · pytest domain 20 · application in-memory 3 · GP-V186 mock
- CI: domain + lifecycle unit en python offline · job **lifecycle-pg** requerido · filtro `+gp-v186`

## Reservas

- Tag `v1.86-beta` / Release-tag CI remoto aún no stampado
- Mesa `/portfolio` sigue mock Playwright (no sustituido por event store)
- V1.87 integrated (auth · isolation · recon · restart proceso) OUT

## OUT (intactos)

- LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger
- Playwright en `frontend-ci` · integrated E2E obligatorio · thaw estricto

## Next

**Auditoría externa tip V1.86** tras CI GREEN · o **V1.87 Integrated Golden Certification** — **sin** abrir LIVE.

## Texto exacto — arranque chat nuevo (dev)

```text
Partida: V1.86 CERRADA (código) · ENTRY accounting + PG event store + P1-01…05.
Leer: docs/CURRENT_SYSTEM.md · docs/engineering/traspaso-relevo-v1-86-lifecycle-event-store-2026-09-02.md · arranque-auditor-v1-86.
Freeze: NO LIVE · no bump 1.35.0-beta · no Playwright en frontend-ci · no integrated obligatorio · no V1.87 aún.
No commitear **/logs/.
```
