# Plan — OI-5 Position revisions (historia auditada)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · ADR-033 §2/§5.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** [`traspaso-relevo-oi4-order-lifecycle-2026-08-26.md`](./traspaso-relevo-oi4-order-lifecycle-2026-08-26.md).

---

## Objetivo

`PositionState` guarda **historia append-only** de cambios de stop y transiciones de status relevantes. `applyCurrentStop` deja de mutar solo `currentStop`: cada cambio real append una `PositionRevision`. Confirm protect / `PersistPositionFromProtect` deja huella en el snapshot JSONB. Sin Alembic · sin broker · sin reconciliación (OI-6).

## Decisiones

| ID  | Decisión                                                                                                                                                                                            |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Objeto `PositionRevision` (TS + Py) embebido en `PositionState.revisions[]`. ≠ Journal ≠ ExecutionRecord ≠ PaperOrder.                                                                              |
| D2  | Campos: `revisionId`, `at`, `previousStop`/`nextStop` (nullable), `previousStatus`/`nextStatus` (nullable), `origin`, `reason` (nullable).                                                          |
| D3  | `origin`: `protect` \| `reduce` \| `override` \| `stop`. Protect wire → `protect`. Empeorar con override auditado sin origen explícito → `override`. Reduce → `reduce`. Stop genérico → `stop`.     |
| D4  | Append **solo** si stop o status cambian de verdad. Mismo stop + mismo status → sin revisión (idempotente).                                                                                         |
| D5  | `apply_position_current_stop` / `applyPositionCurrentStop` append. `apply_position_reduce` append en transición de status. **Mark no** (no muda stop/status).                                       |
| D6  | Nacimiento `from_fill`: `revisions=[]`. `initialStop` ≠ revisión.                                                                                                                                   |
| D7  | Wire: `PersistPositionFromProtect` pasa `origin=protect` (+ reason si override). `PersistPositionFromExit` pasa `origin=reduce`. **No** tocar `confirm_recommendation.py` (ya usa Persist protect). |
| D8  | Sin Alembic · sin `contract:gen` · JSON en snapshot. **No** broker · **No** OI-6 · **No** PaperBroker.                                                                                              |

## Kernel

```text
applyCurrentStop(pos, stop, origin?, reason?)
  stop|status cambian → append PositionRevision
  sin cambio real     → sin append (updatedAt sí puede moverse)

applyReduce(pos, qty, …)
  status cambia       → append (origin=reduce)
  mark                → sin revisión

PersistPositionFromProtect → origin=protect
PersistPositionFromExit    → origin=reduce
```

## Ficheros

- `packages/shared/src/cognitive/position-revision.ts` · `position-revision.test.ts`
- `packages/shared/src/cognitive/position-state.ts` — campo `revisions` + append en stop/reduce
- `packages/py/analytics/.../position_revision.py` · `tests/test_position_revision.py`
- `packages/py/analytics/.../position_state.py` — espejo
- `persist_position_from_protect.py` · `persist_position_from_exit.py` — origin
- Tests application: ampliar `test_persist_position_from_protect.py`
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP Hoy · CHANGELOG · relevo

## Freeze (intactos)

ADR-033 invariantes H2 · Confirm = única firma · OI-1…OI-4 · `PAPER_D_EXECUTE` off · broker no · Lab ≠ mesa · thin 5.x/8.x · pending ≠ stop (H1) · confirm execute paths · SEMI E2E docs ajenos.

## E1

OI-6 Reconciliation **o** operar SEMI (TRIGGERED → Confirm → protect). **No** broker en el mismo chat.
