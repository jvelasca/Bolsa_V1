# Domain Language — QROS / Bolsa V1

> **Documento vivo** (diccionario canónico). Una palabra → un significado.  
> Complementa [RFC-000](./rfc/000-ubiquitous-language.md) (cadena Trading/Feature/Execution).  
> Fronteras: [ADR-015](./adr/015-scientific-domain-vs-trading-domain.md) (objetos) · [ADR-019](./adr/019-dual-universes-lab-vs-trading.md) (universos UI LAB vs TRADING).  
> Actualizar **aquí** (o enmienda RFC-000) al introducir términos nuevos — no en ADRs filosóficos sueltos.

**Última sync:** 2026-08-02 (universos LAB / TRADING · Mandato operativo ADR-020).

---

## 0. Tres contextos (bounded contexts)

| Context ID | Nombre | Contiene | **No** contiene |
|------------|--------|----------|-----------------|
| `SCIENTIFIC` | Scientific Domain | RQ, Hypothesis, Evidence, Belief, Knowledge, DiscoveryVector… | Position, Order, Trade (fill), StopLoss |
| `TRADING` | Trading Domain | Strategy, Signal, Recommendation, Order, Position, Policy… | Belief, Theory, DiscoveryVector, Evidence Weight |
| `INFRA` | Infrastructure Domain *(conceptual; no ADR propio aún)* | Docker, PG, workers, cache, broker adapters, logs, telemetry | Hipótesis, Beliefs, Strategies |

Puente operativo: **Scientific → Reasoning → Trading** (ADR-015).  
Puente de producto UI: **LAB ↔ TRADING** por instrumento (Adoptar / Vigilar / Proponer / Abrir estudio) — [ADR-019](./adr/019-dual-universes-lab-vs-trading.md).  
Infra sirve a ambos; no es dueña del significado de Belief ni de Position.

### 0.1 Universos de producto (experiencia)

| Universo UI | Alineado con | Contiene (producto) | **No** contiene |
|-------------|--------------|---------------------|-----------------|
| **LAB** (Backtesting) | Scientific + experiments H0 | Embudo, Ver, Verificar D→hoy, Cartera LAB, CORE-R study | Ledger DEMO / Paper como PnL “mío” |
| **TRADING** | Trading Domain | Cuenta activa, órdenes, panel Operativa, caminos A/B/C/D | Película DÍA D / mesa Verificar (to-be) |

Canónico: [diseño dual](./engineering/dual-universes-lab-trading-design-2026-08-02.md).

---

## 1. Scientific Domain

| Término | Definición oficial | Relaciona con | **No** significa | Nació en |
|---------|-------------------|---------------|------------------|----------|
| **QROS** | Sistema Operativo de Investigación Cuantitativa; el producto es conocimiento, no el BT | ADR-011 | “Backtester con IA” | ADR-011 |
| **Research Question (RQ)** | Pregunta de investigación que agrupa hipótesis y experimentos | Open Problem, Hypothesis | Una sola Strategy | ADR-013 |
| **Open Problem (OP)** | Pregunta que permanece abierta tras cerrar RQs (“sabemos que no sabemos por qué”) | RQ | FAIL | ADR-013 |
| **Hypothesis** | Afirmación falsable sobre comportamiento; **unidad canónica** | Experiment, Belief, Strategy (vía ref) | Un preset de indicadores | ADR-011/015 |
| **Anti-Hypothesis** | Descartes explícito (“esto no funciona en…”) | Hypothesis, Meta-Knowledge | Un FAIL puntual sin persistir | ADR-013 |
| **Observation** | Lectura de hechos/datos sin conclusión (p.ej. RSI=24, ADX=31) | Fact, Feature | Inference | Este doc / ADR-015 |
| **Experiment / Trial** | Ejecución medible (BT, WFO fold, paper window); consume \(K\) | Evidence, `research_trials` | “La estrategia óptima” | ADR-011/013 |
| **BacktestRun** | Manifest + resultado de un BT H0; es un **Experiment**, no Knowledge | RunManifest, Evidence | Optimizer crowning | ADR-009, ADR-015 F3 |
| **Evidence** | Resultado estadístico de experimento(s); cambia **rápido** | EdgeReport, Belief | Knowledge consolidado | ADR-011 D18 |
| **Belief** | Credencia contextual hoy (+ CI, n, weight, why-uncertain) | Evidence, Knowledge | “Es verdad absoluta” | ADR-011/013 |
| **Knowledge** | Teoría consolidada (**lenta**); estadios CANDIDATE→…→DEPRECATED | Belief, MKL, Validity Context | Un trial bueno | ADR-011/012/013 |
| **Knowledge Confidence** | Confianza **estructural** del nodo (reconfirmación en el tiempo) | Knowledge, Belief | Belief puntual | ADR-012 |
| **Theory** | Knowledge en estadio alto / claim generalizable | Knowledge, Transfer | Strategy | ADR-012 |
| **Discovery Vector** \(\mathbf{d}\) | Representación **interna** multidimensional del hallazgo | Discovery Score | Un único número | ADR-013 |
| **Discovery Score** \(D\) | Proyección UI de \(\mathbf{d}\); ¿merece seguir investigando? | \(\mathbf{d}\), math_version | ¿Operar? / EdgeReport | ADR-013 |
| **Research Value** \(V_r\) | Cuánto se **aprendió** (≠ PnL) | EIG, Scientific Cost | Beneficio del BT | ADR-013 |
| **EIG** | Expected Information Gain *ex ante* | Curiosity, Budget | \(\mathbb{E}[\mathrm{PnL}]\) | ADR-013 |
| **Scientific Cost** | Coste de investigar (\(K\), multiple testing, oportunidad) | Budget, \(V_r\) | Solo CPU ms | ADR-013 |
| **Research Budget / \(K\)** | Tope de ensayos; peaje estadístico | DSR, trials ledger | “Lanzar grid infinito” | ADR-011 |
| **EdgeReport** | Dictamen estadístico de ventaja (¿considerar edge?) | Evidence, Gate | Discovery Score | RFC-008 / ADR-011 |
| **Landscape / Robustness** | Forma de la superficie paramétrica; pico aislado → FAIL | \(R\) en \(\mathbf{d}\) | Max PnL IS | ADR-011/013 |
| **Causal Plausibility** \(P_c\) | Claim causal vs mera correlación | Grafo, ADR-014 | “Causa demostrada” | ADR-013 |
| **Unexpectedness** \(U_x\) | Sorpresa vs prior | \(V_r\), Curiosity | Confirmación esperada | ADR-013 |
| **Validity Context** | Regímenes/periodos donde aplica el Knowledge | Decay, DEPRECATED | Solo “fecha de creación” | ADR-013 |
| **Falsifier** | Evidencia/condición que invalidaría la hipótesis | Hypothesis | Un FAIL genérico | ADR-011 D21 |
| **Meta-Knowledge** | Conocimiento sobre *cómo investigar* | Research Knowledge | Market Knowledge | ADR-011 D14 |
| **Ley L-T** | No hay conclusión sin evidencia reconstruible | DOI interno, Evidence | Knowledge huérfano | ADR-013 |
| **research_trials** | Ledger QROS de ensayos (\(K\)); ≠ `trial_records` cognitivo | BacktestRun, Hypothesis | EdgeReport live | ADR-016 |

### Pipeline científico (capas)

```text
Observation → Inference → Reasoning → Decision (hacia Trading)
```

| Capa | Hace | No hace |
|------|------|---------|
| Observation | Registra hechos | Interpreta edge |
| Inference | Actualiza Beliefs / relaciones del grafo | Autoriza órdenes |
| Reasoning | Explica, conflictos, Reject inference, falsabilidad | Ejecuta trades |
| Decision | Emite DecisionPackage / Recommendation candidata | Salta el Gate |

---

## 2. Trading Domain

| Término | Definición oficial | Relaciona con | **No** significa | Nació en |
|---------|-------------------|---------------|------------------|----------|
| **Strategy / Preset** | Spec ejecutable; **referencia** Hypothesis/Knowledge ids | Hypothesis (F2) | La hipótesis misma | ADR-015, RFC-000 |
| **Signal** | Evento táctico discreto | Recommendation | Belief | RFC-000 |
| **Recommendation** | Acción propuesta + sizing | Signal, Gate | Evidence | RFC-000 |
| **Intent / Order / Trade / Position** | Cadena de ejecución | EXECUTION | Research Trial | RFC-000 |
| **TradingPolicy / RiskPolicy** | Reglas de autorización y riesgo | Gate, RFC-008 | Discovery Score | RFC-008 |
| **DecisionPackage** | Artefacto cognitivo hacia Gate | Reasoning, Evidence | Un backtest | RFC-008 |

Ver cadena completa en [RFC-000 §4](./rfc/000-ubiquitous-language.md).

---

## 3. FAIL / incertidumbre (códigos)

| Código | Dominio | Significado breve |
|--------|---------|-------------------|
| `FAIL_SAMPLE` | Scientific | Muestra insuficiente |
| `FAIL_NO_EDGE` | Scientific | Sin ventaja tras evidencia adecuada |
| `FAIL_OVERFIT` | Scientific | Pico / multiple testing |
| `FAIL_NO_TRANSFER` | Scientific | No generaliza |
| `FAIL_COST` | Scientific | Edge muere con costes |
| `FAIL_REGIME` | Scientific | Solo un régimen |
| `FAIL_FALSIFIED` | Scientific | Falsifier disparado |
| `FAIL_DESIGN` | Scientific | Experimento mala reputación |
| `U_SAMPLE` / `U_CONFLICT` / `U_AMBIGUOUS` / `U_REGIME` / `U_DESIGN` / `U_CAUSAL` | Scientific | *Why uncertain?* (ADR-013) |

---

## 4. Infraestructura (vocabulario mínimo)

Términos `INFRA.*` (no son Knowledge ni Trading): PostgreSQL, worker/queue, cache, broker adapter, connector de mercado, object storage, telemetry, scheduler.  
Detalle de plataforma: ADR-010, docs operativos — **no** mezclar en schemas de Belief.

### 4.1 Cuentas y carteras (producto)

| Término | Definición oficial | **No** significa |
|---------|-------------------|------------------|
| **Cuenta activa** | Única cuenta **TRADING** con la que opera la app | Multi-ledger operativo; Cartera LAB |
| **Demo** (`simulated`) | Cuenta simulada; único tipo operativo hoy | Broker real |
| **Paper** (tipo cuenta) | Futuro: cuenta **real** enlazada a broker por API | Paper-trading / simulación |
| **Desplegar en demo** | Camino A → ledger de la cuenta activa DEMO | Crear cuenta tipo Paper |
| **Cartera LAB** | Sandbox del universo Backtesting (sims / Verificar); no es «Activa» | Segunda DEMO de inversión |
| **Adoptar** | Puente: ligar TOP/#1 a operativa TRADING (abre/cierra **mandato**) | Escribir fills desde la película Verificar |
| **Mandato operativo** | Playbook vigente en TRADING para un instrumento×cuenta; con **tenure** (desde/hasta) | Finalistas LAB; tag *setup* de un trade suelto |
| **F-hoy / F-D** | Finalistas operativos vs TOP experimento as-of D ([ADR-021](./adr/021-dia-d-reconciliation.md)) | Un solo TOP que se pisa al cambiar DÍA D |
| **Historial de mandato** | Tramos cerrados + vigente (`MandateTenure`) | Snapshot de adopción sin fechas |
| **Verificar (D→hoy)** | Sesión LAB fase C con #1 congelada | Operar en Trading / MODO DÍA D (as-is deprecado) |
| **Panel Operativa** | Columna Trading (Recomendación / Info / Configuración) a altura completa | Embudo LAB Coach; rail Coach legado |
| **En estudio** | Lista virtual = pestañas de gráfico abiertas | Watchlist persistida / catálogo |
| **Índice Operativo (IO)** | Score 0–100 (Composite + suelo distress) + ranking entre En estudio | Ranking Finalistas LAB |
| **Coach en vivo** | *(legado)* contenido absorbido por **Panel Operativa** | Reabrir embudo dentro del desk |

Canónico cuentas: [account-premises-demo-vs-paper-2026-07-31.md](./engineering/account-premises-demo-vs-paper-2026-07-31.md).  
Canónico universos: [ADR-019](./adr/019-dual-universes-lab-vs-trading.md).  
Canónico mandato: [ADR-020](./adr/020-operating-mandate-tenure.md).

---

## 5. Reglas de uso

1. PRs que introduzcan entidades de dominio **actualizan esta tabla** (o RFC-000) en el mismo PR.  
2. Si un término responde a **dos preguntas**, dividirlo (ADR-012 / ADR-013).  
3. Contaminación cruzada (p.ej. campo `belief` en `orders`) = violación ADR-015.  
4. UI: “laboratorio / LAB / research” vs “operativa / TRADING” en copy ([ADR-019](./adr/019-dual-universes-lab-vs-trading.md)).

---

## 6. Índice ADR rápido

| ADR/RFC | Rol |
|---------|-----|
| [011](./adr/011-quantitative-research-platform.md) | ¿Qué es el QROS? |
| [012](./adr/012-scientific-validation-knowledge-evolution.md) | ¿Cómo evoluciona el conocimiento? |
| [013](./adr/013-research-mathematics-statistical-foundations.md) | ¿Qué significa matemáticamente? |
| [015](./adr/015-scientific-domain-vs-trading-domain.md) | Scientific ≠ Trading (objetos) |
| [019](./adr/019-dual-universes-lab-vs-trading.md) | LAB ≠ TRADING (universos UI / carteras) |
| [020](./adr/020-operating-mandate-tenure.md) | Mandato operativo (tenure estrategia×instrumento) |
| [021](./adr/021-dia-d-reconciliation.md) | Reconciliación DÍA D (F-hoy · F-D · V) |
| [016](./adr/016-research-persistence-model.md) | Persistencia Scientific Domain |
| [017](./adr/017-baseline-v1-5-research-observatory.md) | **Baseline v1.5** — laboratorio congelado |
| [009](./adr/009-backtesting-research-platform-h0.md) | Motor de medición H0 |
| [RFC-008](./rfc/008-cognitive-decision-architecture.md) | Evidence / MKL / Gate |
| [RFC-000](./rfc/000-ubiquitous-language.md) | Cadena Trading + Domain IDs |
| ADR-014 | Causal profundo — **diferido** |
