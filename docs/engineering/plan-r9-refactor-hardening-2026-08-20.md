# PLAN PROFUNDO — Refactorización, corrección y mejoras R-9 (hardening financiero + limpieza + arquitectura)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product/Ops`) · **backlog:** `docs/engineering/backlog-trabajo-2026-08-20.md`.
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐ §0 (PREMISAS ESENCIALES ACTUALES **E1–E9**).
> **AsOf:** 2026-08-20.
> **Estado:** 📋 **PROPUESTA — SIN IMPLEMENTAR.** Ningún cambio se ejecuta sin **aprobación explícita del usuario** (§1.4). Es el **plan director**; cada fase se abre como subagente acotado bajo las premisas E1–E9.

---

## 1. Contexto y mandato

### 1.1 Qué se pide

El propietario ha encargado **un plan profundo de refactorización, corrección de errores y mejoras**, que se ejecutará **minimizando el riesgo al máximo y solo con su aprobación**. Requisitos explícitos:

1. Los cambios se hacen **lanzando subagentes** para que el agente actual no pierda contexto (premisa **E2**).
2. Controlar la **saturación** de chats/agentes; en los **relevos de chat** se genera un **documento + texto de paso** para que el siguiente chat arranque con los datos de finalización y **riesgo de alucinación ≈ 0** (premisas **E2/E3**).
3. Documentarlo todo en `/docs` y **DOCSTRINGS** (premisa **E5**).
4. Crear **TESTS/SCRIPTS** de verificación (premisa **E6**).
5. La app **no está en producción** → se puede refactorizar lo que sea preciso **manteniendo la idea del proyecto**.
6. **Limpiar** código y documentos obsoletos (premisa **E8**).
7. Documentar este mandato como **PREMISAS ESENCIALES ACTUALES** (hecho en `docs/PROJECT_PREMISES.md` ⭐ §0).

### 1.2 Veredicto de la auditoría interna (2026-08-20)

He auditado el tip `main` (`c06983d`, 1 commit tras `v1.1.0` = `e7b4655`) y **coincido con el auditor externo en los 4 hallazgos pendientes de la capa financiera**. Evidencia verificada en código (file:line):

| #   | Hallazgo                                                                        | Gravedad        | Evidencia verificada                                                                                                                                                                                                                                                                                                                       |
| --- | ------------------------------------------------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Idempotencia de depósitos/retiros **no aislada por cuenta** ni por payload      | 🔴 **P0**       | `ledger_repository.py:155-175` `find_cash_movement_by_reference()` filtra SOLO por `reference_type`+`reference_id` (NO `account_id`, NO `type`). `UNIQUE` es por-cuenta+type (`tables.py:1179-1190`) pero el lookup NO → **semántica UNIQUE ≠ lookup** (drift). Un 2º request que reutiliza `idempotency_key` en otra cuenta → no ingresa. |
| 2   | Cookie de sesión **stateless con `time.monotonic()`**                           | 🔴/🟠 **P0/P1** | `auth/session.py:35-37,67` usa `time.monotonic()` para `exp` → **deadline relativo al proceso/host**. No portable a multi-host/K8s; en proceso único funciona.                                                                                                                                                                             |
| 3   | Custody mutex se libera **antes del COMMIT** de la transacción DB               | 🟠 **P1**       | `application/accounts.py:528` `release_custody_charge()` antes del COMMIT del request (que ocurre en `get_db_session`). Ventana en la que un segundo GET podría no ver el cash descontado. DB-UNIQUE (`uq_ledger_entries_...`) blinda el doble cargo → el mutex es solo optimización.                                                      |
| 4   | La release afirma invariante **DB** `balance_after` que **no es un constraint** | 🟠 **P1**       | `tables.py:1172-1219` `LedgerEntryRow` solo tiene el UNIQUE parcial; **NO hay `CheckConstraint` ni trigger** sobre `balance_after`. El invariante vive en tests (`test_r8c_ledger_balance_atomic.py`), no en el esquema. Un CHECK plano no puede leer otra fila → garantía física requiere trigger/proc.                                   |

**Coincidencia con el auditor externo:** ✅ **4/4** de los hallazgos P0/P1 de la capa financiera están confirmados en el código actual. Los puntos "resueltos" de la auditoría previa (locking, workers, bootstrap advisory-lock, transferencias deterministic-lock, SAVEPOINT, OpenAPI/contract:check) también los he verificado y **coinciden como resueltos**.

### 1.3 Deuda adicional no cerrada (para inventario, no todo accionable)

- **R-8C.2** scheduler-vs-worker (no-ARQ comparte event-loop) — documentada, **no tocar salvo decisión**.
- **M-4/T-M4** job dedicado de custodia — **diferido por freeze**.
- **`pending-delete` riesgo alto** (`readLegacyPendingOrders`, `chartNewTabSeed`, etc.) — **NO tocar hasta `purge storage`**.
- **Legacy portfolio ↔ InvestmentAccount** puente `legacy_portfolio_id` — deuda estructural, planificar deprecación (V2).
- Arquitectura Python: **dependencias no declaradas** en `pyproject.toml` y ciclo `analytics ↔ market` reportados en la 1ª auditoría (verificar de nuevo; varias ya se movieron). **Verificar antes de declarar**, no asumir.
- Float→Decimal en borde HTTP (DTOs financieros usan `float`) — **mejora, no bloqueante**.
- Padding `margin_used` = margen **teórico interno**, no broker — documentar semántica.

### 1.4 Regla de oro del plan

> **NADA se implementa sin aprobación explícita del propietario por fase y por commit.**
> Este plan es el **documento director**. Las fases se abren de una en una, cada una con su subagente acotado, batería y texto de paso. Si el contexto se satura, se cierra el chat y se abre otro con el texto de paso de este plan + backlog.

---

## 2. Estrategia de ejecución (cómo se minimiza el riesgo)

### 2.1 Fases acotadas, una por subagente (NUNCA todo-en-uno)

Cada fase:

- Objetivo **único y medible** (criterio de aceptación explícito).
- Alcance **disjunto de ficheros** (manifiesto de archivos a tocar / NO tocar).
- Un **subagente acotado** con brief inyectado (contexto, archivos, batería, orden de escribir el resultado en backlog/traspaso).
- Verificación **del coordinador** (diff + batería real) antes de proponer commit.
- **Aprobación del usuario por commit**.
- Test/script de verificación incluidos en la fase.

### 2.2 Control de saturación / relevos (premisas E2/E3)

| Mecanismo          | Cómo                                                                                                                                   |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Límite paralelismo | Máx. ~3 subagentes en paralelo, alcances disjuntos.                                                                                    |
| Trigger de relevo  | Si el contexto se llena, **cerrar chat** y abrir otro pegando el **texto de paso** (este plan + backlog + bloque "estado verificado"). |
| Anti-alucinación   | Toda afirmación (file:line/commit/test) se contrasta contra código/datos reales. **Documento manda**.                                  |
| Firma de estado    | Cada texto de traspaso incluye HEAD, rama, árbol, CI.                                                                                  |

### 2.3 Orden de ejecución seguido por este plan

```
FASE 0  → documentar/verificar mandato + línea base inmutada (este doc)      [DONE: doc]
       ↓ aprobación usuario
FASE 1  → R-9.1 idempotencia aislada por cuenta (+ type)  [🔴 P0, dinero]
FASE 2  → R-9.2 request-fingerprint + 409                            [🔴 P0, dinero]
FASE 3  → R-9.3 custody commit-ordering (commit antes de release)    [🟠 P1, dinero]
FASE 4  → R-9.4 DTOs financieros estrictos (Pydantic)                [🟠 P1, dinero]
FASE 5  → R-9.5 sesión epoch (time.time) + opcional session_id/revoc. [🟠 P1, seguridad]
FASE 6  → R-9.6 invariante balance_after ⇒ trigger/proc DB (decidir)  [🟠 P1, verdad]
FASE 7  → Test-suite de concurrencia/invariantes (escenarios de ataque) [🟠, garantía]
FASE 8  → Limpieza código/doc obsoletos + docstrings + deuda menor    [🟡, higiene]
FASE 9  → (opcional/V2) desacoplar analytics↔market + puente legacy    [🟡, arquitectura]
```

### 2.4 Batería obligatoria por fase (la re-verifica el coordinador)

- **Backend:** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de ficheros en gate CI · pytest de la zona (app money-path / infra real si toca DB) · `git status` acotado.
- **Frontend (si toca contrato/API):** `pnpm --filter @bolsa/web typecheck|lint|build` · `contract:check` (en Windows: `$env:PYTHONIOENCODING='utf-8'` antes) si cambia schema.
- **DB (si toca migración):** migración desde **DB limpia** y desde **DB existente** (subir/downgrade), idempotencia de `database_bootstrap`, arranque con 2+ workers.
- **Escenarios de concurrencia (FASE 7):** 100 POST simultáneos · misma key / distintas keys · deposit+withdraw · BUY+SELL · custody+trade · rollback a medias · Redis caído · PG restart · 2 API workers · API+scheduler.

---

## 3. Detalle por fase (correcciones)

### 🔴 FASE 1 — R-9.1: Idempotencia de dinero aislada por cuenta y por `type`

**Problema:** `find_cash_movement_by_reference()` (`ledger_repository.py:155-175`) filtra SOLO por `reference_type`+`reference_id` (agarra el movimiento más antiguo) → una `idempotency_key` de la cuenta A puede "absorber" a la misma key en la cuenta B (repo A:310/336; B:382/416). Además, depósito y retiro comparten `reference_type="external"` pero difieren en `type` → hoy la consulta global tampoco distingue deposit vs withdrawal.

**Decisión F1 (2026-08-20, aprobada): ✅ OPCIÓN A** — **NO se toca el UNIQUE** (`uq_ledger_entries_account_reference` ya es por-cuenta+`type`, migración 004). Se **alinea el lookup con el UNIQUE** añadiendo `account_id` y `type` al filtro de `find_cash_movement_by_reference`:

- Firma: añadir parámetros keyword-only `account_id: str` y `type: str`.
- Filtro: `WHERE account_id = :aid AND reference_type = :rt AND reference_id = :rid AND type = :t`.
- Callers en `accounts.py`: depósito (`type="deposit"`) en `:305/:335`; retiro (`type="withdrawal"`) en `:382/:416`, pasando `account_id=scope.account.id`.
- Fake de test `_FakeLedgerRepo.find_cash_movement_by_reference` (`test_deposit_withdraw_idempotency.py:82`) actualizado a la nueva firma.
- **Riesgo trade+fee:** nulo (ese código usa `reference_type="transaction"` y no llama a este método).
- **Sin migración** (el UNIQUE ya es por-cuenta+type; solo se corrige la semántica del guard).

**Criterio de aceptación:**

- Test nuevo: 2 cuentas reutilizan la MISMA `idempotency_key` → cada cuenta ingresa su importe (arregla P0 cross-cuenta).
- Test nuevo: misma cuenta + misma `key` pero `type` distinto (deposit vs withdrawal) → dos movimientos separados (arregla ambigüedad cross-type).
- Batería: ruff 0 · mypy (ledger_repo + accounts + test) 0 · pytest app money-path (incl. `test_deposit_withdraw_idempotency.py`) · `git status` acotado a infra+application+tests.

---

### 🔴 FASE 2 — R-9.2: Request-fingerprint + 409 `IDEMPOTENCY_KEY_REUSED`

**Problema:** misma `idempotency_key` con **payload distinto** hoy rejuega el original en silencio (semántica laxa). Confirmado en los 3 write-paths activos:

- **Deposit/Withdraw** (`accounts.py` `DepositCashToAccount`/`WithdrawCashFromAccount`): si el guard `find_cash_movement_by_reference` encuentra el movimiento, lo rejuega sin comparar el `amount` entrante. `deposit key=ABC amt=1000` + `deposit key=ABC amt=5` → devuelve el de 1000€.
- **Trade** (`ExecuteTrade` `accounts.py:620`): `find_transaction_by_idempotency` rejuega sin comparar instrument/type/qty/price.
- **No hay use-case de transferencia activo** (transf_cash eliminado en R-7 B-3); solo 3 write-paths.

**Decisión F2 (2026-08-20, coordinador): ✅ OPCIÓN B — SIN migración.** No añadir columna `request_hash`/tabla `idempotency`. En el replay (guard previo y en el `except IdempotencyKeyExists`), **comparar el payload entrante contra los campos financieros YA persistidos**:

- Deposit/Withdraw: cotejar `amount` (y `note`→`description`) del request vs `existing.amount`/`existing.description`.
- Trade: cotejar `instrument_id`, `trade_type`, `quantity`, `price` vs `existing`.
- Si coinciden → re-devolver original (idempotente 200 con la misma shape). Si difieren → **nuevo error de dominio `IdempotencyKeyReused`** que la capa de rutas mapea a **HTTP 409**.
- Reducción de superficie vs opción A (columna+hash): **sin migración Alembic, sin columna nueva**, solo dominio + use-case + mapeo de ruta. Menor riesgo, aborda directamente la ambigüedad financiera del hallazgo.
- ⚠️ Es un cambio de **contrato HTTP** (nueva semántica de respuesta 409) → la fase debe incluir mapeo de ruta, y si toca `web`/`openapi`, `contract:check` + regen acotada de `openapi.json`/`schema.d.ts` como fase propia (premisa E1/E5). Se evaluará si el 409 necesita exponerse en la API pública o si basta un código de error interno; decisión en fase.

**Criterio de aceptación:** tests de mismo-key-mismo-payload (OK, devuelve original), mismo-key-distinto-payload (409 `IDEMPOTENCY_KEY_REUSED`), en deposit, withdraw y trade; sin migración nueva; battery verde; `contract:check` donde aplique.

**Estado (2026-08-20, IMPLEMENTADO):** dominio `IdempotencyKeyReused` + comparación de payload en los 3 write-paths + exception handler app-wide en `main.py`→409 · tests app (8) + API integr (3) · ruff 0 · mypy sin errores nuevos. **Contrato:** los 3 endpoints NO declaran `responses={409}`, así que el 409 no figura aún en OpenAPI (cambio semántico de contrato). Pendiente decisión separada (premisa E1/E5) si exponer el 409 en OpenAPI/`schema.d.ts` + `contract:check`; no se ejecutó `contract:gen` en esta fase.

---

### 🟠 FASE 3 — R-9.3: Custody commit-ordering / manejo de la carrera de custodia

**Read-first (verificado 2026-08-20):** en `ApplyCustodyFees.execute` (`accounts.py:552-648`), `release_custody_charge` ocurre en `:599/:610/:644/:647`, **antes** del COMMIT del request (que ocurre en la capa de dependencia API). `append_custody_fee` (`ledger_repository.py:201`) inserta `type="fee"`, `reference_type="custody"`, `reference_id="custody-YYYY"`. La protección física contra doble cargo es el **UNIQUE DB** `(account_id, custody, custody-YYYY, fee)` (migración 004). El mutex Redis (SET NX, `risk_runtime.claim_custody_charge`) es optimización, NO autoridad.

> **Intuición clave:** el doble cargo YA está bloqueado por el UNIQUE. El fallo real es que, en una carrera de 2 GET concurrentes que liberan el claim antes del commit, el 2º request acaba en **`IntegrityError` no manejado → 500 en una lectura**, en vez de una respuesta limpia.

**Decisión F3 (2026-08-20, coordinador): ✅ OPCIÓN A REFINADA — tratar la carrera como idempotente (no 500).** Sin mover el commit a otro sitio (sería un cambio arquitectónico grande). En `ApplyCustodyFees.execute`:

1. Envolver la mutación DB de custodia (`deduct_cash` + `append_custody_fee`) en `_idempotent_savepoint` (helper ya existente) para poder revertir solo el intento del perdedor sin descartar la transacción de la request.
2. Capturar el `IntegrityError` (usando `is_unique_violation`, helper ya en `db_errors.py`) de la colisión UNIQUE de custodia → **devolver `False`** (ya se cobró este periodo), en vez de propagar 500.
3. Mantener la liberación del mutex tal cual (es optimización); la corrección no depende del orden release/commit porque, si se pierde el claim, el UNIQUE+savepoint+catch re-validan.

- **Criterio:** NUNCA doble cargo (ya garantizado por UNIQUE) y **nunca 500 en carrera**; el 2º GET devuelve la misma lectura con custodia ya aplicada.

**Criterio de aceptación:** test de 2 custody concurrentes simulando la carrera (2º `append_custody_fee` choca con UNIQUE) → devuelve `False`/semántica idempotente sin 500; el 1º cobra; sin doble cargo; release siempre ocurre (except paths intactos). Battery verde.

**Estado (2026-08-20, IMPLEMENTADO):** `ApplyCustodyFees.execute` envuelve la mutación (`deduct_cash`+`append_custody_fee`+`touch_activity`) en `_idempotent_savepoint`; `except IntegrityError` → `is_unique_violation` → `release` + `return False` (idempotente, nunca 500); early-exits y `except Exception` intactos. Tests: 2 nuevos en `application/tests/test_custody_idempotency.py`. Battery: ruff 0 · mypy sin errores nuevos (7 preexistentes fuera de región F3) · pytest application 261 + infra custody Postgres 4. Sin migración/DTO/web/contrato.

---

### 🟠 FASE 4 — R-9.4: DTOs financieros estrictos (Pydantic)

**Read-first (verificado 2026-08-20):** en `apps/api-python/src/bolsa_api/schemas/accounts.py`, `CreateInvestmentAccountDto` (`:134`) expone `initial_deposit: float` (`:141`), `leverage: float` (`:142`), `margin_call_level_pct: float|None` (`:143`); `CommissionProfileDto` (`:8`) expone `stock_commission_pct/min/max`, `vat_on_commission_pct`, `fx_conversion_pct`, `custody_annual_pct` — todos `float` sin restricción ni `allow_inf_nan=False`. **Confirmado:** ninguna capa valida estos invariantes (ni el DTO, ni `CreateSimulatedAccount.execute` en `application/accounts.py:68-97` que solo reenvía, ni `settings_from_dict`, ni la entidad/repo). El consumo fluye: `routes/accounts.py:79-96` → `CreateSimulatedAccount` → `account_repo.create_simulated_account`.

**Decisión F4 (2026-08-20, coordinador): ✅ DTO-LEVEL Pydantic validation (fail-fast 422 en el borde API), acotada al plan.** Sin cambios en domain/application/entidad/repo, sin migración. El refactor a `Decimal` hasta el borde se pospone (fuera del alcance de esta fase; cambio más amplio). Aplicar:

- `CreateInvestmentAccountDto`: `initial_deposit >= 0`, `leverage > 0`, `margin_call_level_pct >= 0` (si no None); `allow_inf_nan=False`.
- `CommissionProfileDto`: `stock_commission_pct >= 0`, `stock_commission_min >= 0`, `stock_commission_max >= 0` (si no None y `>= stock_commission_min`), `vat_on_commission_pct >= 0`, `fx_conversion_pct >= 0`, `custody_annual_pct >= 0` (si no None); `allow_inf_nan=False`.
- Otros DTOs con campos financieros en `schemas/accounts.py`: aplicar la misma disciplina SOLO a los que estén en el alcance directo de este fichero; NO ampliar a otros DTOs del proyecto (dejar a F8). Mantener `populate_by_name`/alias tal cual para no romper el wire.
- Cuidado: no romper los `model_config` existentes (hay `# type: ignore[typeddict-unknown-key]` en `CommissionProfileDto`/`AccountSettingsDto`/`InvestmentAccountDto` que debe conservarse).

**Criterio de aceptación:** tests de DTOs con valores absurdos (negativos, `leverage=0`, `NaN`, `inf`) → `ValidationError`; valores límite válidos (`initial_deposit=0`, `leverage>0`, tasas=0) siguen pasando; sin romper el wire (alias/`populate_by_name`) ni la suite (wizard, presets). Batería verde.

**Estado (2026-08-20, IMPLEMENTADO):** `CommissionProfileDto` + `CreateInvestmentAccountDto` con `ge=0`/`gt=0` + `allow_inf_nan=False` (patrón `Field` como `DepositCashDto`/`WithdrawCashDto`) y `model_validator(mode="after")` (patrón `instrument_strategy_tops`) para `stock_commission_max >= stock_commission_min`. Alias/`populate_by_name`/defaults intactos → sin cambio de wire. Tests: `apps/api-python/tests/test_schemas_accounts.py` (21). Battery: ruff 0 · mypy 0 (schemas+tests) · pytest 21 nuevos + 33 offline API + 5 `test_accounts` intégr (DB). Sin migración ni cambios domain/application/entidad/repo.

---

### 🟠 FASE 5 — R-9.5: Sesión con epoch en vez de `monotonic()` (+ revocación opcional)

**Problema:** `session.py` usa `time.monotonic()` → no portable multi-host.

**Corrección propuesta:**

- Cambiar `exp` a **Unix epoch UTC** (`time.time()`), mantener HMAC y `Secure`/`SameSite`/TTL.
- **Opcional (decisión §5.2):** si se quiere revocación real (logout que invalida sesión copiada), introducir `session_id` + store Redis con TTL y `session_version` por usuario. Para app personal local, el cambio a epoch es suficiente y de menor riesgo.

**Criterio de aceptación:** login→cookie válida TTL; logout borra cookie; con epoch la cookie es portable; tests auth existentes (10) verdes.

**Decisión de alcance (2026-08-20, aprobada por el usuario): ✅ OPCIÓN A — solo epoch.** `session.py`: `time.monotonic()` → `time.time()` (epoch UTC) en `session_deadline` y en la comparación de `verify_session_cookie`; actualizar el docstring del módulo que explica el deadline monotónico. NO se toca `session_id`/revocación Redis (mayor alcance, no recomendada para app local). Adaptar los tests de `test_auth.py` que dependen de `time.monotonic()` (`test_expired_session_cookie_rejected` lo parchea en `:138-144`) al nuevo reloj, y añadir un test de expiración/portabilidad con epoch que no dependa de un timer concreto.

**Estado (2026-08-20, IMPLEMENTADO):** `session.py` pasa `time.monotonic()` → `time.time()` (epoch UTC) en `session_deadline` y en `verify_session_cookie`, y el docstring del módulo explica el deadline epoch portable. `test_auth.py`: `test_expired_session_cookie_rejected` adaptado a `time.time()` (epoch congelado + avance del reloj) y añadido `test_session_epoch_portability_and_expiry` (portabilidad/expiración con epoch congelado, sin depender de timer monotónico). Decisión usuario: **opción A** (solo epoch, sin revocación Redis). Battery: ruff 0 · mypy `session.py` (gate CI) Success 0 · pytest `test_auth.py` 11 passed (10+1). Sin migración/contrato/web. Commit `ef4c136` pusheado a `main`.

---

### 🟠 FASE 6 — R-9.6: Invariante `balance_after` como garantía física (decidir)

**Problema:** el invariante solo está en tests; la release lo afirma como "DB". Un CHECK no puede leer otra fila.

**Corrección propuesta (elegir §5.2):**

- **Opción A (recomendada, cierra el claim):** **trigger/procedure** PostgreSQL que, en `INSERT/UPDATE` de `ledger_entries` y por `account_id` en orden `(executed_at, id)`, valide `balance_after == prev_balance + Σ amount`; NEGATIVO si no cumple. Pipeline de migración Alembic + test de carga en infra real.
- **Opción B (mantener en app, corregir el claim de la release/docs):** mantener el invariante como **verificación por grupo atómico** (tests `test_r8c_*`) y **corregir la documentación** (release/README) para que NO afirme constraint DB cuando es postcondición de app. Menor riesgo, menor garantía.

**Criterio de aceptación (opción A):** INSERT corrupto → rechazado por DB; migración desde BD limpia y existente OK; tests de invariante en infra real verdes.

**Decisión de alcance (2026-08-20, aprobada por el usuario): ✅ OPCIÓN B — postcondición app + corregir docs.** Verificado en código (`tables.py:1172-1219`): `LedgerEntryRow` solo tiene el UNIQUE parcial `uq_ledger_entries_account_reference`; **NO hay `CheckConstraint` ni trigger** sobre `balance_after` (grep 0 en código). El invariante vive SOLO en tests (`test_r8c_ledger_balance_atomic.py`). Se corrige la documentación que afirma "invariante DB `balance_after`" (que NO es un constraint) para que diga la verdad: **postcondición de app verificada por grupo atómico en el test-suite**, no garantía física de la BD. NO se añade trigger ni migración (menor riesgo; la garantía física se descarta por decisión).

**Estado (2026-08-20, IMPLEMENTADO):** decisión usuario **opción B** (postcondición app + corregir docs, sin trigger/migración). Corregidas las afirmaciones "invariante DB `balance_after`" en `PROJECT_STATE.md` (R-8C) y `audit-pack-estado-global-2026-08-20.md` (mensaje clave + fila R-8C) para reflejar la verdad: el invariante es una **postcondición de app verificada por grupo atómico en `test_r8c_ledger_balance_atomic.py`**, NO un constraint/trigger DB. Registrada la decisión de alcance en la FASE 6 y en §5.2. Docs-only (0 código, 0 migración). Commit `e5d8926` pusheado a `main`.

---

### 🟠 FASE 7 — Suite de concurrencia e invariantes (escenarios de ataque)

**Problema:** no hay batería sistemática de concurrencia/rollback/idempotencia.

**Corrección propuesta (tests/scripts nuevos):**

- `test_concurrency_*.py` en infra real con escenarios del §2.4.
- Scripts de verificación: `scripts/verify/` con checks de invariantes y de aislamiento entre cuentas (A/B).
- Test de seguridad: `request(account=A, portfolio=B)` ⇒ 403/404 y NO muta B.
- Regression: `database_bootstrap` idempotente con 2 workers; migración limpia y existente.

**Criterio de aceptación:** todos verdes en CI; documentar resultados.

**Diseño de alcance (2026-08-20, coordinador — no requiere decisión de usuario; solo reúso lo existente):**

- **Reutiliza, NO duplica** (mapa de tests existentes verificado): `test_financial_invariants.py` ya cubre `test_concurrent_buys_no_double_spend` (anti-doble-gasto con `asyncio.gather`+`with_for_update`) y `test_round_trip_balance_coherent`; `test_r8a_idempotency_backstop.py` cubre el backstop concurrente a repository (trade key + cash movement key) contra PG real; `test_r8c_ledger_balance_atomic.py` cubre el invariante `balance_after` por grupo atómico; `test_r8c_ledger_balance_atomic` + `test_ledger_entries_reference_unique` cubren UNIQUE. La suite F7 debe **añadir lo que falta**, no repetir.
- **Nuevos ficheros a crear** dentro del alcance:
  1. `packages/py/infrastructure/tests/test_concurrency_scenarios.py` — escenarios de ataque en PG real (patrón `db_session` de `test_r8a_idempotency_backstop.py`): mismos-key-distintas-cuentas (aislamiento A/B), deposit+withdraw racing en la misma cuenta, BUY+SELL racing sobre la misma posición, custody+trade racing (reusa `ApplyCustodyFees`), y verificación de que el perdedor de cada carrera NO deja estado inconsistente (cash/ledger). Nada de sleep/`time.sleep` salvo esperas pequeñas; usar transacciones/tasks `asyncio` con `with_for_update` o el UNIQUE como autoridad.
  2. `scripts/verify/` — directorio nuevo con un script de verificación de invariantes y aislamiento entre cuentas (prefijo `verify_*.py`, invocable con `uv run`): `verify_ledger_balance_chain.py` (recorre `ledger_entries` por cuenta en orden `executed_at` y comprueba `balance_after[n] == prev + amount[n]`) y `verify_account_isolation.py` (comprueba que una `idempotency_key`/`reference_id` usada en la cuenta A no se "absorbe" en la cuenta B). Exit 0 si OK, mensaje claro si no.
  3. Test de seguridad (aislamiento por cuenta a nivel request) SOLO si existe un helper claro en la app infra existente; si no, documentarlo como pendiente (no inventar un stack de integración nuevo en esta fase).
- **¿Regression de `database_bootstrap` con 2 workers?** Requiere levantar N procesos → se excluye del alcance del subagente (entorno); se documenta como verificación manual/CI pendiente. No añadir.
- **Sin cambios de código de producción, sin migración, sin contrato, sin web.**

**Estado (2026-08-20, IMPLEMENTADO):** creados `packages/py/infrastructure/tests/test_concurrency_scenarios.py` (4 tests en PG real: aislamiento A/B misma key, deposit+withdraw racing, buy+sell racing, custody+trade racing, sin doble cargo) y `scripts/verify/verify_ledger_balance_chain.py` + `verify_account_isolation.py` (invariante `balance_after` por grupo atómico y aislamiento por cuenta, exit 0/1). Battery (verificada por el coordinador): ruff 0 en los 3 ficheros · mypy 0 en los 3 · pytest `test_concurrency_scenarios.py` 4 passed con PG real (no skipped) · ambos verify scripts EXIT 0 con PG real. `scripts/research` ruff noise preexistente (no tocado). Sin cambio de producción/migración/contrato. Commit `5d59671` pusheado a `main`.

---

### 🟡 FASE 8 — Limpieza de código/doc obsoletos + DOCSTRINGS + deuda menor

**Alcance (criterio E8):** eliminar/archivar código y documentos que ya no reflejan la realidad (p. ej. deuda "Alembic baseline pendiente" ya resuelta, helpers muertos), **solo** si 0 imports y no dependen de storage por nombre. Revisar `pending-delete/README.md` (riesgo alto: solo nominal, no ejecutar). Rellenar docstrings de símbolos públicos tocados. Depurar documentación que diverge del código (README vs realidad, §1.3).

**Criterio de aceptación:** battery/typecheck verdes tras limpiar; `git status` acotado; docs actualizadas sin perder evidencia.

**Inventario del coordinador (2026-08-20, verificado file:line):** read-first acotado con 3 subagentes `explore` de alcances disjuntos (Python / web / shared), cada hallazgo recontrastado por el coordinador con `rg` antes de listarse. Decisión §5.2 F8 (pending-delete riesgo alto = **solo inventariar, NO ejecutar**) ya tomada y respetada: ninguno de los ítems pending-delete de riesgo alto se propone para borrar. Verificado además que la deuda "Alembic baseline pendiente" **ya no es deuda viva** (retirada de `PROJECT_STATE.md` y del README real; ADR-025 la mantiene solo como hito FUTURO diferido y deliberado → **NO se toca**, no es docs obsoleta). Lo siguiente es el inventario "LIMPIO para borrar" (0 imports / sin storage por nombre) y "DUDOSO" (decisión usuario).

**A. Backend Python — LIMPIO para borrar (0 usos / sin storage):**
| path:line | símbolo | tipo | evidencia | reemplazo |
| --- | --- | --- | --- | --- |
| `application/sync_scheduler.py:69` | `SYNC_SCOPE_STALE` | constante muerta | rg → 1 hit (def) | — |
| `application/sync_scheduler.py:70` | `SYNC_SCOPE_ALL` | alias muerto | rg → 1 hit (def) | — |
| `application/daily_opinion_stance.py:50` | `_clamp_stars` | helper privado muerto | rg → 1 hit (def) | `map_io_to_stars` |
| `application/tracker_schedule.py:28` | `is_scheduled_tracker` | helper público muerto | rg → 1 hit (def) | `schedule_kind(...)` inline |
| `application/investor_profiles.py:103` | `GetAccountInvestorProfile` | use-case muerto | rg → 1 hit (def); API llama `store.get_for_account` directo | `store.get_for_account` |
| `schemas/instrument_lifecycle.py:76` | `DeleteInstrumentRequestDto` | DTO Pydantic muerto | rg → 1 hit (def); no en OpenAPI/routes | — |
| `schemas/workspaces.py:17` | `WorkspacePayloadDto` | DTO Pydantic muerto | rg → 1 hit (def); no en OpenAPI/routes | `CreateWorkspaceRequestDto` |
| `auth/session.py:6` | "(monotónico, ver abajo)" | docstring obsoleto (residuo F5) | contradice `session.py:12-17` (epoch UTC) | eliminar paréntesis |

**B. Web — limpios confirmados y clusteres muertos:**

- Módulos/componentes huérfanos (0 importadores, no ruta/barrel/drilldown): `charts/chart-overlay-indicators-zone.tsx`, `charts/indicator-templates-dialog.tsx`, `charts/rsi-indicator-chart.tsx`, `backtests/backtest-result-tabs.tsx`, `components/ui/info-tip.tsx`.
- Barrels re-export huérfanos: `trading/lists-tab/lists-tab.tsx` (`WatchlistPanel` se importa directo desde `watchlist-panel.tsx`), `trading/trading-coach-rail.tsx`.
- Cluster muerto `trading/lists-tab/list-membership-dialog.tsx` + slice `trading-ui-store.ts` (`listMembershipInstrument`/`open/closeListMembershipDialog`): dialog sin renderers (rg 0), slice solo consumido por el dialog, no persistido.
- Slice muerto `stores/ui-store.ts` (`indicatorTemplatesOpen`/`open/closeIndicatorTemplates`): solo consumido por el dialog huérfano `indicator-templates-dialog.tsx`; no persistido.
- Alias `@deprecated` muertos (0 imports): `charts/indicator-compute.ts:1554` `resolveSubLineSeries`; `charts/chart-drawing-tools.ts:654/661` `ExtraFavoriteRailBlock`/`extraFavoriteRailBlocks`; `lib/chart-list-membership.ts:126` `resolveVirtualListForInstrument`; `backtests/dia-d-favorites.ts:281-282` `DIA_D_QUICK_PRESETS`/`DiaDQuickPresetId`; `trading/trading-dia-d-banner.tsx:23` `TradingDiaDBanner`; `trading/trading-operativa-panel.tsx:575-576` `TradingCoachRail` (alias).
- `instruments/instruments-hub-model.ts:266/288` `onlyInPortfolio` (alias `@deprecated`): 0 uso salvo su propio def + test `instruments-hub-model.test.ts:137` que solo valida el alias → **requiere actualizar ese test** a `scopeFilter` antes de borrar.

**C. Shared — limpios confirmados y dudosos:**

- `package shape` (verificado): `@bolsa/shared` solo expone el root `.`/`dist/index.js` (no deep-path), y `rg` = 0 imports relativos `shared/src/...` → un símbolo solo es alcanzable vía barrel; ser re-exportado en barrel no es uso.
- LIMPIO: `indicator-templates.ts:91` `isIndicatorApiSupportedLegacy` (`@deprecated`, 0 refs) → `isIndicatorApiSupported` (`indicators-runtime.ts:117`). `default-lists.ts:97` `resolveEstudioPersonalListId` (`@deprecated` ADR-024, solo 2 tests que validan alias) → `resolveEstudioListId`. (Requiere actualizar esos 2 tests.)
- **C-DUDOSO resuelto (decisión usuario 2026-08-20: ✅ BORRAR):** `chart-new-tab-setup.ts:26/29/35` `DEFAULT_NEW_CHART_CONFIG_SOURCE` / `NEW_CHART_CONFIG_SOURCE_LABELS` / `normalizeNewChartConfigSource` — 0 refs y sin storage; cumplen E8 por sí solos. **DECISIÓN: BORRAR.** El tipo `NewChartConfigSource` y el campo `workspace.newChartConfigSource` (pending-delete RIESGO ALTO, migración workspaces) **se mantienen** (el tipo lo importa `chart-defaults.ts:21/244`).

**D. DUDOSO backend (decisión usuario 2026-08-20: ✅ BORRAR):**

- `packages/py/analytics/src/bolsa_analytics/prediction/ports.py` — módulo `IPredictionPort` sin importador y no exportado en `prediction/__init__`; **DECISIÓN: BORRAR** (cumple E8: 0 imports; solo ancla de diseño ya no usada).

**E. Excluidos (no tocar):** `pending-delete` riesgo alto (`readLegacyPendingOrders`, `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource`, `readLegacyTimeframeFavorites`, re-export `presetRuleGroups`) · gobernanza IA (`packages/py/ai/adapters/base.py` no observado como candidate por freeze) · workers/scheduler (R-8C.2) · wire/persistencia shared (`chartPanel`, `prediction`, `chart-list-context`, `strategy-definitions`, `IndicatorTemplate.items`, knobs `chart-toolbar`) · `NewChartConfigSource` tipo + `newChartConfigSource` campo (pending-delete). Fila `session.py:12-17` (parte correcta del docstring) se conserva.

**Plan de ejecución (tras aprobación):** 1 commit de inventario + 3 subagentes de limpieza con alcances disjuntos (Python / web / shared) que apliquen los LIMPIO aprobados, cada uno con su batería; el coordinador re-verifica diffs + batería real antes de proponer commits de aprobación por usuario.

**Estado (2026-08-20, IMPLEMENTADO):** aplicado y pusheado a `main`. Inventario del coordinador (`8cd39ad`) + limpieza en un commit (`5ea336f`). Backend: `SYNC_SCOPE_STALE`/`SYNC_SCOPE_ALL` (sync_scheduler), `_clamp_stars` (daily_opinion_stance), `is_scheduled_tracker` (tracker_schedule), `GetAccountInvestorProfile` (investor_profiles) y DTOs `DeleteInstrumentRequestDto`/`WorkspacePayloadDto` borrados; `prediction/ports.py` eliminado; docstring `session.py` sin el residuo "(monotónico)". Web: 5 componentes/módulos huérfanos + 2 barrels + cluster `list-membership-dialog` + slices `trading-ui-store`/`ui-store` + 7 aliases `@deprecated` + `onlyInPortfolio` (test→`scopeFilter`) borrados. Shared: `isIndicatorApiSupportedLegacy` (+ const privada), `resolveEstudioPersonalListId`, y los 3 helpers muertos de `chart-new-tab-setup.ts` borrados (se conserva el tipo `NewChartConfigSource` y el campo pending-delete `newChartConfigSource`). Batería del coordinador (post-hook): ruff 0 · mypy solo 2 preexistentes · pytest application/analytics 25 + api-python 91 · shared typecheck/lint/test 17/17 + build · web typecheck/lint/test 713/713. `pending-delete` riesgo alto intacto. Commit `5ea336f` pusheado a `main`.

---

### 🟡 FASE 9 — (Opcional / alinear con V2) Arquitectura Python + puente legacy

**Alcance (más amplio, requiere ADR):**

- Re-verificar dependencias `analytics ↔ market` y **declarar** en `pyproject.toml` lo realmente usado (tras auditoría read-only; no se asume).
- Definir direcciones unívocas (`domain ↑ analytics ↑ application ↑ infrastructure ↑ api`) y los tipos compartidos a `domain`.
- Plan de deprecación del puente `legacy_portfolio_id`.

**Criterio de aceptación:** `import-linter` verde; dependencias declaradas; sin ciclo analytics↔market.

**Estado (2026-08-24):** **F9-A CERRADA** (A1 tests `703991e` · A2 contrato `a1e1681` · A3 CI lint-imports). **F9-B** (`legacy_portfolio_id`) **PARKED** — no abrir sin ADR (ADR-030). Plan acotado: `plan-r9-f9-analytics-market-2026-08-24.md`.

---

## 4. Documentación, DOCSTRINGS y tests (obligatorios por fase)

Como manda la premisa E5/E6, **cada fase entrega**:

1. **Docstring** de módulo + símbolos públicos creados/tocados (norma `code-documentation-standard`).
2. **Test o script** de verificación que demuestre la corrección (no basta "compila").
3. **Actualización** de `backlog-trabajo-2026-08-20.md` (update-last) y `PROJECT_STATE.md`.
4. Si cambia contrato HTTP: schemas + **regen de `openapi.json`/`schema.d.ts`** + `contract:check` verde (fase propia, no colateral).

---

## 5. Decisiones que necesitan aprobación del usuario

> Antes de abrir las fases correspondientes, el propietario debe elegir. El coordinador NO toma estas decisiones en silencio.

### 5.1 Aprobación general

- ✅/❌ ¿Apruebas el plan director y el orden de fases §2.3?

### 5.2 Decisiones por fase (una vez aprobado el plan)

| Ref    | Decisión                                                      | Opciones                                                                                                                                                                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- |
| **F1** | Cómo aislar idempotencia por cuenta **manteniendo trade+fee** | ✅ **DECIDIDA (2026-08-20):** Opción A — alinear el lookup (`account_id`+`type`) con el UNIQUE existente por-cuenta+`type`. NO tocar UNIQUE/trade+fee. Sin migración.                                                                                                                                                                         |
| **F3** | Orden custody                                                 | A) release tras COMMIT (recomendada) · B) documentar Redis como optimización                                                                                                                                                                                                                                                                  |
| **F5** | Alcance sesión                                                | ✅ **DECIDIDA (2026-08-20):** Opción A — solo epoch (`time.time()`), sin revocación Redis.                                                                                                                                                                                                                                                    |
| **F6** | Invariante `balance_after`                                    | ✅ **DECIDIDA (2026-08-20):** Opción B — postcondición app + corregir docs (sin trigger DB).                                                                                                                                                                                                                                                  |     |
| **F8** | Limpieza `pending-delete` riesgo alto                         | ✅ **DECIDIDA (2026-08-20):** Opción A — solo inventariar, NO ejecutar (aplicada). **Complemento 2026-08-20 (aprobado):** BORRAR los LIMPIO E8 (0 imports/sin storage) en Python+web+shared + los 2 dudosos (`chart-new-tab-setup` 3 helpers y `prediction/ports.py`) → ✅ BORRAR, manteniendo intactos los ítems pending-delete riesgo alto. |
| **F9** | Arquitectura + puente legacy                                  | A) diferir a V2 (recomendado ahora) · B) abrir fase de desacople                                                                                                                                                                                                                                                                              |

---

## 6. Texto de paso (para el GESTOR/USUARIO de cara al siguiente chat)

> **RELEVO → FASE R-9 (PROPUESTA, SIN IMPLEMENTAR).** Repo `Bolsa_V1`, rama `main`, tip `c06983d` (1 commit tras `v1.1.0`), árbol limpio. **NO hay que tocar código todavía.** El **plan director** es `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md`; las **PREMISAS ESENCIALES** están en `docs/PROJECT_PREMISES.md` ⭐ §0 (E1–E9). **LEE PRIMERO** el plan + backlog (`backlog-trabajo-2026-08-20.md` §0/§1) + `PROJECT_STATE.md`.
> **Auditoría interna coincide 4/4 con la externa** en los pendientes P0/P1: (1) idempotencia money no aislada por cuenta/type (`ledger_repository.py:155-175`), (2) sesión con `monotonic()` (`session.py`), (3) custody release antes de COMMIT (`accounts.py:528`), (4) `balance_after` sin constraint DB (`tables.py:1172`).
> **Acción del usuario:** decidir §5 (aprobación general + opciones por fase). Tras aprobación, abrir **FASE 1** con un subagente acotado y el flujo E1–E9.
> **NO tocar:** gobernanza IA · workers (R-8C.2) · M-4/T-M4 · `pending-delete` riesgo alto · features nuevas.

---

## 7. Enlaces (fuentes de verdad)

- Premisas: `docs/PROJECT_PREMISES.md` (⭐ E1–E9 · §4 orquestación/relevo/anti-alucinación)
- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md`
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Plan R-8 (previo): `docs/engineering/plan-r8-prevencion-riesgo-2026-08-20.md`
- Traspaso R-8 (cierre + versionado): `docs/engineering/traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md`
- Auditoría externa v1.1.0 (fuente de los hallazgos R-9): aportada por el propietario en conversación
- Norma docs: `docs/engineering/code-documentation-standard-2026-08-03.md`
