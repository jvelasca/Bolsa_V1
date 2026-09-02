# Relevo — V1.86 Lifecycle Event Store (FastAPI + PostgreSQL)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tip [`v1.86-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta) → [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · [run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402) **success**.  
> **Partida:** V1.85 PASS modelo mock · tip [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3) · auditoría [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md).  
> **Spec/plan:** [`spec-v186-lifecycle-event-store-2026-09-02.md`](./spec-v186-lifecycle-event-store-2026-09-02.md) · [`plan-v186-lifecycle-event-store-2026-09-02.md`](./plan-v186-lifecycle-event-store-2026-09-02.md).  
> **Relevo tag / arranque:** [`traspaso-relevo-tag-v1-86-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-86-beta-2026-09-02.md) · [`arranque-auditor-v1-86-beta-2026-09-02.md`](./arranque-auditor-v1-86-beta-2026-09-02.md).

## Hecho

- P1-01…05: ENTRY accounting · `event_id_conflict` · identity envelope · payload · trail LONG
- Domain kernel `bolsa_domain.lifecycle` + espejo TS `lifecycle-events.ts`
- Alembic `015_lifecycle_events` · `PostgresLifecycleEventStore` · POST/GET FastAPI `/api/lifecycle/*`
- Idempotent CLOSE replay estable (normalize vs prefix)
- Vitest 23 · pytest domain 21 · GP-V186 · **lifecycle-pg** GREEN
- Filtro CI `+gp-v186` · **stamp CI GREEN remoto** tip `baaa7034`

## Reservas

- Mesa `/portfolio` sigue mock Playwright (no sustituido por event store)
- V1.87 integrated (auth · isolation · recon · restart proceso) OUT
- Tag certifica tip código `baaa7034`; docs stamp post-GREEN en `main` (no exige retag)

## OUT (intactos)

- LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger
- Playwright en `frontend-ci` · integrated E2E obligatorio · thaw estricto

## Next

**Auditoría externa tip V1.86** — **sin** abrir LIVE · **sin** V1.87 aún.

## Texto exacto — arranque chat nuevo (dev)

```text
Partida: V1.86 CERRADA · tip código baaa7034 (tag v1.86-beta) · CI GREEN run 33686297402 · pre-release v1.86-beta.
Leer: docs/CURRENT_SYSTEM.md · docs/engineering/traspaso-relevo-tag-v1-86-beta-2026-09-02.md · arranque-auditor-v1-86-beta (externo).
Freeze: NO LIVE · no bump 1.35.0-beta · no Playwright en frontend-ci · no integrated obligatorio · no V1.87 aún.
No commitear **/logs/.
```
