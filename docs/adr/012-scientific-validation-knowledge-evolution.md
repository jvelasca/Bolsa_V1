# ADR 012: Scientific Validation & Knowledge Evolution

## Estado

**Aceptado** — 2026-07-24  
**Tipo:** leyes científicas / epistemológicas (no arquitectura de motores).  
**Depende de:** [ADR-011](./011-quantitative-research-platform.md) (QROS), [RFC-008](../rfc/008-cognitive-decision-architecture.md).

> ADR-011 define **qué es** el QROS y sus motores.  
> Este ADR define **cómo evoluciona** el conocimiento: nacimiento, evidencia, creencia, consolidación, decay, pruning, contradicciones y transferencia.

---

## 1. Objetivo científico constitucional

> **El objetivo del QROS no es maximizar el beneficio histórico, sino construir conocimiento predictivo reproducible con la menor incertidumbre posible.**

El trading es aplicación de ese conocimiento bajo TradingPolicy — no la función objetivo de la investigación.

---

## 2. Regla de una pregunta por concepto

Para evitar inflación de métricas, **cada concepto responde a una sola pregunta**. Si responde a dos, se divide o se elimina.

| Concepto | Pregunta única |
|----------|----------------|
| **Evidence** | ¿Qué muestran los experimentos (ahora)? |
| **Belief** | ¿Cuánto creo esta hipótesis **hoy**, en este contexto? |
| **Knowledge** | ¿Qué considero **consolidado** (teoría lenta)? |
| **Knowledge Confidence** | ¿Cuán **estructuralmente** confiable es ese conocimiento (antigüedad × reconfirmación)? |
| **Knowledge Quality Score** | ¿Qué **calidad** tiene el nodo de conocimiento (reuso, transfer, conflicto…)? |
| **Discovery Score** | ¿Merece **seguir investigándose** este hallazgo/línea? |
| **EdgeReport** | ¿Hay ventaja estadística suficiente para **considerar** operar? |
| **TradingPolicy / Gate** | ¿Está **permitido** ejecutar? |
| **Research Entropy** | ¿Cuánta incertidumbre queda sobre esta hipótesis/región? |
| **Research ROI** | ¿Cuánto conocimiento esperado por unidad de \(K\)/cómputo? |
| **Experiment Reputation** | ¿Qué tan bien diseñado fue este experimento? |

---

## 3. Ciclo de vida de una hipótesis

```text
Pregunta / observación
        ↓
Hipótesis (falsificable + falsifiers)
        ↓
Experimento(s)  ──→  Experiment Reputation
        ↓
Evidence (nivel A–D)
        ↓
Belief update (CI, n, weight, contexto)
        ↓
¿Consolidation? ──sí──→ Knowledge (+ Knowledge Confidence)
        ↓ no / conflict
Mantener Belief · generar nuevas preguntas · o abandonar (ROI)
```

### 3.1 Nacimiento

- Toda hipótesis declara: afirmación, dominio, contexto, **falsifiers**, presupuesto \(K\) inicial.  
- No nace como Knowledge. Nace como hipótesis con Belief bajo / prior débil.

### 3.2 Acumulación de evidencia — niveles (estilo EBM)

No toda evidencia alimenta Knowledge con el mismo peso:

| Nivel | Requisitos mínimos (orientativos) | Peso relativo |
|-------|-----------------------------------|---------------|
| **A** | WFO + MC + Paper (+ Live si aplica) | Máximo |
| **B** | WFO + MC (o CPCV) | Alto |
| **C** | Solo backtest IS/OOS puntual | Bajo — **no consolida Knowledge** solo |
| **D** | Hipótesis / narrativa sin experimento | Nulo para Knowledge; solo prior |

Evidence de nivel C puede mover **Belief** ligeramente; **no** basta para Consolidation.

### 3.3 De Belief a Knowledge (Consolidation)

Pasa a Knowledge solo si:

1. Belief estable (CI estrecho, \(n\) suficiente).  
2. Evidence ≥ nivel B (idealmente A en dominio crítico).  
3. Landscape no-pico.  
4. Falsifiers no disparados.  
5. Proceso explícito de Consolidation (ADR-011 D16) — no automático por un buen trial.

Una mala racha posterior **baja Belief / Knowledge Confidence**; no borra Knowledge de golpe (ADR-011 D18).

### 3.4 Contradicciones

- Dos teorías incompatibles **pueden coexistir** con Beliefs/pesos distintos.  
- El Reasoning Engine **no elige en silencio**: mantiene ambas, registra `CONTRADICTS`, puede generar investigación o **Reject inference** si el conflicto bloquea la decisión.

---

## 4. Belief vs Knowledge Confidence

| | **Belief** | **Knowledge Confidence** |
|--|------------|---------------------------|
| Pregunta | ¿Creo la hipótesis **ahora**? | ¿El conocimiento consolidado está **bien asentado**? |
| Sensible a | Trials recientes, régimen actual | Reconfirmaciones a lo largo del tiempo, transfer, paper/live |
| Ejemplo | 0.71 tras 40 experimentos recientes | 98 = momentum clásico revalidado años; 61 = patrón “IA equities” nuevo |

Ambos pueden bajar; solo Knowledge Confidence bajo + Decay + contradicciones activan **Pruning** agresivo.

---

## 5. Causalidad vs correlación — **L1**

El grafo semántico (ADR-011 D20) **debe tipar la naturaleza del vínculo**:

| Tipo de arista | Significado |
|----------------|-------------|
| `CORRELATED_WITH` | Co-movimiento observado; **sin** claim causal |
| `SUPPORTS` / `CONTRADICTS` | Evidencia a favor/en contra de una hipótesis |
| `HYPOTHESIZED_CAUSES` | Claim causal **provisional** (requiere diseño/experimentos específicos) |
| `CAUSES` | Solo tras umbral alto de evidencia + falsación de alternativas (raro al inicio) |
| `DEPENDS_ON` / `SPECIAL_CASE_OF` / `GENERALIZES` | Estructura lógica / taxonomía |

**Prohibido** promover `CORRELATED_WITH` → `CAUSES` sin expediente de investigación causal. Evita sobreajuste intelectual.

---

## 6. Decay por dominio — **L2**

No todo envejece igual. Cada nodo Knowledge/Belief lleva **Decay Policy** por dominio:

| Dominio (tipos de conocimiento) | Decay típico (orientativo) |
|---------------------------------|----------------------------|
| **Market** (estructura de precio/régimen) | Medio |
| **Indicator** (comportamiento de señales) | Medio–rápido |
| **Risk** | Medio |
| **Macro** | Medio–lento |
| **Execution** (microestructura, costes) | Rápido |
| **Behavioral** | Variable / régimen |
| **Research** (meta: qué investigar) | Lento |

Ejemplos: ROE/fundamentales estructurales → decay lento; sentimiento redes → horas/días.  
El Decay Manager aplica la política del **tipo**, no un único \(\lambda\) global.

---

## 7. Tipos de conocimiento — **L3**

Knowledge no es un cajón único. Nodos tipados (relacionables en el grafo):

- Market Knowledge  
- Indicator Knowledge  
- Risk Knowledge  
- Macro Knowledge  
- Execution Knowledge  
- Behavioral Knowledge  
- Research Knowledge (meta)

Transfer y Curiosity razonan por tipo.

---

## 8. Transfer científico — **L4**

No se transfiere `RSI=12`. Se transfiere la **hipótesis / teoría**:

> “Bancos europeos tienden a responder mejor a indicadores lentos en regímenes X.”

Sobre un banco nuevo: prior Belief elevado **condicional**, luego experimentos de confirmación (Evidence).  
Transfer fallido baja Belief y puede `CONTRADICTS` / especializar (`SPECIAL_CASE_OF`).

---

## 9. Experiment Reputation — **L5**

Además de reputación de hipótesis:

| Señal de buen experimento | Señal de mal experimento |
|---------------------------|---------------------------|
| Hold-out respetado, \(K\) declarado | Peeking / múltiples tests ocultos |
| Costes aplicados, manifest completo | Costes ignorados |
| Falsifiers evaluados | Solo maximizar IS |
| Un bloque libre (parsimonia) | 12 params libres |

Evidence de experimentos con baja reputación tiene **peso reducido** en Belief updates.

---

## 10. Decay, pruning y olvido — **L6**

1. **Decay** — baja Confidence/Belief según política de dominio.  
2. **Pruning** — si Belief bajo + Confidence baja + sin evidencia reciente + contradicciones: archivar / fusionar / retirar del grafo activo.  
3. Archivo **no es borrado físico** inicial: trazabilidad DOI interno (ADR-011 D22) se conserva.

---

## 11. Relación con EdgeReport / Gate / Discovery Score

Orden de preguntas (nunca fusionar):

1. Evidence / EdgeReport → ¿hay señal estadística?  
2. Belief (+ CI) → ¿creemos la hipótesis ahora?  
3. Knowledge (+ Confidence / Quality) → ¿hay teoría consolidada?  
4. Discovery Score → ¿seguir investigando?  
5. Gate / Policy → ¿ejecutar?

Reject inference puede cortar en 2–3 aunque Discovery Score sea alto.

---

## 12. Consecuencias

- ADR-011 **congelado** como arquitectura; evoluciones científicas van aquí (o RFCs derivados).  
- Implementación: Fase 1 no necesita Belief/Knowledge aún; Fase 2 debe crear contratos alineados con Evidence → Belief → Knowledge y tipos L3.  
- Causalidad estricta evita “historias bonitas” disfrazadas de teoría.

---

## 13. Ratificación

- [x] Objetivo científico (§1)  
- [x] Una pregunta por concepto (§2)  
- [x] Ciclo de vida + niveles A–D (§3)  
- [x] L1–L6 (causalidad, decay por dominio, tipos, transfer, experiment reputation, pruning)  
- [x] Estado → **Aceptado**

**No implica código.** Fase 1 y estimadores de scores siguen bajo activación explícita.  
Fundamentos formales de magnitudes (Discovery Score, EIG, Research Value, incertidumbre): [ADR-013](./013-research-mathematics-statistical-foundations.md).
