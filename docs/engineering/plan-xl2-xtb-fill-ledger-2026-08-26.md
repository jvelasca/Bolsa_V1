# Plan — XL-2 XTB fill → ledger (money path)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo [`traspaso-relevo-lr1-live-reconciliation-2026-08-26.md`](./traspaso-relevo-lr1-live-reconciliation-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** LR-1 cerrado.

---

## Objetivo

Cuando el bridge XTB confirma **fill** (`status: filled`), `XtbBrokerAdapter` llama `execute_trade` y el ledger se actualiza. Confirm / FillPending toman el branch `executed`. **`submitted` sigue ≠ fill ≠ ledger.**

≠ thaw `PAPER_D_EXECUTE` · ≠ UI venue (fase siguiente) · LR-1 intacto · mesa default paper · Mock `not_wired` intacto.

## Decisiones

| ID  | Decisión                                                                                                                                                      |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Bridge order status añade `filled` (además de rejected/submitted).                                                                                            |
| D2  | Mock fail-closed: default `rejected`. Opt-in `XTB_BRIDGE_ALLOW_ORDERS=1` → `submitted`. Segundo opt-in `XTB_BRIDGE_FILL_ORDERS=1` → `filled` (solo si ALLOW). |
| D3  | Solo `filled` → `execute_trade` → `fillStatus=executed` + `transactionId`.                                                                                    |
| D4  | `submitted` → sin ledger; Confirm/FillPending `unknown` / `live_submitted_no_fill` (XL-1).                                                                    |
| D5  | Excepción de `execute_trade` tras fill bridge → `unknown` (OI-3); no mentir `executed`.                                                                       |
| D6  | `XtbBrokerAdapter(execute_trade=…)` requerido para filled path; sin execute → `unknown` / `xtb_execute_not_wired`.                                            |
| D7  | Receipt `fillStatus` admite `executed` en adapter xtb solo tras ledger OK.                                                                                    |
| D8  | Sin Alembic · sin `contract:gen` · sin UI venue · sin thaw. Tests adapter + Confirm + FillPending + spine.                                                    |

## Kernel

```text
XtbBrokerAdapter.submit
  no bridge → not_wired
  POST /orders → rejected | submitted | filled
  rejected → rejected (no ledger)
  submitted → submitted (no ledger)
  filled + execute_trade OK → executed + trade
  filled + boom / no execute → unknown
```

## Ficheros

- `scripts/xtb-bridge-mock.mjs` — filled opt-in
- `packages/py/market/.../providers.py` — status `filled`
- `packages/py/application/.../broker_adapter.py` — execute on filled
- `packages/shared` + analytics receipt si hace falta (executed ya existe)
- Tests Confirm / FillPending / adapter
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · PaperBroker · BA-1 · PH-1 · XL-1 · LR-1 · `PAPER_D_EXECUTE` off · mesa default paper.

## E1

UI venue selector Paper \| Live (DI Confirm/FillPending). **No** thaw.
