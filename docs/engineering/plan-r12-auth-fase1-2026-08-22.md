# PLAN R-12 — Auth User→Account→Resource fase 1 (R12-AUTH)

> **Padre:** [`plan-r12-auditoria-ux-2026-08-21.md`](./plan-r12-auditoria-ux-2026-08-21.md) §2 gate R12-AUTH.
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐§0. 0 commits sin OK.
> **AsOf:** 2026-08-22. JWT / multi-user **siguen D4** (no esta fase).

---

## 0. Hallazgo (verificado)

Hoy el «user» es un **gate `APP_PASSWORD`** (cookie HttpOnly + Bearer). No hay tabla `users` ni `request.user`. `InvestmentAccount.user_id` existe y al crear queda **siempre `None`**. Con cookie válida el cliente opera **cualquier** `account_id` (path / `X-Account-Id`).

## 1. Fase 1 — aislamiento mecánico single-tenant (NO JWT)

**Qué:**

1. Principal en request tras auth OK: `request.state.principal = "app"` (constante; no claims JWT).
2. Stamp `user_id` en **altas nuevas** (`account_repository` create / seed) con el mismo principal (p. ej. `"app"` o setting `APP_OWNER_ID`, default `"app"`).
3. `list_accounts` / `get` filtran o rechazan si `user_id` está set y no coincide. Cuentas legacy `user_id is None` **siguen visibles** (no backfill masivo en esta fase).
4. `Depends(require_account_access)` en rutas de **cuentas** (path `{account_id}` list/get). Portfolio money (`ExecuteTrade`, deposit/withdraw) **NO**.

**NO:** tabla users · register/refresh · JWT · `contract:gen` · `ExecuteTrade` / cash · gobernanza IA · `PAPER_D_EXECUTE` · `pending-delete` · editar `bolsa_application/accounts.py` (conflicto R12-ACCOUNTS; el split corre en paralelo).

## 2. Ficheros típicos

`middleware/auth.py` · `auth/session.py` o `auth/principal.py` · `api/dependencies.py` · `routes/accounts.py` (guards) · `account_repository.py` · tests `test_auth.py` + isolation nueva.

## 3. Batería

`pytest apps/api-python/tests/test_auth.py` + tests isolation · ruff/mypy zona auth+repo · **no** chaos money · `git diff` sin `openapi.json` salvo que el DTO `userId` ya existiera (no regen).

## 4. Hecho cuando

Login sigue igual (un password). Cuentas nuevas llevan `user_id`. Get de cuenta con `user_id` ajeno → 404/403. Legacy `None` no se rompe. Cero JWT.

---

## 5. Fase 2 — más superficie Account (NO JWT, NO money)

**Qué:** el mismo `require_account_access` en rutas `{account_id}` que F1 no cubrió, y en lecturas de cartera/`X-Account-Id` (si el header viene).

Path:

- `core_r.py` GET/PUT `/accounts/{account_id}/core-r`
- `mandates.py` GET/PUT `/accounts/{account_id}/mandates`
- `supervised_f3.py` GET/PUT `/accounts/{account_id}/supervised-f3-queue`
- `investor_profiles.py` GET/PUT `/accounts/{account_id}/active-profile`

Header `X-Account-Id` (solo si está presente; `None` = comportamiento actual):

- `portfolio.py` GET `/portfolio` y GET `/portfolio/transactions`
- `pending_orders.py` list/create/delete (recurso de cuenta, no cash)

**NO:** `POST /portfolio/trade` · deposit/withdraw · JWT · `ai_governance` · `contract:gen` · `PAPER_D_EXECUTE` · purge pending-delete · paquete `bolsa_application/accounts/`.

Tests: extender `test_account_isolation.py` (foreign id → 404 en al menos core-r GET, mandates GET, portfolio GET con header).

Batería: pytest isolation + test_auth · ruff zona tocada.

---

## 6. Fase 3 — mismo 404 en cash/trade (NO JWT, NO reescribir motor)

**Qué:** el guard de visibilidad en las rutas de dinero. **Cero cambio** en `ExecuteTrade` / deposit / withdraw use-cases (paquete `accounts/`).

- `accounts.py` routes: `POST /accounts/{account_id}/deposits` y `/withdrawals` → `Depends(require_account_access)`
- `portfolio.py`: `POST /portfolio/trade` → `Depends(require_account_header_access)` (header ausente → `None`, igual que hoy; header ajeno → 404)

**NO:** JWT · tabla users · `ai_governance` · `contract:gen` · `PAPER_D_EXECUTE` · purge · reescribir ledger/idempotencia.

Tests: foreign deposit → 404; foreign `X-Account-Id` en trade → 404 (no hace falta un trade válido si el Depends corta antes); legacy `user_id=None` deposit sigue 2xx/4xx de negocio, no 404 de owner.

> Plan D4 (JWT / multi-user, post F1–F3): [`plan-r12-auth-d4-jwt-multiuser-2026-08-22.md`](./plan-r12-auth-d4-jwt-multiuser-2026-08-22.md) — draft, sin implementar hasta OK propietario.
