# PLAN PROFUNDO — R-10 / v1.2.1: Correcciones de la auditoría externa post‑v1.2.0 (2026-08-20)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product/Ops`) · **backlog:** `docs/engineering/backlog-trabajo-2026-08-20.md`.
> **Premisas:** `docs/PROJECT_PREMISES.md` ⭐ §0 (**PREMISAS ESENCIALES ACTUALES E1–E9**).
> **AsOf:** 2026-08-20.
> **Estado:** 📋 **PROPUESTA — PLAN AUTORIZADO (decisiones cerradas). SIN IMPLEMENTAR.** Ningún cambio de código se ejecuta sin **aprobación explícita del usuario POR COMMIT** (§2.4). Es el **plan director de R‑10**; cada fase se abre como subagente acotado bajo las premisas E1–E9.
> **R‑9 quedó CERRADA** (F1–F8, decisión 2026-08-20) y **v1.2.0 intacta**. R‑10 es un paquete nuevo nacido de la **auditoría externa sobre `b28e956`/`v1.2.0`** (capa financiera P1/P2).

---

## 1. Contexto y mandato

### 1.1 Origen

- El propietario pidió **auditar la APP tras la última versión** y confrontar con una **auditoría externa** sobre el estado actual, decidiendo si es posible **refactorizar y mejorar los errores**. No se hace nada sin un **plan profundo aprobado** y con **aprobación por commit** (premisas E1–E4).
- La auditoría externa audita `main → b28e956`, `tag v1.2.0 → b28e956`, y **no** detecta P0. Valora global 8.7/10, backend financiero 9.0/10. Los puntos P0 de rondas previas (R-9 F1–F8) los da **resueltos**.
- Este plan registra los **6 pendientes P1/P2** que quedan y las **decisiones del propietario** (§3) tomadas 2026-08-20.

### 1.2 Estado verificado (firma — no adivinar)

| Contexto                     | Valor verificado                                                 |
| ---------------------------- | ---------------------------------------------------------------- |
| HEAD actual                  | `0de43ec` (tip de `main`)                                        |
| HEAD auditado por la externa | `b28e956` (= tag `v1.2.0`)                                       |
| Rama / árbol                 | `main` = `origin/main` · **limpio** (`git status --short` vacío) |
| Tags                         | `v1.0.0`, `v1.1.0`, `v1.2.0`                                     |
| Estado R‑9                   | **CERRADA** (F1–F8) — decisión propietario 2026-08-20            |

### 1.3 Evidencia verificada en código (file:line) — los 6 puntos

| #   | Hallazgo externo                                                                                           | Gravedad | Evidencia verificada (file:line)                                                                                                                                                                                                                                                                                             |
| --- | ---------------------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `balance_after` de trade y fee = **cash FINAL** (ambos)                                                    | 🔴 P1    | `packages/py/application/src/bolsa_application/accounts.py:817` (`trade_balance = result.summary.portfolio.cash`), `:824` (`append_trade(balance_after=trade_balance)`), `:844` (`append_fee(balance_after=result.summary.portfolio.cash)`). El summary ya incluye comisiones → ambas filas guardan el mismo saldo post‑fee. |
| 2   | Custodia parcial **silenciosa** (`allow_partial=True`) → cobra parcial y marca DONE, **pierde obligación** | 🔴 P1    | `accounts.py:623-647`: `deduct_cash(charge_legacy_id, fee_amount, allow_partial=True)` (`:625-629`), `charged = cash_before - balance_after` (`:630`), `append_fee(amount=charged, ..., reference_id=f"custody-{period}")` (`:643-647`).                                                                                     |
| 3   | `TaxProfileDto` sin constraints (a diferencia de `CommissionProfileDto`)                                   | 🔴 P1    | `apps/api-python/src/bolsa_api/schemas/accounts.py:42-50`: `stamp_duty_buy_pct: float`, `dividend_withholding_pct: float`, `capital_gains_tax_pct: float \| None`, `fiscal_year_start_month: int` — sin `ge`, sin `allow_inf_nan=False`, sin rango [1,12].                                                                   |
| 4   | Comparación idempotente con **tolerancia `0.01`** (debería ser normalización a precisión `Numeric(18,6)`)  | 🟡 P2    | `accounts.py:302` (`_cash_movement_payload_matches`: `abs(Decimal(...)-Decimal(...)) < Decimal("0.01")`), `:337-345` (`_trade_payload_matches`: `tol = Decimal("0.01")`, compara `quantity`/`price`).                                                                                                                        |
| 5   | **Mutación en GET**: `ApplyCustodyFees` se ejecuta dentro de lecturas                                      | 🟠 P1/P2 | `GetAccountSummary.execute` → `ApplyCustodyFees(...).execute(scope)` `accounts.py:176`; `GetTaxReport.execute` → idem `accounts.py:866`. Un GET muta cash/ledger. Duplica `M-4/T-M4` (diferido) y `R-8C.2`.                                                                                                                  |
| 6   | `idempotency_key` **opcional** en operaciones financieras críticas                                         | 🟡 P2    | `idempotency_key=None` permite que un retry HTTP sin key cree 2ª operación. Revisar DTO/use-case de deposit `:xxx`, withdraw, trade.                                                                                                                                                                                         |

> Nota: el invariante `Σ ledger.amount == cash` está intacto y verificado; el problema #1 rompe solo la **semántica secuencial** de `balance_after`, no la reconciliación.

---

## 2. Estrategia de ejecución (minimizar riesgo — premisas E1–E9)

### 2.1 Fases acotadas, una por subagente (nunca todo-en-uno)

Cada fase:

- Objetivo único y medible (criterio de aceptación explícito).
- **Manifiesto de ficheros** a tocar / NO tocar.
- **Un subagente acotado** con brief inyectado (contexto, archivos, batería, obligación de escribir el resultado en backlog/traspaso).
- **Verificación del coordinador** (diff + batería real) antes de proponer commit.
- **Aprobación del usuario POR COMMIT**.
- **Test/script de verificación** incluidos en la fase.

### 2.2 Control de saturación / relevos (premisas E2/E3)

| Mecanismo          | Cómo                                                                                                                                   |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Límite paralelismo | Máx. ~3 subagentes en paralelo, alcances disjuntos.                                                                                    |
| Trigger de relevo  | Si el contexto se llena, **cerrar chat** y abrir otro pegando el **texto de paso** (este plan + backlog + bloque "estado verificado"). |
| Anti-alucinación   | Toda afirmación (file:line/commit/test) se contrasta contra código/datos reales. **Documento manda**.                                  |
| Firma de estado    | Cada texto de traspaso incluye HEAD, rama, árbol, CI.                                                                                  |

### 2.3 Orden de ejecución de R‑10

```
FASE 0  → este plan (decisión propietario) + premisas                          [DONE: este doc]
       ↓ aprobación usuario
F1      → idempotency_key OBLIGATORIA en deposit/withdraw/trade (D5)            [contrato, base]
F2a     → TaxProfileDto estricto (P1.3)                                          [schemas, bajo riesgo]
F2b     → comparación idempotente exacta, sin tolerancia 0.01 (P2)              [accounts, bajo]
F3      → balance_after trade/fee corregido, SIN backfill (P1.1)                [accounts+verify, medio]
F4a     → custodia Opción B: obligación pendiente (tabla/ADR/migración) (P1.2)  [datos, ALTO]
F4b     → custodia fuera del GET → job programado (D4) (reabre M-4/T-M4)        [scheduler, ALTO]
F5      → docs + CHANGELOG + tag/release v1.2.1 + limpieza obsoletos (E8)       [higiene]
```

Cada fase se abre de una en una, con su subagente acotado y batería. **F1, F2a, F2b, F5 son de riesgo bajo; F3 medio; F4a y F4b altos** (datos + scheduler) y requieren ADR/estrategia antes de código.

### 2.4 Batería obligatoria por fase (la re-verifica el coordinador)

- **Backend:** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de ficheros en gate CI · pytest de la zona (app money-path / infra real si toca DB).
- **Frontend (si toca contrato/API — F1, F5):** `pnpm --filter @bolsa/web typecheck|lint|build` · `contract:check` precedido de `$env:PYTHONIOENCODING='utf-8'` (si cambia schema).
- **DB (si toca migración — F4a):** migración desde **DB limpia** y desde **DB existente** (up/downgrade), idempotencia de `database_bootstrap`, validación de datos.
- **Invariantes:** `scripts/verify/verify_ledger_balance_chain.py` y `verify_account_isolation.py` (casa con F3).

---

## 3. Decisiones del propietario (cerradas 2026-08-20)

| Ref  | Decisión                           | Valor aprobado                                                                                                                                                                                 |
| ---- | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1   | Encaje del paquete                 | **Nueva fase R‑10 / v1.2.1**; **R‑9 quedó cerrada** y **v1.2.0 intacta**.                                                                                                                      |
| D2   | Alcance                            | Ejecutar **las 6 correcciones** (P1 + P2/P1.5).                                                                                                                                                |
| D3   | Custodia parcial                   | **Opción B**: registrar **obligación de custodia pendiente** (outstanding liability); **cobrar completo solo cuando haya saldo suficiente**; NO marcar DONE parcialmente ni perdonar el resto. |
| D3.1 | Representación de la obligación    | **Tabla/estado de obligación pendiente en DB** (columna o entidad con su estado) → **requiere migración + ADR** (a diseñar y aprobar en la fase F4a).                                          |
| D4   | Mutación en GET                    | **Sí**: retirar `ApplyCustodyFees` del path de lectura (`GetAccountSummary`/`GetTaxReport`) y moverlo a **job programado** (desbloquea `M-4/T-M4`).                                            |
| D4.1 | Desfase de saldo en UI             | **Aceptar desfase**: el saldo aparece pre‑custodia hasta que corra el job del día (los GET quedan 100% de solo lectura).                                                                       |
| D5   | Idempotency‑key                    | **Obligatoria** en `POST deposit/withdraw/trade` → **cambio de contrato** + **regen OpenAPI/`schema.d.ts` + `contract:check`** + ajuste de consumidores web.                                   |
| D6   | Backfill `balance_after` histórico | **NO reescribir histórico** (forward‑only). Solo escrituras futuras corregidas + `verify_ledger_balance_chain.py` para validar.                                                                |
| D7   | F2 TaxProfile + idempotencia       | **Separadas** en **F2a** (TaxProfile) y **F2b** (idempotencia exacta).                                                                                                                         |

> Estas decisiones se reflejarán en `backlog-trabajo-2026-08-20.md` (§0 relego + §6) al cerrar cada fase y en la fase F5.

---

## 4. Detalle por fase

### 🔴 FASE F1 — R-10.1: idempotency_key OBLIGATORIA en deposit/withdraw/trade (D5)

**Problema:** hoy `idempotency_key=None` permite retry sin protección (P2). Se endurece a obligatoria.

**Alcance (design-oriented, se confirma al abrir):**

- `DepositCashToAccount` / `WithdrawCashFromAccount` / `ExecuteTrade` (y sus DTOs en `apps/api-python/src/bolsa_api/schemas/accounts.py`, rutas `api/v1/routes/accounts.py`).
- Hacer `idempotency_key` **requerido** (quitar `=None`/default). Definir el 4xx exacto si falta (422 Pydantic es lo natural).
- **Ajustar consumidores web** que no pasan key hoy (ver en fase: call-sites de `deposit`/`withdraw`/`trade` en `apps/web`), incl. los caminos internos AUTO/confirm que ya usan key estable (R-7 B-4); añadir `idempotency_key` generada por cliente o por la UI.
- **Contrato:** regen `openapi.json`/`schema.d.ts` + `contract:check` verde. **NO** `contract:gen` de forma amplia; regen acotada (fase propia ya es).
- **Sin migración** (no afecta a DB).

**Riesgo:** alto (contrato) → por eso va **solo** y con regen acotada.

**Mapeo verificado (read-only, subagentes `explore` 2026-08-20) — estado de la opcionalidad:**

- **Backend (6 sitios opcionales en producción):** `DepositCashDto.idempotency_key` (`schemas/accounts.py:277`), `WithdrawCashDto` (`:285`), `TradeRequestDto` (`schemas/portfolio.py:69`); firmas `DepositCashToAccount.execute(:378)`, `WithdrawCashFromAccount.execute(:473)`, `ExecuteTrade.execute(:751)` — todas `str | None = None`. Ninguna ruta valida presencia (`routes/accounts.py:388,410`, `routes/portfolio.py:108`). Único ramal que ya asume no-None: `ExecuteTrade` `:796` (`if idempotency_key is None: raise`). Callers internos (AUTO `execution_router.py:479,625`, confirm `confirm_recommendation.py:88`) **ya pasan clave estable**.
- **Frontend (5 call-sites NO pasan `idempotencyKey`):** 3× `api.executeTrade` → `instruments/instrument-detail-page.tsx:107`, `trading/order-dialog.tsx:88`, `trading/pending-orders-monitor.tsx:96`; 1× `depositCash` y 1× `withdrawCash` → `accounts/account-detail-panel.tsx:175,180`. Los DTOs TS de `@bolsa/shared` (`packages/shared/src/portfolio-cash.ts:32,37`) **no declaran** la propiedad; el body inline de `executeTrade` (`apps/web/src/lib/api.ts:1454`) tampoco. La ruta F3/confirm `/api/ai/intents/confirm` ejecuta el trade server-side y **no expone idempotencyKey** desde web (`api.ts:1348`, call-sites `supervised-f3-panel.tsx:355,416`) — queda como alcance abierto (el trade server-side ya usa clave interna vía B-4; NO se obliga en el endpoint de confirm salvo decisión).
- **Tests que dependen de la opcionalidad (deberán actualizarse):** `application/tests/test_deposit_withdraw_idempotency.py:207,211,222,264` (sin clave → id nuevo), `test_idempotency_reused.py:245`, `test_execute_trade_idempotency.py:207-222` (documenta "escotilla residual" sin clave), fakes `:98`/`:172`; API integr `tests/integration/test_trade_idempotency.py:83-90` (2º POST sin clave esperando 200).

**Estrategia de generación de clave (DISEÑO a confirmar por el propietario — ver §5.2 R-10-F1):** la obligatoriedad en el borde DTO rompe 5 call-sites web y 6 tests. Se requiere decidir cómo proveen la key los consumidores:

- **A — Cada call-site genera y cachea una key por operación lógica** (reutilizada en retries hasta resolución éxito/fracaso): idempotencia real entre retries; toca los 5 call-sites + 2 DTOs shared + body `executeTrade`.
- **B — Inyección centralizada en `api.ts` (middleware `onRequest`)** genera la key en cada POST financiero: mínimo toque (1 punto), pero sin cache por operación no protege retries del mismo intento (la key cambia cada llamada) → NO cumple el objetivo de idempotencia entre retries.
- **C — (recomendada para integridad) A + helper de generación reutilizable**: extraer `createRandomId()` (ya en `@bolsa/shared/src/create-id.ts`) como base + cache de key por "operación en curso" en cada call-site; garantiza retry seguro (misma key → replay/409).

**Criterio de aceptación:** `POST deposit`/`withdraw`/`trade` sin `idempotency_key` → 422 (Pydantic); con key → normal; **retry del mismo intento** con la misma key → replay/409 según payload; web typecheck/lint/test verdes (con los 5 call-sites ajustados); DTOs shared actualizados; `contract:check` verde (regen acotada de `openapi.json`+`schema.d.ts`); `git status` acotado. Tests de opcionalidad actualizados a obligatoria.

> **⚠️ Contract-check y baseline F4 (verificado 2026-08-20, worktree aislado en HEAD):** el `contract:gen` reproduce sobre HEAD un **drift de ratios preexistente a F1** (`custodyAnnualPct/fxConversionPct/stockCommission*/vatOnCommissionPct/initialDeposit/leverage/marginCallLevelPct` — constraints de **R-9 F4**, nunca regeneados en OpenAPI; decisión pendiente del backlog). Por eso `contract:check` **ya estaba rojo antes de F1** por ese baseline. **F1 NO introduce drift**: su `openapi.json`/`schema.d.ts` se regen erán de forma **acotada** (solo `idempotencyKey` en los 3 DTOs), y el baseline F4 queda pendiente de su fase/decisión de contrato (NO colar en F1). Criterio de éxito F1: `contract:check` verde **salvo el delta de ratios F4 preexistente**, que se documenta y se deja intacto.
>
> **F1-C (decisión propietario 2026-08-20):** key cacheada por operación en curso (reutilizada en retries → replay/409) en los 5 call-sites web, sobre helper `createIdempotencyKey()` (`@bolsa/shared/src/idempotency-key.ts`, UUID v4 sobre `createRandomId`). **El endpoint `/api/ai/intents/confirm` queda FUERA de F1** (el trade server-side ya usa clave interna vía B-4).

### 🟡 FASE F2a — R-10.2a: `TaxProfileDto` estricto (P1.3)

**Problema:** `schemas/accounts.py:42-50` sin constraints.
**Corrección:** `stamp_duty_buy_pct ge=0`, `dividend_withholding_pct ge=0`, `capital_gains_tax_pct ge=0` (si no None), `fiscal_year_start_month` en `[1,12]` (por `model_validator(mode="after")`), todos `allow_inf_nan=False`. **NO cambiar `wire`** (alias/`populate_by_name` intactos). Conservar `model_config` y los `# type: ignore[typeddict-unknown-key]`.
**Criterio:** tests de DTO en `test_schemas_accounts.py` (valores absurdos → `ValidationError`; límites válidos pasan); ruff 0 · mypy 0 (schemas+tests) · pytest zona; sin migración.

**Manifiesto verificado (2026-08-20):**

- **DTO:** `TaxProfileDto` = `apps/api-python/src/bolsa_api/schemas/accounts.py:42-50`. Campos: `jurisdiction: str`, `cost_basis_method: str`, `stamp_duty_buy_pct: float`, `dividend_withholding_pct: float`, `capital_gains_tax_pct: float|None`, `fiscal_year_start_month: int`. Sin constraints hoy.
- **Restricciones firmes:** NO cambiar el wire — conservar `model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)` con su `# type: ignore[typeddict-unknown-key]`, y los `alias` (`costBasisMethod`, `stampDutyBuyPct`, `dividendWithholdingPct`, `capitalGainsTaxPct`, `fiscalYearStartMonth`). `jurisdiction`/`cost_basis_method` quedan sin restricción.
- **Tests:** `apps/api-python/tests/test_schemas_accounts.py` (usa `pytest.raises(ValidationError)`, `overrides`, import de DTOs). Añadir tests de `TaxProfileDto`: negativos/NaN/Inf en los 3 pct → `ValidationError`; `fiscal_year_start_month` fuera de [1,12] → `ValidationError`; límites válidos (0, y pct None) pasan; alias y populate_by_name intactos (wire-serialization).
- **¿Alcance de contrato?** `TaxProfileDto` es DTO de request del endpoint de perfil de cuenta. Añadir constraints Pydantic NO cambia el JSON wire (solo validación) → **sin regen de `openapi.json`/`schema.d.ts`** salvo que `contract:gen` lo pida y solo añada `minimum`, en cuyo caso NO comitear drift colateral (documentar). `contract:check` preexistente rojo por baseline F4 (no F2a).
- **Sin migración.** Nivel de riesgo bajo.

### 🟡 FASE F2b — R-10.2b: comparación idempotente exacta, sin tolerancia (P2)

**Problema:** `_cash_movement_payload_matches` (`accounts.py:302`) y `_trade_payload_matches` (`:337-345`) usan `Decimal("0.01")`.
**Corrección:** comparar **igualdad exacta de valores normalizados a la precisión financiera** (`Numeric(18,6)`). Ej.: `Decimal(str(x)).quantize(Decimal("0.000001"))`. Eliminar la tolerancia de 1 céntimo.
**Criterio:** tests en `test_idempotency_reused.py` (misma key + payload `100.004` vs `100.000` → **409**, ya NO rejuega; mismos valores exactos → replay). ruff 0 · mypy 0 · pytest app idempotencia.

**Manifiesto verificado (2026-08-20):**

- **Funciones a cambiar:** `_cash_payload_matches` (`accounts.py:301`) → reemplaza `abs(...) < Decimal("0.01")` por **igualdad exacta normalizada**; `_trade_payload_matches` (`:336-344`) → reemplaza `abs(...) > tol` por igualdad exacta normalizada.
- **Criterio de normalización (importante):** normalizar el entrante y el persistido a **escala fija de 6 decimales** (`Decimal(str(x)).quantize(Decimal("0.000001"))`) y comparar con `==`. ELIMINAR la tolerancia de 1 céntimo. `100.004` vs `100.000` → **distinto → raise/return False → 409**; `100` vs `100.000000` → **igual → replay**.
- **Advertencia anti-alucinación:** `quantize` por defecto usa `ROUND_HALF_EVEN`. Como la escala es de 6 decimales y los valores de dinero/trade típicos tienen ≤6 decimales, la normalización no debe introducir redondeos espurios; usa `Decimal(str(x))` (no construir desde float). No inventes contextos ni tolerancias adicionales — el objetivo es exactitud granular a 6 decimales. Documenta la semántica en el docstring (sustituyendo la mención a "tolerancia de 1 céntimo").
- **Dependencias/imports:** `Decimal` está importado localmente en cada función (`from decimal import Decimal`). Mantener.
- **Tests:** en `packages/py/application/tests/test_idempotency_reused.py` (zona de payload mismatch) y, si es más natural, `test_deposit_withdraw_idempotency.py`/`test_execute_trade_idempotency.py`. Añadir/ajustar casos: key reutilizada con `amount` que difiere en <1 céntimo pero es distinto a nivel granular (p.ej. `100.004` vs `100.000`) → **409**; cantidades que difieren en el 6º decimal percibido (p.ej. mismas → replay). Los casos previos que usaban `0.01` de tolerancia que YA debían dar 409 siguen igual; los que dependían de la tolerancia para "clavar" replay deben seguir pasando (mismas cantidades exactas).
- **Sin migración, sin contrato, sin tocar F1/F2a/F3/F4.** Riesgo bajo-medio (afecta semántica de 409, zona protegida de R-9 F2 — respetar el mecanismo de replay/carrera).

### 🟠 FASE F3 — R-10.3: `balance_after` de trade + fee corregido, SIN backfill (P1.1)

**Problema:** `accounts.py:817/824/844` guardan cash FINAL en ambas filas.
**Corrección:** capturar `cash_before` **antes** de la mutación. `append_trade(balance_after= cash_before - total)` y `append_fee(balance_after= cash_before - total - fee)`. Revisar el comentario `# M3` (`:815`) y el `summary = await _portfolio_repo.get_summary(...)` para obtener `cash_before` sin re‑leer un post‑fee ya mutado.
**Semántica resultante:** `balance_after[n] = balance_after[n-1] + amount[n]` dentro de cada operación (trade→fee). **Actualizar `verify_ledger_balance_chain.py`** si asumía otra cosa.
**Sin backfill (D6).**
**Criterio:** tests de invariante secuencial en`test_r8c_ledger_balance_atomic.py`/`test_concurrency_scenarios.py` verdes; `verify_ledger_balance_chain.py` EXIT 0; ruff 0 · mypy 0; sin migración.

### 🔴 FASE F4a — R-10.4a: Custodia Opción B — obligación pendiente + cobro completo (P1.2, ALTO)

> Requisito previo del plan (§2.3 y §5.2): **ADR** + diseño en este doc + **decisión explícita del propietario** antes de abrir código.

**Problema:** `ApplyCustodyFees` (`accounts.py:555-647`) cobra `allow_partial=True` y marca `custody-YYYY`/fee en el ledger aunque falte saldo → la obligación desaparece.
**Corrección (Opción B, D3+D3.1):**

- Introducir una **tabla de obligación de custodia pendiente** (u estado de cuenta) con su `outstanding` y estado (`PENDING`/`APPLIED`/…), migración Alembic + ADR.
- `ApplyCustodyFees`: si `cash < fee` → **no marca DONE**; persiste/actualiza `outstanding` y queda `PENDING` para reintento posterior (job). Si `cash >= fee` → cobra el **total**, actualiza obligación → `APPLIED`/liquidado y escribe el ledger.
- Mantener la protección de carrera idempotente (R-9 F3) y el UNIQUE.
- **Sin pérdida de obligación**: nunca se perdona en silencio; el `Σ ledger == cash` se mantiene.

**Criterio:** test de custodia con `cash < fee` → quedada PENDING + `outstanding==fee`, sin cargo ni DONE; después, cash suficiente → cobra completo y liquida; dos intentos concurrentes no duplican (idempotente); migración desde DB limpia y existente OK.

### 🔴 FASE F4b — R-10.4b: Custodia fuera del GET → job programado (D4, ALTO)

**Problema:** `GetAccountSummary` (`:176`) y `GetTaxReport` (`:866`) mutan en GET.
**Corrección (D4):**

- Retirar `ApplyCustodyFees` de esos use‑cases de lectura. **Los GET quedan de solo lectura**.
- Mover la aplicación de custodia a un **job programado** (scheduler) sobre todas las cuentas activas. Desbloquea `M-4/T-M4` (job dedicado, diferido por freeze — la decisión D4 lo reactiva).
- **Desfase temporal aceptado (D4.1)**: el saldo aparece pre‑custodia hasta el job del día. Documentar en HELP/UX.
- Mantener la idempotencia y el UNIQUE del cargo.

**Criterio:** GET summary/tax no mutan (no escriben ledger/cash); el job aplica custodia de forma idempotente y sin duplicar; tests de regresión de R-9 F3/F7 verdes; batería scheduler.

### 🟢 FASE F5 — R-10.5: Docs + CHANGELOG + versión + limpieza obsoletos (E8)

- Actualizar `backlog-trabajo-2026-08-20.md` (§0 relego + §6), `PROJECT_STATE.md`, `engineering-index`, y este doc (estados por fase).
- Registrar decisión de contraste contra la auditoría externa y el **texto de paso** de R‑10.
- **Tag/release `v1.2.1`** (pendiente aprobación, precedente v1.2.0 en `b28e956`).
- Limpieza (E8): revisar `pending-delete/README.md` (riesgo alto: solo inventariar), y retirar/marcar docs obsoletos que ya no reflejen la realidad tras R‑10. Revisar `// M3` y comentarios que cambian de semántica.

---

## 5. Puntos que requieren ADR/decisión ANTES de abrir código (no auto‑cerrar)

| Ref    | Punto                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Estado                                                  |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| **F1** | **Estrategia de generación de `idempotency_key` en el cliente.** ✅ **DECIDIDA (2026-08-20):** **Opción C** — cada call-site genera una key única y la **cachea por operación en curso** (reutilizada en retries → replay/409), sobre un **helper reutilizable** derivado de `createRandomId` (`@bolsa/shared/src/create-id.ts`). **El endpoint `/api/ai/intents/confirm` NO exige key en F1** (el trade server-side ya usa clave interna vía B-4); alcance F1 = solo `deposit`/`withdraw`/`trade` directos. | ✅ **DECIDIDA (2026-08-20)** — Opción C + confirm fuera |
| F4a    | **ADR** del modelo de obligación de custodia pendiente (tabla/estado, transición de cuentas con `custody-YYYY` ya marcado como DONE en v1.2.0 sin re‑cobrar retroactivamente).                                                                                                                                                                                                                                                                                                                               | ⏳ pendiente (se abre en modo Plan dentro de F4a)       |
| F4a    | Migración Alembic de la tabla + estrategia para **no re‑cobrar** periodos ya liquidados como DONE en v1.2.0.                                                                                                                                                                                                                                                                                                                                                                                                 | ⏳ en el ADR                                            |
| F4b    | Estrategia de job: alcance (todas cuentas activas vs cuentas con saldo), frecuencia, fallo/sin saldo (→ PENDING), coexistencia con scheduler no‑ARQ (R-8C.2).                                                                                                                                                                                                                                                                                                                                                | ⏳ decisión en F4b                                      |
| F5     | Tag/release `v1.2.1` + confirmar subversión en `apps/web/package.json`/`packages/shared/package.json`.                                                                                                                                                                                                                                                                                                                                                                                                       | ⏳ aprobación final                                     |

---

## 6. Texto de paso (relevo / nuevo chat)

> **RELEVO → FASE R‑10 (v1.2.1).** Repo `Bolsa_V1`, `main` = `4e4a81a` = `origin/main` (push aprobado 2026-08-20), árbol limpio. **R‑9 cerrada**; **v1.2.0** taggeada (`b28e956`). **NO tocar código sin aprobación por commit.**
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/PROJECT_PREMISES.md` ⭐ §0 (E1–E9) · `docs/engineering/PROJECT_STATE.md` · este doc (`plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`) · traspaso R‑9 (`traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`).
> **Plan director:** este doc. **Progreso por fase:** se actualiza aquí y en el backlog al cerrar cada una.
> **Orden:** F1 → F2a → F2b → F3 → F4a → F4b → F5. Cada fase: un subagente acotado (alcances disjuntos, máx ~3 en paralelo, brief con mapa de consumidores verificado) + verificación del coordinador (diff + batería real) + **aprobación del usuario por commit** + push a `main`.
> **Decisiones cerradas (2026-08-20):** D1 encaje R‑10/v1.2.1 · D2 las 6 correcciones · D3/D3.1 custodia Opción B con tabla de obligación (migración+ADR) · D4/D4.1 custodia fuera del GET (job) con desfase aceptado · D5 idempotency‑key obligatoria (contrato+regen) · D6 sin backfill → forward‑only · D7 F2a/F2b separadas · **F1-C** (key cacheada por operación en curso, helper `createRandomId`) · **F1-no-confirm** (endpoint `/api/ai/intents/confirm` fuera del alcance).
> **NO tocar** (salvo decisión): `pending-delete` riesgo alto · gobernanza IA · workers ARQ/no‑ARQ excepto la parte de custodia‑job que decida F4b · features nuevas.

---

## 7. Enlaces (fuentes de verdad — no inventar estado)

- Premisas E1–E9: `docs/PROJECT_PREMISES.md` ⭐ §0
- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md`
- Plan R‑9 (cerrado): `docs/engineering/plan-r9-refactor-hardening-2026-08-20.md`
- Traspaso R‑9: `docs/engineering/traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Auditoría externa (fuente): aportada por el propietario en conversación (audita `b28e956`/`v1.2.0`)
- Norma docs: `docs/engineering/code-documentation-standard-2026-08-03.md`
