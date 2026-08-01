# ADR 017: Research Platform Baseline v1.5

## Estado

**Aceptado** — 2026-07-24  
**Tipo:** baseline de ingeniería (congela arquitectura ya validada; **no** introduce conceptos nuevos).  
**Depende de:** [ADR-009](./009-backtesting-research-platform-h0.md), [ADR-010](./010-platform-kernel-radar-execution.md), [ADR-011](./011-quantitative-research-platform.md), [ADR-012](./012-scientific-validation-knowledge-evolution.md), [ADR-013](./013-research-mathematics-statistical-foundations.md), [ADR-015](./015-scientific-domain-vs-trading-domain.md), [ADR-016](./016-research-persistence-model.md), [RFC-000](../rfc/000-ubiquitous-language.md), [RFC-008](../rfc/008-cognitive-decision-architecture.md), [domain-language.md](../domain-language.md), [research-lifecycle.md](../engineering/research-lifecycle.md).

> Formaliza la línea base tras **Fase 1** (motor + ledger \(K\)) y **Fase 1.5** (Research Observatory).  
> ADR-014 (causalidad profunda) permanece **reservado / aplazado**.

---

## 1. Objetivo

Declarar **estable** la primera versión funcional del QROS como laboratorio observable.

A partir de este ADR:

- el **Scientific Domain** (arquitectura y persistencia Fase 1) queda congelado como baseline;
- el **Trading Domain** permanece desacoplado (ADR-015);
- el **Research Observatory** (`/api/research/*` + UI `/research`) es la interfaz oficial de lectura del laboratorio;
- las siguientes fases serán **evolutivas** sobre esta base, no reescrituras — salvo ADR de sustitución explícito.

---

## 2. Componentes de la Baseline v1.5

| Componente | Estado | Referencia |
|------------|--------|------------|
| Backtest Engine H0 | ✅ | ADR-009 |
| Cost Model (commission / slippage / spread) | ✅ | Fase 1 |
| Metrics IS (Sharpe, Sortino, Calmar, MaxDD, PF, WR, …) | ✅ | Fase 1 |
| `backtest_runs` (+ trades) | ✅ | ADR-016 |
| `research_trials` (ledger \(K\)) | ✅ | ADR-016 |
| Research API (consulta) | ✅ | Fase 1.5 |
| Research Dashboard / History UI | ✅ | Fase 1.5 |
| Bloque Research en resultado BT | ✅ | Fase 1.5 |
| Domain Language | ✅ | RFC-000 / domain-language |
| ADR-009 … ADR-016 | ✅ | este baseline |
| RFC-000, RFC-008 | ✅ | lenguaje + cognitive (live ≠ research ledger) |
| Research lifecycle (ops) | ✅ | research-lifecycle.md |

```text
POST /backtests/run  →  Engine H0  →  backtest_runs + research_trials
                                              │
                                     Research Observatory
                                      API  ·  UI /research
```

---

## 3. Explícitamente fuera de Baseline (congelado)

Mientras v1.5 esté vigente **no** se implementan:

- Evidence Store (`research_evidence`)
- Belief Engine / `hypothesis_beliefs`
- Knowledge Engine / Knowledge Graph
- Discovery Vector persistente / Discovery Score
- Reasoning Engine / Curiosity / EIG adaptativo
- IA Planner / generador de hipótesis
- Causal Discovery (ADR-014)

Mejoras **aceptables** sin nuevo ADR de dominio: UX, rendimiento, filtros, exportaciones, observabilidad, bugs.  
**No aceptables** sin ADR nuevo: cambios semánticos de dominio, entidades cognitivas de research, reinterpretar ADR-009–016.

---

## 4. Criterio de salida → Fase 2

La transición a Evidence / Belief / Knowledge **no** depende del calendario.

Depende de **madurez del laboratorio**, por ejemplo:

1. API y UI de Observatory estables y usadas de forma habitual.
2. El ledger describe fielmente los experimentos (sin consultar Postgres a mano).
3. Volumen significativo de `research_trials` con sentido estadístico.
4. Patrones repetidos cuya consolidación justifique `research_evidence` (inspección individual ya no basta).
5. Preguntas de investigación reales formuladas desde los datos.

Umbrales orientativos (no dogmáticos): p. ej. cientos de trials acumulados y uso regular del observatorio. El hito es **empírico**.

---

## 5. Política de ADR futuros

Los ADR posteriores deberán **extender** esta Baseline, no sustituirla, salvo que el nuevo ADR declare explícitamente el reemplazo de una decisión anterior.

Prioridad operativa inmediata: **explotar el laboratorio** (familias de BT / optimize, validar trazabilidad `trialId` → run, acumular \(K\)) — no aumentar el número de conceptos.

**Nota operativa (2026-07-27):** el track de producto UI del laboratorio (Optimizar P3–P3.O + explotación P5–P9) está **cerrado y documentado** ([research-lifecycle.md § Cierre temporal](../engineering/research-lifecycle.md)).

**Activación Fase 2 (2026-07-27):** [ADR-018](./018-fase2-evidence-store-v0.md) — P2.A–P2.F cerrada (Evidence→…→MKL stub) con batería `pnpm test:fase2`. Discovery / Planner / Decay+Pruning siguen congelados.

---

## 6. Ratificación

- [x] Baseline v1.5 definida  
- [x] Componentes incluidos / excluidos  
- [x] Criterio empírico de salida a Fase 2  
- [x] Política de cambios y ADR futuros  
- [x] Estado → **Aceptado**

**Con ADR-017 finaliza la fase de diseño fundacional del QROS. A partir de este punto, la evolución del sistema deberá estar impulsada prioritariamente por la evidencia obtenida del propio laboratorio y no por nuevas ampliaciones conceptuales.**
