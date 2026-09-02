# Relevo — V1.87 Lifecycle Operational Integration & Concurrency

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tip [`v1.87-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.87-beta) → [`646b97ac`](https://github.com/jvelasca/Bolsa_V1/commit/646b97ac) · [run 33689747400](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400) **success**.  
> **Partida:** V1.86 auditoría NO beta estable · tip [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md).  
> **Spec/plan:** [`spec-v187-lifecycle-operational-certification-2026-09-02.md`](./spec-v187-lifecycle-operational-certification-2026-09-02.md) · [`plan-v187-lifecycle-operational-certification-2026-09-02.md`](./plan-v187-lifecycle-operational-certification-2026-09-02.md).  
> **Relevo tag / arranque:** [`traspaso-relevo-tag-v1-87-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-87-beta-2026-09-02.md) · [`arranque-auditor-v1-87-beta-2026-09-02.md`](./arranque-auditor-v1-87-beta-2026-09-02.md).

## Hecho

- P0: JWT obligatorio en POST/GET `/api/lifecycle/*` · account/position ownership → 401/403/404
- P1: `sequence_no` + `lifecycle_aggregates` + `SELECT … FOR UPDATE` + `UNIQUE(position_id, sequence_no)`
- P1: Alembic 015 ensure-indexes · 016 sequence · CI `lifecycle-pg` hace `alembic upgrade head` (sin `metadata.create`)
- P1: DTO `extra="forbid"` · Decimal domain→DB · `IntegrityError` clasificado (`fill_id` ≠ `event_id`)
- Mock fill IDs namespaced por `position_id` (UNIQUE global fill_id seguro multi-posición)
- Tests: DTO offline · in-memory concurrent T1 · PG alembic/schema + concurrent + auth · **34 passed** local
- **stamp CI GREEN remoto** tip `646b97ac`

## Reservas

- Mesa `/portfolio` sigue mock Playwright
- V1.88 integrated golden + kill/restart API + recon real **OUT**
- Tag certifica tip código `646b97ac`; docs stamp post-GREEN en `main` (no exige retag)

## OUT (intactos)

- LIVE · scheduler · bump `1.35.0-beta` · `dryRun=false` browser · fills ledger
- Playwright en `frontend-ci` · integrated E2E obligatorio · thaw estricto
- Lifecycle accounting ≠ autoridad de equity de cartera (ledger)

## Next

**Auditoría externa tip V1.87** — **sin** abrir LIVE · **sin** V1.88 aún.

## Texto exacto — arranque chat nuevo (dev)

```text
Partida: V1.87 CERRADA · tip código 646b97ac (tag v1.87-beta) · CI GREEN run 33689747400 · pre-release v1.87-beta.
Leer: docs/CURRENT_SYSTEM.md · docs/engineering/traspaso-relevo-tag-v1-87-beta-2026-09-02.md · arranque-auditor-v1-87-beta (externo).
Freeze: NO LIVE · no bump 1.35.0-beta · no Playwright en frontend-ci · no integrated obligatorio · no V1.88 aún.
No commitear **/logs/.
```
