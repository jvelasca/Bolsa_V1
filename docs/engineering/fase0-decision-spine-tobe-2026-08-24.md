# F0.2 — TO-BE Decision Spine (arquitectura objetivo, docs-only)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Ciclo:** Fase 0 Decision Spine · rebanada **F0.2** (TO-BE, cero código).
> **AsOf:** 2026-08-24 · HEAD `f69a7b0` == `origin/main`.
> **Alcance:** qué queremos que sea el spine. **No mapping, no Daily UI, no Fit code.**
> **Inputs obligatorios:** [AS-IS F0.1](./fase0-decision-spine-asis-2026-08-24.md) + [RFC-008](../../docs/rfc/008-cognitive-decision-architecture.md) (Assessment→DecisionRuntime→DecisionPackage→PolicyGate→Execution) + tesis competitiva (roadmap F0.1 §0).
> **Método:** coordinador redacta desde el inventario; toda afirmación de código lleva `path:line` del AS-IS, **no memoria**.
> **Criterio de parada:** cabe en una lectura · no inventa módulos que F0.1 no marcara NOT FOUND o stub · Daily es vista · Fit es el único create neto a medio plazo.

---

## 0. Veredicto TO-BE (una frase)

**Un spine ordenado** (Dato → Evidence/Assessment → DecisionPackage → PolicyGate/Risk → Fill) que hace converger las **tres colas de entrada** **antes** de `ExecuteTrade`, de modo que SEMI y AUTO sean «el mismo motor con otra policy», y **Daily como vista** del agregador sobre ese spine.

---

## 1. Las tres colas de entrada (qué se unifica)

| #     | Cola (AS-IS)              | Origen file:line                                                                                                                                                                                                    | En AS-IS                                             | En TO-BE                                                                                                                           |
| ----- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **1** | **SEMI (F3)**             | `ProposeRecommendationFromTa` → `run_decision_runtime` → `Recommendation` → `SupervisedF3Panel` → `ConfirmRecommendationIntent` → `ExecuteTrade` (`propose_recommendation.py:142` · `confirm_recommendation.py:87`) | **salta `check_opening`** (§3.1, §4)                 | pasa por el **mismo Risk/Policy de cesta** que AUTO antes de fill                                                                  |
| **2** | **AUTO (scan / Paper D)** | `build_opportunity_package` → `run_decision_runtime` · `ExecutionRouter` → `check_opening` → `ExecuteTrade` (`execution_router.py:536/:638/:793`)                                                                   | tiene `check_opening` (§3.2, §4)                     | toma el **mismo Decision Package** que SEMI (mismo camino, otra policy `paper_auto`)                                               |
| **3** | **Dictamen (Estudio)**    | `DailyOpinionService` → `compute_stance` → `instrument_daily_opinions` → ALARMA → Proponer F3 (`daily_opinion_service.py:76` · `daily_opinion_stance.py:75`)                                                        | no genera DecisionPackage/Recommendation solo (§3.3) | **es un emisor de Assessment/Opinión** que alimenta el spine en la etapa de oportunidad; si pasa la alarma, entra por la cola SEMI |

**Regla de diseño:** las tres colas **no** son tres cajas a `ExecuteTrade`. Son tres **emisores de evidencia** que convergen en **un** `DecisionRuntime` → **un** `DecisionPackage` → **un** Policy/Risk → fill.

---

## 2. Spine TO-BE (columna ordenada convergiendo antes de ExecuteTrade)

```
DATO → Assessments (de las 3 colas)
  → DecisionRuntime (un solo punto de integración)   decision_runtime.py:256
  → DecisionPackage + Recommendation                 decision-package.ts:39 · recommendation.py:23
  → Policy Gate + Risk (cesta)                       policy_gate.py:57 · risk_engine.py:55 (check_opening)
  → ConfirmRecommendationIntent (SEMI)  O  ExecutionRouter (AUTO)
  → ExecuteTrade                                      accounts/trade.py:17
```

### 2.1 Principios que el TO-BE garantiza

1. **Convergencia pre-fill.** Toda orden atraviesa el **mismo** Decision + Fit + Risk de cesta antes de tocar `ExecuteTrade`. Hoy hay **dos entradas** con distinta autorización (AS-IS §4: SEMI sin `check_opening`, AUTO con `check_opening`).
2. **Persistir el Decision Package** antes de fill (hoy `decision_sessions` captura «foto»: `DecisionSessionRow`, `tables.py:602`). El TO-BE hace de esa foto un **contrato** que SEMI y AUTO comparten.
3. **«Mismo motor, otra policy.»** La única diferencia SEMI vs AUTO es la **autorización** (humano `/confirm` vs policy `paper_auto` / scan / Paper D), no la arquitectura (AS-IS §4 tabla entradas).

---

## 3. Conservar / adaptar por nivel (qué del AS-IS entra sin crear)

| Río AS-IS (EXISTS)                                                                                        | Rol en TO-BE                                                                                         |
| --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `InstrumentRanking` → **NO** (NOT FOUND); hoy hay `rankIndiceOperativo` cliente (`operativa-index.ts:46`) | El ranking de mesa queda como **vista/consumidor**; el spine no crea un motor de ranking nuevo ahora |
| `PortfolioFit` → **NOT FOUND** (solo stub `composite_score.py:325-330` pata cartera `not_evaluated`)      | **Único create neto a medio plazo** (§5) — NO se abre en F0.2                                        |
| Opportunity (`opportunity.py:37/:76`)                                                                     | Emisor de oportunidad → alimenta Runtime                                                             |
| Dictamen (`compute_stance`)                                                                               | Emisor de Assessment/Opinión (cola 3)                                                                |
| Runtime (`run_decision_runtime`, `decision_runtime.py:256`)                                               | **Núcleo único** del spine; todo pasa por aquí                                                       |
| Gate (`evaluate_policy_gate`, `policy_gate.py:57`)                                                        | **Gate de cesta** único pre-fill                                                                     |
| Risk (`check_opening`, `risk_engine.py:55`)                                                               | **Risk de cesta** único pre-fill (SEMI ya NO lo salta)                                               |
| Mandate (`MandateTenureDto`, `operating-mandate.ts:13`)                                                   | Definen la policy por ticker×cuenta (playbook)                                                       |
| DailyOps (`GetDailyOpsReport`)                                                                            | Alimenta la **vista** Daily (§4), no decide                                                          |
| ExecuteTrade (`accounts/trade.py:17`)                                                                     | Único cierre de fill (no reabrir internals)                                                          |

> **Lo que NO existe y NO se inventa en F0.2:** `OrderProposal`, `DecisionJournal`, `DailyOrchestrator`, motor de Attribution (más allá de `mandate_trade_links`), `InstrumentRanking` — todos marcados **NOT FOUND** en AS-IS §7. Si aparecen en el diseño, se **plantean como create de fases futuras con decisión**, no como parte del spine.

---

## 4. Daily Decision Board = **vista** (no orquestador)

- El agregador ya existe: `GetDailyOpsReport` (AS-IS `daily_ops_report.py:51`). Hoy es **digest que no decide** (AS-IS §6: `GetDailyOpsReport` es digest vs tablero de acción, y el tablero **no existe** — NOT FOUND `DailyDecisionBoard`).
- **TO-BE:** el Daily es una **vista de solo lectura** sobre el spine (estado de colas, paquetes pendientes, gates). **No** introduce un `DailyOrchestrator` que decida en paralelo.

---

## 5. Fit (PortfolioFit) — el ÚNICO create neto a medio plazo

- AS-IS: `PortfolioFit` **NOT FOUND**; existe solo el **stub** de la pata cartera de `composite_score` (`composite_score.py:325-330`, peso 0, `not_evaluated`).
- **TO-BE (a medio plazo, NO en esta rebanada):** elevar ese stub a un **encaje de cesta** que el Policy/Risk consulte antes del fill. Es el único módulo nuevo; el resto es _ordenar_.
- **F0.2 no abre este código.** Solo lo declara como destino.

---

## 6. Solapes que el TO-BE debe resolver (heredados de AS-IS §6)

| Solape AS-IS                                         | Decisión TO-BE (diseño, no código)                                                                                                                      |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Recommendation.action` vs `DecisionPackage.action`  | `Recommendation` envuelve el paquete + sizing/status (AS-IS §6). En TO-BE el **DecisionPackage es el contrato**; `Recommendation` es la cara operativa. |
| Dictamen `stance` vs `DecisionAction`                | Vocabularios no sincronizados (AS-IS §6). TO-BE unifica el vocabulario de acción en el DecisionPackage.                                                 |
| Composite/IO cliente vs `combined_score` del runtime | Dos fusiones TA/FA (AS-IS §6). TO-BE: las **evidencias** se fusionan en el Runtime; la IO de mesa es consumo, no una segunda fusión de decisión.        |
| `OrderIntent` F3 vs scan→Router                      | Dos caminos a caja (AS-IS §6). TO-BE **un solo puerto de fill** pre-orden (ver §2).                                                                     |

---

## 7. Verificación de coherencia TO-BE ↔ AS-IS (anti-alucinación)

| Regla TO-BE                       | Soporte AS-IS (file:line)                                                               |
| --------------------------------- | --------------------------------------------------------------------------------------- |
| Converger antes de `ExecuteTrade` | AS-IS §4: dos entradas (SEMI `:87` sin `check_opening`; AUTO `:638` con `:536/:793`)    |
| Runtime único                     | `decision_runtime.py:256` (EXISTS)                                                      |
| Gate/Risk de cesta único pre-fill | `policy_gate.py:57` · `risk_engine.py:55` (EXISTS)                                      |
| SEMI ya no salta `check_opening`  | AS-IS §3.1/§4: la cola SEMI **no** lo usa por defecto → gap a cerrar                    |
| Fit = único create                | `composite_score.py:325-330` stub · `PortfolioFit` NOT FOUND                            |
| Daily = vista                     | `daily_ops_report.py:51` agregador · `DailyDecisionBoard`/`DailyOrchestrator` NOT FOUND |

---

## 8. Fuera de alcance F0.2

F0.3 mapping (conservar/adaptar/crear por ítem), Fit code, Daily UI, motor money, Belief, gobernanza IA, `contract:gen`, Track B. **Esto es un documento.** Solo código tras plan + aprobación (premisa E1).
