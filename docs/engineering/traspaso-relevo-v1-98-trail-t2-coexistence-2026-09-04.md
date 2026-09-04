# RELEVO — V1.98 Trail + T2 Coexistence (2026-09-04)

> **Padre:** [`spec-v198`](./spec-v198-trail-t2-coexistence-2026-09-04.md) · [`plan-v198`](./plan-v198-trail-t2-coexistence-2026-09-04.md).  
> **Partida:** tip [`v1.97-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.97-beta) → `2e9d4675`.  
> **Estado:** implementación lista para CI / tip (tag pendiente).

## Hecho

- FSM Python: `trailing` ⇄ `TRAIL_APPLIED`, `trailing`→`T2_TRIGGERED`, `t2_executed`→trail/EXIT, `t2_ready`→`POSITION_CLOSED`
- `last_fill_price(log)` para geometría de trail; `last_price_for_stage` solo snapshots mock
- `needs_atomic_t2_pair` true desde `t1_executed` **y** `trailing`
- TS mock sincronizado + SHORT `trail_relaxation`
- `stop_worsens` canónico en `bolsa_domain.lifecycle`; analytics/`protect_stop_worsens_exposure` delegan
- Tests: domain V1.98 + bridge trailing + vitest FSM

## Residuales (OUT de esta slice)

- SEMI Confirm protect **no** escribe `TRAIL_APPLIED` (solo PositionRevision + journal)
- `open` → T2 / `open` → TRAIL no añadidos
- E2E integrado opt-in · LIVE bloqueado · `PAPER_D_EXECUTE` off

## Next

1. CI local / Release-tag cuando se etiquete `v1.98-beta`
2. Arranque auditor tip ([arranque](./arranque-auditor-v1-98-trail-t2-coexistence-2026-09-04.md))
3. Después: Beta Stabilization (no más capas FSM salvo residuales documentados)

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no Alembic · no auto-heal · no unificar ledger
