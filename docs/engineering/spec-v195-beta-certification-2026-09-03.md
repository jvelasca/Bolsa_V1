# Spec — V1.95 Beta Certification / Financial Integrity Close (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CI GREEN** · tip [`v1.95-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.95-beta) → [`6f262293`](https://github.com/jvelasca/Bolsa_V1/commit/6f262293) · [run 33804374800](https://github.com/jvelasca/Bolsa_V1/actions/runs/33804374800) · partida [`v1.94-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.94-beta) → [`363984d2`](https://github.com/jvelasca/Bolsa_V1/commit/363984d2).  
> **Padre:** [`respuesta-auditor-v194-financial-integrity-2026-09-03.md`](./respuesta-auditor-v194-financial-integrity-2026-09-03.md) + AUDITORIA 2 (borde HTTP + FIFO tz).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.  
> **No** declarar BETA estable / PAPER explotable hasta auditoría tip V1.95.

```text
Confirm OPEN → T1 → EXIT
  → GET /lifecycle/integrity  (compose: lifecycle ⊕ fill ⊕ OI-6)
  → corrupt fill/ledger or dead_*
  → integrity ≠ clean  →  Confirm new OPEN = DENY
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** auto-heal.  
**No** Playwright obligatorio en `frontend-ci`.  
**No** `queue_sequence` Alembic.  
**No** heartbeat / materialized operational state (P2-01 aparcado).  
**No** features de producto nuevas.

## 1. Entregas

| ID    | Entrega                                                                                                                           | Prioridad |
| ----- | --------------------------------------------------------------------------------------------------------------------------------- | --------- |
| D0    | respuesta auditor V1.94 + AUDITORIA 2 + spec/plan/relevo/arranque V1.95 + docs stamp                                              | P2        |
| P1-01 | Ruff GREEN · Typecheck GREEN · OpenAPI integrity + `operationalState`                                                             | P1        |
| P1-02 | `dead_non_head` nunca `clean`; ops DEGRADED; `dead_*` DENY apertura                                                               | P1        |
| P1-03 | `lag` DENY en opening gate                                                                                                        | P1        |
| P1-04 | Fill chain OPEN+T1+T2+EXIT; OR-4 usa compose (no solo lifecycle)                                                                  | P1        |
| P1-A  | GET `/integrity` + `/reconciliation`: `report is None` → JSON `blocked`/`BLOCKED` (nunca assert/500); OR-4 lookup → `unavailable` | P1        |
| P1-B  | `_outbox_sort_key` fallback UTC aware (+ naive→UTC); sin TypeError FIFO                                                           | P1        |
| P1    | Golden HTTP V1.95 + units en python-ci offline                                                                                    | P1        |
| P2-02 | Reusar PositionState del recon lifecycle (sin doble list)                                                                         | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · `queue_sequence` · heartbeat · auto-heal · Playwright frontend-ci obligatorio · features mesa · V1.96 por inercia · declarar PAPER explotable antes de auditoría tip + CI GREEN

## 3. Criterio de cierre

P0=0 · P1=0 · Ruff GREEN · Typecheck GREEN · Release-tag CI GREEN (lifecycle-pg incluye golden V1.95) · Confirm OPEN DENY con integrity no-clean · Freeze verde. **Aún no** declarar «beta PAPER explotable» / BETA estable hasta auditoría tip V1.95.
