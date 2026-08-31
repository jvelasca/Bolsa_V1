# RELEVO — tag v1.43-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-43-trail-revision-2026-08-31.md`](./traspaso-relevo-v1-43-trail-revision-2026-08-31.md) · [`traspaso-relevo-tag-v1-42-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-42-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **TIP STAMPED** — `v1.43-beta` → `5dfac890` · Release-tag CI pending after push.  
> **Arranque auditor:** [`arranque-auditor-v1-43-beta-2026-08-31.md`](./arranque-auditor-v1-43-beta-2026-08-31.md).

---

## 0. Confirmación

Sobre tip `v1.42-beta` → `5e3fb1a4` (Operating Excellence F2–F8):

| Pieza            | Entrega                                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------- |
| V1.43 trail SEMI | Confirm TRAIL/protect → `PersistPositionFromProtect` → `apply_position_current_stop(origin=trail)` · reason `trail_confirm` |
| Dominio          | `PositionRevisionOrigin` + `trail` (TS + PY) · enqueue `revisionOrigin=trail` si `primaryReason=TRAIL`                      |
| Proyección       | TradeStory / POT / ExecutionState: hint → `trailingApplied` / clear `trail_hint_not_applied` tras stop = hint               |
| Honestidad       | GP-08 · honesty #20 SEMI · Journey J05                                                                                      |
| UI tip           | AdminRail collapsed pin (hover no expande) — commit en tip                                                                  |

**Regla:** hint ≠ `currentStop` hasta Confirm+revision. Reusa protect Confirm (no motor nuevo, no Alembic, no broker trail).

Freeze: Confirm = firma · Spine · `PAPER_D_EXECUTE` off · AUTO opt-in · `protect_hint` thin ≠ autoridad · hint never auto-promotes · sin drag · sin thaw LIVE.

## 1. Release

| Pieza        | Valor                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------ |
| Tag tip      | `v1.43-beta` → `5dfac890`                                                                  |
| Código trail | `6136c27c` `feat(trail): SEMI Confirm trail → PositionRevision origin=trail → currentStop` |
| Previo tip   | `v1.42-beta` → `5e3fb1a4`                                                                  |
| CI tag       | Pending — workflow `release-tag-ci` tras push del tag                                      |

## 2. Pre-flight tip (local)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/position-revision.test.ts src/cognitive/position-operating-truth-golden-path.test.ts src/cognitive/trade-story-golden-path.test.ts src/cognitive/operational-honesty-scenarios.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_revision.py packages/py/application/tests/test_persist_position_from_protect.py packages/py/application/tests/test_operative_journeys.py packages/py/application/tests/test_persist_position_from_fill.py -q
```

Resultado local (2026-08-31): shared build OK · 48 shared + 20 web · tsc OK · pytest **36 passed**.

## 3. Residuals parked

- Auto-promote hint → `currentStop` (SEMI o AUTO)
- Broker trailing / OCO / Lab P2 / drag → PositionRevision
- Thaw LIVE / Accept estricto / `PAPER_D_EXECUTE` default on
- Nueva tabla/Alembic · package bump · Ranking=BUY · segundo Mercado
- Tratar `protect_hint` thin como CTA authority sin Confirm
