# Plan — OI-1 Continuidad operativa

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**

---

## Objetivo

Cerrar los cuatro agujeros de continuidad detectados en auditorías post-v1.10:

1. Manual `POST /portfolio/trade` → PositionState
2. Pending SELL → `PersistPositionFromExit`
3. Confirm no miente si fill OK y persist falla
4. Proteger persiste stop operativo (≠ broker)
5. Lab `executeTrades` → exit persist si `trade_executed`

## Decisiones D1–D8

Ver plan adjunto en chat OI-1 · ADR-034 §2.

## Ficheros

- `post_fill_position_sync.py` · `persist_position_from_protect.py`
- `execute_gated_portfolio_trade.py` · `fill_pending_order.py` · `confirm_recommendation.py` · `position_exit_evaluator.py`
- `dependencies.py` · `supervised-f3-panel.tsx`
- Tests: `test_post_fill_position_sync.py` · `test_persist_position_from_protect.py` · ampliaciones confirm/fill/gated

## E1

Operar SEMI (manual buy → fila `human_manual`; protect → stop persistido) **o** plan OI-2.
