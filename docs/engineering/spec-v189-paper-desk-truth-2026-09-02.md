# Spec — V1.89 PAPER Desk Truth (SEMI) (2026-09-02)

> **AsOf:** 2026-09-02 · **Estado:** **ABIERTA**  
> **Padre:** [`respuesta-auditor-v188-lifecycle-integrated-golden-2026-09-02.md`](./respuesta-auditor-v188-lifecycle-integrated-golden-2026-09-02.md).  
> **Partida tip:** `v1.88-beta` → [`33685242`](https://github.com/jvelasca/Bolsa_V1/commit/33685242). **No** LIVE · **no** bump · **no** unificar cash ledger.

```text
CONFIRM SEMI (execute=true) paper fill OK
  → PositionSync (existente)
  → AppendLifecycleEvent (sidecar)     ← NEW
  → cash ledger (intacto, no merge)

GET /api/lifecycle/positions/{id}/snapshot  ← desk / cert lee stage

GOLDEN RECON:
  OPEN→T1 → HTTP resolve → HTTP clear (recon_status_for_incident_clear)
  → TRAIL→EXIT→CLOSED
```

## 0. Freeze (enmendado solo en desk truth)

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** sustituir `/portfolio` por lifecycle (sidecar + snapshot).  
**No** Playwright obligatorio en `frontend-ci`.  
**No** cablear ExecutionRouter AUTO como writer primario.

## 1. Entregas

| ID  | Entrega                                                                   | Prioridad |
| --- | ------------------------------------------------------------------------- | --------- |
| P0  | Helper `lifecycle_from_fill` + hook post-`PositionSync` (Confirm)         | P0        |
| P0  | Idempotencia `fillId`/`eventId` = `transaction_id`                        | P0        |
| P0  | Golden: recon vía HTTP resolve/clear (fail-closed look-up)                | P0        |
| P1  | Confirm open/reduce/exit → GET snapshot stage coherente                   | P1        |
| P1  | Mesa/cert lee snapshot stage (sin depender de e2e mock para esa aserción) | P1        |
| P2  | Mismo helper en `/portfolio/trade` + FillPending (opcional mismo slice)   | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · auto-heal books · `PAPER_D_EXECUTE` on · retag V1.88

## 3. Criterio de cierre

Tests PG/CI demuestran Confirm→append→snapshot + golden recon HTTP. Freeze checklist verde. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.89.
