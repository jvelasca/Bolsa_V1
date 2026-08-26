# Plan — DEX-1 PostgreSQL SubmitIntent (durabilidad física)

> **Padre:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · triage [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs).
> **Relevo:** [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

---

## Objetivo

El auditor exige:

```text
BEGIN
  ↓
INSERT submit_intent (recorded)
  ↓
COMMIT
  ↓
mark send_attempted (+ send_attempted_at)
  ↓
adapter.submit()
  ↓
UPDATE venue_bound | filled
```

Tras crash del proceso:

```text
restart / proceso B
  ↓
SELECT submit_intent
  ↓
UNKNOWN + mismos ids · 0 re-POST
```

OR-2 dejó el _concepto_; DEX-1 deja la _persistencia_.

---

## Decisiones

| ID  | Decisión                                                                                                                                                                                                                                                                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Tabla Alembic **`submit_intents`** (revisión `013_submit_intents.py`) + modelo SQLAlchemy en `tables.py`.                                                                                                                                                                                                                                                                                                              |
| D2  | Columnas mínimas: `id` (PK), `decision_id` UNIQUE, `intent_id` UNIQUE, `order_id` UNIQUE, `account_id`, `venue`, `phase`, `venue_order_id` nullable, `reason` nullable, `send_attempted_at` nullable timestamptz, `created_at`, `updated_at`. UNIQUE(`account_id`, `decision_id`) si multi-cuenta lo exige; si `decision_id` ya es globalmente único en Confirm, UNIQUE(`decision_id`) basta + índice en `account_id`. |
| D3  | `PostgresSubmitIntentStore` implementa el Protocol `SubmitIntentStore` (get/put/delete). API DI: PG en runtime; InMemory sigue para unit tests.                                                                                                                                                                                                                                                                        |
| D4  | Ampliar `SubmitIntentPhase`: `recorded` \| `send_attempted` \| `venue_bound` \| `filled` (mínimo auditor §18–19). Espejo TS.                                                                                                                                                                                                                                                                                           |
| D5  | `send_attempted_durable(intent)`: true si phase ∈ {`send_attempted`,`venue_bound`,`filled`} **o** `send_attempted_at` no null — **no** solo `intent is not None`. Fila `recorded` sin send = aún no se intentó enviar (permite put fallido / pre-send abort).                                                                                                                                                          |
| D6  | Flujo Confirm: put `recorded` → commit → mark `send_attempted` → `adapter.submit` → bind/fill (igual fail-closed si put falla). Post-adapter `not_wired`/`rejected` → delete o phase explícita (conservar semántica OR-2 actual).                                                                                                                                                                                      |
| D7  | Tests: unit store PG (si hay fixture DB) o contract tests del Protocol; Confirm con store InMemory + al menos un test que demuestre put/get vía implementación PG **o** stub async que simule commit. DEX-2 cierra el kill de proceso.                                                                                                                                                                                 |
| D8  | **No** DEX-2 kill real · **no** DEX-3 Incident · **no** Confirm split · **no** `contract:gen` salvo types phase compartidos si ya hay espejo.                                                                                                                                                                                                                                                                          |

---

## Kernel

```text
fill local ya existe           → replay executed (OR-1)
store tiene fila durable       → UNKNOWN reconstruido (no adapter) — política no re-POST
store tiene send_attempted+    → (observabilidad; send_attempted_durable)
si no                          → put recorded → send_attempted → adapter.submit
                                → venue_bound | filled
```

Preferencia de seguridad: si existe fila durable para `decision_id`, **no** re-POST (alineado OR-2), aunque phase sea solo `recorded` (el put ya ocurrió pre-send; crash entre put y mark = UNKNOWN).

---

## Ficheros

- Alembic: `packages/py/infrastructure/alembic/versions/013_submit_intents.py`
- Modelo: `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py` (`SubmitIntentRow`)
- Kernel: `packages/py/analytics/.../submit_intent.py` + `packages/shared/src/cognitive/submit-intent.ts`
- Store: `packages/py/application/.../submit_intent_store.py` (`PostgresSubmitIntentStore`)
- Confirm: `confirm_recommendation.py` (mark send_attempted)
- DI: `apps/api-python/.../dependencies.py`
- Tests: `test_submit_intent.py` · `test_confirm_crash_restart.py` · `test_submit_intent_store_pg.py`
- Docs: CURRENT_SYSTEM · ADR-035 · CHANGELOG Unreleased · relevo DEX-1→DEX-2

---

## DoD

- [x] Migración `013` aplica / downgrade limpio.
- [x] `PostgresSubmitIntentStore` get/put/delete por `decision_id`; UNIQUE viola → fail-closed.
- [x] Fases incluyen `send_attempted` + `send_attempted_at`; `send_attempted_durable` no trata `recorded` puro como “ya enviado” **salvo** la política de no re-POST si hay fila (documentada en Confirm).
- [x] API Confirm usa store PG cuando hay sesión DB; tests unitarios pueden InMemory.
- [x] Spine / tests OR-2 existentes siguen verdes (InMemory).
- [x] Sin DEX-3/4/5 · sin thaw · sin AUTO · sin broker producción.
- [x] Docs stamp + relevo al chat DEX-2.

---

## Freeze (intactos)

ADR-034 · OR-1/3/4/5/6 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · thin 5.x/8.x · Lab ≠ mesa · JSONB PositionState SoT.

## E1

Tras DEX-1: **DEX-2** real crash/restart (store/cliente fresco leyendo PG). **No** Incident UI ni Confirm split en el mismo chat.
