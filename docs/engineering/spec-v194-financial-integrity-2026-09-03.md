# Spec — V1.94 Financial Integrity & Reconciliation (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CÓDIGO LISTO** (pendiente tag/CI GREEN remoto) · partida tip [`v1.93-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.93-beta) → [`7168de3a`](https://github.com/jvelasca/Bolsa_V1/commit/7168de3a) · CI [run 33759914125](https://github.com/jvelasca/Bolsa_V1/actions/runs/33759914125).  
> **Padre:** [`respuesta-auditor-v193-operational-failure-injection-2026-09-03.md`](./respuesta-auditor-v193-operational-failure-injection-2026-09-03.md).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
Confirm fill (transactions.id)
  → PositionState + outbox (same TX)
  → Lifecycle events (worker TX1≠TX2)
  → Ledger reference_id = tx_id

FinancialIntegrity (detect/report):
  OI-6 cash/holdings  ⊕  Lifecycle↔PositionState simétrico  ⊕  fill links
  → operationalState OK|DEGRADED|BLOCKED
  → OR-4 opening veto on drift|blocked
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** auto-heal.  
**No** Playwright obligatorio en `frontend-ci`.  
**No** `queue_sequence` Alembic.  
**No** heartbeat / `processing_started_at` (P2-05 aparcado).  
**No** features de producto nuevas.

## 1. Entregas

| ID    | Entrega                                                                | Prioridad |
| ----- | ---------------------------------------------------------------------- | --------- |
| D0    | respuesta auditor V1.93 + spec/plan/relevo/arranque V1.94 + docs stamp | P2        |
| P2-01 | Recon simétrica Lifecycle→PositionState (`orphan_lifecycle`)           | P2        |
| P2-02 | `dead_head` = FIFO head; `dead_non_head` ≠ blocked                     | P2        |
| P2-03 | Batch `list_events_for_account` (sin N+1 snapshots)                    | P2        |
| P2-04 | `operationalState` distinto de `slaBreached` + Consola                 | P2        |
| P1    | Fill chain: `open_transaction_id` ↔ `fill_id` ↔ ledger `reference_id`  | P1        |
| P1    | `GET /lifecycle/integrity` + compose OI-6 + OR-4 veto apertura         | P1        |
| P1    | Suite PG integrity + rename step CI                                    | P1        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · `queue_sequence` · heartbeat · auto-heal · Playwright frontend-ci obligatorio · features mesa/producto · declarar PAPER explotable antes de auditoría tip

## 3. Criterio de cierre

CI `lifecycle-pg` GREEN con V1.88–V1.93 **más** integrity (orphan, dead_head vs non-head, fill mismatch, crash→clean, JWT 401). Freeze verde. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.94.
