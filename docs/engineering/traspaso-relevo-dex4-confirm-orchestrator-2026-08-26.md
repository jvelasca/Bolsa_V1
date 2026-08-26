# RELEVO — DEX-4 Confirm = orquestador · apertura DEX-5 · 2026-08-26

> **Padre:** [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./plan-dex4-confirm-orchestrator-2026-08-26.md) · ADR-035 · roadmap v1.13.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **463 → 465**.
> **Estado:** **DEX-4 CERRADO** (código + tests + docs). Next = **DEX-5**.
> **Arranque chat nuevo:** este fichero + plan DEX-4 + ADR-035 + roadmap v1.13 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

DEX-4 descompone el God Use Case Confirm (~1531 → orquestador ~922 + 7 coordinators). El siguiente hueco del auditor es **invariantes operacionales / property suite** (DEX-5). No mezclar pack auditor v113 en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                           | Estado              |
| ----------------------------------------------- | ------------------- |
| `bolsa_application/confirm/` 7 coordinators     | **Hecho**           |
| Confirm = orquestador (API pública intacta)     | **Hecho**           |
| Regresión OR-1…OR-4 / DEX-1…3                   | **Hecho**           |
| Spine ancla `test_dex4_confirm_orchestrator.py` | **Hecho** · **465** |
| DEX-5 property suite · pack v113                | **No**              |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked. Redis multi-worker **parked**.
- Mesa UI banner / HTTP resolución incidente = candidata posterior (no en DEX-5).

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** implementar **DEX-5** — invariantes operacionales / property-based anclada a spine (qty ≥ 0 · filled ≤ ordered · terminal no re-ejecuta · 1 decision → ≤1 live order · drift blocks opening · protect no aumenta exposición). Citar plan DEX-4 + ADR-035. Cero pack v113 · cero UI Mesa incidente · cero thaw.
2. **Opción B:** operar SEMI con v1.12 + DEX-1…4 (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **No** pack auditor v113 en el mismo chat que DEX-5 (pack = cierre de fase / tag).

## 4. Docs clave

- [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./plan-dex4-confirm-orchestrator-2026-08-26.md)
- [`plan-dex3-operational-incident-2026-08-26.md`](./plan-dex3-operational-incident-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo: [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./traspaso-relevo-dex3-operational-incident-2026-08-26.md)
