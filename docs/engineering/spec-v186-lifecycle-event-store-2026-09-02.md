# Spec — V1.86 Lifecycle Event Store (FastAPI + PostgreSQL)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tip [`v1.86-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta) → [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034) · [run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402) **success**.  
> **Padre:** [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md) · [`spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md`](./spec-v185-lifecycle-integrity-financial-event-model-2026-09-02.md).  
> **Partida tip:** `v1.85-beta` → [`665242a3`](https://github.com/jvelasca/Bolsa_V1/commit/665242a3). **No** LIVE · **no** V1.87 integrated obligatorio.

```text
POST event → VALIDATE (FSM · time · identity · payload · trail)
          → APPEND (PG transaction, append-only)
          → REDUCE → SNAPSHOT
GET  snapshot ← reduce(log) desde PostgreSQL
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger artificial.  
V1.73–V1.85 mock paths intactos (`setStage` limpia log). **No** Playwright en `frontend-ci`. **No** auth/isolation/recon full (V1.87).

## 1. Accounting (P1-01)

`POSITION_OPENED` = ENTRY fill. Sin nuevo nodo FSM.

```text
initial: remaining=0, cash=LIFECYCLE_CASH (100000)
OPEN:  cash -= qty*price + fees; remaining += qty; avgCost = price
EXIT fills (T1/T2/CLOSE): cash += qty*price − fees; remaining −= qty
realizedPnl += (price − avgCost)*qty − fees
unrealizedPnl = (lastPrice − avgCost)*remaining
equity = cash + marketValue
equity == initialEquity + realizedPnl + unrealizedPnl  (sin flujos externos)
```

CLOSED trail golden: cash **100055**, equity **100055**, realized **55**.

## 2. Idempotencia / identidad / payload / trail

| Regla                                                      | Código                  |
| ---------------------------------------------------------- | ----------------------- |
| mismo eventId + mismo payloadHash                          | 200 idempotent          |
| mismo eventId + distinto payload                           | `event_id_conflict` 409 |
| instrument/decision/tradePlan ≠ envelope                   | `identity_mismatch` 409 |
| qty≤0 · price≤0 · fees<0 · qty>remaining · CLOSE≠remaining | `invalid_payload` 409   |
| LONG trail newStop < previousStop                          | `trail_relaxation` 409  |
| timestamp malformado                                       | `invalid_timestamp` 400 |
| fillId duplicado                                           | `duplicate_fill_id` 409 |

`eventId` omitido → UUID servidor. `venueOrderId` opcional (no inventar).

## 3. Persistencia

Tabla `lifecycle_events` append-only (Alembic 015): UNIQUE `event_id`, UNIQUE parcial `fill_id`, `payload_hash`, envelope, JSONB payload.  
Servicio: SELECT log → validate → INSERT en una transacción.  
HTTP: `POST /api/lifecycle/events` · `GET /api/lifecycle/positions/{positionId}/snapshot`. **No** sustituye `/api/portfolio` ni mock Playwright.

## 4. IN / OUT

**IN:** P1-01…05 · domain kernel Python · espejo TS mock · PG store · FastAPI thin · matriz tests · CI domain + job `lifecycle-pg`.

**OUT:** V1.87 · LIVE · bump · reescribir GP-V179/181/183 · unificar ledger · limpiar ECONNREFUSED/PyJWT.

## 5. Certificación

- Vitest + pytest dominio (matriz negativa).
- PG: OPEN→T1→CLOSE→nueva sesión→GET ≡ snapshot; equity invariante.
- GP-V186 mock: conflict 409 + OPEN cash 99000 (filtro `+gp-v186`).
