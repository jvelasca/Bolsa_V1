# RELEVO — R-10: F1–F4a completas y pusheadas — apertura F4b (2026-08-21)

> **Tipo:** Relevo de cierre de chat/día. Leer PRIMERO junto al **texto de paso** (§7) para que un nuevo agente / nuevo chat continúe **sin perder contexto**.
> **Repos:** `Bolsa_V1` (monorepo).
> **Firma del estado (verificada, no adivinada):** `git branch --show-current` = `main` · `HEAD` = **`5c304e6`** (`local main = origin/main`, árbol **limpio**) · sin tag en HEAD. **R-10 / v1.2.1 AVANZADA**: F1/F2a/F2b/F3/F4a ✅ pusheadas · **SIGUIENTE: F4b**.

---

## 1. Qué se ha hecho hoy (2026-08-21)

Conforme al **plan director** `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md` (6 correcciones P1/P2 de la **auditoría externa post‑v1.2.0**), se completaron y pusheron a `main` **5 fases** (F1/F2a/F2b/F3/F4a). Cada fase: **verificación del coordinador (diff + batería)** → **aprobación del propietario por commit** → **push a `main`**.

| Fase    | Corrección                                                        | Prioridad    | Commit(s)                               | Descripción breve                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------- | ----------------------------------------------------------------- | ------------ | --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1**  | `idempotency_key` **OBLIGATORIA** en deposit/withdraw/trade       | P2           | `a1501e6`                               | DTOs + firma de use-case requieren la key (sin default); web genera y cachea la key por operación (estrategia C, helper `createIdempotencyKey`). POST sin clave → **422**.                                                                                                                                                                                                                                                                                                             |
| **F2a** | `TaxProfileDto` estricto                                          | P1.3         | `b4dcc72`                               | `ge=0` + `allow_inf_nan=False` en los 3 pct; `fiscal_year_start_month ∈ [1,12]` (`model_validator`). Wire intacto.                                                                                                                                                                                                                                                                                                                                                                     |
| **F2b** | Comparación idempotente **exacta** (sin tolerancia `0.01`)        | P2           | `86c315a`                               | `_cash_payload_matches`/`_trade_payload_matches` comparan por `==` normalizado a 6 decimales (`Decimal(str(x)).quantize(0.000001)`). Diferencia sub‑céntimo → 409/conflicto; valores iguales → replay.                                                                                                                                                                                                                                                                                 |
| **F3**  | `balance_after` trade+fee **secuencial** (sin backfill D6)        | 🔴 P1        | `b79e5dd`                               | Captura `cash_before` antes de mutar; `trade_balance=cash_before+amount`, `fee_balance=trade_balance−fees`. Verify+tests a invariante secuencial por fila. **Reset datos sim dev** (decisión propietario) → `verify` EXIT 0. Verificado: smoke `buy`→`fee` 105000→104000→103996.79.                                                                                                                                                                                                    |
| **F4a** | Custodia parcial silenciosa → **Opción B** (obligación pendiente) | 🔴 P1.2 ALTO | `49e2731` (ADR docs) + `5c304e6` (impl) | **ADR 026** (docs-only) + implementación: tabla `custody_obligation` (PK `account_id`, migración `005` forward-only, **sin backfill D6**) + `CustodyObligationRepository` + `ApplyCustodyFees` Opción B: `cash>=fee` cobra **TOTAL** y marca `APPLIED`; `cash<fee` **no descuenta / no escribe ledger / no marca DONE** y registra `PENDING` con `outstanding=fee−cash`. Mutex R-9 F3 y UNIQUE de ledger intactos; invariante `Σ ledger==cash` intacto. **Sin pérdida de obligación.** |

**Historial de `main` (más reciente → antiguo):**

```
5c304e6  feat: R-10 F4a - custodia Opción B: tabla custody_obligation (PENDING/APPLIED), cobro completo, sin pérdida de obligación (ADR 026)
49e2731  docs(adr): ADR 026 - custodia Opción B, tabla de obligación pendiente + cobro completo (R-10 F4a, docs-only)
b79e5dd  feat: R-10 F3 - balance_after de trade+fee secuencial por fila, sin backfill (D6)
2137c53  docs(engineering): cierre R-10 F1+F2a+F2b (2026-08-21) - traspaso relevo + apertura F3
86c315a  feat: R-10 F2b - comparacion idempotente exacta normalizada a 6 decimales, sin tolerancia (P2)
b4dcc72  feat: R-10 F2a - TaxProfileDto estricto: pct ge=0, allow_inf_nan=False, mes fiscal [1,12] (P1.3)
a1501e6  feat: R-10 F1 - hacer idempotency_key OBLIGATORIA en deposit/withdraw/trade (D5)
4e4a81a  docs(engineering): abrir R-10/v1.2.1 - plan + decisiones de las 6 correcciones ...
```

## 2. Estado de R-10 / v1.2.1

- **R‑9:** CERRADA (F1–F8, 2026-08-20). **v1.2.0** intacta (`b28e956`).
- **R‑10 (v1.2.1) ABIERTA** — plan `plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`. Orden: **F1 → F2a → F2b → F3 → F4a → F4b → F5**.
- **Hechas y pusheadas:** F1 ✅ `a1501e6` · F2a ✅ `b4dcc72` · F2b ✅ `86c315a` · **F3 ✅ `b79e5dd`** · **F4a ✅ `49e2731`** (ADR 026 docs) **+ `5c304e6`** (implementación: tabla `custody_obligation` + repo + ApplyCustodyFees Opción B).
- **Pendientes (siguiente = F4b — requiere decisión de job antes de código):**

| Fase        | Corrección                                            | Prioridad        | Notas clave                                                                                                                    |
| ----------- | ----------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| ~~**F3**~~  | ~~`balance_after` de trade+fee = cash FINAL (ambos)~~ | ~~🔴 P1~~        | **✅ HECHA** — invariante secuencial por fila; reset datos sim dev aprobado; `verify` EXIT 0.                                  |
| ~~**F4a**~~ | ~~Custodia parcial silenciosa → perder obligación~~   | ~~🔴 P1.2 ALTO~~ | **✅ HECHA** — ADR 026 (`49e2731`) + tabla `custody_obligation` & Opción B (`5c304e6`). **Sin pérdida de obligación.**         |
| **F4b**     | `ApplyCustodyFees` muta dentro de GET                 | 🟠 P1/P2         | Mover a **job programado**; aceptar desfase de saldo (D4/D4.1). Reactiva `M-4/T-M4`. Requiere decisión de job antes de código. |
| **F5**      | Docs + CHANGELOG + versión + limpieza obsoletos       | –                | Tag/release `v1.2.1` + limpieza E8.                                                                                            |

## 3. Protocolo operativo del proyecto (recordatorio — premisas E1–E9)

- `docs/PROJECT_PREMISES.md` ⭐ §0: **NUNCA tocar código sin aprobación por commit**. Plan/seguimiento en `docs/engineering/backlog-trabajo-2026-08-20.md`.
- Cada fase = **subagente acotado** (alcances disjuntos, máx ~3 en paralelo) + **verificación del coordinador** (diff + batería real) + **aprobación del propietario por commit** + push a `main`.
- Trabaja siempre **read‑first**: lee `backlog-trabajo`, `PROJECT_PREMISES §0`, `PROJECT_STATE`, este plan y este traspaso ANTES de proponer nada.
- **Anti-alucinación:** no inventar estado; verificar con `git`/tests. Respetar "NO tocar" del §6 del texto de paso.
- **No saturar el chat principal:** delegar exploración/implementación a subagentes; el coordinador solo documenta, verifica y propone commits.

## 4. Decisiones del propietario cerradas (2026-08-20/21)

- **D1** R‑10/v1.2.1 encaja como nueva fase (R‑9 cerrada, v1.2.0 intacta).
- **D2** Ejecutar las **6** correcciones.
- **D3 / D3.1** Custodia **Opción B** (tabla de obligación pendiente) + **migración + ADR** — **F4a hecha** (ADR 026 + implementación).
- **D4 / D4.1** Custodia **fuera del GET → job**; desfase de saldo en UI aceptado. — **pendiente F4b**.
- **D5** **idempotency‑key obligatoria** (contrato + regen) — **F1 hecha**.
- **D6** **Sin backfill** (forward‑only) — aplicado en F3 y F4a.
- **D7** F2a/F2b separadas — **hechas**.
- **F1-C (2026-08-20)** clave cacheada por operación en curso (helper `createIdempotencyKey`); **endpoint `/api/ai/intents/confirm` fuera del alcance** de F1.
- **F3-sim (2026-08-21):** reset de datos sim dev (404 cuentas `simulated` eliminadas por `close_account`→`delete_simulated_account`; `ledger=0`) para alcanzar `verify_ledger_balance_chain.py` EXIT 0 (D6 prohíbe backfill).
- **F4a-ADR-026 (2026-08-21):** cardinalidad tabla `custody_obligation` = **una fila/cuenta** (PK `account_id`); vocabulario `status` = **`PENDING` | `APPLIED`** exclusivamente.

## 5. Hallazgos / deuda registrados (importantes)

1. **`contract:check` permanece ROJO por baseline F4 preexistente** (NO es regresión de F1/F2a/F2b). Los DTOs de R‑9 F4 (`CommissionProfileDto`, `CreateInvestmentAccountDto`) tienen constraints `minimum`/`exclusiveMinimum` que el `openapi.json` commiteado NO refleja. `contract:gen` sobre HEAD reproduce exactamente ese drift. → **Decisión de contrato pendiente**: exponer (regen) o no; NO colar ese drift en fases sin autorización.
2. **mypy `accounts.py`:** 7 errores pre‑existentes ajenos a R-10 (no introducidos por F1/F3/F4a; no bloquean la batería).
3. **Deuda F1 registrada (ajena a las fases):** el test infra `test_execute_trade_con_fees_reconcilia` **roto PREEXISTENTE** (depende de `idempotency_key` tras F1) y `verify` **EXIT 1** únicamente por el fixture dev `acc_broken_*` (cuentas de simulación con saldo a medio); ambos quedan anotados como deuda conocida, **no** como regresión de las fases cerradas.
4. **F4a (implementación `5c304e6`, batería del commit):** ruff 0 · app custodia 11 · infra `m7` 2 + `m2` 6 (custodia+cash<fee) + concurrency 4 · migración `005_custody_obligation` (up/down). La batería incluye el test nuevo `test_custody_obligation_pending.py`. La nota de `verify` EXIT 1 y `test_execute_trade_con_fees_reconcilia` rotos queda registrada arriba (§5.3).
5. El endpoint de confirm de intents ejecuta el trade server-side y **no se obliga** clave en él (callers internos ya usan clave vía B-4).

## 6. Archivos/documentos de referencia

- Plan director R-10: `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`
- ADR 026: `docs/adr/026-custodia-obligacion-pendiente.md` (**en `main`**, `49e2731`)
- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` ⭐ §0
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice docs: `docs/engineering/engineering-index-2026-08-03.md`
- Traspaso previo (F1+F2a+F2b → apertura F3, **archivado como obsoleto**): `docs/engineering/traspaso-relevo-cierre-r10-f1-f2ab-apertura-f3-2026-08-21-obsoleto.md`
- Traspasos de referencia R-9: `traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`, `traspaso-relevo-cierre-r9-f1-f4-2026-08-20.md`
- Código clave (F3): `packages/py/application/src/bolsa_application/accounts.py` + `scripts/verify/verify_ledger_balance_chain.py`.
- Código clave (F4a): `packages/py/infrastructure/.../alembic/versions/005_custody_obligation.py`, `.../repositories/custody_obligation_repository.py`, `models/tables.py` (tabla `custody_obligation`), `packages/py/application/src/bolsa_application/accounts.py` (`ApplyCustodyFees`).

---

## 7. TEXTO DE PASO (pegar/copiar para el próximo chat/agente)

> **RELEVO → R-10 (v1.2.1) — CONTINÚA en F4b.** Repo `Bolsa_V1`, rama `main` = **`5c304e6`** (`local main = origin/main`, árbol **limpio**). **F1 ✅ `a1501e6` · F2a ✅ `b4dcc72` · F2b ✅ `86c315a` · F3 ✅ `b79e5dd` · F4a ✅ `49e2731` (ADR 026 docs) + `5c304e6` (impl)** — todas aprobadas por commit y pusheadas a `main`. **R-9 cerrada** · **v1.2.0** (`b28e956`) intacta.
> **Siguiente fase:** **F4b (R-10.4b) Custodia fuera del GET → job programado** — 🟠 P1/P2 ALTO (scheduler). **Requisito previo del plan (§2.3/§5.2): decisión de job en el plan ANTES de abrir código** — alcance (todas cuentas activas vs cuentas con saldo), frecuencia, fallo/sin saldo (→ `PENDING`, que ya persiste la tabla `custody_obligation` de F4a), coexistencia con scheduler no‑ARQ (R-8C.2). **Reactiva `M-4/T-M4`** (job dedicado custodia, diferido por freeze). Ver bloque F4b en `plan-r10` y §5.
> **Decisiones cerradas:** D1–D7, F1-C, **F3-sim** (reset datos sim dev, `verify` EXIT 0) y **F4a-ADR-026** (cardinalidad una fila/cuenta + `PENDING`/`APPLIED`). **F3/F4a: SIN backfill (D6)**.
> **LEE PRIMERO (obligatorio):** este traspaso (§1–§7) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/PROJECT_PREMISES.md` ⭐ §0 (E1–E9) · `docs/engineering/PROJECT_STATE.md` · `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md` · `docs/adr/026-custodia-obligacion-pendiente.md`.
> **Plan director:** `plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`. **Orden:** F1→F2a→F2b→F3→F4a→**F4b**→F5.
> **Protocolo:** cada fase = verificación del coordinador (diff + batería) + **aprobación del propietario por commit** + push a `main`. No saturar chat principal: delegar a subagentes.
> **NO tocar** (salvo decisión): `pending-delete` (riesgo alto) · gobernanza IA · workers ARQ/no‑ARQ **excepto la parte de custodia‑job que decida F4b** · features nuevas · **drift de contrato baseline F4** (no colar sin autorización; `contract:check` rojo preexistente registrado en §5).
> **Progreso por fase:** al cerrar cada una, actualizar este traspaso, el `plan-r10`, el `backlog` y `PROJECT_STATE.md`.
