# ADR 015: Scientific Domain vs Trading Domain

## Estado

**Aceptado** — 2026-07-24  
**Tipo:** frontera de dominios (ubiquitous language / bounded contexts).  
**Depende de:** [ADR-011](./011-quantitative-research-platform.md), [ADR-012](./012-scientific-validation-knowledge-evolution.md), [ADR-013](./013-research-mathematics-statistical-foundations.md), [RFC-008](../rfc/008-cognitive-decision-architecture.md), [ADR-009](./009-backtesting-research-platform-h0.md).

> **ADR-014** permanece **reservado** (causalidad profunda / incertidumbre avanzada) y **no** bloquea Fase 1.  
> Este ADR (**015**) cierra la recomendación de auditoría: separar el **modelo científico** del **modelo de trading** antes de acumular experimentos.

---

## 1. Contexto

Sin esta frontera, conceptos como Hypothesis, Belief, Strategy y Signal tienden a mezclarse en tablas, APIs y UI. A escala de miles de investigaciones eso genera deuda imposible de migrar.

El QROS es una **plataforma científica**; el trading es **una aplicación** del conocimiento — no el dueño del modelo de datos.

---

## 2. Decisión

Existen **dos dominios de objetos** con lenguajes distintos. Solo se conectan por un puente explícito (Reasoning → DecisionPackage / Policy), no por herencia ni por “usar la misma tabla”.

```text
 Scientific Domain                    Trading Domain
 ─────────────────                    ──────────────
 ResearchQuestion                     Strategy / Preset
 OpenProblem                          Signal
 Hypothesis / Anti-Hypothesis         Recommendation
 Experiment / Trial                   Order / Trade / Fill
 Evidence                             Position / Portfolio
 Belief                               Account / Ledger
 Knowledge / Theory                   RiskPolicy / TradingPolicy
 DiscoveryVector                      Execution / Slippage model (ops)
 ResearchBudget / ScientificCost
```

```text
Scientific Domain
       │
       ▼
Reasoning Engine  (Inference ⊂ composición de beliefs/grafo;
                   Reasoning ⊂ justificación + reject + “por qué / qué lo falsaría”)
       │
       ▼
Trading Domain  (DecisionPackage → Gate → Paper/Live)
```

### 2.1 Reglas de frontera

| Regla | Norma |
|-------|--------|
| **F1** | Ningún objeto Trading es fuente de verdad de Belief/Knowledge. |
| **F2** | Una Strategy **referencia** hipótesis/knowledge ids; no *es* la hipótesis. |
| **F3** | Backtest H0 (ADR-009) es **instrumento de Experiment** en Scientific Domain; su output alimenta Evidence, no “la estrategia ganadora” como Knowledge. |
| **F4** | APIs y paquetes deben poder etiquetarse `scientific.*` vs `trading.*` (migración gradual OK; no mezclar nombres en contratos nuevos). |
| **F5** | UI puede mostrar ambos; copy de producto: laboratorio vs operativa (ADR-011). |

### 2.2 Inference vs Reasoning (capas mentales)

Dentro del Reasoning Engine (ADR-011), distinguir:

1. **Inference** — derivar relaciones / actualizar Beliefs desde Evidence + grafo.  
2. **Reasoning** — explicar, detectar conflictos, **Reject inference**, falsabilidad (“qué tendría que pasar para dejar de creerlo”).  
3. **Decision** — emitir artefacto hacia Trading Domain (solo tras Policy).

No implica tres microservicios en Fase 1; sí contratos y nombres claros cuando existan.

---

## 3. Backlog conceptual (no bloquea Fase 1)

Queda **explícitamente fuera** de este ADR y **no** congela ingeniería H0/Fase 1:

| Tema | Destino sugerido |
|------|------------------|
| **Infrastructure Domain** (tercer contexto) | Documentado en [domain-language.md](../domain-language.md); ADR propio solo si hace falta |
| **Observation** como capa explícita antes de Inference | domain-language + Reasoning Engine |
| Knowledge Lifetime (Birth→…→Archived) | Extensión ADR-012 o ADR futuro |
| Motor de sorpresa (Unexpectedness completo) | Post Fase 4–5 |
| Actualización bayesiana explícita (priors) | ADR futuro / nota en 013 |
| Opportunity Cost de investigar A vs B | Planner Fase 5 |
| Knowledge Graph como “el” sistema | Evolución natural; no reescribir ADR-011 ahora |
| Causal discovery auto, GNN, RL, LLM→Beliefs | **Prohibido temprano** (ruido); ADR-014+ |

**Diccionario canónico vivo:** [docs/domain-language.md](../domain-language.md) — no más ADRs filosóficos de alto nivel antes de Fase 1.

**Prioridad de implementación intacta:** motor determinista → ledger → validation → knowledge → reasoning → IA planner.

---

## 4. Consecuencias

**Positivas:** lenguaje ubicuo estable; QROS no colapsa en “otro optimizador de estrategias”; RFC-008 Trading/Policy encaja como consumidor del Scientific Domain.

**Costes:** algo más de indirection en esquemas Fase 2+; Fase 1 (`research_trials`, costes) nace **ya** en Scientific Domain.

---

## 5. Ratificación

- [x] Scientific Domain ≠ Trading Domain  
- [x] Puente único vía Reasoning → Decision  
- [x] Strategy ⊄ Hypothesis  
- [x] Backlog §3 no bloquea Fase 1  
- [x] Estado → **Aceptado**

**Código:** pausa hasta *«adelante con Fase 1»*.
