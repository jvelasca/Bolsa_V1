# RELEVO — V1.42 F2b SubmitIntent read list (2026-08-31)

> **Padre:** [`plan-v142-f2b-submit-intent-list-2026-08-31.md`](./plan-v142-f2b-submit-intent-list-2026-08-31.md) · [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO** — GET in-flight + soft-join instrumentId; Mercado UNKNOWN sin Confirm.  
> **No tag** en este slice (código en tip; release-tag cuando el owner lo pida).

---

## 0. Qué cierra F2b

| Pieza                                                                        | Estado |
| ---------------------------------------------------------------------------- | ------ |
| `SubmitIntentStore.list_in_flight` (phases ≠ filled)                         | CÓDIGO |
| `GET /api/accounts/{account_id}/submit-intents`                              | CÓDIGO |
| Soft-join `decision_sessions.decision_id → instrument_id` (fail-closed null) | CÓDIGO |
| Web hook + wire → `buildExecutionState({ submitIntent })`                    | CÓDIGO |
| Cockpit UNKNOWN → «Ver operaciones» / sin Confirm                            | CÓDIGO |

**Regla:** list facts → mismo `ExecutionState` UNKNOWN en Mercado / Hoy / Journal / Operaciones. Nunca reenviar.

## 1. Freeze verificado

Confirm / `confirm_recommendation.py` / `confirm/submit_intent.py` recover · Router · `PAPER_D_EXECUTE` · AUTO execute · F2 precedencia · F3/F4 **intocados**.

## 2. Next (hoja, no implementar aquí)

| Tag | Nombre                              | Notas                |
| --- | ----------------------------------- | -------------------- |
| F3  | PositionOperatingTruth              | + prioridad CTA §A.8 |
| F4  | TradeStory                          | Journal consume      |
| F5+ | Mercado/Hoy 2.0 → SEMI → PAPER AUTO | Spec §D              |

## 3. Pre-flight cierre

Ver plan F2b §criterios.
