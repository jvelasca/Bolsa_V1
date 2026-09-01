# Spec — V1.48 Paper Desk Event Continuity

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v147-paper-desk-runtime-truth-2026-09-01.md`](./spec-v147-paper-desk-runtime-truth-2026-09-01.md).  
> **Plan:** [`plan-v148-paper-desk-event-continuity-2026-09-01.md`](./plan-v148-paper-desk-event-continuity-2026-09-01.md).  
> **Tip certificado previo:** `v1.47-beta` → `77f96ead`. **No** AUTO completo. EntryTick sigue **HonestStub** (Entry real = **V1.49**).

Cierra ambigüedades de Runtime Truth: el `eventId` persistido es la identidad de ejecución. **No** LIVE. `PAPER_D_EXECUTE` default **off**. **No** scheduler. **No** MarketProfile.

Runtime (no el diagrama aspiracional):

```text
MarketSnapshot → Evaluator → PositionEvent efímero
  → PositionPolicyDecision → ExitPermission JIT
  → claim events[] (solo execute; dry-run no escribe)
  → Protect CAS | Sell UNIQUE(eventId) → Fill → PositionRevision
  → ExecutionSnapshot + operatingState + nextAction
```

`sequence` es metadato servidor (conteo same-kind ese día). **No** entra en el hash de `eventId`.

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic (tabla nueva) · sin bump package · sin nav L1 · sin DeskRunner / scheduler · `HonestStubPaperDeskEntry` · dry_run default true · BME/ES hardcode intacto.

## 1. Honestidad V1.47 (TRAIL)

La clave `positionId|eventType|asOf|sequence|action` **no** la usa TRAIL/PROTECT. Solo REDUCE/EXIT, siempre con `sequence=1`. TRAIL era idempotente por **stop-delta** (`PositionRevision`). El hueco real: `PositionEvent` no persistía; dos workers TRAIL hacían read-modify-write sin CAS; `ExecutionSnapshot` estaba vacío.

## 2. Identidad de evento (P0)

- Log durable = `position_state.events[]` + `revisions[]` (mismo JSONB). TRAIL/PROTECT: `eventId` ligado a `revisionId` cuando hay cambio de stop.
- TRAIL/PROTECT: evento nuevo iff `next_stop` cambia. Mismo stop = replay. 182 luego 185 el mismo día = dos eventos.
- T1 REDUCE / STOP EXIT: un evento por `(positionId, eventType, asOf-day, action)`. Se reclama **antes** del sell.
- `executionIntentId` = `eventId` persistido (no la clave día-compuesta). Stop/qty van en el payload del evento.
- `sequence` lo asigna el servidor (conteo same-kind ese día). TRAIL puede ser 1, 2, 3… **No** forma parte de `eventId`.
- TRAIL/PROTECT: CAS `current_stop = expected_previous`. Perdedor = replay, no segunda revisión.
- REDUCE/EXIT: `UNIQUE(portfolio_id, idempotency_key)` con key = `eventId`. Violación = replay. Claim `None` → `event_claim_failed` (nunca `idempotency_key = positionId`).
- REDUCE sin `quantity` > 0 → `missing_reduce_quantity`. Solo EXIT puede asumir remaining.
- Redis/memoria `claim_auto_execute_idempotency` **no** es autoridad.

## 3. ExecutionTruth (P1)

`ExecutionSnapshot` se rellena desde `submit_intents` in-flight (y claves de eventos no resueltos). AUTO no crea un segundo intent si ya hay uno unresolved para ese `eventId`. Excepción de `list_in_flight` → snapshot vacío (**fail-open** de detección de intent; el backstop es UNIQUE `eventId`, no `positionId`). Simetría fail-closed con recon queda fuera (V1.49).

Recon: `clean | drift | unavailable`. Excepción de lookup → `unavailable`, **no** fingir drift. Entry fail-closed si drift **o** unavailable. Protective exit ALLOWED. Notas/UI distinguen «cartera con drift» vs «no se pudo verificar».

## 4. Acciones y estados

Cada fila PositionTick proyecta:

- `decisionAction` — HOLD / PROTECT / TRAIL / REDUCE / EXIT
- `executedAction` — NONE / APPLIED / DRY_RUN / DENIED
- `nextAction` — incluye **MONITOR**. Tras protect/trail **APPLIED** → MONITOR. `SUBIR_STOP` solo si hay trail propuesto y aún no aplicado (p. ej. dry-run). Dry-run ≠ APPLIED.

`operatingState` (proyección, no motor nuevo): `OPEN_UNPROTECTED` · `PROTECTED` · `TRAILING` · `PARTIALLY_REDUCED` · `EXIT_PENDING` · `CLOSED` · `RECONCILIATION_ERROR`.

## 5. Freshness (honesty, no matriz)

STALE puede devolver mark para diagnóstico/UI. AUTO no-protectivo se mantiene en hold. Protective JIT puede seguir. **No** se implementan flags `fresh_for_analysis|entry|protect|exit` en este slice.

Contrato V1.44 (no es bug): T1/T2/TIME con mercado cerrado → `HOLD` + `queue_next_session`. STRUCTURAL_STOP / invalidation / portfolio risk **pueden** ejecutarse con sesión cerrada. El fill PAPER usa `operable_mark` = último close conocido (`fill_source` conceptual = `last_close`). Eso **subestima** el gap de apertura vs LIVE. No se encola el stop a la apertura en V1.48; Lab P2 / LIVE deben tratar este sesgo.

Perfil `aggressive_swing`: `t1_reduce_fraction = 0` → tocar T1 es **HOLD** de diseño (deja correr hasta T2). No es un fallo de detección.

## 6. Golden Session + CAOS

Un pytest de sesión: context → Entry stub → protect → T1 reduce → TRAIL #1 → TRAIL #2 → exit → fill → recon → journal projection.

CAOS-01 ciclo duplicado · CAOS-02 mismo TRAIL · CAOS-03 TRAIL 1 luego 2 · CAOS-04 crash tras evento · CAOS-05 crash tras order · CAOS-06 fill parcial · CAOS-07 stale (test propio) · CAOS-08 recon unavailable · CAOS-09 mercado cerrado · CAOS-10 dos workers TRAIL · crash antes del claim (recuperable, un sell) · mark MISSING fail-closed · kill switch AUTO DENY (protect y exit).

## 7. OUT

EntryTick Estudio → Ranking → TradePlan → OpeningGate (**V1.49**) · MarketProfile / multi-exchange · UI Mercado cards · scheduler · LIVE · OCO · flip env · package bump · tabla `position_events`.
