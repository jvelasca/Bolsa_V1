# RELEVO / TRASPASO — Fase 0 Decision Spine · cierre F0.6b (Decision Board v1, backend) → apertura UI web (sub-rebanada)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** de la **UI web del Decision Board**, fase **NO APROBADA** aún. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Tramo docs COMPLETO** · **F0.5a métrica decidida** · **F0.5b PortfolioFit v1 CERRADA** · **F0.6a fuente decidida (Decision Board)** · **F0.6b Decision Board v1 (backend) CERRADA** · **UI web SIN aprobar**.
> **SHA al cerrar este hilo:** `git log -1 --format=%H` = `8df8a65` (feat(f0-6b)). Working tree puede tener docs Fase 0 sin commit.

---

## 1. Qué está hecho (no reabrir)

- **F0.1 AS-IS · F0.2 TO-BE · F0.3 Mapping · F0.4 Descarga** — docs COMPLETOS (verificado VERDE). D1 aceptada: risk de cesta SEMI=AUTO sin override.
- **F0.5a — MÉTRICA de encaje DECIDIDA** — concentración de cesta por **activo** y por **sector**, comportamiento **VETO** (fail-closed). Sector desde DB (`instruments.sector`) vía JOIN.
- **F0.5b — PortfolioFit v1 CERRADO (commit `3670a09`):** `compute_portfolio_fit` (as-if fill) · `Position.sector` · regla **`MaxSectorExposure`** (antes sin evaluar) + `MaxConcentration` a nivel cesta · cableado `execution_router`→`check_opening`. Batería 31 · ruff 0 · mypy 0 · verificador APROBADO.
- **F0.6a — FUENTE de la vista Daily DECIDIDA por el propietario (2026-08-24):**
  - La vista Daily = **Decision Board** (tablero de ACCIÓN): qué está pendiente de decidir (colas SEMI_F3 por confirmar, AUTO en espera/vetado, dictamen) + **estado de cada gate** (PASS/VETO). Solo lectura, sin orquestador (F0.2 §4, F0.3 no-op `DailyOrchestrator`).
- **F0.6b — Decision Board v1 CERRADO** (commit `8df8a65`, **backend-only**, UI fuera de alcance por decisión del propietario):
  - **Nuevo** `packages/py/application/src/bolsa_application/decision_board.py` — use-case **`GetDecisionBoard`** (solo lectura, no muta, no ejeccuta ExecuteTrade ni crea orquestador).
    - `extract_gate_outcome(payload)` (`:25`): lee `compliance_check`/`complianceCheck`/`runtime.decisionPackage.complianceCheck` (caso `propose`) y, si no resultó en `passed`, cae al fallback `policyGate`/`policy_gate` top-level via `_resolve_policy_gate` (`:94`) — cubre los shapes reales de las sesiones AUTO del hot-path (`allowed`, `gate.passed`, `riskEngine.verdict`, `riskEngine.allowed`).
    - `_classify_session(status, gate)` (`:180`): `status` en {`open`,`pending`}; gate `VETO`→`vetoed`, `DEFERRED`→`deferred`, resto→`auto_waiting`; fuera de {`open`,`pending`}→`None` (decidida, no cuenta).
    - Buckets `pendingConfirm/vetoed/deferred/autoWaiting` + cola SEMI_F3 (`supervised_f3.get().queue`) + `decisionSessions` recientes.
  - **Endpoint** `GET /accounts/{account_id}/decision-board` (`apps/api-python/src/bolsa_api/api/v1/routes/accounts.py:293`) + DTOs (`schemas/accounts.py:352`), dependency `get_decision_board_use_case` (`dependencies.py:421`).
  - **Batería 22 passed** (17 board incl. H-1 corregido + 3 API + 2 daily regression) · **ruff 0** · **mypy 0**.
  - **Ciclo de verificación en 2 etapas:** verificador read-only independiente → detectó **H-1 (severidad ALTA)**: `extract_gate_outcome` no leía `policyGate` top-level de las sesiones AUTO del hot-path (persisten el gate con `runtime=None`), por lo que los VETO de AUTO caerían a `auto_waiting` y el bucket `vetoed` quedaría en 0. Corregido (fallback `policyGate` + `_resolve_policy_gate` + 6 tests) → **re-verificador APROBADO sin hallazgos residuales**.
  - 2 fallos pre-existentes confirmados ajenos a F0.6b: (a) `test_list_account_summaries_one_summary_per_account` — `TypeError` `owner_user_id` en un fake de `accounts/summary.py`; (b) test de integración con DB (404 `investor-profiles`, requiere Postgres).

## 2. Decisiones tomadas / pendientes

| Id          | Decisión                                                                                                                                  | Estado                                  |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **D1**      | Risk de cesta (`check_opening`) aplica **igual** en SEMI y AUTO, **sin override** humano.                                                 | ✅ **ACEPTADA** (2026-08-24)            |
| **D0-fase** | F0.5 (Fit código) **APROBADA para abrir** · F0.6 (Daily vista) backend **CERRADA** · UI web **NO**.                                       | ✅ F0.5 CERRADA · F0.6b CERRADA · UI ⏳ |
| **F0.5a**   | Métrica de encaje = **concentración de cesta por activo y por sector**, comportamiento **VETO**, sector desde DB.                         | ✅ **DECIDIDA** (2026-08-24)            |
| **F0.6a**   | Fuente de la vista Daily = **Decision Board** (tablero de acción: colas pendientes + estado de cada gate), solo lectura, sin orquestador. | ✅ **DECIDIDA** (2026-08-24)            |
| **F0.6b**   | Alcance de la rebanada = **solo backend** (use-case + endpoint + DTO + tests). UI web deliberadamente **fuera** de esta rebanada.         | ✅ **CERRADA** (2026-08-24)             |
| **D2**      | Autoridad = `DecisionPackage` (contrato) vs `Recommendation` (cara operativa).                                                            | ⏳ recomendada (a) — confirmar          |
| **D3**      | Lab/Radar **fuera** del spine (ADR-019).                                                                                                  | ⏳ recomendada (a) — confirmar          |

## ⚠️ Instrucción para el nuevo chat (no repetir el tropiezo)

**La UI web del Decision Board está SIN aprobar.** El agente NO debe abrir código ni lanzar subagentes de implementación hasta que el propietario **apruebe la fase** (premisa E1) y confirme el **alcance de la UI** (qué pantallas/acciones, y si es solo lectura o incluye acción de confirmar SEMI). La UI **consume el endpoint ya existente** `GET /accounts/{account_id}/decision-board`; NO debe reinventar el agregador ni abrir un orquestador. **Reusar los estilos/patrones del hub web existente** (apps/web u otro) — consultar el index/estado del front antes de crear componentes.

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.
- El backend F0.6b ya cerrado: **no reescribir** `decision_board.py` ni el endpoint salvo que la UI exponga un hueco real.

## 4. Tarea del siguiente chat (UI web — SIN aprobar aún)

**PASO 0 (obligatorio, sin código):** que el propietario **apruebe la fase UI web** y **defina el alcance** (pantallas, si incluye acción de confirmar SEMI_F3 o es solo lectura). El agente solo presenta opciones ancladas al endpoint real. NO abrir código antes.

**Después (con fase aprobada):** construir la **UI de solo lectura** del Decision Board que consume `GET /accounts/{account_id}/decision-board`, una rebanada acotada, path:line verificado, batería, aprobación antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo de la UI)

```
CONTEXTO: Fase 0 Decision Spine. F0.1–F0.4 docs CERRADOS. F0.5a métrica decidida
(concentración cesta activo+sector, VETO). F0.5b PortfolioFit v1 CERRADA (3670a09).
F0.6a fuente decidida (Decision Board: colas pendientes + gates). F0.6b Decision Board
v1 CERRADA (8df8a65, backend: endpoint GET /accounts/{id}/decision-board).
UI web PENDIENTE y NO APROBADA — read-only, no abrir código ni subagentes de impl hasta aprobar.
LEE: docs/engineering/traspaso-relevo-f0-6b-cierre-apertura-ui-2026-08-24.md
+ backlog §0 + PROJECT_STATE §2b + PROJECT_PREMISES ⭐§0
+ packages/py/application/src/bolsa_application/decision_board.py (use-case, referencia)
+ la ruta GET /accounts/{id}/decision-board en apps/api-python.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.
D1 aceptada: risk de cesta SEMI=AUTO, sin override. D2/D3 a confirmar si aplican.

TAREA: PRIMERO → aprobación de fase UI + definición de alcance (pantallas/acciones).
NO lanzo agentes ni código hasta aprobar.
DESPUÉS → UI de solo lectura del Decision Board consumiendo el endpoint, una rebanada,
path:line verificado, batería, aprobación antes de commit.
NO REESCRIBIR el backend F0.6b ni abrir orquestador.
NO TOCAR: money, IA, contract:gen, Track B, pending-delete, ExecuteTrade internals.
Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería, aprobación del propietario antes de commit.
```
