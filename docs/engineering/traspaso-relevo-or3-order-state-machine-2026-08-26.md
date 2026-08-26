# RELEVO — OR-3 Full order state machine · 2026-08-26

> **Padre:** [`plan-or3-order-state-machine-2026-08-26.md`](./plan-or3-order-state-machine-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.11-beta` → `76d0f951`**. Spine **382 → 387**.
> **Estado:** **CERRADO (código + tests + docs).** Cambiar de chat recomendado para OR-4.
> **Arranque chat nuevo:** este fichero + ADR-035 + roadmap v1.12 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

OR-3 cierra el lifecycle de `PaperOrder` más allá de `CREATED`/`FILLED`: grafo legal + PaperBroker `SUBMITTED`→`FILLED`/`UNKNOWN` + crash recovery con `paperOrder.status=UNKNOWN`. El siguiente hueco del auditor es **recon → opening veto** (OR-4): `drift` / live `unavailable` bloquean aperturas; exits protectivos ALLOW. No mezclar suite A–L (OR-5) ni CTA LIVE (OR-6) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                             | Estado       |
| ------------------------------------------------- | ------------ |
| Literal + grafo + `transition_paper_order` PY/TS  | **Hecho**    |
| `filledQuantity` para PARTIAL                     | **Hecho**    |
| PaperBroker SUBMITTED → FILLED / UNKNOWN          | **Hecho**    |
| Crash recovery `paperOrder.status=UNKNOWN`        | **Hecho**    |
| OI-4 CREATED→FILLED directo + idempotencia        | **Intactos** |
| Spine                                             | **387**      |
| OR-4 veto / OR-5 suite / OR-6 CTA / OCO / Alembic | **No**       |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OI-1…OE-1 **no se reabren**.
- Auto-exit **no** es CTA cotidiano. **No** más brokers. **No** AUTO on.
- DurableSubmitIntent fases OR-2 intactas (≠ estados PaperOrder).

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** **OR-4** recon → opening veto — `drift` / live `unavailable` → DENY aperturas; exits protectivos ALLOW; sin auto-heal. Citar ADR-035.
2. **Opción B:** operar SEMI con OR-1…OR-3 (TRIGGERED → Confirm → retry/crash + estados de orden). No reabrir thin. No XTB capital.
3. **No** suite A–L (OR-5), **no** CTA «EJECUTAR EN LIVE» (OR-6), **no** pack auditor v112 (al tag).

## 4. Docs clave

- [`plan-or3-order-state-machine-2026-08-26.md`](./plan-or3-order-state-machine-2026-08-26.md)
- [`plan-or2-crash-restart-2026-08-26.md`](./plan-or2-crash-restart-2026-08-26.md)
- [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo OR-2: [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./traspaso-relevo-or2-crash-restart-2026-08-26.md)
