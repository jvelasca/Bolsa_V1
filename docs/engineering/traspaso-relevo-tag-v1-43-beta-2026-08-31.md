# RELEVO — tag v1.43-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-43-trail-revision-2026-08-31.md`](./traspaso-relevo-v1-43-trail-revision-2026-08-31.md) · [`traspaso-relevo-tag-v1-42-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-42-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CERTIFICADO** — tip `v1.43-beta` → `5dfac890` · Release-tag CI **GREEN** · auditoría externa **PASS**.  
> **Arranque auditor:** [`arranque-auditor-v1-43-beta-2026-08-31.md`](./arranque-auditor-v1-43-beta-2026-08-31.md).  
> **Fuera:** auto-promote · broker trailing / OCO · Lab P2 · thaw LIVE · OpportunityScore · segundo Mercado · package bump · `protect_hint` thin como CTA sin Confirm.

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

| Pieza        | Valor                                                                                                            |
| ------------ | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip      | `v1.43-beta` → `5dfac890` (annotated object `503a2639`; peeled código trail `6136c27c`)                          |
| Código trail | `6136c27c` `feat(trail): SEMI Confirm trail → PositionRevision origin=trail → currentStop`                       |
| Previo tip   | `v1.42-beta` → `5e3fb1a4` (CI GREEN)                                                                             |
| CI tag       | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719601) · `headSha=5dfac890` |

Jobs del mismo push `v1.43-beta` (2026-08-31T20:01Z), todos **success**:

| Workflow          | Run                                                                          |
| ----------------- | ---------------------------------------------------------------------------- |
| Release tag CI    | [33433719601](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719601) |
| Frontend CI       | [33433719555](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719555) |
| Python CI         | [33433719641](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719641) |
| Optimize lab      | [33433719624](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719624) |
| Fase 2 scientific | [33433719686](https://github.com/jvelasca/Bolsa_V1/actions/runs/33433719686) |

## 2. Pre-flight tip (local)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/position-revision.test.ts src/cognitive/position-operating-truth-golden-path.test.ts src/cognitive/trade-story-golden-path.test.ts src/cognitive/operational-honesty-scenarios.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_revision.py packages/py/application/tests/test_persist_position_from_protect.py packages/py/application/tests/test_operative_journeys.py packages/py/application/tests/test_persist_position_from_fill.py -q
```

Resultado local (2026-08-31): shared build OK · 48 shared + 20 web · tsc OK · pytest **36 passed**. Re-check auditoría: mismos números.

## 3. Auditoría externa

**Veredicto (2026-08-31, tip `5dfac890`):** **PASS** — trail SEMI durable. Siete preguntas de foco OK.

**Matiz de alcance (auditoría externa, ronda posterior):** PASS V1.43 = TRAIL SEMI + Operating Excellence F2–F8 **dentro del alcance documentado**. **No** significa «AUTO de gestión de posiciones certificado». LIVE **no**. `PAPER_D_EXECUTE` off. AUTO opt-in. Next = [V1.44 Position Automation Contract](./spec-v144-position-automation-2026-08-31.md) (policy + JIT + Golden Paths; sin execute). Lab P2 sigue parked.

| #   | Foco                                                        | Resultado |
| --- | ----------------------------------------------------------- | --------- |
| 1   | Confirm TRAIL → `origin=trail` · `trail_confirm`            | PASS      |
| 2   | Hint ≠ `currentStop` / autoridad CTA hasta Confirm+revision | PASS      |
| 3   | Stop=hint → TradeStory/POT/ES applied · clear secondary     | PASS      |
| 4   | GP-08 · honesty #20 · Journey J05                           | PASS      |
| 5   | Freeze (Confirm · `PAPER_D_EXECUTE` off · Spine/Router/nav) | PASS      |
| 6   | Regresión 8 preguntas `v1.42-beta`                          | PASS      |
| 7   | Release-tag CI GREEN                                        | PASS      |

**Matiz (no FAIL):** POT/ExecutionState pueden marcar `applied` por geometría stop=hint sin revisión `origin=trail`; TradeStory exige la revisión. En el camino canónico V1.43 (Confirm TRAIL) coinciden.

**CI tag:** GREEN (tabla §1). No retag. No thaw. No Lab P2. No Alembic nuevo (sigue `014`). Package `1.35.0-beta` intacto.

HEAD post-tip `033fe6e6` = docs re-pin only (4 ficheros); **no** forma parte del tip certificado.

## 4. Residuals parked

- Auto-promote hint → `currentStop` (SEMI o AUTO)
- Broker trailing / OCO / Lab P2 / drag → PositionRevision
- Thaw LIVE / Accept estricto / `PAPER_D_EXECUTE` default on
- Nueva tabla/Alembic · package bump · Ranking=BUY · segundo Mercado
- Tratar `protect_hint` thin como CTA authority sin Confirm (`mapMesaNextAction` → Proteger; enqueue no aplica stop)
- Honesty #20 `19c` Mercado cerrado (`todo`)

## 5. Next

**V1.44 Position Automation Contract** — [spec](./spec-v144-position-automation-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md) · [plan](./plan-v144-position-automation-foundation-2026-08-31.md). Sin AUTO execute de posiciones. Lab P2 / OCO / broker trail / thaw LIVE siguen parked.
