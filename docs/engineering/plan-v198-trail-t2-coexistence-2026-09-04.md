# Plan — V1.98 Trail + T2 Coexistence

> **Padre:** [`spec-v198-trail-t2-coexistence-2026-09-04.md`](./spec-v198-trail-t2-coexistence-2026-09-04.md).  
> **Estado:** **IN** · partida `v1.97-beta` → `2e9d4675`.

| ID    | Entrega                                                                         | Estado |
| ----- | ------------------------------------------------------------------------------- | ------ |
| P1-01 | `TRANSITIONS` Python: trail self-loop · trailing→T2 · t2→trail · t2_ready→CLOSE | DONE   |
| P1-02 | `last_fill_price` + guard TRAIL (mock accounting intacto)                       | DONE   |
| P1-03 | `needs_atomic_t2_pair` desde `trailing`                                         | DONE   |
| P1-04 | Sync TS FSM + SHORT trail_relaxation                                            | DONE   |
| P2-01 | `stop_worsens` en dominio; analytics/DEX-5 delegan                              | DONE   |
| P2-02 | Tests domain + bridge trailing + vitest                                         | DONE   |
| D0    | spec/plan/relevo/arranque + CURRENT_SYSTEM                                      | DONE   |

## Política

- Trail + T2 **conviven** tras T1 (regla de producto alineada con ExitPolicy).
- `t2_ready` + `TRAIL_APPLIED` sigue ilegal (par a medias).
- Sin Alembic. Freeze LIVE / `PAPER_D_EXECUTE` off.

## OUT

- LIVE · bump · unificar ledger · PAPER_D_EXECUTE on · SEMI protect→TRAIL sidecar · open→T2/TRAIL · LineagePath flags
