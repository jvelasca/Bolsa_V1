# Plan — OR-2 Crash/restart recovery (UNKNOWN reconstruible)

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **382**.
> **Relevo:** [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./traspaso-relevo-or2-crash-restart-2026-08-26.md).

---

## Objetivo

El escenario de crash del auditor:

```text
Confirm → record intento → adapter.submit (puede haber llegado al venue)
→ el proceso muere antes de responder
→ reinicio / retry Confirm
→ ExecutionRecord unknown + mismos intent_id / order_id
→ mapeo intent ↔ venue_order_id si ya se conoció
nunca un segundo adapter.submit a ciegas
```

OR-1 cierra retry **post-fill**. OR-2 cierra retry **sin fill local**: el intento ya se registró.

## Decisiones

| ID  | Decisión                                                                                                                                                                                                                      |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Identidad = `decision_id` (OR-1). Objeto `DurableSubmitIntent` (fase `recorded` \| `venue_bound` \| `filled`). **No** es la state machine OR-3 (`SUBMITTED`/`ACK`/…). PaperOrder sigue `CREATED`\|`FILLED`.                   |
| D2  | Puerto `SubmitIntentStore` (get/put). Confirm **persiste `recorded` antes** de `adapter.submit`. Si `put` falla → `error` pre-send (no se envía).                                                                             |
| D3  | Store con fila para ese `decision_id` y **sin** fill local → reconstruir `UNKNOWN`, **no** `adapter.submit`. Fill local sigue ganando (OR-1).                                                                                 |
| D4  | Tras el adapter: `venue_order_id` → `venue_bound` (mapeo durable); fill → `filled`. Recovery adjunta `venueOrderId` si existe.                                                                                                |
| D5  | **Sin Alembic.** El store es el límite de durabilidad. Tests = store compartido entre «procesos». Producción = singleton de proceso (retry mismo worker). Tabla PG / Redis multi-worker = parked (plan explícito si se abre). |
| D6  | Tests spine: crash post-record; crash post-mapeo venue; retry live `submitted` = 1 submit; fill local sigue short-circuit. Sin `contract:gen`.                                                                                |
| D7  | **No** OR-3 machine · **no** veto recon (OR-4) · **no** auto-heal · **no** CTA LIVE · **no** FillPending en esta rebanada.                                                                                                    |

## Kernel

```text
fill local ya existe              → replay executed (OR-1; no adapter)
store tiene intento, sin fill     → UNKNOWN reconstruido (no adapter)
si no                             → put recorded → adapter.submit
                                   → bind venue_order_id | mark filled
crash entre recorded y ack        → UNKNOWN (crash_before_venue_ack)
crash tras venue_order_id         → UNKNOWN + mapeo (no re-POST)
```

## Ficheros

- [`submit_intent.py`](../../packages/py/analytics/src/bolsa_analytics/cognitive/submit_intent.py) + espejo TS
- [`submit_intent_store.py`](../../packages/py/application/src/bolsa_application/submit_intent_store.py)
- [`confirm_recommendation.py`](../../packages/py/application/src/bolsa_application/confirm_recommendation.py)
- Tests: `test_submit_intent.py` · `test_confirm_crash_restart.py`
- Spine: `pnpm test:decision-spine`

## DoD

- [x] Crash post-`recorded` → `unknown` + mismos ids · 0 `adapter.submit` en el retry.
- [x] Crash post-`venue_bound` → `unknown` + `venueOrderId` · 0 re-POST.
- [x] Retry Confirm live `submitted` (mismo store) → 1 submit.
- [x] Fill local (OR-1) sigue ganando al in-flight.
- [x] Sin Alembic · sin `contract:gen` · OI-3/OI-4 outcomes intactos · PaperOrder no gana estados.
- [x] Docs: stamp CURRENT_SYSTEM / ADR-035 / CHANGELOG Unreleased · relevo OR-2.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · no OR-3 machine · no veto recon (OR-4) · thin 5.x/8.x congelados · Lab ≠ mesa.

## E1

Tras OR-2: **OR-3** order state machine **o** operar SEMI. **No** OR-4/OR-5/OR-6 en el mismo chat.
