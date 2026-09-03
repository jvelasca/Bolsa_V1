# Plan — V1.90 Lifecycle Reliability

> **Padre:** [`spec-v190-lifecycle-reliability-2026-09-03.md`](./spec-v190-lifecycle-reliability-2026-09-03.md).  
> **Estado:** **CERRADA** · **stamp CI GREEN remoto DONE** — [`v1.90-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.90-beta) → [`0c2e3af7`](https://github.com/jvelasca/Bolsa_V1/commit/0c2e3af7) · [run 33726147414](https://github.com/jvelasca/Bolsa_V1/actions/runs/33726147414) · partida [`v1.89-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.89-beta) → [`58806be1`](https://github.com/jvelasca/Bolsa_V1/commit/58806be1).

| ID  | Entrega                                          | Estado |
| --- | ------------------------------------------------ | ------ |
| D0  | respuesta auditor V1.89 + spec/plan/relevo V1.90 | DONE   |
| P0  | Idempotencia sin `now()` + tests                 | DONE   |
| P0  | Alembic 017 outbox + drain                       | DONE   |
| P0  | Golden Confirm→lifecycle V1.90 + CI lifecycle-pg | DONE   |
| P1  | AUTO lifecycle_from_auto + hook                  | DONE   |
| P1  | SHORT ratchet + reject recommend_short           | DONE   |
| P2  | Mesa labels + OpenAPI tipado                     | DONE   |

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · Playwright frontend-ci obligatorio
- Commitear `**/logs/`
