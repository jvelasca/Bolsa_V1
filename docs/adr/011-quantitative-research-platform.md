# ADR 011: Quantitative Research Operating System (QROS)

## Estado

**Aceptado** — 2026-07-24 (v1.1 constitucional) — **congelado**  
Auditorías A1–A3; enmienda epistemológica A1 (Evidence ≠ Belief ≠ Knowledge).  
**Leyes de evolución del conocimiento:** [ADR-012](./012-scientific-validation-knowledge-evolution.md).  
**Fundamentos matemáticos / scores:** [ADR-013](./013-research-mathematics-statistical-foundations.md) (v1.1; ADR-014 causal profundo diferido).  
**Frontera de dominios:** [ADR-015](./015-scientific-domain-vs-trading-domain.md) (Scientific ≠ Trading).  
**Enlazado con:** [RFC-008](../rfc/008-cognitive-decision-architecture.md), ADR-009, [ADR-010](./010-platform-kernel-radar-execution.md), ADR-012, ADR-013, ADR-015.

> **Numeración:** `010` = Platform Kernel. Este ADR es **011**.

---

## 1. Cambio de categoría

Bolsa V1 **deja de diseñarse** como “plataforma de trading con backtesting profesional”.

**Definición oficial del producto (núcleo):**

> Construir un **Sistema Operativo de Investigación Cuantitativa (Quant Research Operating System, QROS)** capaz de **generar, validar, acumular, razonar y reutilizar** conocimiento científico sobre el comportamiento de los mercados financieros, para asistir o automatizar decisiones de inversión de forma **explicable, reproducible y estadísticamente robusta**.

**Objetivo científico (complementa ADR-012):**

> El objetivo del QROS **no** es maximizar el beneficio histórico, sino construir **conocimiento predictivo reproducible** con la **menor incertidumbre posible**.

El **trading** (paper/live) es el **primer caso de uso** de ese conocimiento — no el objetivo del sistema.

| Antes (H0 / retail) | Después (QROS) |
|---------------------|----------------|
| Optimizar parámetros | **Investigar** (= reducir incertidumbre) |
| Estrategia como unidad | **Hipótesis** (+ Belief + falsadores) |
| Backtester = el producto | Backtest = **instrumento** de experimento |
| PASS / FAIL binario | **Evidence → Belief → Knowledge** (velocidades distintas) |
| Max PnL IS | **Discovery Score** (temporal) + Entropy / Research ROI |

---

## 2. Contexto (problema)

Maximizar \(PnL_{IS}(\theta)\) produce amnesia, picos aislados, ausencia de peaje \(K\), soberbia algorítmica (“siempre hay señal”) y nula meta-investigación.

H0 ([ADR-009](./009-backtesting-research-platform-h0.md)) es la base **determinista de medición**. Este ADR define la **capa científica** encima. El Evidence Engine de [RFC-008](../rfc/008-cognitive-decision-architecture.md) es el **mismo concepto de evidencia** a escala de decisión en vivo; QROS lo usa también en research.

---

## 3. Modelo epistemológico (constitucional) — **D18**

Separación explícita de responsabilidades y **velocidades de cambio**:

```text
Datos
  ↓
Hechos (Facts / Assessments)
  ↓
Experimentos (trials, estrategias como manifestaciones)
  ↓
Evidencia (Evidence)     ← cambia con cada trial / EdgeReport
  ↓
Belief                   ← cambia con agregación evidencial (+ CI)
  ↓
Knowledge                ← cambia lento (teoría consolidada)
  ↓
Reasoning                ← compone / rechaza inferencia
  ↓
TradingPolicy / Decision Engine (RFC-008)
```

| Capa | Qué es | Velocidad | Ejemplo |
|------|--------|-----------|---------|
| **Experiment** | Ejecución medible (BT, WFO fold, paper window) | Rápida | Un run con `manifest` |
| **Evidence** | Resultado estadístico de uno o más experimentos | Rápida | DSR=0.92, p-MC=0.03, landscape CV=0.12 |
| **Belief** | Credencia contextual sobre una hipótesis | Media | belief=0.71 · CI · n=40 · weight |
| **Knowledge** | Teoría reutilizable consolidada (MKL) | Lenta | “Momentum en tech con VIX bajo suele…” |

**Por qué importa:** una mala racha (evidence reciente débil) **baja el Belief**, pero **no borra** Knowledge consolidado de golpe. El Knowledge solo se degrada vía **Decay**, contradicciones acumuladas y **Pruning** (D24).

### Taxonomía de producto (5 niveles) — alineada

```text
5. POLÍTICA     → TradingPolicy / Hard Gate
4. TEORÍA / Knowledge  → MKL (+ Belief agregado, Decay, Pruning)
3. HIPÓTESIS    → unidad canónica (+ Belief, falsadores)
2. HECHOS       → Facts / Assessments
1. DATOS        → OHLCV PIT, fundamentales, eventos
```

**Unidad canónica (D9):** Hypothesis. Las estrategias son **experimentos / artefactos ejecutables**, no el conocimiento.

---

## 4. Principios fundacionales

### P1 — Investigar ≠ optimizar

Investigar = reducir **Research Entropy**. Valor ≈ **Research ROI** = \(E[\Delta \text{Information}] / \text{Research Cost}\) (en \(K\) y cómputo), no solo PnL.

### P2 — IA propone y planifica; motor y suite juzgan

Prohibido que la IA declare Sharpe, edge, Discovery Score o Belief. Solo formula hipótesis/preguntas y planes.

### P3 — Landscape obligatorio

Pico aislado (p.ej. CV de métricas en vecindad &gt; 0.25) → **FAIL**.

### P4 — Belief System — **D13** (ampliado)

Cada hipótesis mantiene al menos:

| Campo | Rol |
|-------|-----|
| `belief` ∈ [0,1] | Grado de creencia puntual |
| `belief_ci` | Intervalo de confianza (o equivalente) |
| `sample_size` / `n_experiments` | Tamaño muestral evidencial |
| `evidence_weight` | Peso agregado (calidad × n) |
| `contexts_ok` / `contexts_fail` | Condicionamiento |
| `falsifiers` | **Qué evidencia la destruiría** (D21) |
| `last_reviewed_at` | Última actualización |
| `evidence_ids[]` / `experiment_ids[]` | Trazas |

**0.72 con n=15 ≠ 0.72 con n=2500.**

### P5 — Meta-Knowledge — **D14**

Market Knowledge vs Meta-Knowledge (“qué líneas de investigación merecen presupuesto”).

### P6 — Knowledge Decay + **Pruning** — **D15 / D24**

- **Decay:** belief/knowledge quality baja sin reconfirmación o tras cambio de régimen.  
- **Pruning:** proceso periódico — belief muy bajo + sin evidencia reciente + muchas contradicciones → archivar / fusionar / retirar del grafo activo.  
Un sistema que solo aprende se vuelve inmanejable.

### P7 — Budget por valor esperado — **D11**

No gastar \(K\) uniforme. Priorizar por **Expected Information Gain** vs **Research Cost** → Research ROI. El sistema debe poder decir: *“no merece la pena investigar esto”*.

### P8 — Consolidation — **D16**

Explorar → demostrar → **generalizar a teoría** (Knowledge lento).

### P9 — Conflictos + **Reject inference** — **D17**

Reasoning Engine detecta conflictos entre creencias y puede **rechazar emitir recomendación** (“no existe evidencia suficiente”) — no solo explicar.

### P10 — Falsabilidad — **D21**

Toda hipótesis declara falsificadores (regímenes, umbrales, contraexperimentos). Popperiano y operativo.

### P11 — Reproducibilidad científica — **D22**

Todo descubrimiento (no solo el BT) debe ser reproducible vía identidad de artefactos (estilo DOI interno):

`knowledge_id` · `hypothesis_version` · `dataset_version` · `code_version` · `feature_version` · `policy_version` · `seed` · `RunManifest` / evidence ids.

### P12 — Scores temporales y de calidad — **D19 / D23**

- **Discovery Score** no es un escalar eterno: lleva **confidence**, **decay**, **trend** (mejorando / estable / degradándose).  
- **Knowledge Quality Score** mide calidad del *conocimiento* (reutilización, transfer, estabilidad, evidencia, conflicto) — distinto del Discovery Score de un hallazgo puntual.

### P13 — Grafo semántico causal — **D20**

Aristas tipadas, no solo “relacionado con”:

`CAUSES` · `SUPPORTS` · `CONTRADICTS` · `DEPENDS_ON` · `SPECIAL_CASE_OF` · `GENERALIZES`

Permite razonar, no solo recordar.

---

## 5. Arquitectura: cinco motores (+ desglose epistemológico interno)

```text
        QUANTITATIVE RESEARCH OPERATING SYSTEM (QROS)
┌─────────────────────────────────────────────────────────────┐
│ RESEARCH ENGINE                                             │
│  Hypothesis · Planner · Curiosity · EIG / Budget / ROI      │
└───────────────────────────┬─────────────────────────────────┘
                            │ experimento
┌───────────────────────────▼─────────────────────────────────┐
│ VALIDATION ENGINE                                           │
│  BT dual · costes · WFO/CPCV · MC · DSR/PSR · Landscape     │
│  → emite Evidence (+ EdgeReport)                            │
└───────────────────────────┬─────────────────────────────────┘
                            │ Evidence
┌───────────────────────────▼─────────────────────────────────┐
│ KNOWLEDGE ENGINE (módulos internos conceptualmente distintos)│
│  [Evidence store] → [Belief Engine] → [Knowledge / Graph]   │
│  Meta-Knowledge · Decay · Pruning · Reputation · Transfer   │
│  Research Tree · reproducibilidad · → MKL (RFC-008)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ Beliefs + Knowledge
┌───────────────────────────▼─────────────────────────────────┐
│ REASONING ENGINE                                            │
│  Compone · conflictos · Reject inference · explica          │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│ TRADING ENGINE (RFC-008)                                    │
│  Policy Gate · Paper (badge) · Live hard gate               │
└─────────────────────────────────────────────────────────────┘
```

Pueden desplegarse como un paquete en Fase 2, pero **los contratos y tablas no deben fusionar Evidence, Belief y Knowledge en un solo blob**.

---

## 6. Decisiones normativas (D1–D24)

| ID | Decisión | Directiva |
|----|----------|-----------|
| **D1** | Objetivo | Discovery Score + Entropy/ROI; no max retorno IS |
| **D2** | Landscape | Obligatorio para PASS; pico → FAIL |
| **D3** | Scores hallazgo | EdgeReport = evidencia; Discovery Score = agregado (temporal: D19) |
| **D4** | Multi-activo | Fase 7 |
| **D5** | MKL | Un solo destino RFC-008 |
| **D6** | Cap \(K\) | 100/sesión · 500/hipótesis (ajustable) |
| **D7** | Hold-out | 20% ciego por universo |
| **D8** | Paper/Live | WARN/UNCHECKED + badge en Paper; Live hard gate |
| **D9** | Unidad | Hypothesis (+ Belief + falsifiers) |
| **D10** | Temprano | Evidence/Belief/Knowledge v1 desde **Fase 2** |
| **D11** | Budget | EIG vs cost → ROI; abandono si no informativo |
| **D12** | Ciclo | Ver §3 (modelo epistemológico completo) |
| **D13** | Belief | Probabilístico + CI + n + evidence_weight |
| **D14** | Meta-Knowledge | Separado del knowledge de mercado |
| **D15** | Decay | Temporal / régimen |
| **D16** | Consolidation | Generalización a teoría lenta |
| **D17** | Reasoning | Conflictos + **Reject inference** + explicación |
| **D18** | Epistemología | Evidence ≠ Belief ≠ Knowledge (velocidades) |
| **D19** | Discovery Score temporal | score + confidence + decay + trend |
| **D20** | Grafo semántico | Aristas CAUSES/SUPPORTS/CONTRADICTS/… |
| **D21** | Falsabilidad | `falsifiers` obligatorios en hipótesis |
| **D22** | Reproducibilidad | Identidad de versiones (DOI interno) en descubrimientos |
| **D23** | Knowledge Quality Score | Calidad del conocimiento ≠ calidad de un BT |
| **D24** | Knowledge Pruning | Archivar / fusionar / retirar conocimiento muerto |

### Discovery Score (producto)

Pesos orientativos: topología 30% · WFE+DSR/PSR 25% · MC 15% · costes 10% · transfer 10% · complejidad 5% · \(K\) 5%.  
Siempre acompañado de **trend/decay/confidence** (D19).  
Gate orientativo: PASS ≥ 70 + landscape OK + DSR mín.; WARN 40–69; FAIL &lt; 40.

### Parsimonia

≤ 4–5 hiperparams libres por **bloque** activo.

### Dualidad BT

VectorBT (discovery) · event-engine + **costes reales** (validation/gate).

---

## 7. Roadmap normativo (Fases 0–7)

| Fase | Entregable |
|------|------------|
| **0** | Ratificación ADR-011 v1.1 (este documento) |
| **1** | Motor creíble: costes en PnL; métricas; `research_trials` (\(K\)); manifests reproducibles |
| **2** | **Evidence store + Belief Engine + Knowledge v1** (contratos separados) + Research Tree mínimo + falsifiers stub + sync MKL |
| **3** | Validation cableada: WFO, CPCV ligero, MC, DSR/PSR, EdgeReport + Gate UI |
| **4** | Landscape + Discovery Score **temporal** |
| **5** | Research Engine v1: Generator, Planner, Curiosity/EIG/Budget |
| **6** | Graph semántico, Meta-Knowledge, Decay+Pruning, Consolidation, Reasoning (reject), Knowledge Quality Score |
| **7** | Multi-activo / portfolio |

UI: etiqueta “Backtesting” permitida; contratos = **QROS**.

---

## 8. Consecuencias

**Positivas:** epistemología estable a 3–5 años; alineación RFC-008; trading explicable y humilde (“no sabemos”); diferenciación difícil de copiar.

**Riesgos:** alcance (mitigar por fases); calibración de Belief (empezar simple); landscape caro (solo candidato final); confusión de scores (UI clara: Evidence / Belief / Discovery / Knowledge Quality).

**ADR-009:** sigue gobernando H0; ADR-011 exige que trials futuros cuelguen de Hypothesis y alimenten Evidence → Belief.

---

## 9. Criterio de éxito

> Bolsa V1 no corona la estrategia que más gana.  
> Genera **evidencia**, actualiza **creencias calibradas** (con IC y n), consolida **conocimiento lento** (con decay y pruning), razona pudiendo **rechazar inferencia**, y solo entonces opera — de forma reproducible.

---

## 10. Glosario (extracto)

| Término | Definición |
|---------|------------|
| Evidence | Resultado estadístico de experimento(s); rápido |
| Belief | Credencia contextual + CI + n + weight |
| Knowledge | Teoría consolidada (lenta) en MKL/grafo |
| Knowledge Quality Score | Calidad del nodo de conocimiento |
| Falsifier | Condición/evidencia que invalidaría la hipótesis |
| EIG | Expected Information Gain |
| Pruning | Retirada/archivo de conocimiento muerto |
| Reject inference | Negativa fundamentada a recomendar |
| DOI interno | Bundle de versiones para reproducir un discovery |

---

## 11. Ratificación

- [x] Definición QROS (§1)  
- [x] D1–D24 (+ modelo epistemológico §3)  
- [x] Roadmap 0–7 (Evidence/Belief/Knowledge en Fase 2)  
- [x] Estado → **Aceptado** (v1.1)

**Próximo paso de ingeniería (histórico):** orden “adelante con Fase 1”.  
**Baseline actual:** [ADR-017](./017-baseline-v1-5-research-observatory.md) (Fase 1 + 1.5 entregadas).  
Persistencia Scientific Domain → [ADR-016](./016-research-persistence-model.md).  
Leyes científicas → [ADR-012](./012-scientific-validation-knowledge-evolution.md).
