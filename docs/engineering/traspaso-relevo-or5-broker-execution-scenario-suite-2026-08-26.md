# RELEVO — OR-5 Broker execution scenario suite · 2026-08-26

> **Padre:** [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./plan-or5-broker-execution-scenario-suite-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **403 → 418**.
> **Estado:** **CERRADO (código + tests + docs).** Cambiar de chat recomendado para OR-6.
> **Arranque chat nuevo:** este fichero + ADR-035 + roadmap v1.12 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

OR-5 certifica la batería del auditor **A–L** + retry (OR-1) + crash (OR-2) en `pnpm test:decision-spine`. Validar, no expandir. El siguiente hueco es **OR-6** (readiness 4 estados + CTA venue). No mezclar pack auditor v112 (al tag) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                          | Estado    |
| ---------------------------------------------- | --------- |
| Matriz A–L + retry + crash en módulo OR-5      | **Hecho** |
| Ancla `verify_decision_spine_battery.mjs`      | **Hecho** |
| Spine                                          | **418**   |
| OR-6 CTA / readiness / UI resolución / Alembic | **No**    |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 / OR-1…OR-4 **no se reabren**.
- Auto-exit **no** es CTA cotidiano. **No** más brokers. **No** AUTO on. **No** auto-heal. **No** mass sim.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** **OR-6** SEMI operational certification — readiness `PAPER_READY` / `PAPER_DEGRADED` / `LIVE_EXPERIMENTAL` / `LIVE_BLOCKED` + CTA `EJECUTAR EN PAPER|LIVE`. Citar ADR-035.
2. **Opción B:** operar SEMI con OR-1…OR-5 (TRIGGERED → Confirm → suite A–L verde). No reabrir thin. No XTB capital.
3. **No** pack auditor v112 (al tag) · **no** thaw estricto · **no** AUTO on.

## 4. Docs clave

- [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./plan-or5-broker-execution-scenario-suite-2026-08-26.md)
- [`plan-or4-recon-opening-veto-2026-08-26.md`](./plan-or4-recon-opening-veto-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo OR-4: [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./traspaso-relevo-or4-recon-opening-veto-2026-08-26.md)
