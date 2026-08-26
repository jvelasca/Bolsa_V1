# Plan — DEX-2 Crash/restart cross-PID (certificación física)

> **Padre:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · ADR-035 · plan DEX-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs).
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. DEX-1 CERRADO. Spine **433 → 440**.
> **Relevo:** [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

---

## Objetivo

El auditor exige (tras DEX-1):

```text
proceso A
  ↓
persist submit_intent (PG) → (opcional) adapter.submit
  ↓
kill / descartar store + sesión
  ↓
proceso B — store/cliente NUEVO leyendo PG
  ↓
Confirm retry → UNKNOWN + mismos ids · 0 re-POST
```

OR-2 dejó el concepto (mismo InMemory). DEX-1 dejó la persistencia. DEX-2 **certifica** que la reconstrucción no depende del singleton de proceso.

---

## Decisiones

| ID  | Decisión                                                                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Tests spine: store/sesión **A** escribe → descartar → store/sesión **B** (nueva instancia) lee el mismo backing durable → Confirm `UNKNOWN` · `adapter.submit` = 0.                                                   |
| D2  | Backing durable = tabla compartida que simula commit PG (fila `SubmitIntentRow`). Dos `PostgresSubmitIntentStore` con sesiones distintas sobre esa tabla.                                                             |
| D3  | Escenarios: (1) crash post-`recorded` sin venue; (2) crash post-`venue_bound` con mapeo; (3) live submitted en A → recovery en B sin segundo POST; (4) put/get cross-sesión; (5) phase `send_attempted` visible en B. |
| D4  | Sin dependencia de `DATABASE_URL` en spine (fake session + tabla compartida). Live PG opcional = deuda menor / chaos.                                                                                                 |
| D5  | **No** cambiar kernel Confirm. **No** DEX-3 Incident · **No** DEX-4 split · **No** pack v113 · **No** `contract:gen` · **No** Alembic nuevo.                                                                          |

---

## Kernel (sin cambio)

```text
fill local ya existe           → replay executed (OR-1)
store fresco tiene fila        → UNKNOWN (no adapter) — DEX-2 certifica store ≠ singleton
si no                          → put recorded → send_attempted → adapter.submit
```

---

## Ficheros

- Tests: `packages/py/application/tests/test_dex2_crash_restart_cross_pid.py`
- Spine: `scripts/research/verify_decision_spine_battery.mjs`
- Docs: plan · CURRENT_SYSTEM · ADR-035 · roadmap · CHANGELOG · relevo DEX-2→DEX-3

---

## DoD

- [x] Store A put → store B get (instancias distintas, mismo backing) → intent idéntico.
- [x] Confirm con store B tras “kill” de A → `unknown` · 0 `adapter.submit` · mismos `intent_id`/`order_id`.
- [x] Post-`venue_bound` en A → B recupera `venueOrderId` · 0 re-POST.
- [x] Live submitted en A → Confirm en B · 0 segundo submit.
- [x] Spine incluye el fichero DEX-2; OR-2 InMemory intacto. Spine **440**.
- [x] Sin DEX-3/4/5 · sin thaw · sin AUTO · sin broker producción.
- [x] Docs stamp + relevo al chat DEX-3.

## Freeze (intactos)

ADR-034 · OR-1/3/4/5/6 · Confirm = única firma · `PAPER_D_EXECUTE` off · thin 5.x/8.x · Lab ≠ mesa · JSONB PositionState SoT.

## E1

Tras DEX-2: **DEX-3** Incident/resolución recon **o** operar SEMI. **No** Confirm split ni pack v113 en el mismo chat.
