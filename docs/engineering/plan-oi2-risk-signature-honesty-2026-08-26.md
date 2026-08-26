# Plan — OI-2 Risk signature honesty

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 §3.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**

---

## Objetivo

Evitar que una apertura SEMI pase la firma de riesgo sin **TradePlan TRIGGERED**. `mode=no_plan` debe **fail-closed** cuando el contexto es recomendación de apertura (`recommend_long` / `recommend_short`).

Manual HTTP (`POST /portfolio/trade`) **no** usa `risk_signature` — sin cambio (I1).

## Decisiones

| ID  | Decisión                                                                                                   |
| --- | ---------------------------------------------------------------------------------------------------------- |
| D1  | Nuevo flag `require_triggered_plan` / `requireTriggeredPlan` (default **false** para compat display-only). |
| D2  | Confirm SEMI opening pasa `require_triggered_plan=True` en `risk_signature_reject_reason`.                 |
| D3  | Sin plan TRIGGERED → `allowed=False`, `blockReason=no_tradeplan`, `reason=risk_signature`.                 |
| D4  | UI F3 panel y `f3-risk-signature-block` muestran copy explícito para `no_tradeplan`.                       |
| D5  | WATCH sin plan sigue siendo display-only en preview; **no** autoriza Confirm execute.                      |

## Ficheros

- `packages/py/analytics/.../risk_signature.py`
- `packages/shared/.../risk-signature.ts`
- `confirm_recommendation.py` — `require_triggered_plan=True` en opening
- `supervised-f3-panel.tsx` · `f3-risk-signature-block.tsx`
- Tests: `test_risk_signature.py` · `risk-signature.test.ts` · `test_confirm_risk_signature.py` · idempotency/journal/persist fixtures con `tradePlan` TRIGGERED

## E1

**OI-3** ExecutionRecord **o** operar SEMI checklist (manual+protect+plan TRIGGERED).
