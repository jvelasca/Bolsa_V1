# RELEVO — Ciclo 4.0 stop estructural + entry_ready + size (2026-08-25)

> [!INFO] **SUPERSEDIDO (2026-08-25).** El relevo vivo es [`traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md`](./traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md). Ciclo 4.0 quedó en origin (`1cbd021`).

> **Padre:** [`traspaso-relevo-tradeplan-propose-confirm-hoy-2026-08-24.md`](./traspaso-relevo-tradeplan-propose-confirm-hoy-2026-08-24.md).
> **Política:** [`docs/adr/031-operational-model-tesis-plan-permiso.md`](../adr/031-operational-model-tesis-plan-permiso.md) §6 nota 4.0.
> **AsOf:** 2026-08-25.
> **HEAD:** `d99b1d1` = `origin/main` (feat `1cbd021` **PUSHEADO**; update-last posterior puede diferir).

---

## 1. Qué se cerró

Stop estructural determinista + `entry_ready` por bias TA + size con equity. **No** familias EntrySetup. **No** `NO_NEW_LONGS`. LLM no calcula SL. `check_opening` intacto. `suggestedQuantity` del ticket F3 no se pisa.

| Pieza           | Regla                                                                                                                           |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| ATR             | `entry ± 1.5 × atr_14`                                                                                                          |
| Swing           | 10 barras cerradas (`bars[-11:-1]`); long `min(low)`, short `max(high)`                                                         |
| Elección        | el más **lejano** (no se acerca el stop; Golden D)                                                                              |
| `entry_ready`   | long + bullish + no exhaustion (simétrico short/bearish)                                                                        |
| Size            | `(equity × risk%) / \|entry − stop\|`; equity = `GetPortfolioSummary.total_equity`; `risk_pct` de plantilla (fallback moderate) |
| Confirm rebuild | sin barras/ATR → `WATCH` / `no_stop` (test conservado)                                                                          |

## 2. Batería

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **75 passed** (antes 67)

## 3. Commits

| SHA       | Mensaje                                                                            |
| --------- | ---------------------------------------------------------------------------------- |
| `1cbd021` | feat(spine): ADR-031 Ciclo 4.0 structural stop, entry_ready, and size with equity. |
| `d99b1d1` | docs: stamp living SoT after Ciclo 4.0 (`1cbd021`).                                |

Push: `17a386d..d99b1d1` → `origin/main`.

## 4. Siguiente (E1)

1. ~~Commit~~ · ~~Push~~.
2. Plan **Ciclo 4.1** redactado: [`plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md`](./plan-ciclo-41-no-new-longs-entrysetup-2026-08-25.md) — **pendiente OK D1–D6**. Sin código hasta aprobación.
3. EntrySetup completo = **4.2** (fuera de 4.1).

## 5. No tocado

F9-B · purge · `PAPER_D_EXECUTE` · broker · `contract:gen` · thesis health / MFE · qty del ticket Confirm.
