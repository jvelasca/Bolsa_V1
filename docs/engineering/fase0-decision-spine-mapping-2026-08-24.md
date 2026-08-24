# F0.3 — Mapping conservar / adaptar / crear (docs-only)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Ciclo:** Fase 0 Decision Spine · rebanada **F0.3** (Mapping, cero código).
> **AsOf:** 2026-08-24 · HEAD `f69a7b0` == `origin/main`.
> **Depende de:** [AS-IS F0.1](./fase0-decision-spine-asis-2026-08-24.md) + [TO-BE F0.2](./fase0-decision-spine-tobe-2026-08-24.md).
> **Alcance:** por cada ítem del inventario AS-IS → acción **CONSERVAR / ADAPTAR / CREAR / (no-op)** con cita `file:line`. **Solo documento.** No decide ni abre código (criterio de parada: ver §4).
> **Nota de método:** cada ítem se contrasta contra AS-IS §2 (estado EXISTS/NOT FOUND/stub) — no contra memoria.

---

## 1. Carta de decisiones por ítem (tras AS-IS §2 + TO-BE §3)

| Nivel propuesto (RFC-008) | Nombre real (AS-IS)                                                                                                 | Estado AS-IS                                                                | Acción TO-BE                               | Justificación                                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Opportunity               | `OpportunityResult` / `build_opportunity_package` (`opportunity.py:37/:76`)                                         | EXISTS engine analytics                                                     | **CONSERVAR**                              | Emisor de oportunidad → alimenta el Runtime único (TO-BE §2.1)                                                                                                          |
| Technical/Fundamental     | `Composite` (`composite_score.py:325-330`)                                                                          | EXISTS + **stub** pata cartera                                              | **ADAPTAR**                                | La pata `portfolioConstraints` es el germen del Fit; la fusion TA/FA debe residir en Runtime, no en una segunda fusión clientemmesa                                     |
| Instrument opinion        | `DailyOpinionService` / `compute_stance` (`daily_opinion_service.py:76` · `daily_opinion_stance.py:75`)             | EXISTS engine aplicación                                                    | **ADAPTAR**                                | Pasa a **emisor de Assessment/Opinión** (cola Dictamen); no genera DecisionPackage solo (AS-IS §3.3)                                                                    |
| Decision                  | `run_decision_runtime` / `DecisionPackageV1` (`decision_runtime.py:256` · `decision-package.ts:39`)                 | EXISTS engine + DTO                                                         | **CONSERVAR → núcleo único**               | Es el punto de integración del TO-BE (§2); toda cola pasa por aquí                                                                                                      |
| Recommendation            | `Recommendation` / `ProposeRecommendationFromTa` (`recommendation.py:23` · `propose_recommendation.py:142`)         | EXISTS DTO + engine F3                                                      | **ADAPTAR**                                | Envuelve el DecisionPackage + sizing/status (AS-IS §6) — resolver solape                                                                                                |
| OrderIntent               | `OrderIntentV1` (`order-intent.ts:20`)                                                                              | EXISTS DTO                                                                  | **CONSERVAR**                              | Puerto de intención; el TO-BE unifica los dos caminos a caja en un solo puerto pre-fill                                                                                 |
| Risk                      | `check_opening` (`risk_engine.py:27/:55`)                                                                           | EXISTS fachada                                                              | **ADAPTAR**                                | Riesgo de **cesta** único pre-fill; SEMI DEJA de saltarlo (cierra gap F0.2 §7)                                                                                          |
| Policy Gate               | `evaluate_policy_gate` / `evaluatePolicyGate` (`policy_gate.py:57` · `policy-gate.ts:28`)                           | EXISTS engine TS+Py                                                         | **CONSERVAR**                              | Gate de cesta único (propose pasivo / paper_auto-hard, AS-IS §6)                                                                                                        |
| ExecutionPolicy           | `ExecutionMode` / `ExecutionPolicyV1` / `ExecutionRouter` (`platform-kernel.ts:79/:88` · `execution_router.py:147`) | EXISTS DTO + engine                                                         | **CONSERVAR**                              | Único responsable del fill tras el spine (AUTO `:638`)                                                                                                                  |
| Mandate                   | `MandateTenureDto` / `MandateTenureRow` (`operating-mandate.ts:13` · `tables.py:1295`)                              | EXISTS DTO + DB                                                             | **CONSERVAR**                              | Playbook ticker×cuenta que define la policy                                                                                                                             |
| Daily ops                 | `GetDailyOpsReport` (`daily_ops_report.py:51`)                                                                      | EXISTS agregador                                                            | **ADAPTAR → vista**                        | Alimenta el Daily Decision Board como **vista**, no decide (F0.2 §4)                                                                                                    |
| ExecuteTrade              | `ExecuteTrade` (`accounts/trade.py:17`)                                                                             | EXISTS ledger paper                                                         | **CONSERVAR (no reabrir internals)**       | Único cierre de fill                                                                                                                                                    |
| InstrumentRanking         | —                                                                                                                   | **NOT FOUND** (proxy `rankIndiceOperativo` cliente `operativa-index.ts:46`) | **(no-op)**                                | Ranking de mesa queda como **vista/consumidor**; el spine no crea motor de ranking ahora (F0.2 §3)                                                                      |
| PortfolioFit              | —                                                                                                                   | **NOT FOUND** (solo stub Composite)                                         | **CREAR (a medio plazo, decisión aparte)** | Único create neto; elevar stub a encaje de cesta (F0.2 §5) — **no se abre en docs**                                                                                     |
| OrderProposal             | —                                                                                                                   | **NOT FOUND**                                                               | **(no-op)**                                | No aparece en el spine; se solapa con OrderIntent+Recommendation                                                                                                        |
| Daily orchestrator        | —                                                                                                                   | **NOT FOUND**                                                               | **(no-op)**                                | Daily es **vista**; no crear orquestador paralelo                                                                                                                       |
| Decision journal          | —                                                                                                                   | **NOT FOUND**                                                               | **decisión futura**                        | Reusar en su lugar `decision_sessions` (`tables.py:602`) como contrato pre-fill; un journal completo (accept/reject+trigger) queda como fase futura con decisión propia |
| Decision session          | `DecisionSessionRow` (`tables.py:602`)                                                                              | EXISTS persistencia foto                                                    | **ADAPTAR**                                | De «foto» a **contrato compartido** por SEMI y AUTO (F0.2 §2.1)                                                                                                         |
| Attribution engine        | —                                                                                                                   | **NOT FOUND** (solo `mandate_trade_links` hook)                             | **(no-op)**                                | No motor nuevo en este alcance                                                                                                                                          |

---

## 2. Resumen consolidado

| Acción              | Ítems                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **CONSERVAR**       | Opportunity · Decision (Runtime) · OrderIntent · PolicyGate · ExecutionPolicy · Mandate · ExecuteTrade                   |
| **ADAPTAR**         | Composite · Dictamen · Recommendation · Risk (cesta) · DailyOps (vista) · DecisionSession (contrato)                     |
| **CREAR**           | **PortfolioFit** (único, a medio plazo, decisión aparte)                                                                 |
| **(no-op)**         | InstrumentRanking (vista) · OrderProposal · DailyOrchestrator · Attribution (sin motor nuevo)                            |
| **Decisión futura** | Dictamen vocabulario vs `DecisionAction` (AS-IS §6) · DecisionJournal completo · reconciliar IO mesa vs `combined_score` |

**Lectura:** el TO-BE se construye **al 100% sobre módulos EXISTS adaptados**; el único _create_ nuevo es **PortfolioFit**, y queda a medio plazo con decisión propia. Nada que el AS-IS marcara NOT FOUND entra como módulo nuevo del spine en esta fase (solo como decisión futura o no-op).

---

## 3. Riesgos / decisiones que F0.3 deja abiertas para el propietario

1. **Gap SEMI-riesgo:** ADAPTAR `check_opening` a cesta implica que el confirm SEMI `confirm_recommendation.py:87` pase por Risk. Decisión de autorización: ¿el humano puede sortear risk por override, o el riesgo aplica igual? → **decisión propietario** en F0.4.
2. **Solape `DecisionPackage` ↔ `Recommendation`:** resolver en F0.4 qué es contrato y qué es cara operativa (AS-IS §6).
3. **Daily como vista:** confirmar que `BacktestsRouteSlot`/Radar quedan fuera del spine (laboratorio) — ver AS-IS §1.

---

## 4. Criterio de parada

- ✓ Cabe en una lectura.
- ✓ No inventa módulos que AS-IS no marcara NOT FOUND o stub.
- ✓ **Daily es vista** (no-op orquestador).
- ✓ **Fit es el único create** y queda declarado a medio plazo, no se abre.
- ✓ Toda afirmación sobre ítems lleva cita del inventario AS-IS (no memoria).

## 5. Fuera de alcance F0.3

F0.4 (descargue de decisión: orden de gates, autorización SEMI vs AUTO), Fit code, Daily UI, motor money, Belief, gobernanza IA, `contract:gen`, Track B. **Esto es un documento.** Solo código tras plan + aprobación (premisa E1).
