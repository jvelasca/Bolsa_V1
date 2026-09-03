# Plan — V1.96 Final Beta Certification / T2

> **Padre:** [`spec-v196-final-beta-certification-2026-09-03.md`](./spec-v196-final-beta-certification-2026-09-03.md).  
> **Estado:** **CI GREEN** · tip [`v1.96-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.96-beta) → [`30479e97`](https://github.com/jvelasca/Bolsa_V1/commit/30479e97) · [run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820).

| ID    | Entrega                                                       | Estado |
| ----- | ------------------------------------------------------------- | ------ |
| D0    | respuesta auditor V1.95 + spec/plan/relevo/arranque + CURRENT | DONE   |
| P1-01 | SEMI TARGET_2 → T2_EXECUTED + puente compartido               | DONE   |
| P1-02 | reason_code en outbox payload + drain                         | DONE   |
| P1-03 | Idempotencia T2 distinta de T1                                | DONE   |
| P1-04 | Golden HTTP V1.96 + units + lifecycle-pg include              | DONE   |
| CI    | Python/Frontend/Release-tag GREEN remoto                      | DONE   |

## Política

- Confirm `reduce` + `exitPlan.primaryReason=TARGET_2` emite `T2_TRIGGERED` + `T2_EXECUTED` (paridad AUTO).
- Resto de `reduce` sigue `T1_EXECUTED`.
- Drain remapea desde payload: `reason_code` debe viajar en outbox.
- Golden V1.95 (OPEN→T1→EXIT) permanece como regresión.
- Opening ALLOW iff compose `status=clean`.

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · queue_sequence · heartbeat · auto-heal · Playwright frontend-ci obligatorio
- E2E integrado · compose portfolio unavailable→blocked
- Commitear `**/logs/`
- Declarar BETA estable sin auditoría tip
