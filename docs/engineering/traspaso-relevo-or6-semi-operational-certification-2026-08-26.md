# RELEVO — OR-6 SEMI operational certification · 2026-08-26

> **Padre:** [`plan-or6-semi-operational-certification-2026-08-26.md`](./plan-or6-semi-operational-certification-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **418 → 433**.
> **Estado:** **CERRADO (código + tests + docs).** Pack + tag **`v1.12-beta`** = [`traspaso-relevo-tag-v1-12-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-12-beta-2026-08-26.md).
> **Arranque chat nuevo:** pack v112 + relevo tag + ADR-035 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambió el chat

OR-6 cerró v1.12 en código. El hueco siguiente era **pack auditor + tag `v1.12-beta`** (hecho en chat de publicación). No mezclar thaw estricto ni AUTO on.

## 1. Qué quedó hecho

| Pieza                                             | Estado                       |
| ------------------------------------------------- | ---------------------------- |
| Kernel 4 estados + espejo TS                      | **Hecho**                    |
| OE-1 campo aditivo `operationalReadiness`         | **Hecho**                    |
| CTA Confirm / ticket manual + badge LIVE          | **Hecho**                    |
| Chip mesa readiness (aparte Autoeval)             | **Hecho**                    |
| UI preferencia venue por cuenta (PA-1)            | **Hecho**                    |
| Spine                                             | **433**                      |
| Pack auditor v112 / tag `v1.12-beta`              | **Hecho** (chat publicación) |
| Thaw estricto / AUTO on / Alembic / UI resolución | **No**                       |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental** (nunca `READY`). Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 / OR-1…OR-5 **no se reabren**.
- Un FAIL crítico **no** se promedia. AUTO FAIL **no** tumba `PAPER_READY`.

## 3. E1 — fork (post-tag)

1. Auditar pack v112 + tag `v1.12-beta` + ADR-035.
2. Operar SEMI (TRIGGERED → Confirm → `Ejecutar en PAPER` · suite A–L · readiness en barra).
3. **No** thaw estricto · **no** AUTO on · **no** XTB capital · **no** UI resolución recon.

## 4. Docs clave

- [`plan-or6-semi-operational-certification-2026-08-26.md`](./plan-or6-semi-operational-certification-2026-08-26.md)
- [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./plan-or5-broker-execution-scenario-suite-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo OR-5: [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md)
