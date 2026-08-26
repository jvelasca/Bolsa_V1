# RELEVO — DEX-5 Operational invariants · apertura pack v113 · 2026-08-26

> **Padre:** [`plan-dex5-operational-invariants-2026-08-26.md`](./plan-dex5-operational-invariants-2026-08-26.md) · ADR-035 · roadmap v1.13.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **465 → 483**.
> **Estado:** **DEX-5 CERRADO** · **pack v113 stampado**. Next = **tag `v1.13-beta`** (si el dueño lo pide).
> **Arranque chat nuevo:** pack v113 + relevo tag + ADR-035 §8 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

DEX-5 formalizó invariantes operacionales (property suite anclada a spine). El pack auditor v113 **ya está stampado** en chat aparte. El siguiente paso es **publicar tag** (owner) o **operar SEMI**.

## 1. Qué quedó hecho

| Pieza                                                     | Estado              |
| --------------------------------------------------------- | ------------------- |
| `paper_order` qty > 0 · FILLED filled ≤ ordered           | **Hecho**           |
| `operational_invariants.py` predicados puros              | **Hecho**           |
| Suite 6 invariantes `test_dex5_operational_invariants.py` | **Hecho**           |
| Spine ancla DEX-5                                         | **Hecho** · **483** |
| Pack auditor v113                                         | **Hecho**           |
| Tag `v1.13-beta`                                          | **Pendiente owner** |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked. Redis multi-worker **parked**.
- Mesa UI banner / HTTP resolución incidente = candidata posterior.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** owner — commit release + tag **`v1.13-beta`** + push + pin SHA tras CI GREEN. Citar pack v113 + ADR-035. Cero thaw · cero UI Mesa · cero AUTO · cero broker.
2. **Opción B:** operar SEMI con v1.12 + DEX-1…5 (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **No** reabrir DEX-1…5 a ciegas en el chat del tag.

## 4. Docs clave

- Pack [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md)
- Relevo tag [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-13-beta-2026-08-26.md)
- [`plan-dex5-operational-invariants-2026-08-26.md`](./plan-dex5-operational-invariants-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
