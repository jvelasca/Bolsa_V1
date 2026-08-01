# RFCs — Constitución técnica Bolsa V1

Documentos **ejecutables** (contratos verificables). No son auditorías de opinión.

Orden de redacción (bloqueado tras auditoría 2026-07-21 + ajuste A1):

| RFC | Título | Estado |
|-----|--------|--------|
| [000](./000-ubiquitous-language.md) | Ubiquitous Language | **approved** |
| [001](./001-artifact-catalog.md) | Artifact System & Catalog | **approved** |
| [002](./002-capability-model.md) | Capability Model & Domain Registry | **approved** |
| [003](./003-architecture.md) | Platform Architecture | **approved** |
| [004](./004-engineering-handbook.md) | Engineering Handbook | **approved** |
| [005](./005-feature-registry.md) | Feature Registry & IFeaturePort | **approved** |
| [006](./006-data-contracts-and-lineage.md) | Data Contracts & Lineage | **approved** |
| [007](./007-ai-governance.md) | AI Governance | **approved** |
| [008](./008-cognitive-decision-architecture.md) | Cognitive Decision Architecture | **approved** (2026-07-22) |

**Pirámide 000–008:** constitución + núcleo cognitivo sellados.

> **Congelación IND-\*:** activa hasta **D2 en curso** (Knowledge Layer + DecisionPackage TA-only).  
> **Núcleo:** Profile → TradingPolicy → Opportunity → Evidence → Decision → Execution (pipeline jerárquico; no comité LLM).

| Fase código | Estado |
|-------------|--------|
| **F1 / F1+** AI Governance | **Hecho** — `bolsa_ai`, draft APIs, JSONL + tabla `llm_calls`, compose Ollama |
| **F2** Feature Registry | **Hecho (esqueleto+)** — DEFs, golden parity, scan + HTTP `/api/features/*` |
| **Ops** | `llm_calls` PG ✅ · Ollama compose ✅ · smoke `@pytest.mark.ollama` ✅ |
| **Linter** | `packages/py/.importlinter` (Proxy First / domain purity) |
| **D0** Cognitive | **RFC-008 approved** |
| **D1** Profile + Policy | **Hecho** — schemas + plantillas + UI Configuración → Perfil inversor |
| **D2** Knowledge + Gate | **Hecho** — Facts → Score_TA → DecisionPackage + `gate_decision_package` (D2.4) |
| **D3** Evidence Engine v1 | **Hecho** — PSR/DSR + TrialsLog + suite + auto-live block |
| **D4** MarketEvents + hot path | **Hecho** — eventos + decay; Gate en `ExecutionRouter` paper_auto |
| **D5** Fund + Opportunity | **Hecho** — Score_FUND + Opportunity TA+FUND + WeightRules horizonte |
| **D6** Macro + Market State | **Hecho** — Score_MACRO + régimen + WeightRules contextuales + `validate_context` |
| **D7** Confidence + Observed + Efectividad | **Hecho** — lifecycle + observed + panel/API |
| **D7+** Persistencia PG cognitiva | **Hecho** — 4 tablas + repos + GET/POST `/api/ai/*` |
| **D7+** Gate → Memory hot path | **Hecho** — `ExecutionRouter` paper_auto persiste PASS/VETO |

Notas: [F1-IMPLEMENTATION-NOTES.md](./F1-IMPLEMENTATION-NOTES.md) · [F2-FEATURE-REGISTRY-NOTES.md](./F2-FEATURE-REGISTRY-NOTES.md).

Dictamen: [AI_PLATFORM_SOLUTION.md](../AI_PLATFORM_SOLUTION.md). ADRs: [docs/adr/](../adr/).
