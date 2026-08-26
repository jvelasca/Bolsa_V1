# RELEVO — OR-4 Reconciliation → opening veto · 2026-08-26

> **Padre:** [`plan-or4-recon-opening-veto-2026-08-26.md`](./plan-or4-recon-opening-veto-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **387 → 403**.
> **Estado:** **CERRADO (código + tests + docs).** Cambiar de chat recomendado para OR-5.
> **Arranque chat nuevo:** este fichero + ADR-035 + roadmap v1.12 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

OR-4 cierra el hueco del auditor: OI-6/LR-1 ya detectaban; ahora `drift` / live `unavailable` **DENY** aperturas en `check_opening`. Exits protectivos ALLOW. Sin auto-heal. El siguiente hueco es la **suite A–L** (OR-5). No mezclar CTA LIVE (OR-6) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                           | Estado    |
| ----------------------------------------------- | --------- |
| `reconciliation_opening_veto_reason` PY/TS      | **Hecho** |
| `check_opening` OR-4 (bypass exit\*)            | **Hecho** |
| Confirm / Fill / HTTP / Router cableados        | **Hecho** |
| OE-1 OI-6 status honesto (≠ `not_wired`)        | **Hecho** |
| Spine                                           | **403**   |
| OR-5 suite / OR-6 CTA / UI resolución / Alembic | **No**    |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 / OR-1…OR-3 **no se reabren**.
- Auto-exit **no** es CTA cotidiano. **No** más brokers. **No** AUTO on. **No** auto-heal.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** **OR-5** Broker execution scenario suite — batería A–L + retry + crash anclada a `pnpm test:decision-spine`. Citar ADR-035.
2. **Opción B:** operar SEMI con OR-1…OR-4 (TRIGGERED → Confirm → retry/crash + estados + veto recon). No reabrir thin. No XTB capital.
3. **No** CTA «EJECUTAR EN LIVE» (OR-6), **no** pack auditor v112 (al tag).

## 4. Docs clave

- [`plan-or4-recon-opening-veto-2026-08-26.md`](./plan-or4-recon-opening-veto-2026-08-26.md)
- [`plan-or3-order-state-machine-2026-08-26.md`](./plan-or3-order-state-machine-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo OR-3: [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./traspaso-relevo-or3-order-state-machine-2026-08-26.md)
