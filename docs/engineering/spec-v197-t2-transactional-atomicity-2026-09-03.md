# Spec — V1.97 T2 Transactional Atomicity + Replay/Crash (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CI GREEN** · tip [`v1.97-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.97-beta) → [`2e9d4675`](https://github.com/jvelasca/Bolsa_V1/commit/2e9d4675) · Release-tag CI **GREEN** ([run 33812286022](https://github.com/jvelasca/Bolsa_V1/actions/runs/33812286022)).  
> **Padre:** [`respuesta-auditor-v196-final-beta-certification-2026-09-03.md`](./respuesta-auditor-v196-final-beta-certification-2026-09-03.md).  
> **Partida:** tip [`v1.96-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.96-beta) → [`30479e97`](https://github.com/jvelasca/Bolsa_V1/commit/30479e97) · CI GREEN ([run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820)).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
t1_executed
  → validate T2_TRIGGERED + T2_EXECUTED in memory
  → single begin_nested / append_many
  → both persisted OR neither

crash mid-pair → retry
  → exactly 1 T2_TRIGGERED
  → exactly 1 T2_EXECUTED
  → exactly 1 ledger fill T2
  → exactly 1 PositionRevision T2
  → 0 doble broker submit
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** auto-heal.  
**No** Playwright obligatorio en `frontend-ci`.  
**No** `queue_sequence` Alembic.  
**No** E2E integrado (sigue opt-in; Stabilization).  
**No** features de producto nuevas.  
**No** migración Alembic (sigue `019_outbox_position_fifo`).

## 1. Entregas

| ID    | Entrega                                                                                                | Prioridad |
| ----- | ------------------------------------------------------------------------------------------------------ | --------- |
| D0    | respuesta auditor V1.96 + spec/plan/relevo/arranque V1.97 + CURRENT_SYSTEM en commit etiquetable       | P2        |
| P2-01 | `append_many` + par atómico `T2_TRIGGERED`+`T2_EXECUTED` (SEMI+AUTO+outbox vía `AppendLifecycleEvent`) | P2        |
| P2-02 | Batería crash/replay: unit + PG store + worker/Confirm                                                 | P2        |
| P2-03 | Tag `v1.97-beta` sobre SHA con stamp documental (no feature-only)                                      | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · `queue_sequence` · heartbeat · auto-heal · Playwright frontend-ci obligatorio · features mesa · E2E integrado · compose `unavailable`→blocked · arquitectura nueva

## 3. Criterio de cierre

P0=0 · P1=0 · P2 puente cerrados con inject crash mid-pair.  
Ruff + Typecheck + Release-tag CI GREEN (`lifecycle-pg` incluye V1.96 + V1.97).  
Imposible (bajo inject) `OPEN+T1+T2_TRIGGERED` sin `T2_EXECUTED` tras COMMIT.  
Tag = stamp. **No** declarar E2E browser certificado. **No** LIVE.
