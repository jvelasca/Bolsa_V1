# RELEVO / TRASPASO — Fase 0 Decision Spine · cierre F0.5b (PortfolioFit v1) → apertura F0.6 (Daily vista)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** de **F0.6 (Daily vista)**, fase **NO APROBADA** aún. Read-first antes de escribir código.
> **AsOf cierre:** 2026-08-24. **Tramo docs COMPLETO** · **F0.5a métrica decidida** · **F0.5b PortfolioFit v1 CERRADA** · **F0.6 sigue sin aprobar**.
> **SHA al cerrar este hilo:** `git log -1 --format=%H` = `3670a09` (feat(f0-5b)). Working tree puede tener docs Fase 0 sin commit (inventario F0.1–F0.4 + este relevo).

---

## 1. Qué está hecho (no reabrir)

- **F0.1 AS-IS · F0.2 TO-BE · F0.3 Mapping · F0.4 Descarga** — docs COMPLETOS (verificado VERDE). D1 aceptada: risk de cesta SEMI=AUTO sin override.
- **F0.5a — METRICA de encaje DECIDIDA por el propietario (2026-08-24):**
  - Métrica = **concentración de cesta** evaluada a dos niveles: peso por **ACTIVO** y peso por **SECTOR**.
  - Comportamiento = **VETO (fail-closed)**: si la apertura propuesta hace que el peso de un activo o un sector supere el límite de policy, el Risk DENY.
  - Sector resuelto desde **DB** (`instruments.sector`) vía JOIN.
- **F0.5b — PortfolioFit v1 IMPLEMENTADO y CERRADO (commit `3670a09`):**
  - **Nuevo** `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_fit.py` — función pura `compute_portfolio_fit` (as-if fill, agrupa por activo y sector, sectores `None` bajo `<unknown>`, no_falso-VETO si denominador no positivo).
  - **`Position`** gana campo `sector` (desde `instruments.sector` en `get_summary`).
  - **Regla `MaxSectorExposure` NUEVA** evaluada (`policy_gate.py`) — antes `max_sector_exposure_pct` estaba configurado pero **nunca se evaluaba**.
  - **`MaxConcentration` extendida a nivel cesta** (mantiene fallback por-trade si no hay datos de cesta).
  - Cableado `execution_router.py` (paper_auto `:560` + live `:821`) → `check_opening` (params `portfolio_positions`/`proposal_sector`) → guard → `ProposedTradeContext` → `policy_gate`.
  - **Batería:** 7 (pure fit) + 3 (risk fit) + 3 (risk) + 15/18 (regresión) = batería total **31 passed** · **ruff 0** · **mypy 0**.
  - **Verificador read-only independiente: APROBADO** (hallazgos no bloqueantes: sobre-agregación sectores `None` bajo `<unknown>` [medio] · `equity=None`→denominador `sum_mvs` incluye puesta [bajo] · `sector`/`proposal_sector` no sincronizados en callers [bajo]).

## 2. Decisiones tomadas / pendientes

| Id          | Decisión                                                                                                                                                                                                                            | Estado                         |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| **D1**      | Risk de cesta (`check_opening`) aplica **igual** en SEMI y AUTO, **sin override** humano.                                                                                                                                           | ✅ **ACEPTADA** (2026-08-24)   |
| **D0-fase** | F0.5 (Fit código) **APROBADA para abrir** · F0.6 (Daily vista) **NO**.                                                                                                                                                              | ✅ F0.5 CERRADA · F0.6 ⏳      |
| **F0.5a**   | Métrica de encaje = **concentración de cesta por activo y por sector** (usar `max_portfolio_concentration_pct` a nivel cesta + `max_sector_exposure_pct`, este último antes sin evaluar). Comportamiento **VETO**. Sector desde DB. | ✅ **DECIDIDA** (2026-08-24)   |
| **D2**      | Autoridad = `DecisionPackage` (contrato) vs `Recommendation` (cara operativa).                                                                                                                                                      | ⏳ recomendada (a) — confirmar |
| **D3**      | Lab/Radar **fuera** del spine (ADR-019).                                                                                                                                                                                            | ⏳ recomendada (a) — confirmar |

## ⚠️ Instrucción para el nuevo chat (no repetir el tropiezo)

**F0.6 (Daily Decision Board / vista) está SIN aprobar.** El agente NO debe abrir código ni lanzar subagentes de implementación hasta que el propietario **apruebe la fase** (premisa E1) y **defina la fuente de la vista** (decisión product: qué expone el spine a la UI del diario — estado de colas, paquetes pendientes, gates). F0.6 es una **vista de solo lectura** sobre `GetDailyOpsReport`/spine, **no** un orquestador (F0.2 §4, F0.3 no-op `DailyOrchestrator`).

## 3. Qué NO tocar (freeze)

- Motor money / ledger / `ExecuteTrade` internals.
- Belief / gobernanza IA · `contract:gen` salvo fase pactada · Track B B1–B12.
- `pending-delete` · no `regen_full`. Purge storage E8 N.

## 4. Tarea del siguiente chat (F0.6 — SIN aprobar aún)

**PASO 0 (obligatorio, sin código):** que el propietario **decida F0.6a — la fuente de la vista Daily** y **apruebe la fase**. El agente solo presenta opciones ancladas al código y espera decisión. NO abrir código antes.

**Después (con fase aprobada): implementar F0.6b (Daily vista):** endpoint de lectura + UI de solo lectura del spine / `GetDailyOpsReport` (`daily_ops_report.py:51`). Leer primero este relevo + F0.1–F0.4 + backlog §0 + PROJECT_STATE §2b.

## 5. Texto de arranque (pegar en el chat nuevo de F0.6)

```
CONTEXTO: Fase 0 Decision Spine. F0.1–F0.4 docs CERRADOS. F0.5a métrica decidida
(concentración cesta activo+sector, VETO). F0.5b PortfolioFit v1 CERRADA (3670a09).
F0.6 (Daily vista) NO APROBADA — read-only, no abrir código ni subagentes de impl.
LEE: docs/engineering/traspaso-relevo-f0-5b-cierre-apertura-f0-6-2026-08-24.md
+ backlog §0 + PROJECT_STATE §2b + PROJECT_PREMISES ⭐§0
+ fase0-decision-spine-implementacion-plan-2026-08-24.md
+ fase0-decision-spine-roadmap-2026-08-24.md + fase0-decision-spine-tobe-2026-08-24.md
+ fase0-decision-spine-mapping-2026-08-24.md + fase0-decision-spine-descarga-2026-08-24.md.

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. No reconstruir.
D1 aceptada: risk de cesta SEMI=AUTO, sin override. D2/D3 a confirmar si aplican.

TAREA: PRIMERO → decisión del propietario de la FUENTE de la vista Daily (F0.6a) y
aprobación de fase. NO lanzo agentes ni código hasta ambas.
DESPUÉS → F0.6b implementar vista de solo lectura (endpoint + UI), una rebanada,
path:line verificado, batería, aprobación antes de commit.
NO TOCAR: money, IA, contract:gen, Track B, pending-delete, ExecuteTrade internals.
Protocolo: subagente acotado + verificador read-only, alcance disjunto, batería, aprobación del propietario antes de commit.
```
