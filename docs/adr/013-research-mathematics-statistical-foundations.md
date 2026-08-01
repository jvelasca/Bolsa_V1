# ADR 013: Research Mathematics & Statistical Foundations

## Estado

**Aceptado** — 2026-07-24 (**v1.1** — cierre auditoría: Discovery Vector, causalidad mínima, incertidumbre tipada)  
**Tipo:** fundamentos matemáticos / estadísticos del QROS.  
**Depende de:** [ADR-011](./011-quantitative-research-platform.md), [ADR-012](./012-scientific-validation-knowledge-evolution.md), [RFC-008](../rfc/008-cognitive-decision-architecture.md).

| Documento | Pregunta |
|-----------|----------|
| ADR-011 | ¿**Qué** es el QROS? |
| ADR-012 | ¿**Cómo** evoluciona el conocimiento? |
| **ADR-013** | ¿**Qué significa matemáticamente** ser mejor / más informativo / más incierto? |
| *(futuro)* ADR-014 | Teoría causal profunda + representación avanzada de incertidumbre *(no bloquea Fase 1)* |

> **Fase 1** sigue en pausa hasta orden explícita *«adelante con Fase 1»*.

---

## 1. Objetivo

Magnitudes **comparables, versionadas, una pregunta cada una**.

**Frase guía:** el QROS construye **conocimiento predictivo reproducible con mínima incertidumbre**, no maximiza PnL histórico.

| Evitar | Preferir |
|--------|----------|
| ¿Qué estrategia gana más? | ¿Qué sabemos **hoy** que **ayer** no sabíamos? |

**Ley constitucional — Research Value ≠ PnL:** un experimento puede ser un **éxito científico** con PnL negativo si reduce incertidumbre o descarta familias (anti-hipótesis).

**Ley de trazabilidad (L-T):** *Nunca* se almacena una conclusión (Belief update material, Knowledge node, Anti-Hypothesis) **sin** la evidencia mínima que permite reconstruirla (evidence ids + manifest / DOI interno).

---

## 2. Research Question + Open Problem

```text
Research Question (RQ)
  ├── Hypotheses / Anti-Hypotheses
  ├── Experiments → Evidence
  ├── Beliefs
  └── Knowledge (si consolidado)

Open Problem (OP)     ← distinto de RQ
  └── Pregunta que permanece abierta tras cerrar RQs
      (p.ej. “¿Por qué funciona la tendencia en bancos?”)
```

- **RQ:** investigable y potencialmente respondible con el método actual.  
- **Open Problem:** conocimiento de segundo orden — *sabemos que no sabemos por qué*; no es un FAIL.

---

## 3. Dimensiones primarias + Discovery Vector

### 3.1 Representación interna obligatoria: **Discovery Vector**

La representación **interna** de un hallazgo/línea **nunca** es un escalar. Es:

\[
\mathbf{d} = \big(E,\; Q_e,\; R,\; T,\; S_t,\; C_r,\; V_r,\; P_c,\; U_x\big)
\]

| Componente | Símbolo | Pregunta única |
|------------|---------|----------------|
| Edge Strength | \(E\) | ¿Magnitud de ventaja estadística? |
| Evidence Quality | \(Q_e\) | ¿Calidad/nivel de experimentos? |
| Robustness | \(R\) | ¿Sensibilidad a perturbaciones? |
| Transferability | \(T\) | ¿Cambio de activo/sector? |
| Temporal Stability | \(S_t\) | ¿Estabilidad en el tiempo? |
| Research Confidence | \(C_r\) | ¿Cuánta certeza residual? (\(\approx 1-U\) agregado) |
| Research Value | \(V_r\) | ¿Cuánto aprendimos? *(≠ PnL)* |
| **Causal Plausibility** | \(P_c\) | ¿Cuánto de esto es *claim causal* vs correlación observada? |
| **Unexpectedness** | \(U_x\) | ¿Cuánta sorpresa informativa hubo vs prior? |

**Discovery Score \(D\)** es solo una **proyección UI** \(D = 100\cdot f_v(\mathbf{d})\).  
Re-pesar en 5 años **no destruye** \(\mathbf{d}\) histórico.

### 3.2 Causal Plausibility \(P_c\) (mínimo normativo)

No pretende “descubrir causalidad verdadera” (imposible en la mayoría de mercados). Impide teorías absurdas:

| Situación | \(P_c\) típico |
|-----------|----------------|
| Correlación observada, sin diseño causal | Bajo |
| Hipótesis con mecanismo económico plausible + falsifiers | Medio |
| Evidencia que discrimina alternativas + transfer | Más alto |
| Arista `CAUSES` en grafo | Solo con \(P_c\) alto + expediente (ADR-012) |

Evidence alta **no implica** \(P_c\) alto. La UI puede mostrar: *Evidence: alta · Causal plausibility: muy baja*.

Detalle formal de identificación causal → **ADR-014** (diferido).

### 3.3 Unexpectedness \(U_x\)

Sorpresa respecto al prior / Meta-Knowledge:

- Resultado “esperado” → \(U_x\) bajo (poco aprendizaje nuevo).  
- Resultado absurdo / contradictorio con teorías → \(U_x\) alto → priorizar investigación / Consolidation review.

### 3.4 Comparabilidad

Misma `math_version`, universo/normalización, horizonte, costes, hold-out — o **no rankear**.

---

## 4. Research Value, EIG y Scientific Cost

\[
\text{Priorizar} \approx \arg\max_i \; \frac{\mathbb{E}[\Delta I_i]}{\mathrm{ScientificCost}_i}
\]

| Magnitud | Rol |
|----------|-----|
| **EIG** \(\mathbb{E}[\Delta I]\) | Ganancia esperada de información *ex ante* |
| **\(V_r\)** | Valor realizado *ex post* (entropy↓, familias eliminadas, falsifiers) |
| **Scientific Cost** | No solo CPU: \(K\) gastados, espacio de búsqueda quemado, riesgo de multiple testing, coste de oportunidad de no explorar otra RQ |

5000 trials sobre un parámetro estéril → Scientific Cost alto, \(V_r\) bajo.  
1 experimento que elimina un área → Scientific Cost bajo relativo, \(V_r\) alto.

---

## 5. Incertidumbre tipada — *Why uncertain?*

Además de \(U\) escalar, toda incertidumbre material lleva **código de causa**:

| Código | Significado | Siguiente experimento típico |
|--------|-------------|------------------------------|
| `U_SAMPLE` | Pocos datos / \(n\) bajo | Más historia / otro TF |
| `U_CONFLICT` | Evidencias o teorías se contradicen | Experimento discriminante |
| `U_AMBIGUOUS` | Dos teorías compatibles con los datos | Diseño que separe mecanismos |
| `U_REGIME` | Depende de régimen no cubierto | Stratified / Validity Context |
| `U_DESIGN` | Experimento mala reputación | Redesign |
| `U_CAUSAL` | Correlación clara, mecanismo nulo | Bajar \(P_c\); no consolidar como CAUSES |

El Curiosity Engine usa \((U, \texttt{why}, \mathrm{EIG})\), no solo \(U\).

---

## 6. Discovery Score (proyección UI)

\[
D = 100 \cdot f_{v}(\mathbf{d})
\]

Pesos orientativos **v1** (sobre subconjunto; \(V_r, P_c, U_x\) entran en planner / reputación, o en \(f_v\) futura):

| Dimensión | Peso v1 |
|-----------|---------|
| \(E\) | 0.20 |
| \(Q_e\) | 0.15 |
| \(R\) | 0.25 |
| \(T\) | 0.10 |
| \(S_t\) | 0.15 |
| \(C_r\) | 0.15 |

Publicar siempre: \(\mathbf{d}\), \(D\), `D_trend`, `D_decay`, `D_confidence`, `math_version`.  
Landscape pico → \(R \rightarrow 0\) puede forzar FAIL aunque \(D\) UI sea alto.

---

## 7. Continuum de Knowledge (no binario)

| Estadio | Significado |
|---------|-------------|
| `CANDIDATE` | Hipótesis prometedora; sin Consolidation |
| `EMERGING` | Belief estable; Evidence ≥ B parcial |
| `ACCEPTED` | Consolidado en MKL con Decay Policy |
| `CANONICAL` | Reconfirmado ampliamente; alta Knowledge Confidence |
| `DEPRECATED` | Pruning / supersedido / Validity Context muerto |

Transitions siguen ADR-012 (niveles A–D, Consolidation). Una mala racha baja Belief / Confidence; no salta de `CANONICAL` a borrado sin Pruning.

### 7.1 Validity Context

Además de Decay temporal: cada nodo Knowledge declara **contextos de validez** (régimen, periodo, macro: p.ej. 2008–2012, pandemia, tipos 0%, inflación alta).

Una teoría puede no “envejecer”: simplemente **deja de aplicar** fuera de su Validity Context → Belief contextual bajo sin necesariamente Deprecated global.

---

## 8. Anti-Hypothesis + FAIL taxonomy

*(Sin cambio de códigos FAIL_*; ver v1.0 §8.)*

Anti-Hypothesis: mismos requisitos de evidencia reconstruible (L-T).

---

## 9. Orden de magnitudes

1. Evidence  
2. Belief (+ CI, \(U\), **why**)  
3. Knowledge (estadio + Confidence + Validity Context)  
4. Discovery Vector \(\mathbf{d}\)  
5. Discovery Score \(D\) (UI)  
6. \(V_r\) / EIG / Scientific Cost (planner)  
7. EdgeReport  
8. Gate / Policy  

---

## 10. Versionado

`math_version` · `estimator_id` · inputs hash · seed opcional.  
Cambiar \(f_v\) = nueva versión; \(\mathbf{d}\) histórico intacto.

---

## 11. ADR-014 (diferido — no bloquea Fase 1)

Reservado para: identificación causal formal, experimentos discriminantes, representaciones avanzadas de incertidumbre y promoción `CORRELATED_WITH` → `HYPOTHESIZED_CAUSES` → `CAUSES`.  
Hasta entonces, \(P_c\) + tipado de aristas (ADR-012) bastan para **impedir** teorías absurdas.

---

## 12. Consecuencias para ingeniería

- Fase 1: costes + métricas brutas + `research_trials` (\(K\)) en **Scientific Domain** ([ADR-015](./015-scientific-domain-vs-trading-domain.md)). **No** requiere \(D\) ni \(\mathbf{d}\) completos.  
- Persistencia futura: guardar **vector** \(\mathbf{d}\), no solo \(D\).  
- Planner (Fase 5): EIG / Scientific Cost / why-uncertain / \(U_x\).

---

## 13. Ratificación

- [x] Discovery Vector como representación interna; \(D\) = proyección UI  
- [x] \(P_c\), \(U_x\), Scientific Cost, why-uncertain  
- [x] Continuum Knowledge + Validity Context  
- [x] RQ + Open Problem; ley L-T  
- [x] Research Value ≠ PnL  
- [x] ADR-014 diferido  
- [x] Estado → **Aceptado v1.1**

**Ingeniería:** pausa hasta *«adelante con Fase 1»*.
