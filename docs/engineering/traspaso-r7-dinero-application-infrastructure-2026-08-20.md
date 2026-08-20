# Traspaso R-7 — Auditoría read-only de la lógica de dinero real en packages/py/{application,infrastructure} + corrección Fase 1 (idempotencia custodia/AUTO)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-7 — el mayor agujero de cobertura heredado de R-6: los use-cases/repos/invariantes contables quedaron FUERA del surface de la re-auditoría web+api+shared. Auditoría **read-only** de `packages/py/application` + `packages/py/infrastructure` (solo py) + corrección por fases acotadas.
> **Estado:** **EN CURSO.** Auditoría COMPLETADA (3 subagentes + verificación personal del coordinador). **Fase 1 COMMITEADA/PUSHEADA a `main`** (`c957df1`). **Fase 2 COMMITEADA/PUSHEADA a `main`** (idempotencia Deposit/Withdraw, A-2). **Fase 3 COMMITEADA/PUSHEADA a `main`** (`d7b8db8`, unique constraint parcial `ledger_entries` account/reference/type, L-M3/M-5). **M-1 COMMITEADA/PUSHEADA a `main`** (`a78eb29`, fallback mark-to-cost en `get_summary`, T-M1). **M-2 COMMITEADA/PUSHEADA a `main`** (`c8e9ced`, invariante reconciliación cash↔ledger, T-M2). **M-3 COMMITEADA/PUSHEADA a `main`** (`6962fd7`, puente cost-basis con fee en cara unrealized del tax-report, T-M3). **M-6 COMMITEADA/PUSHEADA a `main`** (`604bfef`, margen real en `_account_summary_from_portfolio`, T-M6). **M-4/T-M5 COMMITEADA/PUSHEADA a `main`** (`6a1759c`, opción B: `total_fees_for_account` excluye custodia; T-M4 job dedicado DIFERIDO por freeze). **M-7/L-M5 CERRADA por L-M3/M-5 + test-postcondición** (`f598e2d`). **B-1 (T-M7) COMMITEADA/PUSHEADA a `main`** (`4f43aeb`, high-water-mark max drawdown). **B-3 (L-M4) COMMITEADA/PUSHEADA a `main`** (`7cffaa7`, `transfer_cash` muerto sin ledger ELIMINADO). **Alto×3 + Medio×7 + Baja B-1 + Baja B-3 de R-7 completados** (queda deuda Baja y T-M4 diferido).
> **AsOf:** 2026-08-20.

---

## 1. Resumen

R-7 cubre el mayor agujero de cobertura señalado por R-6: la lógica de dinero real (trades, depósitos, invariantes contables, idempotencia, transferencias) vive en `packages/py/{application,infrastructure}` y quedó fuera del surface pactado en R-6 (que era web+api+shared). Se ejecutó un barrido transversal **read-only** (3 subagentes `explore` en paralelo: money-path de trades, depósitos/ledger/custodia, y truth-of-results/posiciones/fiscal) y el coordinador **verificó personalmente** los hallazgos de riesgo Alto contra el código real.

Resultado: **inventario de deuda NUEVA** priorizado por riesgo dinero/verdad (Alto×3, Medio×7, Bajo×5) + confirmación de que **todos los invariantes F1 siguen intactos** (sin regresión). El usuario eligió como Fase 1 corregir dos de los tres Altos que son fixes application-layer acotados sin migración. **Fase 1 COMMITEADA y PUSHEADA a `main`** (`c957df1`). El resto queda inventariado para fases futuras con decisión.

## 2. Cómo se ejecutó (protocolo)

- 3 subagentes `explore` **read-only** en paralelo, cada uno con una zona de dinero + dimensiones explícitas (atomicidad multi-repo, scope leaks, redondeo/precisión, idempotencia, fail-open, fidelidad domain↔application) y **instrucción de NO reportar** la deuda ya cerrada (F1/F-FIN-1/F-FIN-2/F5b/etc.).
- El coordinador **verificó personalmente** los hallazgos de riesgo alto (y key medio) leyendo `accounts.py`, `portfolio_repository.py`, `ledger_repository.py`, `tables.py`, `risk_runtime.py`, `execution_router.py`, `auto_execute_idempotency.py` antes de aceptarlos.
- Corrección de Fase 1: implementada por el coordinador (fixes acotados, application-layer), batería por archivos, revisión de diffs, **aprobación del usuario** y commit convencional directo en `main` (rama protegida, push aprobado).

## 3. F1 intactos verificados (NO regresión — no re-auditar)

Confirmados personalmente en código actual:

- **with_for_update** en `execute_trade` (`portfolio_repository.py:226` y posición `:244`), `deduct_cash` (`:330`), `add_cash` (`:398`), `transfer_cash` (`:361-370`, ambos lados). ✅
- **deduct_cash valida saldo DENTRO del lock** (`:335`) con `allow_partial` explícito (`:340`). ✅
- **Idempotencia de trade** vía `find_transaction_by_idempotency` (`:166-194`) + unique constraint `(portfolio_id, idempotency_key)` en `transactions` (externo). ✅
- **F-FIN-1 fail-closed**: `_resolve_portfolio` exige `legacy_portfolio_id`, sin default global por nombre (`portfolio_repository.py:31-45`). ✅
- **balance_after** = cash real del repo, sin recálculo manual (`accounts.py` ExecuteTrade). ✅
- **transfer_cash atómico** (ambos lados en lock, orden determinista por id, single flush). ✅ — NOTA: era **código muerto** (sin callers), ver L-M4 → **ELIMINADO en B-3** (`7cffaa7`, ver §4k).
- **Decimal vs Numeric(18,6)** en almacenamiento; `Decimal(str(...))` antes de escribir. ✅

## 4. Fase 1 corregida — `c957df1` `fix(py-application): idempotencia de custodia y release de claim AUTO (R-7/F1)`

### Fix A — Doble cargo de custodia bajo lecturas concurrentes (GET summary/tax)

- **Problema:** `GetAccountSummary` (`accounts.py`) y `GetTaxReport` ejecutan `ApplyCustodyFees` como **side-effect de una GET** (deduct cash + `append_custody_fee`, `reference_id="custody-{year}"`). El dedup solo era time-based (`last_custody_charge_at` + `(now-last).days < 365`); dos GET concurrentes que ven `last=None` **ambas cobran** → doble cargo anual, y la fila de custodia no tenía unique constraint (L-M3).
- **Fix:** mutex atómico `claim_custody_charge(account_id, period)` en `risk_runtime.py` — Redis `SET NX` + fallback memoria (mismo patrón que `claim_auto_execute_idempotency`), clave `custody|{account}|{year}`. `ApplyCustodyFees.execute`:
  - guard duradero del ledger primero (sin cambios de semántica);
  - toma el claim; si no lo consigue → `return False` (otro request ya está cobrando);
  - libera el claim en **toda** salida sin cargo (equity≤0, sin cartera de cargo) y **tras** cargo persistido (el guard duradero del ledger ya protege el año).
- **Files:** `risk_runtime.py` (nuevo `CUSTODY_*`, `claim_custody_charge`, `release_custody_charge`, `make_custody_idempotency_key`, `clear_custody_memory_for_tests`) · `accounts.py` (import + reestructura `ApplyCustodyFees`).

### Fix C — Claim AUTO quemado en fill fallido (reintento silenciosamente suprimido)

- **Problema:** `ExecutionRouter._execute_paper_trade` tomaba `claim_auto_execute_idempotency` **antes** del fill (`execution_router.py`). Si `ExecuteTrade.execute` lanzaba `ValueError` (p. ej. fondos/acciones insuficientes), el claim quedaba retenido → un reintento del mismo día×política×instrumento se saltaba con `status="skipped"` y razón "Idempotencia AUTO: ya ejecutado" **aunque el trade nunca se ejecutó**.
- **Fix:** nuevo `release_auto_execute_idempotency(key)` en `risk_runtime.py` (borra memoria + Redis best-effort); en el `except ValueError` del fill (solo ahí, donde NO se ha movido dinero) se libera el claim si se tomó.
- **Files:** `risk_runtime.py` (`release_auto_execute_idempotency`) · `execution_router.py` (import + release en `except ValueError`).

### Bonus mypy

- `_redis_client` tipado `-> Any | None`: `risk_runtime.py` queda **mypy-limpio** (también limpia los `no-untyped-call` pre-existentes del patrón).

### Tests (nuevo `packages/py/application/tests/test_custody_idempotency.py`, 5 casos)

1. `claim_custody_charge`/`release` serializan por cuenta+periodo; reintento tras release OK.
2. Lectura concurrente (claim en vuelo) → la 2ª GET se salta (sin cargo extra); y tras cargo persistido, dedup duradero impide repetir.
3. Sin patrimonio (equity≤0) → no cobra y libera mutex (un tick posterior con patrimonio puede cobrar).
4. Dedup periódico vía ledger (ya cobrada este periodo) → no repite.
5. `release_auto_execute_idempotency` permite reintento tras release.

### Batería Fase 1 (verde)

| Comprobación                                                                                                                                                                                                                                                               | Resultado               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (config CI)                                                                                                                                                                                               | ✅ 0                    |
| `mypy risk_runtime.py --config pyproject.toml`                                                                                                                                                                                                                             | ✅ Success              |
| pytest application money-path + nuevos (`test_execution_router_memory`, `test_auto_execute_idempotency`, `test_account_drawdown`, `test_paper_d_propose`, `test_custody_idempotency`, `test_propose_recommendation_f3`, `test_position_policies`, `test_daily_ops_report`) | ✅ 25 passed            |
| Árbol limpio tras push                                                                                                                                                                                                                                                     | ✅ (`0c0cf23..c957df1`) |

> **Nota de entorno:** no se pudieron correr la suite infra/DB ni domain/market/analytics en este hilo (requieren Postgres/Redis vivos; el auto-review bloqueó el run fuera del surface de R-7). Los cambios de Fase 1 son **application-only**; no se tocaron archivos compartidos/domain/infra. **CI a confirmar en `main`** tras el push (Python CI quality: Ruff+Mypy en domain/market/infrastructure — no toca application — y Pytest market+analytics off?line; Frontend/Optimize/Fase2/Gitleaks sin impacto esperado por path-filter).

---

## 4b. Fase 2 corregida — `fix(py-application): idempotencia de deposit/withdraw (R-7/F2, A-2)`

### A-2 — retry tras timeout no mueve dinero 2×

- **Problema:** `DepositCashToAccount.execute` y `WithdrawCashFromAccount.execute` generaban `movement_id = new_id()` **fresco en cada llamada**, sin `idempotency_key`. Un retry (p. ej. tras timeout de red) ejecutaba el movimiento **2 veces** (doble abono/adeudo). `ledger_repo.has_reference` existía pero era código muerto.
- **Fix (application+infra+api, sin migración):**
  - **Use-case** (`accounts.py`): nuevo parámetro keyword-only `idempotency_key: str | None = None`. Si se suministra, **guard previo a mutar cash**: `find_cash_movement_by_reference("external", idempotency_key)`; si existe → **rejuega el movimiento original** (nueva helper `_cash_movement_result_from_entry`) sin volver a tocar `cash` ni añadir entrada. `movement_id = idempotency_key or new_id()` → la clave queda persistida como `reference_id` en el ledger.
  - **Repo** (`ledger_repository.py`): nueva `find_cash_movement_by_reference(reference_type, reference_id) -> LedgerEntry | None` (entrada más antigua; masa `mypy strict` de infra limpia).
  - **API** (`schemas/accounts.py` + rutas): `idempotency_key: str | None = None` (alias `idempotencyKey`) en `DepositCashDto`/`WithdrawCashDto` y reenvío en las rutas de `deposits`/`withdrawals`. Aditivo y wire-compatible; **no** requiere `contract:gen`.
  - Se conserva `reference_type="external"` para no romper la clasificación semántica del FE (`packages/shared/src/portfolio-cash.ts` mapea `external`).
- **Tests** (`packages/py/application/tests/test_deposit_withdraw_idempotency.py`, 6 casos, repos fake en memoria, sin DB):
  1. Depósito idempotente: misma key no re-abona ni añade entrada; replays con misma shape (`id=key`, `kind`, `amount`, `balance_after`).
  2. Depósitos con keys distintas mueven dinero dos veces (`cash=150`).
  3. Depósito sin key → id fresco por llamada.
  4. Retirada idempotente: misma key no re-adeuda.
  5. Replay de retirada NO falla por efectivo insuficiente (guard previo a validar saldo consumido).
  6. Retirada sin key valida saldo (`ValueError`).
- **Limitación (documentada):** el guard es best-effort a nivel aplicación (check + mutación no atómica; el ledger **sigue sin unique constraint** — **L-M3/M-5** es fase aparte con migración Alembic que cierra la generación la concurrencia real).

### Batería Fase 2 (verde)

| Comprobación                                                                                         | Resultado                       |
| ---------------------------------------------------------------------------------------------------- | ------------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (config CI)                         | ✅ 0                            |
| `mypy ledger_repository.py` (infra, CI-gated)                                                        | ✅ Success                      |
| pytest application money-path F1 + nuevos (`…` F1-8 orquillas + `test_deposit_withdraw_idempotency`) | ✅ 31 passed (25 + 6)           |
| pytest api-python offline (CORS/Auth/Health/WinLoop/Q2Hygiene/RateLimit/StartupRoute)                | ✅ 32 passed                    |
| `git status`                                                                                         | ✅ solo 4 modificados + 1 nuevo |

> **Nota:** `mypy accounts.py` sigue con los 6 errores `no-untyped-def`/`arg-type` **pre-existentes** (líneas 46/84/97/383/634/672; application NO está en el gate mypy de CI). Los cambios de Fase 2 en `accounts.py` son mypy-limpios. `contract:check` del FE no se ve afectado (respuestas sin cambios).

---

## 4c. Fase 3 corregida — `fix(py-infra): UNIQUE parcial account/reference/type en ledger_entries (R-7/F3, L-M3/M-5)`

### L-M3/M-5 — unique constraint de `ledger_entries` (cierra la ventana de concurrencia real de A-2/F2 y A-1/M-7)

- **Problema:** `ledger_entries` SIN unique constraint en `(reference_type, reference_id)` → filas duplicadas posibles; raíz habilitadora de las dobles concesiones (money). La Fase 2 aplicó un guard best-effort a nivel aplicación; esta fase cierra la ventana real a nivel BD.
- **Bloqueo de diseño (descubierto en planificación, verificado por auditoría read-only):** un `UNIQUE (reference_type, reference_id)` —global **o por-cuenta**— rompería los trades con fees, porque `ExecuteTrade` escribe `append_trade` + `append_fee` con el **mismo** `reference_id=tx.id`, `reference_type="transaction"` **y mismo `account_id`** (`accounts.py:598,615`; `ledger_repository.py:65,100`). Solo difieren en `type` (`"buy"/"sell"` vs `"fee"`).
- **Solucion aplicada (opción A, decisión usuario):**
  - **Migración `004_ledger_reference_unique.py`** (nueva, `down_revision=003`): `CREATE UNIQUE INDEX uq_ledger_entries_account_reference ON ledger_entries (account_id, reference_type, reference_id, type) WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL`.
  - **Por-cuenta + `type`:** cierra trade+fee (difieren en `type`) y evita colisiones globales de `("custody","custody-YYYY")` y `("migration","initial-deposit")` en cuentas distintas.
  - **Parcial** `WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL`: respeta la semántica NULL de Postgres y los seeds `(None,None)`.
  - **Idempotente** (guard `pg_indexes`) + **preflight de duplicados** que **FALLA con error descriptivo** (no borra datos; decisión dinero/verdad).
  - **`LedgerEntryRow` (`tables.py`):** `__table_args__` con `Index(..., unique=True, postgresql_where=...)` espejo → `target_metadata` consistente con autogenerate (verificado `compare_metadata`: 0 diffs para el índice).
  - **Semántica `external`:** el índice queda por-cuenta, pero el guard real `find_cash_movement_by_reference` (`ledger_repository.py:148-168`, account-agnostic) es la primera línea y ya cubre la reutilización cross-cuenta de la `idempotency_key`; el índice es el backstop de concurrencia del mismo movimiento. Documentado en el docstring de la migración.
- **Nota operativa:** `revision` acortado a `004_ledger_reference_unique` (26 chars) porque `alembic_version.version_num` es `varchar(32)` (Prisma) y el nombre completo desbordaría.
- **Tests** (`packages/py/infrastructure/tests/test_ledger_entries_reference_unique.py`, 6 casos, Postgres real, patrón `test_f3b`):
  1. Alembic head es el nuevo + `ensure_migrated()` idempotente y el índice único parcial existe en `ledger_entries`.
  2. Duplicado `(account_id, reference_type, reference_id, type)` → `IntegrityError`.
  3. trade (`buy`) + fee (`fee`) mismo account/tx → **OK** (no colisiona, difieren en `type`).
  4. Custodia `("custody","custody-2026")` en DOS cuentas → **OK** (por-cuenta).
  5. Filas con `reference_type IS NULL` → **OK** (el parcial las excluye).
  6. (head + index, ver 1).
- **Actualización mínima de aserción:** `test_f3b_alembic_data_epoch.py` espera `004_ledger_reference_unique` como head (líneas ~91 y ~120) y en el docstring.

### Batería Fase 3 (verde, verificada por el coordinador)

| Comprobación                                                                 | Resultado                 |
| ---------------------------------------------------------------------------- | ------------------------- |
| `ruff check` (4 archivos, config CI)                                         | ✅ 0                      |
| `mypy` `tables.py` + `004_ledger_reference_unique.py` + 2 tests (gate infra) | ✅ Success                |
| pytest infra **Postgres real** (suite completa, incl. 6 tests nuevos)        | ✅ 63 passed              |
| pytest application idempotencia (deposit/withdraw 6 + custodia 5)            | ✅ 11 passed              |
| `git status`                                                                 | ✅ solo files del alcance |

---

## 4d. Fase M-1 corregida — `a78eb29` `fix(py-infra): fallback mark-to-cost en get_summary para posiciones sin precio D1 (R-7/M-1, T-M1)`

> Decisión de usuario: **Opción B** (fallback al último precio de transacción), en vez de A (exclusión).

### M-1 (T-M1) — `get_summary`: posiciones sin precio D1 fabricaban una pérdida fantasma

- **Problema:** en `SqlAlchemyPortfolioRepository.get_summary`, una posición sin close D1 (`_latest_closes` no devuelve precio) quedaba con `market_value = None` → NO sumaba a `total_market_value` ni `total_equity`, **pero su `cost_basis` SÍ se sumaba a `total_cost`** (`total_cost += cost_basis` incondicional). Como `total_unrealized_pnl = total_market_value − total_cost`, esa posición reportaba una **pérdida = coste completo** aunque no hubiera pérdida real, y `total_equity = cash + Σ market_value` la excluía → equity inconsistente y subestimada (afectaba custodia `ApplyCustodyFees`, gates de riesgo y el FE).
- **Fix (Opción B, mark-to-cost):** cuando una posición no tiene close D1, se usa como `last_price` el **último precio transaccional** del instrumento dentro de la cartera (`TransactionRow.price` del trade más reciente por `executed_at`).
  - Nuevo helper `_latest_transaction_prices(portfolio_id, instrument_ids)` → **una sola query** `DISTINCT ON (instrument_id) ... order_by(executed_at.desc())` para el conjunto de instrumentos sin precio (sin N+1), devolviendo `dict[instrument_id, float]`.
  - En el bucle, `last_price = closes.get(...)` y, si `None`, `last_price = tx_prices.get(...)`; `market_value` deja de ser `None` → la posición **sí** suma a `total_market_value` y a `total_cost`, conservando `total_equity = cash + Σ mv` y con `unrealized ≈ 0` (precio ≈ coste del último trade).
  - **Semántica del caso "sin close y sin transacción":** la posición queda sin precio observable → **NO** suma a `total_market_value` **NI** a `total_cost`, para que `total_unrealized_pnl` no fabrique la pérdida fantasma y `total_equity` no contabilice un valor desconocido.
- **Files:** `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/portfolio_repository.py` · nuevo `packages/py/infrastructure/tests/test_get_summary_no_price_fallback.py`. No se tocó application/domain/api/FE.

### Batería M-1 (verde, verificada por el coordinador)

| Comprobación                                                                           | Resultado                 |
| -------------------------------------------------------------------------------------- | ------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (2 files del alcance) | ✅ 0                      |
| `mypy portfolio_repository.py` (config raíz, gate CI)                                  | ✅ Success                |
| pytest infra **Postgres real** (suite completa, incl. 3 tests nuevos)                  | ✅ 66 passed              |
| pytest application (fakes, sin DB)                                                     | ✅ 235 passed             |
| `git status`                                                                           | ✅ solo files del alcance |

> **Nota anti-alucinación del coordinador:** al verificar la batería, un primer `ruff` lanzado con la config del **paquete `infrastructure`** reportó 27 `I001` espurios (imports en ~27 archivos NO tocados); el gate real de CI corre `ruff` con la **config raíz `pyproject.toml`**, bajo la cual los 2 archivos del alcance pasan limpios. Lección: usar SIEMPRE la config del CI (`--config pyproject.toml` raíz), no la del paquete, para la batería.

---

## 4e. Fase M-2 corregida — `c8e9ced` `fix(py-infra): invariante de reconciliación cash↔ledger con sum_cash_amounts (R-7/M-2, T-M2)`

> Decisión de usuario: **método repo + tests-postcondición** (sin guard de runtime bloqueante); **M-2 acotado a reconciliación** (B-3 no se toca en esta fase).

### M-2 (T-M2) — invariant cash↔ledger

- **Problema:** cash nunca se reconcilia contra el ledger; `equity=cash+Σmv` es tautológica. No hay invariant que re-compute cash desde el ledger y compare. `test_financial_invariants.py` solo cubre coherencia `cash`/`balance_after` a nivel repo SIN ledger.
- **Fix (método + tests-postcondición):**
  - Nuevo método `SqlAlchemyLedgerRepository.sum_cash_amounts(account_id) -> Decimal`: Σ `amount` de TODAS las filas ledger del account, scoped por `account_id` (única clave inequívoca). Semántica del signo verificada: seed `deposit`(+initial), `deposit`(+), `withdrawal`(−), `buy/sell`(∓notional sin fee), `fee`(−abs, trade y custody). Como el seed es fila `deposit` +X, Σ total ya lo incluye ⇒ Σ == cash actual. Sin guard de runtime.
  - Tests `test_m2_ledger_cash_reconciliation.py` (Postgres real), postcondición `Σ ledger == Σ cash` del account tras cada write-path de app: seed de cuenta nueva, `DepositCashToAccount`, `WithdrawCashFromAccount`, `ExecuteTrade` con fees (2 filas buy+fee reproducen −total−fees), `ApplyCustodyFees`, coherencia a nivel ACCOUNT (helper `_account_total_cash` = Σ `PortfolioRow.cash` de TODAS las legacy portfolios del account vía `InvestmentPortfolioRow`), y `xfail` documental de la escotilla B-3 (`add_cash` directo rompe el invariant; NO se sanea en esta fase).
- **Files:** `ledger_repository.py` · nuevo `test_m2_ledger_cash_reconciliation.py`. No se tocó aplicación/domain/api/FE ni `transfer_cash`/`add_cash`/`deduct_cash` (B-3 intacto).

### Batería M-2 (verde, verificada por el coordinador)

| Comprobación                                                                           | Resultado                 |
| -------------------------------------------------------------------------------------- | ------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (2 files del alcance) | ✅ 0                      |
| `mypy ledger_repository.py` (config raíz, gate CI)                                     | ✅ Success                |
| pytest infra **Postgres real** (suite completa, incl. 6 nuevos + 1 xfail)              | ✅ 72 passed, 1 xfailed   |
| pytest application (fakes, sin DB)                                                     | ✅ 235 passed             |
| `git status`                                                                           | ✅ solo files del alcance |

---

## 4f. Fase M-3 corregida — `6962fd7` `fix(py-domain): puente de reconciliación cost-basis con fee en cara unrealized del tax-report (R-7/M-3, T-M3)`

> Decisión de usuario: **puente de conciliación (opción iv)** — NO tocar el storage ni `execute_trade` (la posición sigue fee-excluida); y **sincronizar la cara unrealized del report** a la posición coherente (con fee).

### M-3 (T-M3) — divergencia cost-basis unrealized (posición) vs realized (tax)

- **Problema:** la POSICIÓN excluye la fee de compra de su cost-basis (`portfolio_repository.py:341` `avg_cost=price`; `:330` weighted-avg sin fee), pero el TAX-REPORT la CAPITALIZA (`tax_report.py` FIFO `unit_cost=(total+fee)/qty`, avg `total_cost += tx.total+fee`). Además `GetTaxReport` (`accounts.py:698-715`) construía `unrealized` con `cost_basis = pos.quantity*pos.avg_cost` (base FEE-EXCLUIDA) e inyectaba en `build_tax_report(... positions=...)` → **el report se contradecía a sí mismo**: realized (con fee) y unrealized (sin fee) no conciliaban. Ejemplo buy 10@100 fee=5 / sell 5@120 fee=3 → desfase 2.50 (mitad del fee amortizado).
- **Fix (puente, opción iv):** nuevo `open_positions_with_fee_basis(transactions, method, prices, live_quantities)` en `domain/tax_report.py` que deriva las posiciones ABIERTAS con cost-basis **con fee**, usando la MISMA máquina FIFO/avg que la cara realized (refactor de `_fifo_realized`/`_average_realized` para devolver `(lines, residual)` SIN duplicar el consumo de lotes). `GetTaxReport` pasa `prices`/`live_quantities` desde `get_summary` y usa `open_positions_with_fee_basis` como `positions=`. El storage/`avg_cost` de la posición y el FE de posiciones NO cambian.
- **Conciliación verificada:** en buy 10@100 fee=5 / sell 5@120 fee=3, FIFO y avg: realized cost_basis 502.5 (5 vendidas) + unrealized cost_basis 502.5 (5 restantes) = 1005 = coste con fee; proceeds 597 + market_value 600 = 1197. El report ya no se contradice.
- **Corrección del coordinador (anti-saturación):** el subagente había añadido una **variable global mutable `_conciliation_gaps` + `tail_conciliation_gaps()`** para documentar gaps report-vs-almacén — estado compartido frágil (no thread-safe) y mecanismo muerto (nadie lo consumía). Lo sustituí por **`logger.warning("M-3 gap report-vs-storage ...")`** real en tiempo real, y ajusté los tests (gap → log; `caplog`) + `test_no_gap_cuando_live_qty_coincide`. Los `UnrealizedGainLine` quedan limpios.
- **Files:** `domain/tax_report.py` · nuevo `domain/tests/test_tax_report_open_positions.py` · `application/accounts.py` (solo cara unrealized del report). No se tocó storage/`execute_trade`/migraciones/FE de posiciones.

### Batería M-3 (verificada por el coordinador, tras la corrección global→log)

| Comprobación                                                                        | Resultado                 |
| ----------------------------------------------------------------------------------- | ------------------------- |
| `ruff` config CI raíz (3 files del alcance)                                         | ✅ 0                      |
| `mypy tax_report.py` (domain, gate CI)                                              | ✅ Success                |
| pytest domain (incl. 7 M-3 nuevos)                                                  | ✅ 21 passed              |
| pytest application (fakes)                                                          | ✅ 235 passed             |
| pytest infra **Postgres real**                                                      | ✅ 72 passed, 1 xfailed   |
| `accounts.py` mypy: sin errores NUEVOS (6 pre-existentes `no-untyped-def` intactos) | ✅                        |
| `git status`                                                                        | ✅ solo files del alcance |

---

## 4g. Fase M-6 corregida — `604bfef` `fix(py-application): margen real en _account_summary_from_portfolio (R-7/M-6, T-M6)`

> Decisión de usuario: **fórmula `margin_used = Σ market_value / leverage`** + **alcance "completar"** (computar los 3 campos; DTO/endpoints intactos, sin `contract:gen`).

### M-6 (T-M6) — margen hardcoded en `_account_summary_from_portfolio`

- **Problema:** `_account_summary_from_portfolio` (`accounts.py:112-114`) fijaba `margin_used=0.0`, `free_margin=cash`, `margin_level_pct=None` sin importar leverage/posiciones.
- **Decisión usuario:** `margin_used = Σ market_value / leverage` (inversión en posiciones bajo apalancamiento; leverage default 1); `free_margin = equity − margin_used` con `equity = total_equity` del resume (M-1/M-2); `margin_level_pct = equity/margin_used*100`, `None` si `margin_used==0`. Coherente con la definición canónica `investment-platform.md:46` (`marginLevelPct = equity/marginUsed*100`).
- **Fix:** `_account_summary_from_portfolio` computa los 3 campos reales. **Fidelidad:** solo las posiciones con `market_value` observable (no None) aportan a `margin_used` (las sin precio, caso M-1, NO cuentan — consistentes con `total_market_value`/`total_equity`). Guard `leverage>0` → si 0 (fail-closed), `margin_used=0.0` y `margin_level_pct=None` (sin dividir por cero). No toqué el DTO `AccountSummary` (valores dentro de campos existentes, shape intacto → sin contract:gen). **Sin tocar FE.**
- **Consumidores (cambio de valor esperado):** FE `dashboard-page.tsx:163` hint "Margen libre" verá `free_margin` real (antes `cash`); API expone los campos en `GetAccountSummary`/`ListAccountSummaries` (shape intacto).
- **Tests** `test_account_summary_margin.py` (6, fakes en memoria): A sin posiciones (0/equity/None), B single con leverage (mv/lvg), C dos posiciones leverage>1, D sin precio no cuenta, D' mixto solo cuenta la con precio, E guard leverage==0 (sin ZeroDivision). El fake `_Account` de `test_list_account_summaries.py` ganó `leverage: float = 1.0`.

### Batería M-6 (verificada por el coordinador)

| Comprobación                                                         | Resultado                 |
| -------------------------------------------------------------------- | ------------------------- |
| `ruff` config CI raíz (3 files del alcance)                          | ✅ 0                      |
| pytest application (fakes, incl. 6 M-6 nuevos)                       | ✅ 241 passed             |
| pytest domain                                                        | ✅ 21 passed              |
| pytest infra **Postgres real**                                       | ✅ 72 passed, 1 xfailed   |
| api-python integration `test_accounts.py` (endpoint summary intacto) | ✅ 5 passed               |
| `accounts.py` mypy: sin errores NUEVOS (6 pre-existentes intactos)   | ✅                        |
| `git status`                                                         | ✅ solo files del alcance |

---

## 4h. Fase M-4 corregida — `6a1759c` `fix(py-infra): total_fees_for_account excluye custodia (fees_paid_total no mezcla trade) (R-7/M-4, T-M5)`

> Decisión de usuario: **Opción B acotada** (corregir solo `fees_paid_total` para que NO mezcle custodia). **T-M4** (custodia side-effect en GET → mover a job dedicado) se **DIFIERE** por colindar con «sin features». La Opción A (job dedicado) sigue disponible para una fase futura con decisión.

### M-4 (T-M5) — `fees_paid_total` mezcla fees de trade con fees de custodia

- **Problema:** `GetTaxReport` sobrescribe `fees_paid_total` (`accounts.py:750-751`) con `total_fees_for_account` (`ledger_repository.py`), que contaba TODAS las filas `type == "fee"` del account **incluyendo custodia** (`reference_type="custody"`, escrita por `append_custody_fee`). Como el cargo de custodia cae dentro del rango fiscal, el report mezclaba comisiones de administración dentro de "Comisiones pagadas" que ve el FE (`tax-report-page.tsx:325`).
- **Fix (Opción B, acotado, infra-only):** `total_fees_for_account` filtra las filas de custodia (`reference_type != "custody"`, conservando `IS NULL`) para que `GetTaxReport` deje de mezclar. Los trade-fees (`reference_type="transaction"`) se siguen contando; el mapeo `map_ledger_fees_to_transactions` (por `reference_id=tx.id`) NO se ve afectado (la custodia usa `reference_id="custody-{period}"`, nunca coincide con un tx).
- **Files:** `ledger_repository.py` (query + docstring) · nuevo `packages/py/infrastructure/tests/test_m4_total_fees_excludes_custody.py` (2, Postgres real). No se tocó application/domain/api/FE.
- **Tests:**
  1. `test_total_fees_for_account_excluye_custodia`: trade-fee (`reference_type="transaction"`) + custodia-fee (`reference_type="custody"`) en el mismo account y rango → `total_fees_for_account == 10.0` (solo trade), no 35.
  2. `test_total_fees_rango_fiscal_respetado`: custodia en el rango + trade-fee fuera del rango → `total == 0.0` (el filtro de rango y el de custodia se componen).

### Batería M-4 (verde, verificada por el coordinador)

| Comprobación                                                                       | Resultado                 |
| ---------------------------------------------------------------------------------- | ------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (2 files alcance) | ✅ 0                      |
| `mypy ledger_repository.py` + test M-4 (config raíz, gate CI)                      | ✅ Success                |
| pytest infra **Postgres real** (suite completa, incl. 2 nuevos)                    | ✅ 74 passed, 1 xfailed   |
| pytest application (fakes, sin DB)                                                 | ✅ 241 passed             |
| `git status`                                                                       | ✅ solo files del alcance |

> **Nota de alcance:** esta fase NO toca T-M4 (custodia como side-effect de GET: `GetAccountSummary` `accounts.py:154-158`, `GetTaxReport` `accounts.py:653-657`, herencia vía `daily_ops_report.py:78`). Esa parte queda **diferida** por colindar con «sin features» (mover a job dedicado es cambio de comportamiento). Mapeo read-only completo en el historial del chat (subagente `explore` + verificación del coordinador).

---

## 4i. Fase M-7 corregida — `f598e2d` `test(py-infra): postcondicion M-7 — UNIQUE de F3 ya impide recargo de custodia del mismo periodo (R-7/M-7, L-M5)`

> Decisión de usuario: **Opción A (solo tests-postcondición, sin tocar código de producción)**. El mapeo read-only confirmó que el re-cobro de custodia (dedup time-only del mutex) **ya está cubierto por L-M3/M-5**, así que M-7 se cierra aportando evidencia de test.

### M-7 (L-M5) — custodia dedup time-only: cubierta por el UNIQUE de F3

- **Hallazgo (mapeo verificado):** el único candidato de re-cobro era la ventana time-only del mutex `claim_custody_charge` (TTL ~48h + fallback de memoria) si dos GET entran tras restart/R-expiry y ambas superan `last_custody_charge_at`. Pero **desde L-M3/M-5** (`004_ledger_reference_unique`, UNIQUE parcial `(account_id, reference_type, reference_id, type)`), `append_custody_fee` (escribe `reference_type="custody"`, `reference_id="custody-{period}"`, `type="fee"`) colisiona si se re-cobra: la 2ª fila se rechaza con **`IntegrityError`**.
- **Atomicidad cash+ledger:** aun si la 2ª request descuenta `cash` (`deduct_cash`) antes del flush que falla, `deduct_cash` y `append_custody_fee` comparten la misma `AsyncSession`; el `except` del use-case (release+raise, `accounts.py:480-482`) + el `except: rollback()` de `get_db_session` (`dependencies.py:270-280`) revierten el descuento → **no queda cash descontado sin fila**.
- **Tests** (`packages/py/infrastructure/tests/test_m7_custody_single_charge_f3_guard.py`, 2, Postgres real):
  1. `test_unique_rechaza_recargo_mismo_periodo`: el UNIQUE rechaza con `IntegrityError` una 2ª fila de custodia del `mismo account+periodo`.
  2. `test_recargo_forzado_no_deja_cash_descontado`: peor caso del mutex — la 2ª request descuenta cash y su append choca; el `rollback` del caller revierte el descuento y `Σ ledger == Σ cash` (coherente con M-2).
- **Files:** solo `test_m7_custody_single_charge_f3_guard.py` (nuevo). **Sin cambios en código de producción.**

### Batería M-7 (verde, verificada por el coordinador)

| Comprobación                                                            | Resultado                 |
| ----------------------------------------------------------------------- | ------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml`        | ✅ 0                      |
| `mypy test_m7_custody_single_charge_f3_guard.py` (config raíz, gate CI) | ✅ Success                |
| pytest infra **Postgres real** (suite completa, incl. 2 nuevos)         | ✅ 76 passed, 1 xfailed   |
| pytest application (fakes, sin DB)                                      | ✅ 241 passed             |
| `git status`                                                            | ✅ solo files del alcance |

---

## 4j. Fase B-1 corregida — `4f43aeb` `fix(py-application): max drawdown high-water-mark en HardMaxDrawdown (R-7/B-1, T-M7)`

> Decisión de usuario: **Opción A — high-water-mark (HWM)**: `max_pct` = drawdown desde el pico de equity (running peak), monotónico no-decreciente, resetea a 0 solo con nuevo máximo. No-depósito/≤0 preserva `max_pct=None` (gate `HardMaxDrawdown` SKIPPED).

### B-1 (T-M7) — max drawdown naive vs depósito inicial → under-bloqueo tras recuperación

- **Problema:** `EquityMarkBook.update` (`account_drawdown.py:93-94`) computaba `max_dd = _dd_pct(initial_deposit, equity)` — función **estateless** `max(0, (ref−cur)/ref*100)` que comparaba el equity **actual** contra el depósito inicial y se recalculara desde cero en cada snapshot, **sin trackear el pico de equity (high-water-mark)** ni el drawdown más profundo. Consecuencia: si la cuenta sufrió un gran descenso y luego **se recuperó** (equity ≈ inicial), `max_pct` colapsaba hacia 0 → el gate `HardMaxDrawdown` (bloquea si `account_max_drawdown_pct <= limit`) **dejaba de bloquear** (under-bloqueo tras recuperación), "olvidando" que se tocó fondo.
- **Flow verificado (mapeo read-only):** `execution_router.py:490-494/:752-756` llama `GLOBAL_EQUITY_MARK_BOOK.update(..., initial_deposit=...)` → `dds.max_pct` (`account_drawdown.py`) → `:517/:780 account_max_drawdown_pct=dds.max_pct` → `trading_policy_guard.py:195` → `risk_engine.py:121` → analytics `policy_gate.py:223-241` (regla `HardMaxDrawdown`: PASS si `<= limit`). Espejo TS del gate en `packages/shared/src/cognitive/policy-gate.ts:200-217` consume `dd.maxPct`. Límites `trading_policy_templates.py:53/122/190` (8/12/18%).
- **Fix (HWM, application-only):** `EquityMarkBook.update` (1 función) ahora
  - trackea `state["peakEquity"]` (running peak). Semilla: si ausente (1er observation), `max(equity, initial_deposit_>0)`; si ya presente (restart vía settings), se conserva. Después `peak = max(peak, equity)` monotónico.
  - trackea `state["maxDrawdownPct"]` (running max / drawdown más profundo desde el pico), reseteado a 0 solo cuando `equity >= peak` (nuevo máximo) — esto preserva el valor profundo tras recuperación parcial (10.0, no 2.0), que es exactamente el fix del under-bloqueo.
  - **Gating preservado:** `max_pct` solo se computa si `initial_deposit is not None and > 0` (baseline presente); sin baseline → `max_pct=None` → gate `HardMaxDrawdown` SKIPPED (idéntico a antes).
  - **Persistencia automática:** `peakEquity`/`maxDrawdownPct` viven en el state dict que `export_settings_fragment`/`load_from_settings` ya serializan/restauran (sin tocar esos métodos). `daily_pct`/`weekly_pct`/`day_open_equity`/`week_open_equity`/`lastEquity` intactos. DTO shape sin cambio (`max_pct: float | None`).
- **Nota de diseño (verificación anti-alucinación del coordinador):** el subagente se desvió del brief "puro `_dd_pct(peak, equity)`" añadiendo el running-max `maxDrawdownPct`. Verifiqué que la desviación es **necesaria y correcta** (el `_dd_pct(peak, equity)` puro reportaría 2.0 en la recuperación parcial 100k→90k→98k, no el 10.0 monotónico que exige la intención documentada y los tests).
- **Files:** `packages/py/application/src/bolsa_application/account_drawdown.py` · `packages/py/application/tests/test_account_drawdown.py` (4 nuevos). No se tocó infra/domain/api/FE ni el shape del DTO.

### Batería B-1 (verificada por el coordinador)

| Comprobación                                                                       | Resultado                   |
| ---------------------------------------------------------------------------------- | --------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (2 files alcance) | ✅ exit 0                   |
| `mypy account_drawdown.py` (config raíz)                                           | ✅ Success                  |
| pytest `test_account_drawdown.py`                                                  | ✅ 6 passed (2 pre + 4 new) |
| pytest application (fakes, sin DB) (suite completa)                                | ✅ 245 passed (4 nuevos)    |
| `git status`                                                                       | ✅ solo files del alcance   |

---

## 4k. Fase B-3 corregida — `7cffaa7` `fix(py-infra): eliminar transfer_cash muerto sin ledger (R-7/B-3, L-M4)`

> Decisión de usuario: **ELIMINAR `transfer_cash`** (código muerto, 0 callers, muta cash SIN ledger). Opción de menor riesgo/superficie y **freeze-compatible** (quitar dead code no es feature). Se descartan «conectar use-case/ruta» (colide con "sin features") y «documentar solo» (deja el hazard vivo).

### B-3 (L-M4) — write-paths de cash sin ledger: `transfer_cash` muerto eliminado

- **Hallazgo (mapeo read-only verificado):** `transfer_cash` (`portfolio_repository.py:402-445`) era atómico (locks ambos `PortfolioRow` en orden determinista por id, single flush) pero **solo mutaba `row.cash`** y **NO escribía ninguna fila ledger**. Grep global: **0 callers** en todo el repo (solo la definición + refs en docs/README). `add_cash`/`deduct_cash` SÍ son vivos y sus use-cases (Deposit/Withdraw/Custodia) ya escriben ledger vía `append_cash_movement`/`append_custody_fee`.
- **Fix (decisión usuario: eliminar):** se **elimina el método `transfer_cash`** completo de `SqlAlchemyPortfolioRepository`. Con ello el único write-path que podía mover dinero SIN ledger Y sin caller desaparece: **un futuro caller ya no puede existir** → hazard cerrado de raíz.
- **`add_cash`/`deduct_cash` se conservan** (vivos y trazados por sus callers); su escotilla residual (un caller que los invoque directo sin `append_cash_movement`) queda documentada en el xfail M-2 reconvertido.
- **Intactos para una futura feature ya trazada (cuando se levante el freeze):** el default `reference_type="transfer"` de `append_cash_movement` (`ledger_repository.py:276`) y el tipo `'transfer'` del FE (`packages/shared/src/portfolio-cash.ts`) permanecen — un futuro use-case de transferencia escribirá ledger desde el primer momento.
- **Files:** `portfolio_repository.py` (eliminar `transfer_cash`) · `test_m2_ledger_cash_reconciliation.py` (docstring + razón xfail B-3 reconvertidos a escotilla residual `add_cash`/`deduct_cash`; `_assert_reconciled` ganó anotación `SqlAlchemyLedgerRepository` vía `TYPE_CHECKING`, cerrando un `no-untyped-def` pre-existente del fichero tocado). No se tocó aplicación/domain/api/FE.

### Batería B-3 (verde, verificada por el coordinador)

| Comprobación                                                                           | Resultado                 |
| -------------------------------------------------------------------------------------- | ------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml` (config CI raíz)      | ✅ 0                      |
| `mypy portfolio_repository.py` + `test_m2_ledger_cash_reconciliation.py` (gate infra)  | ✅ Success                |
| pytest infra **Postgres real** (suite completa)                                        | ✅ 76 passed, 1 xfailed   |
| pytest application money-path (deposit/withdraw, custody, margin, drawdown, execution) | ✅ 32 passed              |
| `git status`                                                                           | ✅ solo files del alcance |

---

## 5. Inventario de deuda NUEVA (de R-7; priorizado por riesgo dinero/verdad)

### 🔴 Alto

| Código | Superficie  | Hallazgo                                                                                                                                                                        | Estado                           |
| ------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| A-1    | application | Custodia aplicada como side-effect de GET (summary/tax) + doble cargo bajo concurrencia (dedup time-only, sin unique constraint en ledger)                                      | ✅ CORREGIDO (Fase 1, `c957df1`) |
| A-2    | application | Deposit/Withdraw **no idempotentes**: `movement_id = new_id()` fresco, sin `idempotency_key`; retry tras timeout mueve dinero 2×. `has_reference` existe pero es código muerto. | ✅ CORREGIDO (Fase 2, ver §4b)   |
| A-3    | application | Claim AUTO de idempotencia quemado si el fill falla → reintento suprimido en silencio                                                                                           | ✅ CORREGIDO (Fase 1, `c957df1`) |

### 🟠 Medio

| Código          | Superficie     | Hallazgo                                                                                                                                                                                                                                                 | Riesgo        |
| --------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------- |
| M-1 (T-M1)      | infrastructure | `get_summary` omite de `total_market_value`/`total_equity` las posiciones sin precio D1, pero SUMA su `cost_basis` a `total_cost` → `total_unrealized_pnl` reporta pérdida = coste completo de posiciones sin precio; equity errónea sin reconciliación. | dinero/verdad | ✅ CORREGIDO (M-1, ver §4d)                                                      |
| M-2 (T-M2)      | infrastructure | Cash NUNCA se reconcilia contra el ledger; identity `equity=cash+Σmv` es tautológica. No hay invariant que re-compute cash desde el ledger y compare.                                                                                                    | dinero/verdad | ✅ CORREGIDO (M-2, ver §4e)                                                      |
| M-3 (T-M3)      | infra+domain   | Divergencia de cost-basis: el `avg_cost`/`cost_basis` de la posición EXCLUYE la fee de compra, pero el tax-report FIFO/avg la INCLUYE → unrealized (posiciones) y realized (tax) no concilian.                                                           | dinero/verdad | ✅ CORREGIDO (M-3, ver §4f)                                                      |
| M-4 (T-M4/T-M5) | application    | `GetTaxReport`/`GetAccountSummary` hacen cargo de custodia en GET (mutan dinero en lectura) + `fees_paid_total` mezcla fees de trade con fees de custodia (dependiente de lectura).                                                                      | dinero        | ✅ **T-M5** (ver §4h, `6a1759c`) · **T-M4 DIFERIDO** (job dedicado, freeze)      |
| M-5 (L-M3)      | infrastructure | Ledger SIN unique constraint en `(reference_type, reference_id)` → filas duplicadas posibles; `has_reference` muerto; raíz habilitadora de dobles concesiones.                                                                                           | dinero        | ✅ CORREGIDO (Fase 3, ver §4c)                                                   |
| M-6 (T-M6)      | application    | Campos de margen hardcoded en `_account_summary_from_portfolio` (`margin_used=0.0`, `free_margin=cash`, `margin_level_pct=None`) aunque haya leverage/posiciones.                                                                                        | dinero        | ✅ CORREGIDO (M-6, ver §4g)                                                      |
| M-7 (L-M5)      | application    | Custodia dedup time-only (además del fix A-1); sin unique constraint la ventana concurr. aún la cubre el mutex, pero un restart/R-expiry en medio puede re-cobrar.                                                                                       | dinero        | ✅ **CERRADA** (ver §4i, `f598e2d`) — cubierta por L-M3/M-5 + test-postcondición |

### 🟢 Bajo

| Código           | Superficie  | Hallazgo                                                                                                                                                                       | Riesgo        |
| ---------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- | ------------------------------------------------------------------------------------- |
| B-1 (T-M7)       | application | "Max drawdown" naive (vs depósito inicial, no high-water-mark) alimenta el risk gate `HardMaxDrawdown` → under-bloqueo tras recuperación.                                      | verdad        | ✅ CORREGIDO (B-1, ver §4j, `4f43aeb`)                                                |
| B-2 (T-M8)       | domain      | `total_unrealized_gain` suma `unrealized_gain or 0.0` → posiciones sin precio se silencian a 0 en el total.                                                                    | verdad        |
| B-3 (L-M4)       | infra+app   | `transfer_cash` atómico pero **código muerto** (0 callers) y **no escribe ledger**; un futuro caller movería dinero sin traza reconciliable.                                   | dinero/verdad | ✅ CORREGIDO (B-3, ver §4k, `7cffaa7`) — `transfer_cash` ELIMINADO (decisión usuario) |
| B-4 (L-M6)       | application | fee ledger escrita en 2ª llamada no atómica con el trade; app guard solo se activa si se pasa `idempotency_key` (nada lo exige).                                               | dinero        |
| B-5 (T-M9/T-M10) | application | FIFO divide sin guard `quantity==0` (latente, repo lo rechaza); `fetch_core_r_pnl_extra_rows` atribuye el PnL whole-account a un instrumento (fail-open, fallback a `list[]`). | verdad        |

### ⚠️ Hábitos (no-deuda, sin re-auditar)

- Mypy gate: CI corre mypy SOLO en `domain/market/infrastructure` (NO application ni apps/api-python) → **application mypy-blind en CI**. Notable gap: `accounts.py`/`execution_router.py` tienen `no-untyped-def` pre-existentes que CI no detecta.
- Los `# type: ignore` Mapped intencionales no son deuda.

---

## 6. Pendientes / fases futuras (no abrir sin decisión)

1. **M-4/T-M4 (resto de M-4):** mover el cargo de custodia del path de lectura (GET summary/tax + herencia daily-ops) a un job dedicado — cambio de comportamiento, requiere decisión (colinda con "sin features"). **T-M5 (mezcla fees) ya CERRADA** (`6a1759c`); **queda solo T-M4, DIFERIDO**.
2. ~~**M-7 (L-M5):** custodia dedup time-only~~ — **✅ CERRADA** (`f598e2d`, ver §4i): cubierta por L-M3/M-5 (UNIQUE rechaza re-cargo + transacción compartida revierte cash) + test-postcondición.
3. ~~**B-1 (T-M7):** "max drawdown" naive en el risk gate `HardMaxDrawdown`~~ — **✅ CERRADA** (`4f43aeb`, ver §4j): high-water-mark (pico de equity + running-max `maxDrawdownPct`).
4. **B-2 (T-M8):** `total_unrealized_gain` silencia a 0 las posiciones sin precio. _(NO confundir con M-1, ya cerrada.)_
5. ~~**B-3 (L-M4):** `transfer_cash`/`add_cash`/`deduct_cash` del repo mutan cash SIN ledger (código muerto; xfail documental en M-2)~~ — **✅ CERRADA** (`7cffaa7`, ver §4k): `transfer_cash` ELIMINADO por código muerto (decisión usuario); xfail M-2 reconvertido a escotilla residual `add_cash`/`deduct_cash`.
6. **B-4 (L-M6):** fee ledger escrita en 2ª llamada no atómica con el trade (el UNIQUE de Fase 3 NO toca `transaction` → queda abierta).
7. **B-5 (T-M9/T-M10):** FIFO divide sin guard `quantity==0`; `fetch_core_r_pnl_extra_rows` atribuye el PnL whole-account a un instrumento.
8. Checklist operativo manual de relevos previos (secret scanning UI, `TRUSTED_PROXIES` prod, `BP/.L`→`BP.L`, logs dev).

**Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4). Una fase = un subagente acotado + batería + aprobación por commit + relevo al cerrar chat. **No hacer `regen_full`** sin decisión. **No `contract:gen`.**

---

## 7. Batería acumulada (verde al cerrar esta parte)

| Comprobación                                                                                                      | Resultado                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `ruff check packages/py apps/api-python --config pyproject.toml`                                                  | ✅ 0                                                                                                         |
| `mypy risk_runtime.py` + `mypy ledger_repository.py` (infra)                                                      | ✅ 0 / Success                                                                                               |
| pytest application money-path + F1 nuevos (8 ficheros)                                                            | ✅ 25 passed                                                                                                 |
| pytest application + F2 nuevos (`test_deposit_withdraw_idempotency`)                                              | ✅ 31 passed (25 + 6)                                                                                        |
| pytest api-python offline (CORS/Auth/Health/WinLoop/Q2Hygiene/RateLimit/StartupRoute)                             | ✅ 32 passed                                                                                                 |
| Árbol tras F1/tras F2/tras F3 (`local main = origin/main`) · pytest infra Postgres real 63 · idempotencia 11      | ✅ (`…c957df1` · a confirmar F2)                                                                             |
| M-1: `ruff` config CI raíz (2 files) · `mypy portfolio_repository.py` · infra real 66 · application 235           | ✅ 0 / Success / 66 / 235 (ver §4d)                                                                          |
| M-2: `ruff` config CI raíz (2 files) · `mypy ledger_repository.py` · infra real 72+1xfail · application 235       | ✅ 0 / Success / 72 / 235 (ver §4e)                                                                          |
| M-3: `ruff` config CI raíz (3 files) · `mypy tax_report.py` · domain 21 · infra real 72+1xfail · application 235  | ✅ 0 / Success / 21 / 72+1xfail / 235 (ver §4f; corrección global→log del coordinador)                       |
| M-4/T-M5: `ruff` config CI raíz (2 files) · `mypy ledger_repository.py`+test · infra real 74+1xfail · app 241     | ✅ 0 / Success / 74+1xfail / 241 (ver §4h)                                                                   |
| M-7/L-M5: `ruff` config CI raíz · `mypy` test · infra real 76+1xfail · app 241                                    | ✅ 0 / Success / 76+1xfail / 241 (ver §4i)                                                                   |
| B-1/T-M7: `ruff` config CI raíz (2 files) · `mypy account_drawdown.py` · application 245 (4 nuevos)               | ✅ 0 / Success / 245 (ver §4j)                                                                               |
| B-3/L-M4: `ruff` config CI raíz (2 files) · `mypy portfolio_repo+test` · infra real 76+1xfail · app money-path 32 | ✅ 0 / Success / 76+1xfail / 32 (ver §4k)                                                                    |
| CI `main` para `c957df1`                                                                                          | → ratificado; F2 a confirmar (Gitleaks/Frontend sin impacto por path-filter; Python CI no gatea application) |

## 8. Texto de traspaso (pegar al abrir el próximo chat / relevo por saturación)

> CONTEXTO (2026-08-20): **R-7 — auditoría read-only de la lógica de dinero real en `packages/py/{application,infrastructure}` COMPLETADA + Fases 1, 2, 3, M-1, M-2, M-3, M-6, M-4/T-M5, M-7/L-M5, B-1 y B-3 PUSHEADAS a `main`. Alto×3 + Medio×7 + Baja B-1 + Baja B-3 de R-7 completados**. Mayor agujero de cobertura heredado de R-6 (use-cases/repos/invariantes contables quedaron fuera del surface web+api+shared).
>
> **Auditoría:** 3 subagentes read-only + verificación personal del coordinador. Invariantes F1/FFIN todo INTACTOS (with_for_update, deduct_cash en lock, idempotencia trade + constraint, F-FIN-1 fail-closed, transfer_cash atómico). Deuda NUEVA: **Alto×3 / Medio×7 / Bajo×5**.
>
> **Fase 1 corregida y pusheada (`c957df1`)** `fix(py-application): idempotencia de custodia y release de claim AUTO (R-7/F1)`:
>
> - **Fix A:** doble cargo de custodia bajo GET concurrentes (summary/tax) — mutex atómico `claim_custody_charge` por cuenta|periodo (Redis SET NX + memoria, patrón auto-exec) en `ApplyCustodyFees.execute`, con release en salidas sin cargo.
> - **Fix C:** claim AUTO liberado en `except ValueError` del fill fallido (`release_auto_execute_idempotency`) — antes el reintento se suprimía en silencio sin haberse ejecutado trade.
> - Bonus: `_redis_client -> Any | None` (risk_runtime mypy-limpio). Tests: `test_custody_idempotency.py` (5).
>
> **Fase 2 corregida y pusheada** `fix(py-application): idempotencia de deposit/withdraw (R-7/F2, A-2)`:
>
> - **A-2:** Deposit/Withdraw no idempotentes (`movement_id = new_id()` fresco → retry tras timeout movía dinero 2×). Fix: `idempotency_key` opcional en use-case + DTO/rutas; guard `find_cash_movement_by_reference("external", key)` previo a mutar cash → rejuega el movimiento original sin duplicar; `movement_id = key or new_id()`; nuevo repo method infra; `idempotencyKey` en `DepositCashDto`/`WithdrawCashDto` (aditivo, sin `contract:gen`). Se conserva `reference_type="external"` (por FE). Sin migración. Tests `test_deposit_withdraw_idempotency.py` (6, fakes en memoria, sin DB).
>
> **Fase 3 corregida y pusheada** `fix(py-infra): UNIQUE parcial account/reference/type en ledger_entries (R-7/F3, L-M3/M-5)`:
>
> - **L-M3/M-5:** `ledger_entries` SIN unique constraint → raíz de dobles concesiones. **Bloqueo:** un `UNIQUE (reference_type, reference_id)` (global O por-cuenta) rompería trade+fee (mismo `tx.id`/`account_id`, solo difieren en `type`). **Solución (opción A):** migración `004_ledger_reference_unique` → `CREATE UNIQUE INDEX uq_ledger_entries_account_reference ON ledger_entries (account_id, reference_type, reference_id, type) WHERE reference_type IS NOT NULL AND reference_id IS NOT NULL`. Por-cuenta + `type` lo resuelve sin romper trade+fee ni custodia/migración multi-cuenta; parcial excluye seeds `(None,None)`; idempotente + preflight que FALLA si hay duplicados (no borra datos). `LedgerEntryRow.__table_args__` espejo (0 diffs). `external` queda por-cuenta (el guard global `find_cash_movement_by_reference` sigue siendo línea-1). Tests `test_ledger_entries_reference_unique.py` (6, Postgres real).
>
> **M-1 (T-M1) corregida y pusheada** `fix(py-infra): fallback mark-to-cost en get_summary para posiciones sin precio D1 (R-7/M-1)`:
>
> - **T-M1:** `get_summary` sumaba el `cost_basis` de posiciones sin close D1 a `total_cost` pero nada a `total_market_value` → `total_unrealized_pnl` fabricaba una pérdida = coste completo y `total_equity` las excluía (inconsistente; afectaba custodia, gates de riesgo y FE). **Opción B (decisión usuario):** fallback mark-to-cost al último `TransactionRow.price` del instrumento en la cartera (nuevo helper `_latest_transaction_prices`, una query `DISTINCT ON instrument_id` por `executed_at desc`, sin N+1). Posición sin close y sin transacción → sin valor observable y NO suma a `total_market_value` ni a `total_cost` (no produce pérdida fantasma). `total_equity = cash + Σ mv` se conserva. Tests `test_get_summary_no_price_fallback.py` (3, Postgres real).
>
> **Batería:** ruff CI-config 0 ✅ · mypy infra 0/Success ✅ · pytest infra **Postgres real 63 passed** (incl. F3 nuevos) ✅ · pytest application idempotencia **11 passed** ✅ · api-python offline **32 passed** ✅. **CI main a confirmar** (F1 ratificado). `mypy accounts.py` conserva 6 errores pre-existentes (`no-untyped-def`/`arg-type`), sin nuevos.
>
> **M-1 extra (batería del coordinador):** ruff config CI raíz 2 files 0 ✅ · mypy `portfolio_repository.py` Success ✅ · pytest infra **66 passed** (3 nuevos) ✅ · pytest application **235 passed** ✅.
>
> **M-2 (T-M2) corregida y pusheada (`c8e9ced`)** `fix(py-infra): invariante de reconciliación cash↔ledger con sum_cash_amounts (R-7/M-2)`:
>
> - **T-M2:** cash nunca se reconcilia contra el ledger (`equity=cash+Σmv` tautológica). Fix (decisión usuario: método + tests-postcondición, sin guard runtime): nuevo `SqlAlchemyLedgerRepository.sum_cash_amounts(account_id)` → Σ `amount` de TODAS las filas ledger del account (scoped por `account_id`; semántica de signo: seed `deposit`+X, `deposit`+ / `withdrawal`− / `buy|sell` ∓notional / `fee` −abs; como el seed es fila `deposit`, Σ ya lo incluye ⇒ Σ==cash). Tests `test_m2_ledger_cash_reconciliation.py` (6, Postgres real): postcondición Σ==Σcash por write-path de app (seed cuenta, Deposit, Withdraw, ExecuteTrade con fees 2 filas, ApplyCustodyFees) + coherencia a nivel ACCOUNT + `xfail` documental de la escotilla B-3 (add_cash directo rompe el invariant; NO se sanea en esta fase, M-2 acotado). Helper `_account_total_cash` = Σ `PortfolioRow.cash` de TODAS las legacy portfolios vía `InvestmentPortfolioRow`.
>
> **M-3 (T-M3) corregida y pusheada (`6962fd7`)** `fix(py-domain): puente de reconciliación cost-basis con fee en cara unrealized del tax-report (R-7/M-3)`:
>
> - **T-M3:** divergencia cost-basis — la POSICIÓN excluye la fee de compra (`avg_cost=price`), el TAX-REPORT la capitaliza, y `GetTaxReport` inyectaba `pos.quantity*pos.avg_cost` (fee-excluida) en la cara unrealized del report → el report se contradecía a sí mismo (realized con fee vs unrealized sin fee). **Decisión usuario: puente (opción iv)** sin tocar storage/`execute_trade` + **sincronizar la cara unrealized**. Fix: nuevo `open_positions_with_fee_basis(transactions, method, prices, live_quantities)` en domain que deriva las posiciones abiertas con base **con fee** usando la MISMA máquina FIFO/avg que realized (refactor `_fifo_realized`/`_average_realized` → `(lines, residual)` sin duplicar consumo de lotes); `GetTaxReport` usa `prices`/`live_quantities` de `get_summary`. Verificado: buy 10@100 fee=5 / sell 5@120 fee=3 → realized cost_basis 502.5 + unrealized 502.5 = 1005 (coste con fee); proceeds 597 + MV 600 = 1197. **Corrección coordinador (anti-saturación):** el subagente usó una global mutable `_conciliation_gaps`+`tail_conciliation_gaps()` muerta → la sustituí por `logger.warning` real del gap report-vs-almacén (en producción es observable) y ajusté tests (`caplog`) + `test_no_gap_cuando_live_qty_coincide`.
>
> **M-6 (T-M6) corregida y pusheada (`604bfef`)** `fix(py-application): margen real en _account_summary_from_portfolio (margin_used/free_margin/margin_level_pct) (R-7/M-6)`:
>
> - **T-M6:** `_account_summary_from_portfolio` fabricaba `margin_used=0.0`, `free_margin=cash`, `margin_level_pct=None` aunque el account tuviera leverage/posiciones. **Decisión usuario: fórmula `margin_used = Σ market_value / leverage`** + **alcance "completar"** (computar los 3 campos; DTO `AccountSummary`/endpoints intactos → sin `contract:gen`). Fix: `_account_summary_from_portfolio` computa `margin_used = Σ(mv de posiciones con precio)/leverage` (guard `leverage>0`, fail-closed→0.0), `free_margin = total_equity − margin_used`, `margin_level_pct = equity/margin_used*100` o `None` si 0. Fidelidad M-1: posiciones con `market_value=None` NO cuentan (coherentes con `total_market_value`/`total_equity`). Sin tocar FE (solo cambia el valor que ve `dashboard-page.tsx:163` "Margen libre"). Tests `test_account_summary_margin.py` (6, fakes en memoria: A sin posiciones / B single leverage / C dos posiciones leverage>1 / D sin precio no cuenta / D' mixto solo cuenta la con precio / E guard leverage==0 sin ZeroDivision); fake `_Account` de `test_list_account_summaries.py` ganó `leverage`.
>
> **SIGUIENTE ETAPA (por decisión 2026-08-20): FIN de R-7** — deuda de dinero real de R-7 **completa** (Alto×3 + Medio×7 + Baja **B-1** + Baja **B-3** cerradas). Quedan **Bajas**: **B-4** (fee atómico) · B-5 · B-2 (unrealized silencia sin precio) · **M-4/T-M4** (job dedicado, DIFERIDO por freeze). **Se decide NO pausar ahora:** cuando R-7 quede del todo cerrado → **guardar + auditorías externas**. **L-M3/M-5 CERRADA · M-1 · M-2 · M-3 · M-6 · M-4/T-M5 · M-7 · B-1 · B-3 TODAS CERRADAS.**
>
> **M-7 (L-M5) CERRADA (`f598e2d`):** el re-cobro de custodia (dedup time-only del mutex) **ya está cubierto por L-M3/M-5** (UNIQUE `(account_id, reference_type, reference_id, type)` rechaza con `IntegrityError` una 2ª fila del mismoaccount+periodo; la transacción compartida de `deduct_cash`+`append_custody_fee` revierte el cash en el `rollback` de `get_db_session`). Añadido test-postcondición `test_m7_custody_single_charge_f3_guard.py` (2, Postgres real). Sin cambios de producción. Ver §4i.
>
> **M-4/T-M5 (mezcla fees) CERRADA (`6a1759c`):** `total_fees_for_account` excluye `reference_type="custody"` → `fees_paid_total` deja de mezclar custodia con trade-fees. Opción B acotada (infra-only). **T-M4 (job dedicado) DIFERIDO** por freeze. Ver §4h + `test_m4_total_fees_excludes_custody.py`.
>
> **B-1 (T-M7) CERRADA (`4f43aeb`):** max drawdown naive → **high-water-mark** en `EquityMarkBook.update` (`account_drawdown.py`): se trackea el **pico de equity** (`peakEquity`) y el **drawdown más profundo desde el pico** (`maxDrawdownPct`, running-max), reseteado a 0 solo cuando `equity >= peak` (nuevo máximo). Corrige el **under-bloqueo tras recuperación** del gate `HardMaxDrawdown` (antes el drawdown se recalculaba vs depósito inicial, estateless, y colapsaba a ~0 al recuperarse). Gating preservado: sin `initial_deposit`/≤0 → `max_pct=None` (gate SKIPPED). Persistencia automática vía `equityMarks`. Shape DTO intacto. Tests `test_account_drawdown.py` (+4: recuperación parcial mantiene 10.0 / nuevo máximo resetea / pico sobrevive restart / sin baseline None). Batería: ruff 0 · mypy Success · app 245. Ver §4j.
>
> **B-3 (L-M4) CERRADA (`7cffaa7`):** write-paths de cash sin ledger → **`transfer_cash` ELIMINADO** (código muerto, 0 callers; decisión usuario "eliminar"). Era el único write-path que movía dinero **sin ledger Y sin caller**; al eliminarlo un futuro caller ya no puede existir → hazard dinero/verdad cerrado de raíz. `add_cash`/`deduct_cash` se conservan (vivos, trazados por Deposit/Withdraw/Custodia vía `append_cash_movement`/`append_custody_fee`); su escotilla residual queda documentada en el xfail M-2 reconvertido (`test_b3_deuda_directa_rompe_invariant_documental`, solo describe `add_cash`/`deduct_cash`). Intactos para una futura transferencia trazada: default `reference_type="transfer"` de `append_cash_movement` (`ledger_repository.py:276`) y tipo `'transfer'` del FE (`portfolio-cash.ts`). Batería: ruff 0 · mypy infra Success · infra real 76+1xfail · app money-path 32. Ver §4k.
>
> Detalle + inventario completo: `docs/engineering/traspaso-r7-dinero-application-infrastructure-2026-08-20.md` · ancla de trabajo vivo: `docs/engineering/backlog-trabajo-2026-08-20.md` (LEER PRIMERO) · estado vivo: `docs/engineering/PROJECT_STATE.md` · índice: `docs/engineering/engineering-index-2026-08-03.md` §5.

---

## 9. Nota de saturación / relevo de chat

Este traspaso está preparado para: (a) seguir aquí con la fase siguiente si el contexto del agente lo permite, o (b) **cerrar el chat y abrir uno nuevo** pegando el §8 si el coordinador percibe saturación. Regla: una fase = subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat.

---

### ✅ CHECKLIST DE RELEVO → FASE CERRADA: **B-1 (T-M7) — max drawdown high-water-mark en HardMaxDrawdown** — deuda Alta+Media+Baja parcial de R-7

**Estado al cerrar (verificado):** `main` limpio, sincronizado con `origin/main` · **CERRADAS: L-M3/M-5 (F3) · M-1 · M-2 · M-3 · M-6 · M-4/T-M5 · M-7 · B-1 · B-3** → **Alto×3 + Medio×7 + Baja B-1 + Baja B-3 de R-7 COMPLETADAS** · **T-M4 (job dedicado) DIFERIDO** por freeze · ancla `docs/engineering/backlog-trabajo-2026-08-20.md` §0 al día (LEER PRIMERO al abrir).

**B-1 cerrada (`4f43aeb`):** `EquityMarkBook.update` (`account_drawdown.py`) pasa de "max drawdown naive vs depósito inicial" (estateless, se recalcula cada snapshot) a **high-water-mark**: trackea el **pico de equity** (`peakEquity`, persistido en `equityMarks`) y el **drawdown más profundo desde el pico** (`maxDrawdownPct`, running-max), reseteado a 0 solo cuando `equity >= peak` (nuevo máximo). Corrige el **under-bloqueo tras recuperación** del gate `HardMaxDrawdown` — tras un gran descenso y recuperación parcial, el gate ya NO deja de bloquear (reporta el valor profundo, p.ej. 10.0, no el instantáneo 2.0). `max_pct` sigue `float | None` (shape DTO intacto; consumidores escritos). Gating preservado: sin `initial_deposit`/≤0 → `max_pct=None` (gate SKIPPED). Persistencia automática vía `export_settings_fragment`/`load_from_settings`. Tests `test_account_drawdown.py` (+4). Ver §4j.

**Próximas candidatas (deuda Baja, requieren decisión de usuario):**

- **B-1 (T-M7):** "max drawdown" naive → **✅ CERRADA** (`4f43aeb`, high-water-mark, ver §4j).
- **B-3 (L-M4):** write-paths de cash sin ledger → **✅ CERRADA** (`7cffaa7`, `transfer_cash` eliminado; ver §4k).
- **B-2 (T-M8):** `total_unrealized_gain` silencia a 0 las posiciones sin precio (_no confundir con M-1, ya cerrada_).
- **B-4 / B-5** (fee atómico / FIFO + PnL whole-account).
- **M-4/T-M4 (diferido):** mover custodia de GET a job dedicado — colinda con «sin features».

**Decisiones de alcance vigentes que NO reabrir sin pedir:** M-3 = puente (storage/`avg_cost` sigue fee-excluido); M-4/T-M5, M-6, M-7, B-1, B-3 CERRADAS; T-M4 (job dedicado) diferido por freeze; B-3 = eliminar `transfer_cash` (código muerto), no reabrir. Freeze: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4).

**Batería acumulada confirmada (referencia del relevo):** ruff 0 (config CI raíz `pyproject.toml`) · mypy infra/domain Success (application mypy-blind en CI) · pytest infra Postgres real **76+1xfail** · domain 21 · application **245** (241 + 4 B-1) · api-python 32.

---

## ✳️ ARRANQUE SIGUIENTE ETAPA: **FIN de R-7 — completar las Bajas restantes y luego GUARDAR + AUDITAR** (por decisión del usuario)

> **Cómo usar:** pega este bloque (o el §8 anterior) como primer mensaje del NUEVO chat. El coordinador del nuevo chat ejecuta la secuencia en orden, una fase = un subagente acotado + batería + aprobación por commit + relevo documentado. **DECISIÓN DE USUARIO (2026-08-20):** NO pausar todavía. **Objetivo: completar el FIN de R-7 (deuda Baja restante)** en chats secuenciales; **cuando R-7 quede del todo cerrado** → **guardar y mandar auditorías externas para ver el estado global**.
>
> **B-1 (T-M7) CERRADA** (`4f43aeb`, high-water-mark max drawdown — ver §4j). **B-3 (L-M4) CERRADA** (`7cffaa7`, `transfer_cash` muerto eliminado — ver §4k).

**Read-first (obligatorio):** leer `docs/engineering/backlog-trabajo-2026-08-20.md` §0 y §1. Si no coincide con el repo → PARAR y re-leer.

**Estado al abrir:** `local main = origin/main` (cierre B-3 `7cffaa7` + docs actualizados), árbol limpio. **CERRADAS: L-M3/M-5 (F3) · M-1 · M-2 · M-3 · M-6 · M-4/T-M5 · M-7 · B-1 · B-3.** Quedan **Bajas de R-7: B-4 · B-5 · B-2** (+ **M-4/T-M4 DIFERIDO** por freeze).

**Plan de trabajo de esta etapa (FIN R-7) — una fase por chat, en este orden sugerido (por riesgo dinero/verdad + saturación):**

1. ~~**B-3 (L-M4)**~~ — ✅ **CERRADA** (`7cffaa7`): `transfer_cash` muerto sin ledger ELIMINADO (decisión usuario "eliminar").
2. **B-4 (L-M6)** — fee ledger escrita en 2ª llamada no atómica con el trade (el UNIQUE de F3 NO toca `transaction`). Riesgo dinero. **[SIGUIENTE del FIN de R-7]**
3. **B-5 (T-M9/T-M10)** — FIFO divide sin guard `quantity==0`; `fetch_core_r_pnl_extra_rows` atribuye PnL whole-account a un instrumento (fail-open). Riesgo verdad.
4. **B-2 (T-M8)** — `total_unrealized_gain` silencia a 0 las posiciones sin precio (NO confundir con M-1, ya cerrada). Riesgo verdad.
5. Al terminar todos → **guardar + mandar auditorías externas del estado global** (revisar también el checklist operativo manual del §4 del backlog y la higiene de ramas `stage/*`).

**Cada fase (mismo protocolo):**

1. **Mapeo read-only** (subagente, sin tocar código): hallazgo file:line verificado + consumidores + si el fix rompe comportamiento esperado.
2. **Decisión de usuario:** alcance y si el cambio de valor esperado es aceptable.
3. **Subagente implementación acotado** + **verificación coordinador** (code diff + test + batería real) + **aprobación + commit + push** (rama `main` protegida; el push requiere aprobación vía tarjeta) + **relevo documentado** (actualizar backlog §0/§1/§6 y traspaso §4x/§5/§8).

**Decisiones de alcance vigentes que NO reabrir sin pedir:** M-3 = puente (storage/`avg_cost` sigue fee-excluido); M-4/T-M4 diferido por freeze (job dedicado); B-3 CERRADA = eliminar `transfer_cash` (código muerto, no reabrir); B-1 CERRADA (high-water-mark, no reabrir); M-6/M-7 CERRADAS. Freeze: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4). **No `regen_full`** sin decisión. **No `contract:gen`** salvo fase pactada.
