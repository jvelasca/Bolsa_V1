# Spec — V1.93 Operational Failure Injection (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CERRADA (CI GREEN)** · tip [`v1.93-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.93-beta) → [`7168de3a`](https://github.com/jvelasca/Bolsa_V1/commit/7168de3a) · CI [run 33759914125](https://github.com/jvelasca/Bolsa_V1/actions/runs/33759914125) · partida [`v1.92-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.92-beta) → [`752918ef`](https://github.com/jvelasca/Bolsa_V1/commit/752918ef).  
> **Padre:** [`respuesta-auditor-v192-lifecycle-concurrency-worker-cert-2026-09-03.md`](./respuesta-auditor-v192-lifecycle-concurrency-worker-cert-2026-09-03.md).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
Worker TX split:
  TX1  claim_batch → COMMIT (processing durable)
  TX2  Append + mark_applied|mark_attempt → COMMIT
       crash → processing + stale reclaim → idempotent OK

Cert PG: post-claim · mid-append · idempotent reclaim · 3 workers · reconnect · kick∥worker

Stats JWT + SLA ages · recon PositionState ↔ Lifecycle (detect/report)
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** Playwright obligatorio en `frontend-ci`.  
**No** `queue_sequence` Alembic.  
**No** features de producto nuevas.

## 1. Entregas

| ID    | Entrega                                                                 | Prioridad |
| ----- | ----------------------------------------------------------------------- | --------- |
| D0    | respuesta auditor V1.92 + spec/plan/relevo/arranque V1.93 + docs stamp  | P2        |
| P2-01 | `GET /outbox/stats` → `require_jwt_principal` + test 401                | P2        |
| P2-02 | README tip vivo (no `v1.8.0-beta`)                                      | P2        |
| P1    | Worker TX1 claim commit / TX2 append+mark (kick HTTP intacto)           | P1        |
| P1    | Suite PG failure injection (crash / idempotent / 3 workers / reconnect) | P1        |
| P2-04 | SLA ages + `slaBreached` en stats + Consola                             | P2        |
| P2    | Recon PositionState↔Lifecycle detect/report + HTTP + Consola            | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · `queue_sequence` · timestamp AUTO fill-time · T2_TRIGGERED real-only · thaw estricto · Playwright frontend-ci obligatorio · restart físico PostgreSQL en GHA · features mesa/producto

## 3. Criterio de cierre

CI `lifecycle-pg` GREEN con worker V1.92 **más** crash post-claim, crash mid-append, idempotent reclaim, tres workers, reconnect. Stats JWT 401. README alineado. Freeze verde. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.93.
