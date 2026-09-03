# Plan — V1.95 Beta Certification

> **Padre:** [`spec-v195-beta-certification-2026-09-03.md`](./spec-v195-beta-certification-2026-09-03.md).  
> **Estado:** **CÓDIGO LOCAL LISTO** · partida [`v1.94-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.94-beta) → [`363984d2`](https://github.com/jvelasca/Bolsa_V1/commit/363984d2) · **pendiente** push + tag + CI GREEN remoto.

| ID   | Entrega                                                                     | Estado       |
| ---- | --------------------------------------------------------------------------- | ------------ |
| D0   | respuesta auditor V1.94 + AUDITORIA 2 + spec/plan/relevo/arranque + CURRENT | DONE         |
| P1   | Ruff + contract:gen + units offline CI                                      | DONE (local) |
| P1   | `dead_non_head` no-clean · lag DENY · compose en OR-4                       | DONE         |
| P1   | Fill chain FILL_KINDS + Golden HTTP V1.95                                   | DONE         |
| P1-A | HTTP `None` → blocked JSON; lookup → `unavailable`                          | DONE         |
| P1-B | FIFO outbox sort key UTC-aware                                              | DONE         |
| P2   | Reuso PositionState · Consola ops state dominante                           | DONE         |
| CI   | Python/Frontend/Release-tag GREEN remoto                                    | PENDING      |

## Política

- Opening ALLOW iff compose `status=clean` (lag/drift/blocked/unavailable DENY).
- `dead_non_head`: issue code FIFO-distinto; status lifecycle no-clean (`lag` wire) → ops **DEGRADED**; gate DENY.
- Fill applied `POSITION_OPENED`/`T1_EXECUTED`/`T2_EXECUTED`/`POSITION_CLOSED` deben estar en ledger `reference_id`.
- Exits siguen bypasseando OR-4.
- Integrity/recon HTTP: nunca `assert`; `report is None` → payload nombrado `blocked` / ops `BLOCKED`.

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · queue_sequence · heartbeat · auto-heal · Playwright frontend-ci obligatorio
- Commitear `**/logs/`
- Declarar BETA estable sin CI GREEN + auditoría tip
