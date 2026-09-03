# Spec — V1.92 Lifecycle Concurrency & Worker Certification (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tag [`v1.92-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.92-beta) → [`752918ef`](https://github.com/jvelasca/Bolsa_V1/commit/752918ef) · [run 33754485267](https://github.com/jvelasca/Bolsa_V1/actions/runs/33754485267) **success**.  
> **Padre:** [`respuesta-auditor-v191-operational-atomicity-2026-09-03.md`](./respuesta-auditor-v191-operational-atomicity-2026-09-03.md).  
> **Partida tip:** `v1.91-beta` → [`4644fef9`](https://github.com/jvelasca/Bolsa_V1/commit/4644fef9). **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
Outbox claim = FIFO cabeza por position_id
  → máximo 1 evento claimable por posición
  → multi-worker seguro (OPEN → T1 → EXIT)

LifecycleOutboxWorker (proceso real)
  → pending → processing → applied | dead
  → stale reclaim (>120s)
  → CI lifecycle-pg certifica el loop

Consola: pending | processing | dead | oldestPendingAge
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** Playwright obligatorio en `frontend-ci`.  
AUTO preparado, **no** activado por defecto.  
**No** features de producto nuevas.

## 1. Entregas

| ID    | Entrega                                                             | Prioridad |
| ----- | ------------------------------------------------------------------- | --------- |
| P1-02 | `claim_batch` FIFO por `position_id` (PG + in-memory) + Alembic 019 | P1        |
| P1-01 | Certificar worker real PG: pending→processing→applied               | P1        |
| P1-02 | Dos workers misma posición OPEN→T1→EXIT orden determinista          | P1        |
| P2-06 | Worker crash → stale claim → segundo worker → recovery              | P2        |
| P2-03 | Aserción Golden `errors == 0` + `applied >= expected`               | P2        |
| P2    | Replay Confirm: no segundo transactionId de ejecución               | P2        |
| P2-04 | `GET /lifecycle/outbox/stats` + card Consola Operativa              | P2        |
| P2-05 | Docs CURRENT_SYSTEM / index / respuesta auditor V1.91               | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · timestamp AUTO fill-time · T2_TRIGGERED real-only · Playwright frontend-ci obligatorio · advisory locks · secuencia extra en outbox · features mesa/producto

## 3. Criterio de cierre

CI `lifecycle-pg` GREEN con worker real + dos workers misma posición + crash/stale + golden V1.88/V1.90/V1.91. Freeze intacto. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.92.
