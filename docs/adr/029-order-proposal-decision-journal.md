# ADR-029: OrderProposal + DecisionJournal — capa mínima del spine post-v1.7.0-beta

**Estado:** Aceptado (docs-only; implementación F1+ requiere plan aprobado)  
**Fecha:** 2026-08-24  
**Contexto:** Ciclo 1/5 post-tag `v1.7.0-beta`. El freeze spine marcaba OrderProposal/Journal como **NOT FOUND** ([AS-IS §7](../engineering/fase0-decision-spine-asis-2026-08-24.md)) y **(no-op) / decisión futura** ([mapping §1](../engineering/fase0-decision-spine-mapping-2026-08-24.md)). El propietario **aprobó abrir los 5 ciclos en orden**; este ADR fija el alcance mínimo v1.

**Depende de:** [RFC-008](../rfc/008-cognitive-decision-architecture.md) · [ADR-015](./015-scientific-domain-vs-trading-domain.md) · [ADR-019](./019-dual-universes-lab-vs-trading.md) · Fase 0 spine (D1/D2/D3 cerradas) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).

---

## 1. Contexto

### 1.1 Qué existe hoy (verificado)

| Artefacto                             | Rol                                                      | Cita                                            |
| ------------------------------------- | -------------------------------------------------------- | ----------------------------------------------- |
| `DecisionPackageV1`                   | Contrato de identidad (acción + instrumento)             | `decision-package.ts:39`                        |
| `RecommendationV1` / `Recommendation` | Cara operativa: acción + sizing + status                 | `recommendation.ts:16` · `recommendation.py:23` |
| `OrderIntentV1` / `OrderIntent`       | Voluntad **autorizada** (humano o policy) antes del fill | `order-intent.ts:20` · `order_intent.py:24`     |
| `DecisionSessionRow`                  | Fotografía del razonamiento (propose/confirm/paper_auto) | `tables.py:602`                                 |
| `ConfirmRecommendationIntent`         | SEMI: Recommendation → Intent → ExecuteTrade + sesión    | `confirm_recommendation.py:225` · `:365`        |
| `ProposeRecommendationFromTa`         | F3: Runtime → Recommendation + sesión `propose`          | `propose_recommendation.py:142` · `:445`        |
| `ExecutionRouter`                     | AUTO: check_opening → ExecuteTrade + sesión              | `execution_router.py:604` · `:716`              |

El camino SEMI ya materializa la cadena:

```text
ProposeRecommendationFromTa → DecisionSession (kind=propose)
  → UI SupervisedF3Panel → confirmOrderIntent
  → ConfirmRecommendationIntent → OrderIntent → ExecuteTrade
```

(`propose_recommendation.py:445` · `supervised-f3-panel.tsx:362` · `confirm_recommendation.py:279` · `:365`)

### 1.2 Qué NO existe

- **`OrderProposal`** — AS-IS §7 NOT FOUND (`fase0-decision-spine-asis-2026-08-24.md:177`).
- **`DecisionJournal`** — AS-IS §7 NOT FOUND (`fase0-decision-spine-asis-2026-08-24.md:179`).
- Tabla `order_intents` — AS-IS §5 NOT FOUND (`fase0-decision-spine-asis-2026-08-24.md:150`).

El mapping F0.3 dejó OrderProposal como **(no-op)** por solape con OrderIntent+Recommendation (`fase0-decision-spine-mapping-2026-08-24.md:30`) y DecisionJournal como **decisión futura** reutilizando `decision_sessions` (`fase0-decision-spine-mapping-2026-08-24.md:32`).

### 1.3 Por qué abrir ahora

- Post-v1.7.0-beta el spine tiene contrato (D2), risk de cesta unificado SEMI=AUTO (D1), Fit, DS-05, DS-03 — [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) § Ejecución.
- Falta un **nombre de fase** estable para «lo que está en cola antes del confirm» y un **audit trail append-only** de transiciones (propuesta → veto → confirm → fill) sin confundirlo con la foto JSONB de `decision_sessions`.
- Daily Decision Board ya es **vista** sobre agregadores existentes (`decision-board-page.tsx:6`); no sustituye un journal de eventos.

---

## 2. Decisión

### 2.1 OrderProposal — capa nominal, sin duplicar Recommendation ni Intent

**OrderProposal** es el **handle de fase spine** entre «Runtime ha decidido» y «Intent autorizado». **No** es un cuarto sizing ni una segunda Recommendation.

| Capa                     | Qué guarda                                                                                                                                       | Qué NO hace                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| `DecisionPackage`        | Identidad de la tesis (acción, métricas, breakdown)                                                                                              | No sizing operativo ni autorización                                  |
| `Recommendation`         | Cara operativa (action, suggestedQuantity, status)                                                                                               | No es voluntad autorizada                                            |
| **`OrderProposal` (v1)** | **Referencias + status de fase**: `proposalId`, `decisionId`, `recommendationId`, `sessionId`, `accountId`, `instrumentId`, `status`, timestamps | **No copia** action, quantity, metrics, side — se resuelven por refs |
| `OrderIntent`            | Voluntad autorizada (side, quantity, source, authorizedBy)                                                                                       | No es propuesta; es post-confirm/policy                              |

**Persistencia v1 (preferir adaptar):** ancla en `decision_sessions` con `kind='propose'` (`decision-session.ts:24`). `OrderProposalV1` es un **DTO de proyección** mapeado desde esa fila + refs embebidas en `payload.recommendation` / `payload.runtime.decisionPackage` — **sin tabla `order_proposals` en F1** salvo que F1 demuestre necesidad de índice aparte.

Estados mínimos v1: `open` | `confirmed` | `rejected` | `superseded` | `expired` (derivados de sesión + journal; no reemplazan `RecommendationStatus` en `recommendation.ts:8`).

### 2.2 DecisionJournal — audit trail append-only, no sustituto de DecisionSession

**DecisionJournal** registra **eventos de transición** del spine (quién/qué/cuándo), en append-only.

|              | `decision_sessions`                                       | `DecisionJournal` (v1)             |
| ------------ | --------------------------------------------------------- | ---------------------------------- |
| Granularidad | Foto completa del razonamiento (JSONB)                    | Evento atómico                     |
| Mutabilidad  | Update en confirm (`confirm_recommendation.py:554`)       | **Append-only**                    |
| Replay       | Decision Replay proyecta pasos (`decision-session.ts:75`) | Timeline cronológica de decisiones |
| Learning     | `SessionOutcomeV1` en sesión (`decision-session.ts:88`)   | Fuera de alcance v1                |

**No reemplaza** `decision_sessions` ni `decision_memory`. Referencia `session_id` y/o `decision_id` cuando existan.

Eventos v1 (cerrados):

| `eventType`                             | Cuándo                                                                                            |
| --------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `proposal_recorded`                     | Tras persist `propose` (`propose_recommendation.py:445`)                                          |
| `gate_evaluated`                        | Tras `check_opening` en SEMI o AUTO (`confirm_recommendation.py:469` · `execution_router.py:604`) |
| `human_confirm`                         | Confirm con `execute=False` o intent autorizado                                                   |
| `human_reject`                          | Intent `rejected_by_gate` / retirada UI                                                           |
| `risk_veto`                             | VETO cesta/freshness/mandate (`confirm_recommendation.py:340` · `CURRENT_SYSTEM.md:49`)           |
| `contract_verified` / `contract_absent` | D2 (`confirm_recommendation.py:290` · `:297`)                                                     |
| `executed`                              | Fill OK (`confirm_recommendation.py:365` · `execution_router.py:716`)                             |

Persistencia v1: **tabla nueva** `decision_journal_entries` (Alembic = autoridad, `CURRENT_SYSTEM.md:12`). Es el único create de DDL en F1.

### 2.3 Alcance v1 — minimal, fail-closed, paper-only

- **Paper-only / DEMO** — mismo universo TRADING (ADR-019); Lab/Radar no emiten journal spine.
- **SEMI = AUTO** en risk de cesta (D1); journal registra vetos en ambos carriles, no los unifica en código nuevo.
- **Fail-closed:** eventos de veto y contract conflict se registran; no se inventan PASS ni sizing.
- **H3 congelado:** aperturas orphan `contract=absent` siguen ejecutando — journal las marca, **no cambia** el comportamiento (`CURRENT_SYSTEM.md:46` · `confirm_recommendation.py:288`).
- **Sin motor Attribution** — `mandate_trade_links` sigue siendo hook (`tables.py:1331`); journal no lo sustituye.

### 2.4 Fuera de alcance v1

- Nuevo motor de ranking, PortfolioFit adicional, DailyOrchestrator.
- Cambiar internals de `ExecuteTrade` (`accounts/trade.py:17`).
- Belief / gobernanza IA · `contract:gen` (salvo F2 aprobado).
- Reconciliar vocabulario Dictamen vs `DecisionAction` (TO-BE §6; diferido).

---

## 3. Alternativas rechazadas

| Alternativa                                                   | Por qué se rechaza                                                                                 |
| ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **A. OrderProposal = nueva Recommendation**                   | Duplica `RecommendationV1` (`recommendation.ts:16`); viola mapping F0.3 no-op por solape.          |
| **B. OrderProposal = alias de OrderIntent**                   | Intent es post-autorización (`order-intent.ts:20`); mezclar fases rompe D2 y el camino SEMI.       |
| **C. Tabla `order_proposals` greenfield en F1**               | Duplica `decision_sessions` propose; preferir proyección DTO hasta demostrar índice/query propio.  |
| **D. DecisionJournal = ampliar JSONB de `decision_sessions`** | Mezcla foto + eventos; dificulta timeline append-only e indexación por cuenta/fecha.               |
| **D. DecisionJournal = reemplazar `decision_sessions`**       | Pierde Decision Replay (`value-analysis-tracker.ts:145`) y learning (`operativa-outcomes.tsx:3`).  |
| **E. Orquestador Daily que decide**                           | TO-BE §4: Daily = vista; `GetDailyOpsReport` no decide (`daily_ops_report.py:51` citado en TO-BE). |

---

## 4. Consecuencias

### Positivas

- Vocabulario spine alineado con RFC-008: propuesta nombrada sin cuarto artefacto de sizing.
- Audit trail consultable para ops y UI read-only (F3).
- F1 acotado: DTO + 1 tabla + writers en puntos existentes (propose, confirm, router).

### Negativas / deuda

- Dos fuentes de verdad **complementarias** (sesión vs journal) — documentar en UI «Session = foto · Journal = timeline».
- Writers best-effort hoy en propose/confirm (`propose_recommendation.py:448` · `confirm_recommendation.py:406`) — F1 debe definir si journal es strict o best-effort igual que sesión.
- F2 puede requerir `contract:gen` — **bloqueado** hasta aprobación explícita.

### Relación con artefactos existentes (diagrama)

```text
Assessment[] → run_decision_runtime          decision_runtime.py:256
  → DecisionPackage (contrato)                 decision-package.ts:39
  → Recommendation (cara operativa)          recommendation.py:23
  → OrderProposal (handle fase, refs only)   [ADR-029 — DTO v1]
  → DecisionSession kind=propose (persist)   tables.py:602 · propose_recommendation.py:445
  → DecisionJournal proposal_recorded        [ADR-029 — tabla v1]

… humano / policy …

  → OrderIntent (autorizado)                 order-intent.ts:20 · confirm_recommendation.py:279
  → DecisionJournal human_confirm | risk_veto | executed
  → ExecuteTrade (fill)                        accounts/trade.py:17
```

---

## 5. Implementación (referencia)

Plan detallado: [`plan-order-proposal-journal-2026-08-24.md`](../engineering/plan-order-proposal-journal-2026-08-24.md).  
Handoff F1: [`traspaso-relevo-order-proposal-journal-apertura-2026-08-24.md`](../engineering/traspaso-relevo-order-proposal-journal-apertura-2026-08-24.md).

**Criterio de aceptación docs:** ADR + plan + traspaso creados; **cero código** en este ciclo.

---

## 6. Referencias

- `docs/engineering/fase0-decision-spine-asis-2026-08-24.md` §7
- `docs/engineering/fase0-decision-spine-tobe-2026-08-24.md` §3, §6
- `docs/engineering/fase0-decision-spine-mapping-2026-08-24.md` (filas OrderProposal, Decision journal)
- `docs/CURRENT_SYSTEM.md`
