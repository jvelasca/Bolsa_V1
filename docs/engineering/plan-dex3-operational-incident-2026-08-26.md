# Plan — DEX-3 OperationalIncident / resolución recon

> **Padre:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · ADR-035 · plan DEX-2.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs).
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. DEX-2 CERRADO. Spine **440 → 463**.
> **Relevo:** [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./traspaso-relevo-dex3-operational-incident-2026-08-26.md).

---

## Objetivo

OR-4 ya **detecta** y **veta** aperturas. El auditor exige el hueco humano:

```text
drift / live unavailable
  ↓
abrir OperationalIncident (OPEN)
  ↓
review (humano)
  ↓
resolve (nota; NUNCA muta libros)
  ↓
clear solo si recon = clean
```

Sin auto-heal. UI Mesa banner = slice posterior. Confirm split = DEX-4.

---

## Decisiones

| ID  | Decisión                                                                                                                                                                                  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Kernel `OperationalIncident`: kind `portfolio_drift` \| `live_drift` \| `live_unavailable`; status `open` → `in_review` → `resolved` → `cleared`. Resolve desde `open` (review opcional). |
| D2  | Un incidente **activo** (`open`/`in_review`/`resolved`) por `(account_id, kind)`. Drift repetido no spamea filas. Tras `cleared`, un drift nuevo abre otro.                               |
| D3  | `resolve` exige nota no vacía. **No** muta cash / holdings / PositionState. `clear` solo si status=`resolved` **y** recon actual `clean`.                                                 |
| D4  | Opening veto adicional: incidente activo → `incident:unresolved` (incluso si el drift ya se fue). Exits ALLOW. Store ausente = gate off (legado).                                         |
| D5  | Alembic `014_operational_incidents` + `PostgresOperationalIncidentStore`. InMemory en unit tests. Runtime API = PG.                                                                       |
| D6  | Wire: `allow_opening_fill` + Confirm / Fill / HTTP gated / Router. Sin HTTP de resolución · sin `contract:gen` · sin UI Mesa.                                                             |
| D7  | **No** DEX-4 Confirm split · **No** DEX-5 property suite · **No** pack v113 · **No** auto-heal · **No** thaw.                                                                             |

---

## Kernel

```text
exit-like signal                         → skip incident veto (igual OR-4)
drift/unavailable + store                → ensure OPEN (idempotente por kind)
cualquier incidente activo               → DENY incident:unresolved
resolve(note)                            → RESOLVED (libros intactos)
clear si recon != clean                  → fail-closed (no clear)
clear si resolved + clean                → CLEARED
store boom                               → DENY fail-closed
sin store                                → gate off
```

---

## Ficheros

- Kernel: `packages/py/analytics/.../operational_incident.py` · espejo TS
- Store: `packages/py/application/.../operational_incident_store.py`
- Alembic: `014_operational_incidents.py` · `OperationalIncidentRow`
- Gate: `opening_permission.py` · `risk_engine.py` · Confirm / Fill / ExecuteGated / Router · DI
- Tests: analytics kernel · application store/workflow/opening · shared TS
- Spine: `test_dex3_operational_incident.py` + `test_operational_incident.py`
- Docs: plan · CURRENT_SYSTEM · ADR-035 · roadmap · CHANGELOG · relevo DEX-3→DEX-4

---

## DoD

- [x] Drift → INC OPEN · 1 activo por kind.
- [x] OPEN → review → resolve(note) → clear(clean). Clear con drift → error.
- [x] Resolve no muta libros. Apertura DENY con incidente activo; exit ALLOW.
- [x] Tras clear + recon clean → apertura ALLOW. Nuevo drift → nuevo INC.
- [x] Spine ancla DEX-3. Sin DEX-4/5 · sin thaw · sin AUTO · sin broker producción.
- [x] Docs stamp + relevo al chat DEX-4.

## Freeze (intactos)

ADR-034 · OR-1/3/4/5/6 · DEX-1/2 · Confirm = única firma · `PAPER_D_EXECUTE` off · thin 5.x/8.x · Lab ≠ mesa · JSONB PositionState SoT.

## E1

Tras DEX-3: **DEX-4** Confirm = orquestador **o** operar SEMI. **No** pack v113 ni property suite en el mismo chat.
