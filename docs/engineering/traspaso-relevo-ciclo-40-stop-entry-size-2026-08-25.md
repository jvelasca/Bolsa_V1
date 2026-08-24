# RELEVO — Ciclo 4.0 stop estructural + entry_ready + size (2026-08-25)

> **Padre:** [`traspaso-relevo-tradeplan-propose-confirm-hoy-2026-08-24.md`](./traspaso-relevo-tradeplan-propose-confirm-hoy-2026-08-24.md).
> **Política:** [`docs/adr/031-operational-model-tesis-plan-permiso.md`](../adr/031-operational-model-tesis-plan-permiso.md) §6 nota 4.0.
> **AsOf:** 2026-08-25.
> **HEAD:** `1cbd021` (local). `origin/main` aún `17a386d`. **Pendiente push.**

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

Stamp SoT post-commit en el commit docs inmediato (HEAD local).

## 4. Siguiente (E1)

1. **Push** de `1cbd021` + stamp — solo si el propietario lo pide.
2. Familias EntrySetup / `NO_NEW_LONGS` — **prohibido** sin plan.

## 5. No tocado

F9-B · purge · `PAPER_D_EXECUTE` · broker · `contract:gen` · thesis health / MFE · qty del ticket Confirm.
