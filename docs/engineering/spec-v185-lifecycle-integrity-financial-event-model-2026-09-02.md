# Spec — V1.85 Lifecycle Integrity & Financial Event Model (E2E mock)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local) · Partida V1.84 PASS 9,5/10 · tip [`v1.84-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.84-beta) → [`504aa19d`](https://github.com/jvelasca/Bolsa_V1/commit/504aa19d) · CI GREEN [run 33659480690](https://github.com/jvelasca/Bolsa_V1/actions/runs/33659480690).  
> **Padre:** [`spec-v184-lifecycle-event-driven-mock-2026-09-02.md`](./spec-v184-lifecycle-event-driven-mock-2026-09-02.md) · [`respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md`](./respuesta-auditor-v184-lifecycle-event-driven-mock-2026-09-02.md).  
> **No** LIVE · **no** FastAPI/PG event store (V1.86).

El log append-only de V1.84 pasa a ser un **log de dominio validado**:

```text
POST event
  → VALIDATE FSM + time + identity
  → APPEND (o idempotent no-op)
  → REDUCE
  → SNAPSHOT + accounting(fills)
  → GET portfolio / summary / desk
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger artificial.  
V1.73–V1.84 intactos (`setStage` limpia log). **No** Playwright en `frontend-ci`. **No** integrated E2E obligatorio.

## 1. FSM (goldens V1.84)

```text
candidate  --POSITION_OPENED--> open
open       --T1_TRIGGERED-----> t1_ready
open       --T1_EXECUTED------> t1_executed      // atajo GP-V184-02
t1_ready   --T1_EXECUTED------> t1_executed
t1_executed--TRAIL_APPLIED----> trailing         // path trail
t1_executed--T2_TRIGGERED-----> t2_ready         // path T2
trailing   --EXIT_REQUIRED----> exit_required
exit_required--POSITION_CLOSED--> closed
t2_ready   --T2_EXECUTED------> t2_executed
t2_executed--POSITION_CLOSED--> closed
```

`T1_TRIGGERED` opcional. `EXIT_REQUIRED` obligatorio solo en trail. Paths trail/T2 exclusivos. `closed` terminal. Ilegal → `illegal_transition` (HTTP 409).

## 2. Tiempo + identidad

| Regla                                                                       | Código              |
| --------------------------------------------------------------------------- | ------------------- |
| `at ≥ previous.at` · `POSITION_CLOSED` estricto `>`                         | `time_regression`   |
| `T1_TRIGGERED.at < T1_EXECUTED.at` · `T2_*` análogo · `TRAIL ≥ T1_EXECUTED` | `time_regression`   |
| `eventId` (default `evt-{kind}-{at}`) · mismo id → 200 idempotent           | —                   |
| `fillId` duplicado (otro eventId)                                           | `duplicate_fill_id` |
| `positionId` ≠ log                                                          | `position_mismatch` |

## 3. Accounting (solo path event-driven)

```text
on fill: cash += qty*price − fees; remaining −= qty; realizedPnl += (price−avgCost)*qty − fees
unrealizedPnl = (lastPrice−avgCost)*remaining
totalPnl = realized + unrealized
totalEquity = cash + lastPrice*remaining
```

Defaults golden: T1 5@105 · T2 3@110 · CLOSE remaining@lastPrice stage · fees 0. Path `setStage` **sin** cambio (GP-V179/V181/V183).

Wire `events` ⊆ log (misma proyección parcial V1.84). GP-V184 journeys iguales; equity CLOSED ya no es cash-only (V1.85 accounting: realized PnL en cash).

## 4. IN

| ID                       | Pri | Comportamiento                                |
| ------------------------ | --- | --------------------------------------------- |
| FSM + appendValidated    | P0  | validate → append / reject                    |
| Monotonicidad + identity | P0  | time · eventId · fillId · positionId          |
| Accounting overlay       | P1  | realized/unrealized/totalPnl · cash           |
| Vitest tabla negativa    | P1  | helpers sin Playwright                        |
| GP-V185                  | P1  | POST 409 · idempotency · PnL · equity cruzada |
| CI `+gp-v185`            | P1  | release-tag-ci                                |

## 5. OUT

- LIVE · scheduler · bump · `dryRun=false` browser · fills ledger
- FastAPI+PG event store · restart→GET (V1.86)
- Wire projection completa · reescribir GP-V179/V181/V183
- Playwright en `frontend-ci` · integrated obligatorio
