# (ARCHIVADO/OBSOLETO) — R-10: F3 implementada + verificada (pendiente commit) — apertura F4a (2026-08-21)

> **ESTADO: OBSOLETO.** Este traspaso de apertura de F3 queda **archivado** — F3 (`b79e5dd`), F4a (`49e2731` + `5c304e6`) están **HECHAS y pusheadas**, y el relevo activo es `traspaso-relevo-cierre-r10-f3-f4a-apertura-f4b-2026-08-21.md`. El contenido histórico (header de estado, notas F3) se conserva solo por trazabilidad. Sujétese al nuevo traspaso y al backlog para el estado real.
>
> **Tipo:** Relevo de cierre de chat/día. Leer PRIMERO junto al **texto de paso** (§7) para que un nuevo agente / nuevo chat continúe **sin perder contexto**.
> **Repos:** `Bolsa_V1` (monorepo).
> **Firma del estado (verificada, no adivinada):** `git branch --show-current` = `main` · `HEAD` = **`86c315a`** (`origin/main` al anterior cierre) · **árbol de trabajo con cambios F3 sin commitear** (4 ficheros código/test/verify + 3 docs) · sin tag en HEAD.

---

## 1. Qué se ha hecho hoy (2026-08-21)

Conforme al **plan director** `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md` (6 correcciones P1/P2 de la **auditoría externa post‑v1.2.0**), se completaron y pusheron **3 fases** (F1/F2a/F2b) y se **implementó+verificó F3** (pendiente commit). Cada fase: **verificación del coordinador (diff + batería)** → **aprobación del propietario por commit** → **push a `main`**.

| Fase    | Corrección                                                  | Prioridad | Commit               | Descripción breve                                                                                                                                                                                                                                                                   |
| ------- | ----------------------------------------------------------- | --------- | -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1**  | `idempotency_key` **OBLIGATORIA** en deposit/withdraw/trade | P2        | `a1501e6`            | DTOs + firma de use-case requieren la key (sin default); web genera y cachea la key por operación (estrategia C, helper `createIdempotencyKey`). POST sin clave → **422**.                                                                                                          |
| **F2a** | `TaxProfileDto` estricto                                    | P1.3      | `b4dcc72`            | `ge=0` + `allow_inf_nan=False` en los 3 pct; `fiscal_year_start_month ∈ [1,12]` (`model_validator`). Wire intacto.                                                                                                                                                                  |
| **F2b** | Comparación idempotente **exacta** (sin tolerancia `0.01`)  | P2        | `86c315a`            | `_cash_payload_matches`/`_trade_payload_matches` comparan por `==` normalizado a 6 decimales (`Decimal(str(x)).quantize(0.000001)`). Diferencia sub‑céntimo → 409/conflicto; valores iguales → replay.                                                                              |
| **F3**  | `balance_after` trade+fee **secuencial** (sin backfill D6)  | 🔴 P1     | _(pendiente commit)_ | Captura `cash_before` antes de mutar; `trade_balance=cash_before+amount`, `fee_balance=trade_balance−fees`. Verify+tests a invariante secuencial por fila. **Reset datos sim dev** (decisión propietario) → `verify` EXIT 0. Verificado: smock `buy`→`fee` 105000→104000→103996.79. |

**Historial de `main` (más reciente → antiguo):**

```
86c315a  feat: R-10 F2b - comparacion idempotente exacta normalizada a 6 decimales, sin tolerancia (P2)
b4dcc72  feat: R-10 F2a - TaxProfileDto estricto: pct ge=0, allow_inf_nan=False, mes fiscal [1,12] (P1.3)
a1501e6  feat: R-10 F1 - hacer idempotency_key OBLIGATORIA en deposit/withdraw/trade (D5)
4e4a81a  docs(engineering): abrir R-10/v1.2.1 - plan + decisiones de las 6 correcciones ...
0de43ec  docs: registrar release notes v1.2.0 + rellenar entrada v1.1.0 en CHANGELOG
b28e956  v1.2.0 (tag) / HEAD auditado por la externa
```

## 2. Estado de R-10 / v1.2.1

- **R‑9:** CERRADA (F1–F8, 2026-08-20). **v1.2.0** intacta (`b28e956`).
- **R‑10 (v1.2.1) ABIERTA** — plan `plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`. Orden: **F1 → F2a → F2b → F3 → F4a → F4b → F5**.
- **Hechas y pusheadas:** F1 ✅ · F2a ✅ · F2b ✅. **F3 ✅ implementada + verificada (pendiente commit/aprobación).**
- **Pendientes (siguiente = F4a — requiere ADR + decisión antes de código):**

| Fase       | Corrección                                                               | Prioridad    | Notas clave                                                                                                                |
| ---------- | ------------------------------------------------------------------------ | ------------ | -------------------------------------------------------------------------------------------------------------------------- |
| ~~**F3**~~ | ~~`balance_after` de trade+fee = cash FINAL (ambos)~~                    | ~~🔴 P1~~    | **✅ HECHA** — invariante secuencial por fila; reset datos sim dev aprobado; `verify` EXIT 0. Pendiente commit.            |
| **F4a**    | Custodia parcial silenciosa con `allow_partial=True` → perder obligación | 🔴 P1.2 ALTO | **Opción B** (tabla/estado de obligación pendiente) → requiere **migración + ADR** (decisión propietario antes de código). |
| **F4b**    | `ApplyCustodyFees` muta dentro de GET                                    | 🟠 P1/P2     | Mover a **job programado**; aceptar desfase de saldo (D4/D4.1). Reactiva `M-4/T-M4`.                                       |
| **F5**     | Docs + CHANGELOG + versión + limpieza obsoletos                          | –            | Tag/release `v1.2.1` + limpieza E8.                                                                                        |

## 3. Protocolo operativo del proyecto (recordatorio — premisas E1–E9)

- `docs/PROJECT_PREMISES.md` ⭐ §0: **NUNCA tocar código sin aprobación por commit**. Plan/seguimiento en `docs/engineering/backlog-trabajo-2026-08-20.md`.
- Cada fase = **subagente acotado** (alcances disjuntos, máx ~3 en paralelo) + **verificación del coordinador** (diff + batería real) + **aprobación del propietario por commit** + push a `main`.
- Trabaja siempre **read‑first**: lee `backlog-trabajo`, `PROJECT_PREMISES §0`, `PROJECT_STATE`, este plan y este traspaso ANTES de proponer nada.
- **Anti-alucinación:** no inventar estado; verificar con `git`/tests. Respetar "NO tocar" del §6 del texto de paso.
- **No saturar el chat principal:** delegar exploración/implementación a subagentes; el coordinador solo documenta, verifica y propone commits.

## 4. Decisiones del propietario cerradas (2026-08-20)

- **D1** R‑10/v1.2.1 encaja como nueva fase (R‑9 cerrada, v1.2.0 intacta).
- **D2** Ejecutar las **6** correcciones.
- **D3 / D3.1** Custodia **Opción B** (tabla de obligación pendiente) + **migración + ADR**.
- **D4 / D4.1** Custodia **fuera del GET → job**; desfase de saldo en UI aceptado.
- **D5** **idempotency‑key obligatoria** (contrato + regen) — **F1 hecha**.
- **D6** **Sin backfill** (forward‑only).
- **D7** F2a/F2b separadas — **hechas**.
- **F1-C (2026-08-20)** clave cacheada por operación en curso (helper `createIdempotencyKey`); **endpoint `/api/ai/intents/confirm` fuera del alcance** de F1.

## 5. Hallazgos / deuda registrados (importantes)

1. **`contract:check` permanece ROJO por baseline F4 preexistente** (NO es regresión de F1/F2a/F2b). Los DTOs de R‑9 F4 (`CommissionProfileDto`, `CreateInvestmentAccountDto`) tienen constraints `minimum`/`exclusiveMinimum` que el `openapi.json` commiteado NO refleja. `contract:gen` sobre HEAD reproduce exactamente ese drift. → **Decisión de contrato pendiente**: exponer (regen) o no; se documentó en el plan (`plan-r10` bloque F1, nota de contrato). **NO colar ese drift en fases sin autorización.**
2. **mypy `accounts.py`:** 7 errores pre‑existentes (líneas 37,67,105,118,568,861,899) ajenos a F1/F2b. No introducidos por R-10; no bloquean la batería.
3. **F1:** `openapi.json`/`schema.d.ts` regen acotada (solo `idempotencyKey` requerido en los 3 DTOs); `idempotency-key.ts` en `@bolsa/shared`.
4. El endpoint de confirm de intents ejecuta el trade server-side y **no se obliga** clave en él (callers internos ya usan clave vía B-4).

## 6. Archivos/documentos de referencia

- Plan director R-10: `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`
- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` ⭐ §0
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Índice docs: `docs/engineering/engineering-index-2026-08-03.md`
- Traspasos previos: `traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`, `traspaso-relevo-cierre-r9-f1-f4-2026-08-20.md`
- Código clave (F2b): `packages/py/application/src/bolsa_application/accounts.py` (`_cash_payload_matches` ~:281, `_trade_payload_matches` ~:326); tests `test_idempotency_reused.py`.
- Verificación de invariante (F3): `scripts/verify/verify_ledger_balance_chain.py` y `verify_account_isolation.py`.

---

## 7. TEXTO DE PASO (pegar/copiar para el próximo chat/agente)

> **RELEVO → R-10 (v1.2.1) — CONTINÚA en F4a.** Repo `Bolsa_V1`, rama `main`. **F1✅ `a1501e6` · F2a✅ `b4dcc72` · F2b✅ `86c315a`** pusheados. **F3 ✅ implementada y verificada — PENDIENTE aprobación de commit por el propietario** (árbol de trabajo con 4 ficheros: `accounts.py`, `test_concurrency_scenarios.py`, `test_r8c_ledger_balance_atomic.py`, `verify_ledger_balance_chain.py` + docs backlog/plan/traspaso). **R-9 cerrada** · **v1.2.0** (`b28e956`) intacta.
> **Siguiente fase:** **F4a (R-10.4a) Custodia Opción B — obligación pendiente + cobro completo** — 🔴 P1.2 ALTO. **Requisito previo del plan (§2.3/§5.2): ADR + diseño en plan + decisión explícita del propietario ANTES de abrir código** (migración Alembic + tabla de obligación). Ver bloque F4a en `plan-r10`.
> **Decisión cerrada F3 (2026-08-21):** reset de datos sim dev (404 cuentas `simulated` eliminadas por `close_account`→`delete_simulated_account`) para alcanzar `verify_ledger_balance_chain.py` EXIT 0 — porque D6 prohíbe backfill y las filas históricas trade+fee (semántica antigua) no cumplen el invariante secuencial. **Si se reasemejan cuentas históricas con la semántica antigua, `verify` volverá a marcarlas.**
> **LEE PRIMERO (obligatorio):** este traspaso (§1–§7) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/PROJECT_PREMISES.md` ⭐ §0 (E1–E9) · `docs/engineering/PROJECT_STATE.md` · `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`.
> **Plan director:** `plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`. **Orden:** F1→F2a→F2b→F3→**F4a**→F4b→F5.
> **Protocolo:** cada fase = verificación del coordinador (diff + batería) + **aprobación del propietario por commit** + push a `main`. No saturar chat principal: delegar a subagentes.
> **Decisiones cerradas:** D1–D7, F1-C (ver §4) y **F3-sim**. **F3: SIN backfill (D6)**.
> **NO tocar** (salvo decisión): `pending-delete` (riesgo alto) · gobernanza IA · workers ARQ/no‑ARQ excepto la parte de custodia‑job que decida F4b · features nuevas · **drift de contrato baseline F4** (no colar sin autorización; `contract:check` rojo preexistente registrado en §5).
> **Progreso por fase:** al cerrar cada una, actualizar este traspaso, el `plan-r10` y el `backlog`.
