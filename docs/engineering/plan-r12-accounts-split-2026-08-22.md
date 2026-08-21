# PLAN R-12 — Split `bolsa_application.accounts` (R12-ACCOUNTS)

> **Padre:** [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md) §2 gate R12-ACCOUNTS.
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐§0 · E1–E9. Una fase = un subagente. 0 commits sin OK.
> **Mapa verificado:** coordinador 2026-08-22 (consumidores `from bolsa_application.accounts import …`, 1071 LOC).
> **AsOf:** HEAD vivo = `git fetch` + `git rev-parse origin/main`. Tag `v1.5.0-beta` → `5e52bd6`.

---

## 0. Qué / qué no

**Qué:** split mecánico de `packages/py/application/src/bolsa_application/accounts.py` (1071 líneas / ~974 no vacías) a paquete `bolsa_application/accounts/` con `__init__.py` fachada. **Cero cambio de comportamiento.** Imports públicos siguen `from bolsa_application.accounts import ExecuteTrade`.

**NO:** JWT / R12-AUTH · `PAPER_D_EXECUTE` · gobernanza IA · `pending-delete` · `contract:gen` · `schemas/accounts.py` / `routes/accounts.py` (siguen vía DI) · reescribir `ExecuteTrade` / ledger / Decimal / custody · `execution_router` / `risk_runtime` salvo imports ya existentes.

Conflicto con R12-AUTH: esta fase **no** añade `user_id` checks. Auth va en fase propia (ficheros `bolsa_api/auth*` + middleware).

---

## 1. Layout destino

Eliminar el módulo plano `accounts.py` al crear el paquete (no pueden coexistir).

| Módulo                    | Contenido                                                                        |
| ------------------------- | -------------------------------------------------------------------------------- |
| `accounts/idempotency.py` | `_idempotent_savepoint`, matchers cash+trade, `_cash_movement_result_from_entry` |
| `accounts/crud.py`        | List/Get/Create/Update/SetDefault/Close/Delete + `UpdateAccountSettings`         |
| `accounts/summary.py`     | `_account_summary_from_portfolio`, `GetAccountSummary`, `ListAccountSummaries`   |
| `accounts/cash.py`        | `DepositCashToAccount`, `WithdrawCashFromAccount`                                |
| `accounts/trade.py`       | `ExecuteTrade`                                                                   |
| `accounts/custody.py`     | `ApplyCustodyFees`                                                               |
| `accounts/ledger.py`      | `ListLedgerEntries`                                                              |
| `accounts/portfolio.py`   | `GetPortfolioSummary`, `ListTransactions`                                        |
| `accounts/tax.py`         | `GetTaxReport`                                                                   |
| `accounts/__init__.py`    | reexporta **todas** las clases públicas + `_account_summary_from_portfolio`      |

Regla anti-ciclo: submódulos solo imports **relativos** (`.idempotency`, …). Nunca `from bolsa_application.accounts import …` desde dentro del paquete.

---

## 2. Consumidores (no cambiar paths)

Todos hoy importan la fachada. Con `__init__` completo → **0 cambios** en callers.

API DI: `apps/api-python/src/bolsa_api/api/dependencies.py`.  
Rutas: `routes/accounts.py` no importa el módulo application.  
`routes/portfolio.py` importa `ExecuteTrade`.

Tests críticos: `test_account_summary_margin.py` importa **privado** `_account_summary_from_portfolio` — debe seguir en la fachada.

---

## 3. Batería

- `ruff check` zona `bolsa_application/accounts`
- `mypy packages/py/application/src --follow-imports=silent`
- pytest application: summary, list summaries, deposit/withdraw idempotency, execute-trade idempotency, idempotency reused, custody ×3
- smoke: `from bolsa_application.accounts import ExecuteTrade, ApplyCustodyFees, DepositCashToAccount, _account_summary_from_portfolio`
- `git diff` sin `openapi.json` / `schema.d.ts`

Infra/chaos PG: no obligatorio en esta PR si application+ruff+mypy verdes; coordinador puede correr m2 si el entorno lo permite.

---

## 4. Hecho cuando

`accounts.py` plano no existe; paquete + fachada; callers intactos; batería §3 verde; 0 lógica nueva.
