# Fase 0.1 — AS-IS Decision Spine (inventario)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) (Product / Ops).
> **Ciclo:** Fase 0 Decision Spine · rebanada **F0.1** (solo inventario).
> **AsOf:** 2026-08-24 · HEAD verificado `f69a7b0` (`feat(help): pestaña Flujo y módulos en Ayuda`) · `main` == `origin/main`.
> **Alcance:** qué hay, dónde, qué no hay. **Cero TO-BE, cero código.**
> **Método:** un subagente explore ([Inventario spine AS-IS](9d9e2748-0594-4f5c-b9a4-3a4dd929b591)) + relectura del coordinador. Citas no verificadas no entran.

---

## 0. Veredicto AS-IS (una frase)

Hay **motores reales** (Opportunity→Runtime→Recommendation, Dictamen, Gate, Risk, Router, ExecuteTrade, Mandato, DailyOps). **No hay una columna ordenada.** Ranking, dictamen, F3 SEMI y Radar/Paper D son **carriles paralelos** que convergen tarde en `ExecuteTrade`.

---

## 1. Rutas de mesa (SPA)

Fuente: [`apps/web/src/app.tsx`](../../apps/web/src/app.tsx) (router `46:94`).

| Path          | Elemento                | Rol en el spine                              |
| ------------- | ----------------------- | -------------------------------------------- |
| `/`           | `Navigate` → `/trading` | Landing mesa                                 |
| `/trading`    | `ChartWorkspacePage`    | Gráfico + Operativa + IO                     |
| `/screeners`  | `ScreenersPage`         | Señales (nav diaria)                         |
| `/confirm`    | `ConfirmPage`           | Firma SEMI                                   |
| `/operations` | `OperationsPage`        | Libro · posiciones                           |
| `/history`    | `HistoryPage`           | Libro · ledger                               |
| `/research`   | `ResearchPage`          | Asesor (Diario / Opiniones = tabs, no rutas) |
| `/overview`   | `OverviewPage`          | Resumen                                      |
| `/accounts`   | `AccountsPage`          | Cuentas / modo DEMO                          |
| `/backtests`  | `BacktestsRouteSlot`    | Laboratorio (fuera de la mañana)             |

Nav diaria (copy, no calcula): `DAILY_NAV_ORDER` en [`daily-nav.ts`](../../apps/web/src/features/confirm/daily-nav.ts) `64:69` = Trading · Señales · Confirmar · Libro.

**Daily Decision Board:** NOT FOUND (ni ruta `/daily`, ni componente con ese nombre).

**Confirmar:** [`confirm-page.tsx`](../../apps/web/src/features/confirm/confirm-page.tsx) `12:23` monta `SupervisedF3Panel` (`supervised-f3-panel.tsx:162`). No orquesta un paquete de cesta.

API spine (no SPA): `POST /ai/recommendations/propose`, `POST /ai/intents/confirm` (capa `ai_governance`; no re-abierta en F0.1).

---

## 2. Inventario por nivel (propuesto vs real)

| Nivel propuesto      | Nombre real                                               | Estado        | path:line                                                    | Clase                                      |
| -------------------- | --------------------------------------------------------- | ------------- | ------------------------------------------------------------ | ------------------------------------------ |
| InstrumentRanking    | —                                                         | **NOT FOUND** | —                                                            | —                                          |
| Ranking mesa (proxy) | `computeIndiceOperativo` / `rankIndiceOperativo`          | EXISTS        | `operativa-index.ts:29`, `:46`                               | **UI / cliente**                           |
| Composite (proxy)    | `composite_score` + pata `portfolioConstraints`           | EXISTS        | `composite_score.py:325-330`                                 | motor + **stub** pata cartera              |
| Opportunity          | `OpportunityResult` + `build_opportunity_package`         | EXISTS        | `opportunity.py:37`, `:76`                                   | engine analytics                           |
| PortfolioFit         | —                                                         | **NOT FOUND** | —                                                            | stub Composite peso 0 / `not_evaluated`    |
| Instrument opinion   | `DailyOpinionService` + `compute_stance`                  | EXISTS        | `daily_opinion_service.py:76` · `daily_opinion_stance.py:75` | engine aplicación                          |
| Decision             | `run_decision_runtime` + `DecisionPackageV1`              | EXISTS        | `decision_runtime.py:256` · `decision-package.ts:39`         | engine + DTO                               |
| Recommendation       | `Recommendation` + `ProposeRecommendationFromTa`          | EXISTS        | `recommendation.py:23` · `propose_recommendation.py:142`     | DTO + engine F3                            |
| OrderProposal        | —                                                         | **NOT FOUND** | —                                                            | —                                          |
| OrderIntent          | `OrderIntentV1`                                           | EXISTS        | `order-intent.ts:20`                                         | DTO                                        |
| Risk                 | `check_opening` (`RISK_ENGINE_VERSION`)                   | EXISTS        | `risk_engine.py:27`, `:55`                                   | fachada aplicación                         |
| Policy Gate          | `evaluate_policy_gate` / `evaluatePolicyGate`             | EXISTS        | `policy_gate.py:57` · `policy-gate.ts:28`                    | engine TS+Py                               |
| ExecutionPolicy      | `ExecutionMode` + `ExecutionPolicyV1` + `ExecutionRouter` | EXISTS        | `platform-kernel.ts:79`, `:88` · `execution_router.py:147`   | DTO + engine                               |
| Mandate              | `MandateTenureDto` / `MandateTenureRow`                   | EXISTS        | `operating-mandate.ts:13` · `tables.py:1295`                 | DTO + DB                                   |
| Daily ops            | `GetDailyOpsReport`                                       | EXISTS        | `daily_ops_report.py:51`                                     | agregador (no decide)                      |
| Daily orchestrator   | —                                                         | **NOT FOUND** | —                                                            | —                                          |
| Decision journal     | —                                                         | **NOT FOUND** | —                                                            | —                                          |
| Decision session     | `DecisionSessionRow`                                      | EXISTS        | `tables.py:602`                                              | persistencia foto                          |
| Attribution engine   | —                                                         | **NOT FOUND** | —                                                            | hay `mandate_trade_links` (hook, no motor) |
| ExecuteTrade         | `ExecuteTrade`                                            | EXISTS        | `accounts/trade.py:17`                                       | ledger paper                               |

---

## 3. Grafos reales (no el spine TO-BE)

### 3.1 Carril SEMI (F3)

```
Assessments
  → ProposeRecommendationFromTa.execute     propose_recommendation.py:142
  → run_decision_runtime                    decision_runtime.py:256
  → Recommendation
  → UI SupervisedF3Panel                    supervised-f3-panel.tsx:162
  → ConfirmRecommendationIntent             confirm_recommendation.py:19
  → ExecuteTrade.execute                    confirm_recommendation.py:87
  → DecisionSession persist
```

`check_opening` **no** está en este camino por defecto (riesgo en el router AUTO).

### 3.2 Carril Opportunity / Paper D / scan (AUTO)

```
build_opportunity_package                   opportunity.py:76
  → run_decision_runtime

hits scan / ProposePaperDPlan
  → ExecutionRouter.execute                 execution_router.py:147 / ~288
  → check_opening                           execution_router.py:536 y :793
  → ExecuteTrade.execute                    execution_router.py:638
```

### 3.3 Carril Dictamen (Estudio)

```
DailyOpinionService                         daily_opinion_service.py:76
  → compute_stance                          daily_opinion_stance.py:75
  → instrument_daily_opinions               tables.py:1246
  → UI Dictamen / Asesor Opiniones
  → (producto) ALARMA → Proponer F3
```

**No** genera `DecisionPackage` ni `Recommendation` solo.

### 3.4 Ranking mesa (IO)

```
hub scores (composite + FA distress)
  → computeIndiceOperativo                  operativa-index.ts:29  (CLIENTE)
  → rankIndiceOperativo                     operativa-index.ts:46
```

Call sites UI (no motor Python): `trading-operativa-panel.tsx`, `list-recommendation-scores-context.tsx`, `sort-visualizados-by-io.ts`, `asesor-opiniones-panel.tsx`, `instruments-page.tsx`.

---

## 4. Dos entradas a ExecuteTrade

Una clase: `ExecuteTrade` (`accounts/trade.py:17`).

| Entrada     | Caller                              | Risk `check_opening` | Autorización                         |
| ----------- | ----------------------------------- | -------------------- | ------------------------------------ |
| SEMI F3     | `ConfirmRecommendationIntent` `:87` | no en este use-case  | humano `/confirm`                    |
| AUTO router | `ExecutionRouter` `:638`            | sí `:536` / `:793`   | policy `paper_auto` / scan / Paper D |

Hasta unificar **antes** de `ExecuteTrade` (mismo Decision + Fit + Risk de cesta), SEMI y AUTO no son “el mismo motor con otra policy”.

---

## 5. Tablas (PK + rol)

Fuente SQLAlchemy [`tables.py`](../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py):

| Tabla                       | PK     | Clase                       | Línea | Rol spine                         |
| --------------------------- | ------ | --------------------------- | ----- | --------------------------------- |
| `execution_policies`        | `id`   | `ExecutionPolicyRow`        | 471   | modo ejecución                    |
| `decision_sessions`         | `id`   | `DecisionSessionRow`        | 602   | foto de razonamiento              |
| `instrument_daily_opinions` | `id`   | `InstrumentDailyOpinionRow` | 1246  | dictamen Estudio                  |
| `mandate_tenures`           | `id`   | `MandateTenureRow`          | 1295  | playbook ticker×cuenta            |
| `mandate_trade_links`       | (link) | —                           | ~1334 | hook atribución, no motor         |
| `ledger_entries`            | `id`   | —                           | ~1174 | verdad money (no tocar en Fase 0) |

**NOT FOUND:** tabla `order_intents`, `operating_mandates` (el mandato vivo es tenure, no una fila “mandate”).

Espejo Prisma: `schema.prisma` modelos `ExecutionPolicy`, `DecisionSession`, `InstrumentDailyOpinion`, `MandateTenure`, `LedgerEntry` (mismos `@@map`).

---

## 6. Solapes (mismo concepto, dos nombres)

| A                              | B                                     | Relación                                           |
| ------------------------------ | ------------------------------------- | -------------------------------------------------- |
| `DecisionPackageV1` (TS)       | `DecisionPackageTa` + alias Py        | mismo artefacto RFC-008                            |
| `Recommendation.action`        | `DecisionPackage.action`              | Rec envuelve package + sizing/status               |
| Dictamen `stance` (buy/hold/…) | `DecisionAction` (`recommend_long`/…) | vocabularios **no sincronizados**                  |
| Composite / IO cliente         | `combined_score` del runtime          | dos fusiones TA/FA; consumidores distintos         |
| CORE-R (Lab)                   | Opinion `review_strategy`             | ambos “revisar estrategia”; uno es frescura Lab    |
| Policy Gate                    | `check_opening`                       | Risk envuelve Gate + kill switch + maxOpen         |
| Policy Gate                    | Opinion `gateStatus`                  | hint `allowTrading`, no el Gate completo           |
| `ExecutionMode` kernel         | modo cuenta SEMI/AUTO UI              | no son el mismo enum                               |
| `OrderIntent` F3               | scan → Router                         | dos caminos a caja                                 |
| `GetDailyOpsReport`            | Daily Board                           | digest vs tablero de acción (el segundo no existe) |

---

## 7. NOT FOUND (explícito)

- `InstrumentRanking`
- `PortfolioFit` / motor de encaje de cartera (solo stub Composite)
- `OrderProposal`
- `DailyDecisionBoard` / `DailyOrchestrator`
- `DecisionJournal`
- Motor de **Attribution** (más allá de links mandato↔trade)
- `computeIndiceOperativo` en Python (solo cliente)
- Clases exactas `RiskEngine`, `PolicyGate`, `DecisionRuntime`, `OperatingMandate` (existen funciones/DTOs con otros nombres)

---

## 8. Verificación coordinador (anti-alucinación)

El subagente acertó el mapa; el coordinador releyó estas citas en disco (HEAD `f69a7b0`):

| #   | Cita                                             | ¿OK? |
| --- | ------------------------------------------------ | ---- |
| 1   | `app.tsx:59` `/` → `/trading`                    | sí   |
| 2   | `app.tsx:87` `/confirm` → `ConfirmPage`          | sí   |
| 3   | `confirm-page.tsx:12-22` reusa F3                | sí   |
| 4   | `daily-nav.ts:64-69` `DAILY_NAV_ORDER`           | sí   |
| 5   | `operativa-index.ts:29` IO cliente               | sí   |
| 6   | `composite_score.py:325-330` stub cartera        | sí   |
| 7   | `accounts/trade.py:17` `ExecuteTrade`            | sí   |
| 8   | `confirm_recommendation.py:87` fill SEMI         | sí   |
| 9   | `execution_router.py:638` fill AUTO              | sí   |
| 10  | `risk_engine.py:55` `check_opening`              | sí   |
| 11  | `decision_runtime.py:256` `run_decision_runtime` | sí   |
| 12  | `tables.py:1246` / `:1295` opiniones + tenures   | sí   |

Desvíos menores del primer reporte del subagente (nombres de clase): el código usa `ProposeRecommendationFromTa`, `ConfirmRecommendationIntent`, `GetDailyOpsReport`, `compute_stance` — no los alias del brief. El inventario de esta página usa **nombres de disco**.

---

## 9. Fuera de alcance F0.1

TO-BE, mapping conservar/adaptar/crear, mocks UX, tests nuevos, motor money, Belief, `contract:gen`, Track B.

**Siguiente rebanada (solo con OK del propietario):** F0.2 TO-BE sobre este inventario, sin subagente de exploración.
