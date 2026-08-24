# RELEVO / TRASPASO — Fase 0 Decision Spine · cierre F0.6 (Decision Board COMPLETA) → apertura fase siguiente

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** de la **siguiente fase**. La Fase 0 Decision Spine queda **COMPLETA** (documentación F0.1–F0.4 + código PortfolioFit F0.5b + Decision Board F0.6 backend y UI). La fase siguiente **la decide el propietario** a partir del backlog. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **F0.1–F0.4 docs COMPLETOS** · **F0.5a métrica decidida** · **F0.5b PortfolioFit v1 CERRADA** · **F0.6a fuente decidida (Decision Board)** · **F0.6b (backend) CERRADA** · **F0.6-UI (web) CERRADA** · **Fase 0 Decision Spine COMPLETA** · **D2 CERRADA con código** (`f7b1f6c`, DecisionPackage = contrato en confirm SEMI).
> **SHA al cerrar este hilo:** `git log -1 --format=%H` = `f7b1f6c`. Working tree limpio.

---

## 1. Qué está hecho (no reabrir)

- **F0.1 AS-IS · F0.2 TO-BE · F0.3 Mapping · F0.4 Descarga** — docs COMPLETOS (verificado VERDE). **D1** aceptada: risk de cesta SEMI=AUTO sin override.
- **F0.5a — MÉTRICA de encaje DECIDIDA** — concentración de cesta por **activo** y por **sector**, comportamiento **VETO** (fail-closed). Sector desde DB (`instruments.sector`) vía JOIN.
- **F0.5b — PortfolioFit v1 CERRADO (commit `3670a09`):** `compute_portfolio_fit` (as-if fill) · `Position.sector` · regla **`MaxSectorExposure`** + `MaxConcentration` a nivel cesta · cableado `execution_router`→`check_opening`. Batería 31 · ruff 0 · mypy 0 · verificador APROBADO.
- **F0.6a — FUENTE de la vista Daily DECIDIDA = Decision Board** (tablero de acción: qué está pendiente de decidir + estado de cada gate). Solo lectura, sin orquestador.
- **F0.6b — Decision Board v1 (backend) CERRADO (commit `8df8a65`):** use-case `GetDecisionBoard` (`decision_board.py`, solo lectura) con `extract_gate_outcome`/`_resolve_policy_gate` (lee `compliance_check` para `propose` y `policyGate` top-level para sesiones AUTO del hot-path) · `_classify_session` · buckets `pendingConfirm/vetoed/deferred/autoWaiting` + cola SEMI_F3. Endpoint `GET /accounts/{account_id}/decision-board` + DTOs. Verificación en 2 ciclos (H-1 corregido → re-verificador APROBADO). Batería 22.
- **F0.6-UI — Decision Board web CERRADA (commit `672e88f`):** página `/decision-board` (`apps/web/src/features/decision-board/`) solo lectura: cards de buckets, cola SEMI_F3 y decision sessions con badge de gate (PASS/VETO/DEFERRED/unknown). `getDecisionBoard` en `api.ts` (`call<DecisionBoardResponseV1>`) · tipo `DecisionBoardV1` en `@bolsa/shared` · ruta `app.tsx` + NavLink `app-top-bar.tsx` + `HERRAMIENTAS_NAV_ORDER` · **contract:gen pactado** (regenera schema + sync aditivo del backend ya mergeado: `/api/auth/refresh`, `login`, logout desc — verificado `auth.py:36/153/186`, no invención). Verificación: 13 tests UI · `tsc -b` 0 · lint 0 · verificador read-only APROBADO (1 hallazgo medio corregido).
- **Fase 0 Decision Spine COMPLETA**: documentación (F0.1–F0.4) + encaje de cesta en risk (F0.5b) + vista de acción del spine en web (F0.6 backend + UI) + **D2 cerrada** (DecisionPackage = contrato en el confirm SEMI, commit `f7b1f6c`). Todo pusheado a `main`.

## 2. Decisiones tomadas / pendientes

| Id          | Decisión                                                                                                                                                                                                                                                                                                                                                                                                      | Estado                                  |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| **D1**      | Risk de cesta (`check_opening`) aplica **igual** en SEMI y AUTO, **sin override** humano.                                                                                                                                                                                                                                                                                                                     | ✅ **ACEPTADA** (2026-08-24)            |
| **D0-fase** | F0.5 (Fit código) APROBADA · F0.6 (Daily vista) **backend + UI APROBADAS y CERRADAS**.                                                                                                                                                                                                                                                                                                                        | ✅ F0.5 CERRADA · **F0.6 COMPLETA**     |
| **F0.5a**   | Métrica de encaje = **concentración de cesta por activo y por sector**, VETO, sector desde DB.                                                                                                                                                                                                                                                                                                                | ✅ **DECIDIDA** (2026-08-24)            |
| **F0.6a**   | Fuente de la vista Daily = **Decision Board** (tablero de acción: colas pendientes + estado de cada gate), solo lectura, sin orquestador.                                                                                                                                                                                                                                                                     | ✅ **DECIDIDA** (2026-08-24)            |
| **D2**      | Autoridad = **`DecisionPackage`** (contrato) vs `Recommendation` (cara operativa). **CERRADA con código**: en el confirm SEMI con `execute=True`, el package de la sesión `propose` es la fuente de verdad → fail-closed si la identidad (acción+instrumento) diverge; visibilidad `contract` (present_verified/absent) cuando no hay sesión. No exige `session_id`, no toca sizing humano. Commit `f7b1f6c`. | ✅ **CERRADA** (2026-08-24) **f7b1f6c** |
| **D3**      | Lab/Radar **fuera** del spine (ADR-019).                                                                                                                                                                                                                                                                                                                                                                      | ⏳ recomendada (a) — confirmar          |

> **Fase 0 Decision Spine COMPLETA.** **D2 CERRADA con código** (`f7b1f6c`, DecisionPackage = contrato en confirm SEMI). Queda **D3** pendiente de confirmación del propietario (no bloquea). **Deuda diferida por esta rebanada (fuera de D2, candidata a Escalón 3 / D1):** re-evaluar gate/risk en el confirm SEMI (hoy solo se concilia identidad, no se re-ejecuta el gate ni el risk de cesta) — el `wait` confirmado sin sesión ejecutaría un sell default, y `reduce`/`exit_hint` no distinguen cerrar de abrir short. La **siguiente fase** del proyecto la decide el propietario (ver §4).

## ⚠️ Instrucción para el nuevo chat (no repetir el tropiezo)

**La siguiente fase está SIN aprobar.** El agente NO debe abrir código ni lanzar subagentes de implementación hasta que el propietario **apruebe la fase** (premisa E1) y **defina el alcance/decisiones bloqueantes** (p. ej. D2/D3). PASO 0 siempre: **read-first** del `backlog §0` + `PROJECT_STATE.md` + `PROJECT_PREMISES ⭐§0`, presentar opciones ancladas al código, esperar decisión. NO reabrir F0.5/F0.6 (cerradas y pusheadas).

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.
- F0.5b (PortfolioFit) y F0.6 (Decision Board) ya cerrados y pusheados: NO reescribir salvo fase pactada que exponga un hueco real.

## 4. Tarea del siguiente chat (fase nueva — SIN aprobar)

**PASO 0 (obligatorio, sin código):** que el propietario decida **qué fase sigue** y apruebe (con decisiones bloqueantes D2/D3 resueltas si aplican). El agente solo presenta opciones ancladas al backlog y espera decisión. NO abrir código antes.

**Después (con fase aprobada):** implementar la rebanada acordada, una a la vez, path:line verificado, batería, aprobación antes de commit.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: Fase 0 Decision Spine CERRADA. F0.1-F0.4 docs + F0.5a metrica decidida +
F0.5b PortfolioFit v1 (3670a09) + F0.6 Decision Board COMPLETA: backend (8df8a65,
endpoint GET /accounts/{id}/decision-board) + UI (672e88f, /decision-board).
D1 aceptada (risk cesta SEMI=AUTO sin override). D2 CERRADA con codigo (f7b1f6c:
DecisionPackage = contrato en confirm SEMI, fail-closed identidad + contract; deuda
diferida: gate/risk en SEMI, wait-sin-sesion, reduce/exit). D3 a confirmar.
LEE: docs/engineering/traspaso-relevo-f0-6-cierre-apertura-siguiente-2026-08-24.md
+ backlog §0 + PROJECT_STATE §3 + PROJECT_PREMISES ⭐§0.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.

TAREA: PRIMERO → el propietario decide QUE FASE SIGUE y la aprueba (D3 a confirmar;
candidata Escalón 3/D1 = re-evaluar gate/risk en confirm SEMI). NO lanzo agentes ni
código hasta aprobar.
DESPUÉS → rebanada acotada, path:line verificado, batería, aprobación antes de commit.
NO TOCAR: money, IA, contract:gen salvo fase pactada, Track B, pending-delete, ExecuteTrade internals.
NO REABRIR F0.5/F0.6/F0.6-UI (cerradas y pusheadas). D2 ya commiteada (no rehacer).
Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería, aprobación del propietario antes de commit.
```
