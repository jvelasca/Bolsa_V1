# Traspaso R-7 — Auditoría read-only de la lógica de dinero real en packages/py/{application,infrastructure} + corrección Fase 1 (idempotencia custodia/AUTO)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-7 — el mayor agujero de cobertura heredado de R-6: los use-cases/repos/invariantes contables quedaron FUERA del surface de la re-auditoría web+api+shared. Auditoría **read-only** de `packages/py/application` + `packages/py/infrastructure` (solo py) + corrección por fases acotadas.
> **Estado:** **EN CURSO.** Auditoría COMPLETADA (3 subagentes + verificación personal del coordinador). **Fase 1 COMMITEADA/PUSHEADA a `main`** (`c957df1`). **Fase 2 COMMITEADA/PUSHEADA a `main`** (idempotencia Deposit/Withdraw, A-2). **Fase 3 COMMITEADA/PUSHEADA a `main`** (`d7b8db8`, unique constraint parcial `ledger_entries` account/reference/type, L-M3/M-5). **M-1 COMMITEADA/PUSHEADA a `main`** (`a78eb29`, fallback mark-to-cost en `get_summary`, T-M1). **M-2 COMMITEADA/PUSHEADA a `main`** (`c8e9ced`, invariante reconciliación cash↔ledger, T-M2). **M-3 COMMITEADA/PUSHEADA a `main`** (`6962fd7`, puente cost-basis con fee en cara unrealized del tax-report, T-M3). Aguardan fases siguientes con decisión del usuario.
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
- **transfer_cash atómico** (ambos lados en lock, orden determinista por id, single flush). ✅ — NOTA: es **código muerto** (sin callers), ver L-M4.
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

## 5. Inventario de deuda NUEVA (de R-7; priorizado por riesgo dinero/verdad)

### 🔴 Alto

| Código | Superficie  | Hallazgo                                                                                                                                                                        | Estado                           |
| ------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| A-1    | application | Custodia aplicada como side-effect de GET (summary/tax) + doble cargo bajo concurrencia (dedup time-only, sin unique constraint en ledger)                                      | ✅ CORREGIDO (Fase 1, `c957df1`) |
| A-2    | application | Deposit/Withdraw **no idempotentes**: `movement_id = new_id()` fresco, sin `idempotency_key`; retry tras timeout mueve dinero 2×. `has_reference` existe pero es código muerto. | ✅ CORREGIDO (Fase 2, ver §4b)   |
| A-3    | application | Claim AUTO de idempotencia quemado si el fill falla → reintento suprimido en silencio                                                                                           | ✅ CORREGIDO (Fase 1, `c957df1`) |

### 🟠 Medio

| Código          | Superficie     | Hallazgo                                                                                                                                                                                                                                                 | Riesgo        |
| --------------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------ |
| M-1 (T-M1)      | infrastructure | `get_summary` omite de `total_market_value`/`total_equity` las posiciones sin precio D1, pero SUMA su `cost_basis` a `total_cost` → `total_unrealized_pnl` reporta pérdida = coste completo de posiciones sin precio; equity errónea sin reconciliación. | dinero/verdad | ✅ CORREGIDO (M-1, ver §4d)    |
| M-2 (T-M2)      | infrastructure | Cash NUNCA se reconcilia contra el ledger; identity `equity=cash+Σmv` es tautológica. No hay invariant que re-compute cash desde el ledger y compare.                                                                                                    | dinero/verdad | ✅ CORREGIDO (M-2, ver §4e)    |
| M-3 (T-M3)      | infra+domain   | Divergencia de cost-basis: el `avg_cost`/`cost_basis` de la posición EXCLUYE la fee de compra, pero el tax-report FIFO/avg la INCLUYE → unrealized (posiciones) y realized (tax) no concilian.                                                           | dinero/verdad | ✅ CORREGIDO (M-3, ver §4f)    |
| M-4 (T-M4/T-M5) | application    | `GetTaxReport`/`GetAccountSummary` hacen cargo de custodia en GET (mutan dinero en lectura) + `fees_paid_total` mezcla fees de trade con fees de custodia (dependiente de lectura).                                                                      | dinero        |
| M-5 (L-M3)      | infrastructure | Ledger SIN unique constraint en `(reference_type, reference_id)` → filas duplicadas posibles; `has_reference` muerto; raíz habilitadora de dobles concesiones.                                                                                           | dinero        | ✅ CORREGIDO (Fase 3, ver §4c) |
| M-6 (T-M6)      | application    | Campos de margen hardcoded en `_account_summary_from_portfolio` (`margin_used=0.0`, `free_margin=cash`, `margin_level_pct=None`) aunque haya leverage/posiciones.                                                                                        | dinero        |
| M-7 (L-M5)      | application    | Custodia dedup time-only (además del fix A-1); sin unique constraint la ventana concurr. aún la cubre el mutex, pero un restart/R-expiry en medio puede re-cobrar.                                                                                       | dinero        |

### 🟢 Bajo

| Código           | Superficie  | Hallazgo                                                                                                                                                                       | Riesgo        |
| ---------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- |
| B-1 (T-M7)       | application | "Max drawdown" naive (vs depósito inicial, no high-water-mark) alimenta el risk gate `HardMaxDrawdown` → under-bloqueo tras recuperación.                                      | verdad        |
| B-2 (T-M8)       | domain      | `total_unrealized_gain` suma `unrealized_gain or 0.0` → posiciones sin precio se silencian a 0 en el total.                                                                    | verdad        |
| B-3 (L-M4)       | infra+app   | `transfer_cash` atómico pero **código muerto** (0 callers) y **no escribe ledger**; un futuro caller movería dinero sin traza reconciliable.                                   | dinero/verdad |
| B-4 (L-M6)       | application | fee ledger escrita en 2ª llamada no atómica con el trade; app guard solo se activa si se pasa `idempotency_key` (nada lo exige).                                               | dinero        |
| B-5 (T-M9/T-M10) | application | FIFO divide sin guard `quantity==0` (latente, repo lo rechaza); `fetch_core_r_pnl_extra_rows` atribuye el PnL whole-account a un instrumento (fail-open, fallback a `list[]`). | verdad        |

### ⚠️ Hábitos (no-deuda, sin re-auditar)

- Mypy gate: CI corre mypy SOLO en `domain/market/infrastructure` (NO application ni apps/api-python) → **application mypy-blind en CI**. Notable gap: `accounts.py`/`execution_router.py` tienen `no-untyped-def` pre-existentes que CI no detecta.
- Los `# type: ignore` Mapped intencionales no son deuda.

---

## 6. Pendientes / fases futuras (no abrir sin decisión)

1. **M-6 (T-M6):** margin hardcoded → `None`/omitir en vez de fabricar `free_margin=cash`. **(PRÓXIMA candidata)**
2. **M-4 (T-M4/T-M5):** sacar el cargo de custodia del path de lectura (mover a un job dedicado) — cambio de comportamiento, requiere decisión (colinda con "sin features").
3. **B-1 (T-M7):** "max drawdown" naive en el risk gate `HardMaxDrawdown`.
4. **B-2 (T-M8):** `total_unrealized_gain` silencia a 0 las posiciones sin precio. _(NO confundir con M-1, ya cerrada.)_
5. **B-3 (L-M4):** `transfer_cash`/`add_cash`/`deduct_cash` del repo mutan cash SIN ledger (código muerto; xfail documental en M-2) — conectar use-case/ruta o eliminar; decidir.
6. **B-4 (L-M6):** fee ledger escrita en 2ª llamada no atómica con el trade (el UNIQUE de Fase 3 NO toca `transaction` → queda abierta).
7. **B-5 (T-M9/T-M10):** FIFO divide sin guard `quantity==0`; `fetch_core_r_pnl_extra_rows` atribuye el PnL whole-account a un instrumento.
8. Checklist operativo manual de relevos previos (secret scanning UI, `TRUSTED_PROXIES` prod, `BP/.L`→`BP.L`, logs dev).

**Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4). Una fase = un subagente acotado + batería + aprobación por commit + relevo al cerrar chat. **No hacer `regen_full`** sin decisión. **No `contract:gen`.**

---

## 7. Batería acumulada (verde al cerrar esta parte)

| Comprobación                                                                                                     | Resultado                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `ruff check packages/py apps/api-python --config pyproject.toml`                                                 | ✅ 0                                                                                                         |
| `mypy risk_runtime.py` + `mypy ledger_repository.py` (infra)                                                     | ✅ 0 / Success                                                                                               |
| pytest application money-path + F1 nuevos (8 ficheros)                                                           | ✅ 25 passed                                                                                                 |
| pytest application + F2 nuevos (`test_deposit_withdraw_idempotency`)                                             | ✅ 31 passed (25 + 6)                                                                                        |
| pytest api-python offline (CORS/Auth/Health/WinLoop/Q2Hygiene/RateLimit/StartupRoute)                            | ✅ 32 passed                                                                                                 |
| Árbol tras F1/tras F2/tras F3 (`local main = origin/main`) · pytest infra Postgres real 63 · idempotencia 11     | ✅ (`…c957df1` · a confirmar F2)                                                                             |
| M-1: `ruff` config CI raíz (2 files) · `mypy portfolio_repository.py` · infra real 66 · application 235          | ✅ 0 / Success / 66 / 235 (ver §4d)                                                                          |
| M-2: `ruff` config CI raíz (2 files) · `mypy ledger_repository.py` · infra real 72+1xfail · application 235      | ✅ 0 / Success / 72 / 235 (ver §4e)                                                                          |
| M-3: `ruff` config CI raíz (3 files) · `mypy tax_report.py` · domain 21 · infra real 72+1xfail · application 235 | ✅ 0 / Success / 21 / 72+1xfail / 235 (ver §4f; corrección global→log del coordinador)                       |
| CI `main` para `c957df1`                                                                                         | → ratificado; F2 a confirmar (Gitleaks/Frontend sin impacto por path-filter; Python CI no gatea application) |

## 8. Texto de traspaso (pegar al abrir el próximo chat / relevo por saturación)

> CONTEXTO (2026-08-20): **R-7 — auditoría read-only de la lógica de dinero real en `packages/py/{application,infrastructure}` COMPLETADA + Fases 1, 2, 3, M-1, M-2 y M-3 PUSHEADAS a `main`**. Mayor agujero de cobertura heredado de R-6 (use-cases/repos/invariantes contables quedaron fuera del surface web+api+shared).
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
> **SIGUIENTES (por decisión):** (1) **M-6 (T-M6)** (margin hardcoded → `None`), (2) M-4 (custodia fuera del path de lectura), B-3 (write-paths de cash sin ledger — xfail documentado), B-1/B-4/B-5. **L-M3/M-5 CERRADA · M-1 CERRADA · M-2 CERRADA · M-3 CERRADA.**
>
> Detalle + inventario completo: `docs/engineering/traspaso-r7-dinero-application-infrastructure-2026-08-20.md` · ancla de trabajo vivo: `docs/engineering/backlog-trabajo-2026-08-20.md` (LEER PRIMERO) · estado vivo: `docs/engineering/PROJECT_STATE.md` · índice: `docs/engineering/engineering-index-2026-08-03.md` §5.

---

## 9. Nota de saturación / relevo de chat

Este traspaso está preparado para: (a) seguir aquí con la Fase 2 si el contexto del agente lo permite, o (b) **cerrar el chat y abrir uno nuevo** pegando el §8 si el coordinador percibe saturación. Regla: una fase = subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat.
