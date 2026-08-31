# RELEVO — V1.43 Trail hint → PositionRevision → currentStop (2026-08-31)

> **Padre:** [`traspaso-relevo-tag-v1-42-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-42-beta-2026-08-31.md) · ADR-042 §4 · GP-08 · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERRADO** — SEMI: TRAIL/protect Confirm → `PersistPositionFromProtect` → `apply_position_current_stop(origin=trail)` → proyección `trailingApplied` / clear `trail_hint_not_applied`.  
> **Tag:** [`traspaso-relevo-tag-v1-43-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-43-beta-2026-08-31.md) · arranque [`arranque-auditor-v1-43-beta-2026-08-31.md`](./arranque-auditor-v1-43-beta-2026-08-31.md).

---

## 0. Qué cierra

| Pieza                                                                   | Estado         |
| ----------------------------------------------------------------------- | -------------- |
| `PositionRevisionOrigin` + `trail` (TS + PY)                            | CÓDIGO         |
| Enqueue protect con `revisionOrigin=trail` cuando `primaryReason=TRAIL` | CÓDIGO         |
| Confirm protect → persist `origin=trail` · reason `trail_confirm`       | CÓDIGO         |
| TradeStory / POT / ExecutionState: hint → applied tras stop = hint      | CÓDIGO + tests |
| GP-08 domain+projection · honesty #20 SEMI                              | CÓDIGO         |
| Journey J05 · persist protect trail                                     | CÓDIGO         |

**Regla:** hint ≠ `currentStop` hasta Confirm+revision. Reusa protect Confirm (no motor nuevo, no Alembic, no broker trail).

## 1. Pre-flight

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/position-revision.test.ts src/cognitive/position-operating-truth-golden-path.test.ts src/cognitive/trade-story-golden-path.test.ts src/cognitive/operational-honesty-scenarios.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
# PY (desde repo root / venv habitual)
pytest packages/py/analytics/tests/test_position_revision.py packages/py/application/tests/test_persist_position_from_protect.py packages/py/application/tests/test_operative_journeys.py packages/py/application/tests/test_persist_position_from_fill.py -q
```

## 2. Freeze (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE thaw · `protect_hint` thin ≠ autoridad · hint never auto-promotes · Spine / Router / propose HTTP / nav L1 intocados.

## 3. OUT (sigue parked)

- Auto-promote hint → `currentStop` (SEMI o AUTO)
- Broker trailing / OCO / Lab P2 / drag → PositionRevision
- Thaw LIVE / Accept estricto / `PAPER_D_EXECUTE` default on
- Nueva tabla/Alembic · package bump · Ranking=BUY · segundo Mercado
- Tratar `protect_hint` thin como CTA authority sin Confirm
