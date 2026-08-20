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

**Problema:** `CreateInvestmentAccountDto`/`CommissionProfileDto` (`schemas/accounts.py`) aceptan `float` sin restricciones → posible `initial_deposit<0`, `leverage<=0`, `commission/VAT/FX/custody<0`, `allow_inf_nan` no forzado.

**Corrección propuesta:** aplicar en todos los DTOs financieros:

- `initial_deposit >= 0`, `leverage > 0`, `margin_call_level_pct >= 0`.
- Comisión/VAT/FX/custodia >= 0.
- `field(..., allow_inf_nan=False)` (config `model_config = ConfigDict(allow_inf_nan=False)` o validators).
- Mantener `Decimal` hasta el borde cuando sea práctico (`Decimal` en HTTP/domain; `Numeric` en DB).

**Criterio de aceptación:** tests de DTOs con valores absurdos → 422; batería verde.

---

### 🟠 FASE 5 — R-9.5: Sesión con epoch en vez de `monotonic()` (+ revocación opcional)

**Problema:** `session.py` usa `time.monotonic()` → no portable multi-host.

**Corrección propuesta:**

- Cambiar `exp` a **Unix epoch UTC** (`time.time()`), mantener HMAC y `Secure`/`SameSite`/TTL.
- **Opcional (decisión §5.2):** si se quiere revocación real (logout que invalida sesión copiada), introducir `session_id` + store Redis con TTL y `session_version` por usuario. Para app personal local, el cambio a epoch es suficiente y de menor riesgo.

**Criterio de aceptación:** login→cookie válida TTL; logout borra cookie; con epoch la cookie es portable; tests auth existentes (10) verdes.

---

### 🟠 FASE 6 — R-9.6: Invariante `balance_after` como garantía física (decidir)

**Problema:** el invariante solo está en tests; la release lo afirma como "DB". Un CHECK no puede leer otra fila.

**Corrección propuesta (elegir §5.2):**

- **Opción A (recomendada, cierra el claim):** **trigger/procedure** PostgreSQL que, en `INSERT/UPDATE` de `ledger_entries` y por `account_id` en orden `(executed_at, id)`, valide `balance_after == prev_balance + Σ amount`; NEGATIVO si no cumple. Pipeline de migración Alembic + test de carga en infra real.
- **Opción B (mantener en app, corregir el claim de la release/docs):** mantener el invariante como **verificación por grupo atómico** (tests `test_r8c_*`) y **corregir la documentación** (release/README) para que NO afirme constraint DB cuando es postcondición de app. Menor riesgo, menor garantía.

**Criterio de aceptación (opción A):** INSERT corrupto → rechazado por DB; migración desde BD limpia y existente OK; tests de invariante en infra real verdes.

---

### 🟠 FASE 7 — Suite de concurrencia e invariantes (escenarios de ataque)

**Problema:** no hay batería sistemática de concurrencia/rollback/idempotencia.

**Corrección propuesta (tests/scripts nuevos):**

- `test_concurrency_*.py` en infra real con escenarios del §2.4.
- Scripts de verificación: `scripts/verify/` con checks de invariantes y de aislamiento entre cuentas (A/B).
- Test de seguridad: `request(account=A, portfolio=B)` ⇒ 403/404 y NO muta B.
- Regression: `database_bootstrap` idempotente con 2 workers; migración limpia y existente.

**Criterio de aceptación:** todos verdes en CI; documentar resultados.

---

### 🟡 FASE 8 — Limpieza de código/doc obsoletos + DOCSTRINGS + deuda menor

**Alcance (criterio E8):** eliminar/archivar código y documentos que ya no reflejan la realidad (p. ej. deuda "Alembic baseline pendiente" ya resuelta, helpers muertos), **solo** si 0 imports y no dependen de storage por nombre. Revisar `pending-delete/README.md` (riesgo alto: solo nominal, no ejecutar). Rellenar docstrings de símbolos públicos tocados. Depurar documentación que diverge del código (README vs realidad, §1.3).

**Criterio de aceptación:** battery/typecheck verdes tras limpiar; `git status` acotado; docs actualizadas sin perder evidencia.

---

### 🟡 FASE 9 — (Opcional / alinear con V2) Arquitectura Python + puente legacy

**Alcance (más amplio, requiere ADR):**

- Re-verificar dependencias `analytics ↔ market` y **declarar** en `pyproject.toml` lo realmente usado (tras auditoría read-only; no se asume).
- Definir direcciones unívocas (`domain ↑ analytics ↑ application ↑ infrastructure ↑ api`) y los tipos compartidos a `domain`.
- Plan de deprecación del puente `legacy_portfolio_id`.

**Criterio de aceptación:** `import-linter` verde; dependencias declaradas; sin ciclo analytics↔market.

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

| Ref    | Decisión                                                      | Opciones                                                                                                                                                              |
| ------ | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | Cómo aislar idempotencia por cuenta **manteniendo trade+fee** | ✅ **DECIDIDA (2026-08-20):** Opción A — alinear el lookup (`account_id`+`type`) con el UNIQUE existente por-cuenta+`type`. NO tocar UNIQUE/trade+fee. Sin migración. |
| **F3** | Orden custody                                                 | A) release tras COMMIT (recomendada) · B) documentar Redis como optimización                                                                                          |
| **F5** | Alcance sesión                                                | A) solo epoch (recomendada, menor riesgo) · B) + session_id/revocación Redis                                                                                          |
| **F6** | Invariante `balance_after`                                    | A) trigger/proc DB (cierra el claim) · B) postcondición app + corregir docs (menor riesgo)                                                                            |
| **F8** | Limpieza `pending-delete` riesgo alto                         | A) solo inventariar, NO ejecutar (recomendada) · B) (requiere `purge storage`)                                                                                        |
| **F9** | Arquitectura + puente legacy                                  | A) diferir a V2 (recomendado ahora) · B) abrir fase de desacople                                                                                                      |

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
