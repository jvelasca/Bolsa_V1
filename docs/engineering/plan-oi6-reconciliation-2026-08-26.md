# Plan — OI-6 Portfolio reconciliation (detect/report)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** [`traspaso-relevo-oi5-position-revisions-2026-08-26.md`](./traspaso-relevo-oi5-position-revisions-2026-08-26.md).

---

## Objetivo

Responder **«¿siguen de acuerdo las capas paper?»** — ledger ↔ holdings ↔ PositionState ↔ cash — con un informe ephemeral. Detect/report. **No** auto-heal. **No** broker. **No** PaperBroker.

≠ M-2 script solo ≠ ADR-021 DÍA D ≠ PaperOrder durable.

## Decisiones

| ID  | Decisión                                                                                                              |
| --- | --------------------------------------------------------------------------------------------------------------------- |
| D1  | Objeto `PortfolioReconciliation` (TS + Py). Informe JSON ephemeral.                                                   |
| D2  | Check outcome: `ok` \| `mismatch` \| `expected` \| `unknown`. Top-level `status`: `clean` si no hay `mismatch`.       |
| D3  | Checks: `cash_ledger` · `holding_qty_vs_position` · `open_without_holding` · `holding_without_open` · `open_tx_link`. |
| D4  | Noops OI-1 (add-on, holding sin OPEN) → outcome **`expected`**, no `ok` silencioso.                                   |
| D5  | Solo detect/report — **no** muta cash/holdings/PositionState.                                                         |
| D6  | PaperOrder **no** requerido (ephemeral). Sin pending cash reserve.                                                    |
| D7  | Kernel + use-case + spine tests. Sin attach Confirm obligatorio. Sin Alembic · sin `contract:gen`.                    |
| D8  | **No** broker · **No** PaperBroker · **No** job auto-reconcile.                                                       |

## Kernel

```text
cash_ledger:           |portfolioCash − Σledger| < ε → ok else mismatch
holding_qty vs OPEN:   qty == remaining → ok
                       qty > remaining  → expected (addon)
                       qty < remaining  → mismatch
OPEN sin holding>0:    mismatch (open_without_holding)
holding>0 sin OPEN:    expected (holding_without_open / legacy)
open_tx_link:          txId ∈ known → ok; sin known set → unknown; missing → mismatch
status:                any mismatch → drift else clean
```

## Ficheros

- `packages/shared/src/cognitive/portfolio-reconciliation.ts` · test
- `packages/py/analytics/.../portfolio_reconciliation.py` · test
- `packages/py/application/.../reconcile_portfolio_integrity.py` · test
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-5 · `PAPER_D_EXECUTE` off · broker no · Lab ≠ mesa.

## E1

PaperBroker **o** edge Confirm `protect_applied` si persist → None. **No** broker live en el mismo chat.
