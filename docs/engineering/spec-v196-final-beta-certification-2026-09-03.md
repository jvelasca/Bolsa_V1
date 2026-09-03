# Spec — V1.96 Final Beta Certification / T2 + operational freeze (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CI GREEN** · tip [`v1.96-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.96-beta) → [`30479e97`](https://github.com/jvelasca/Bolsa_V1/commit/30479e97) · [run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820).  
> **Padre:** [`respuesta-auditor-v195-beta-certification-2026-09-03.md`](./respuesta-auditor-v195-beta-certification-2026-09-03.md).  
> **Partida:** [`v1.95-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.95-beta) → [`6f262293`](https://github.com/jvelasca/Bolsa_V1/commit/6f262293) · CI GREEN ([run 33804374800](https://github.com/jvelasca/Bolsa_V1/actions/runs/33804374800)).  
> **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.  
> **No** declarar BETA estable / PAPER explotable hasta auditoría tip V1.96.

```text
Confirm OPEN → T1 → T2 → EXIT
  → GET /lifecycle/integrity  clean / operationalState=OK
  → corrupt T2 ledger reference
  → integrity drift / BLOCKED
  → Confirm new OPEN = DENY
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** auto-heal.  
**No** Playwright obligatorio en `frontend-ci`.  
**No** `queue_sequence` Alembic.  
**No** E2E integrado (sigue opt-in; último pendiente **después** de V1.96).  
**No** `portfolio_status=unavailable` → blocked en compose (P2 registrado).  
**No** features de producto nuevas.

## 1. Entregas

| ID    | Entrega                                                                                          | Prioridad |
| ----- | ------------------------------------------------------------------------------------------------ | --------- |
| D0    | respuesta auditor V1.95 + spec/plan/relevo/arranque V1.96 + CURRENT_SYSTEM coherente en el tag   | P2        |
| P1-01 | Confirm SEMI `reduce`+`TARGET_2` → `T2_EXECUTED` + puente `T2_TRIGGERED` (mismo helper que AUTO) | P1        |
| P1-02 | `reason_code` en payload outbox (drain remapea; sin él T2 se degrada a T1)                       | P1        |
| P1-03 | Idempotencia Confirm: T2 reduce no colisiona con T1 (mismo `decisionId`+action+side)             | P1        |
| P1-04 | Golden HTTP V1.96 OPEN→T1→T2→EXIT→corrupt T2→OPEN DENY + units offline                           | P1        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · `queue_sequence` · heartbeat · auto-heal · Playwright frontend-ci obligatorio · features mesa · E2E integrado · compose `unavailable`→blocked · declarar PAPER explotable antes de auditoría tip + CI GREEN

## 3. Criterio de cierre

P0=0 · P1 cobertura T2=0 · Ruff GREEN · Typecheck GREEN · Release-tag CI GREEN (`lifecycle-pg` incluye golden V1.96) · Confirm OPEN DENY tras corrupción T2 · Freeze verde. **Aún no** declarar «beta PAPER explotable» / BETA estable hasta auditoría tip V1.96.
