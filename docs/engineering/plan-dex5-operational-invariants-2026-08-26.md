# Plan — DEX-5 Operational invariants

> **Padre:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · ADR-035 · plan DEX-4.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs).
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. DEX-4 CERRADO. Spine **465 → 483**.
> **Relevo:** [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](./traspaso-relevo-dex5-operational-invariants-2026-08-26.md).

---

## Objetivo

Unit/integration OR/DEX son fuertes; el auditor pide **stochastic / invariants = DEX-5**. Formalizar 6 invariantes como propiedades comprobables ancladas al spine. Sin producto nuevo.

```text
qty ≥ 0
filled ≤ ordered
terminal ≠ re-ejecuta (fill)
1 decision_id → ≤1 live order_id (estable)
drift / incident unresolved → blocks opening
protect sin override → no empeora stop (no ↑ exposición)
```

---

## Decisiones

| ID  | Decisión                                                                                                                                |
| --- | --------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Suite `test_dex5_operational_invariants.py` + properties de dominio en analytics.                                                       |
| D2  | **Sin** `hypothesis`. Property-based = grafo OR-3 + `random.Random` seeded + `parametrize`. 10k sim / OperationalPolicy parked.         |
| D3  | Endurecer `paper_order`: `quantity <= 0` fail-closed en build; FILLED rechaza `filled < 0` o `filled > ordered`.                        |
| D4  | Protect: property sobre `apply_position_current_stop` (long/short × stops) + `adverse_exposure`.                                        |
| D5  | Drift/opening: property thin sobre `reconciliation_opening_veto_reason` + `check_opening` (`reconciliation:*` / `incident:unresolved`). |
| D6  | 1 decision → ≤1 order: `stable_order_id_from_decision` + Confirm replay (mismo `ORD-`, un submit).                                      |
| D7  | **No** Alembic · **No** `contract:gen` · **No** Confirm refactor · **No** pack v113 · **No** UI Mesa · **No** thaw.                     |

---

## Ficheros

- Kernel: `packages/py/analytics/.../paper_order.py` · `operational_invariants.py`
- Tests: `test_dex5_operational_invariants.py` · ampliación `test_paper_order.py`
- Battery: `scripts/research/verify_decision_spine_battery.mjs`
- Docs: plan · CURRENT_SYSTEM · ADR-035 · roadmap · CHANGELOG · index · relevo → pack v113

---

## DoD

- [x] 6 invariantes con tests property/seeded; ancla `test_dex5_*` en spine.
- [x] PaperOrder: filled ≤ ordered · qty ≥ 0; regresión OR-3 verde.
- [x] Spine count documentado (**465 → 483**).
- [x] Docs stamp + relevo al chat pack v113 (pack ≠ este chat).

## Freeze (intactos)

ADR-034 · OR-1/3/4/5/6 · DEX-1…4 · Confirm = única firma · `PAPER_D_EXECUTE` off · thin 5.x/8.x · Lab ≠ mesa · JSONB PositionState SoT · Incident UI Mesa parked.

## E1

Tras DEX-5: **pack auditor v113** (cierre de fase / tag) **en chat nuevo**, **o** operar SEMI. No mezclar pack en el mismo chat que DEX-5.
