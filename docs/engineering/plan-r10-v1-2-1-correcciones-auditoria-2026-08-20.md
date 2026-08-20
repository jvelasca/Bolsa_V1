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

**Criterio de aceptación:** `POST deposit`/`withdraw`/`trade` sin `idempotency_key` → 422; con key → normal; web typecheck/lint/test verdes; `contract:check` verde; `git status` acotado.

### 🟡 FASE F2a — R-10.2a: `TaxProfileDto` estricto (P1.3)

**Problema:** `schemas/accounts.py:42-50` sin constraints.
**Corrección:** `stamp_duty_buy_pct ge=0`, `dividend_withholding_pct ge=0`, `capital_gains_tax_pct ge=0` (si no None), `fiscal_year_start_month` en `[1,12]` (por `model_validator(mode="after")`), todos `allow_inf_nan=False`. **NO cambiar `wire`** (alias/`populate_by_name` intactos). Conservar `model_config` y los `# type: ignore[typeddict-unknown-key]`.
**Criterio:** tests de DTO en `test_schemas_accounts.py` (valores absurdos → `ValidationError`; límites válidos pasan); ruff 0 · mypy 0 (schemas+tests) · pytest zona; sin migración.

### 🟡 FASE F2b — R-10.2b: comparación idempotente exacta, sin tolerancia (P2)

**Problema:** `_cash_movement_payload_matches` (`accounts.py:302`) y `_trade_payload_matches` (`:337-345`) usan `Decimal("0.01")`.
**Corrección:** comparar **igualdad exacta de valores normalizados a la precisión financiera** (`Numeric(18,6)`). Ej.: `Decimal(str(x)).quantize(Decimal("0.000001"))`. Eliminar la tolerancia de 1 céntimo.
**Criterio:** tests en `test_idempotency_reused.py` (misma key + payload `100.004` vs `100.000` → **409**, ya NO rejuega; mismos valores exactos → replay). ruff 0 · mypy 0 · pytest app idempotencia.

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

| Ref | Punto                                                                                                                                                                          | Estado                                            |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------- |
| F4a | **ADR** del modelo de obligación de custodia pendiente (tabla/estado, transición de cuentas con `custody-YYYY` ya marcado como DONE en v1.2.0 sin re‑cobrar retroactivamente). | ⏳ pendiente (se abre en modo Plan dentro de F4a) |
| F4a | Migración Alembic de la tabla + estrategia para **no re‑cobrar** periodos ya liquidados como DONE en v1.2.0.                                                                   | ⏳ en el ADR                                      |
| F4b | Estrategia de job: alcance (todas cuentas activas vs cuentas con saldo), frecuencia, fallo/sin saldo (→ PENDING), coexistencia con scheduler no‑ARQ (R-8C.2).                  | ⏳ decisión en F4b                                |
| F5  | Tag/release `v1.2.1` + confirmar subversión en `apps/web/package.json`/`packages/shared/package.json`.                                                                         | ⏳ aprobación final                               |

---

## 6. Texto de paso (relevo / nuevo chat)

> **RELEVO → FASE R‑10 (v1.2.1).** Repo `Bolsa_V1`, `main` = `0de43ec` (tip), árbol limpio. **R‑9 cerrada**; **v1.2.0** taggeada (`b28e956`). **NO tocar código sin aprobación por commit.**
> **LEE PRIMERO (obligatorio):** `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/PROJECT_PREMISES.md` ⭐ §0 (E1–E9) · `docs/engineering/PROJECT_STATE.md` · este doc (`plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`) · traspaso R‑9 (`traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`).
> **Plan director:** este doc. **Progreso por fase:** se actualiza aquí y en el backlog al cerrar cada una.
> **Orden:** F1 → F2a → F2b → F3 → F4a → F4b → F5. Cada fase: un subagente acotado (alcances disjuntos, máx ~3 en paralelo, brief con mapa de consumidores verificado) + verificación del coordinador (diff + batería real) + **aprobación del usuario por commit** + push a `main`.
> **Decisiones cerradas (2026-08-20):** D1 encaje R‑10/v1.2.1 · D2 las 6 correcciones · D3/D3.1 custodia Opción B con tabla de obligación (migración+ADR) · D4/D4.1 custodia fuera del GET (job) con desfase aceptado · D5 idempotency‑key obligatoria (contrato+regen) · D6 sin backfill → forward‑only · D7 F2a/F2b separadas.
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
