# ADR 016: Research Persistence Model (Scientific Domain)

## Estado

**Aceptado** — 2026-07-24  
**Tipo:** puente práctico concepto → PostgreSQL (sin filosofía nueva).  
**Depende de:** [ADR-011](./011-quantitative-research-platform.md), [ADR-015](./015-scientific-domain-vs-trading-domain.md), [ADR-013](./013-research-mathematics-statistical-foundations.md), [ADR-009](./009-backtesting-research-platform-h0.md), [RFC-008](../rfc/008-cognitive-decision-architecture.md), [domain-language.md](../domain-language.md).

> Cierra la recomendación de auditoría: fijar **qué se materializa en BD** antes de Fase 1.  
> No introduce Causalidad (ADR-014) ni Belief Engine completo (Fase 2).

---

## 1. Principios de persistencia

| Principio | Norma |
|-----------|--------|
| **P-S1** | Tablas Scientific **no** guardan Position/Order/Trade de cuenta. |
| **P-S2** | Append-only preferido para Evidence / trials; Belief/Knowledge son mutables con historial o snapshots. |
| **P-S3** | IDs de Hypothesis / RQ / Trial / Evidence son **inmutables** (cuid/uuid); no se reutilizan. |
| **P-S4** | Toda conclusión material respeta **Ley L-T**: FKs o ids de evidencia reconstruible. |
| **P-S5** | Versionado DOI interno en JSON/`manifest` o columnas: `data_version`, `code_version`/`engine`, `math_version`, `seed`, `feature_version` (nullable hasta exista). |
| **P-S6** | Recalcular métricas derivadas no reescribe filas históricas de Evidence; se añade snapshot o se versiona `math_version`. |

---

## 2. Mapa concepto → tabla (hoy + destino)

### 2.1 Ya existe (reutilizar / no duplicar semántica)

| Concepto | Tabla actual | Notas |
|----------|--------------|--------|
| Experiment (BT H0) | `backtest_runs` + `backtest_trades` | Instrumento de Experiment; output → Evidence vía trial |
| Strategy (Trading, ref) | `strategy_definitions` | Spec ejecutable; **no** es Hypothesis |
| Optimize job | `optimization_runs` | Contiene trials IS; cada trial debe poder emitir fila en ledger \(K\) |
| EdgeReport (cognitivo live) | `edge_reports` | RFC-008; **no** sustituye Evidence de research |
| Trial cognitivo (DSR live) | `trial_records` | RFC-008 Decision/DSR; **distinto** del ledger QROS |

**Anti-colisión:** `trial_records` (cognitivo / cuenta) ≠ `research_trials` (laboratorio QROS). Nombres distintos a propósito.

### 2.2 Fase 1 — crear

| Concepto | Tabla | Inmutable | Contenido mínimo |
|----------|-------|-----------|------------------|
| Research Trial (ledger \(K\)) | **`research_trials`** | fila append-only | Ver §3 |

Cada `POST /backtests/run` (y cada trial de optimize, cuando se cablee) **inserta** ≥1 `research_trials` y contabiliza `k_contribution` (default 1).

### 2.3 Fase 2+ — crear (contratos; no implementar en Fase 1)

| Concepto | Tabla sugerida | Mutable? | Estado |
|----------|----------------|----------|--------|
| Research Question | `research_questions` | metadata sí; id no | pendiente |
| Open Problem | `open_problems` | sí | pendiente |
| Hypothesis / Anti-Hypothesis | `hypotheses` (`kind`: hypothesis \| anti) | texto/falsifiers versionables | **P2.B CRUD** ([ADR-018](./018-fase2-evidence-store-v0.md)) |
| Evidence snapshot | `research_evidence` | append-only | **P2.A** |
| Belief state | `hypothesis_beliefs` | sí (+ `belief_history` append-only) | **P2.C v0** |
| Knowledge node | `knowledge_nodes` | sí (estadio, decay, validity_context) | **P2.D stub** (Consolidation explícita) |
| Research tree edge | `research_tree_edges` | append / soft-delete | **P2.E** |
| MKL sync event | `mkl_sync_events` | append-only | **P2.F stub** |
| Discovery Vector | columna JSON en evidence/trial o tabla `discovery_vectors` | append-only por `math_version` | pendiente |

---

## 3. Esquema Fase 1: `research_trials`

### 3.1 Columnas normativas

| Columna | Tipo | Rol |
|--------|------|-----|
| `id` | cuid/uuid PK | Inmutable |
| `instrument_id` | FK | Activo del experimento |
| `hypothesis_id` | FK nullable | Fase 2; null permitido en Fase 1 |
| `research_question_id` | FK nullable | Fase 2 |
| `backtest_run_id` | FK nullable → `backtest_runs` | Si el trial es un BT H0 |
| `optimization_run_id` | FK nullable → `optimization_runs` | Si viene de optimize |
| `strategy_definition_id` | FK nullable | Ref Trading Domain (ADR-015 F2) |
| `preset_key` / `strategy_name` | text | Identidad ejecutable H0 |
| `params` | JSONB | Parámetros del trial |
| `blocks` | JSONB nullable | entry/exit/… (futuro) |
| `is_metrics` | JSONB | Métricas brutas del run (Sharpe… cuando existan) |
| `is_score` | decimal nullable | Score IS legado / utility simple |
| `k_contribution` | int default 1 | Peaje \(K\) |
| `proposed_by` | text | `human` \| `grid` \| `optuna` \| `ai` \| `system` |
| `parent_trial_id` | FK self nullable | Linaje |
| `fail_code` | text nullable | `FAIL_*` si aplica |
| `manifest_ref` | JSONB nullable | Copia/resumen DOI: data_version, engine, seed… |
| `created_at` | timestamptz | |

Índices: `(instrument_id, created_at DESC)`, `(hypothesis_id)`, `(backtest_run_id)`, `(proposed_by, created_at)`.

### 3.2 Qué **no** va en Fase 1

- Belief / Knowledge / Discovery Vector completo  
- Hold-out gates  
- Landscape  
- Cálculo de \(D\) / \(V_r\) (solo métricas brutas en `is_metrics`)

### 3.3 Relación con `backtest_runs`

```text
backtest_runs     = artefacto Experiment H0 (equity, trades, manifest)
research_trials   = asiento del ledger científico (K + trazabilidad)
```

Un BT crea **ambos** (1:1 en el caso simple). Optimize puede crear N trials sin N `backtest_runs` completos al inicio (Fase 1: al menos link a `optimization_runs` + metrics JSON).

---

## 4. Inmutable vs derivado vs memoria

| Clase | Ejemplos | Regla |
|-------|----------|--------|
| **Inmutable** | ids, `research_trials` rows, `edge_reports`, manifests históricos | No UPDATE de métricas “corrigiendo el pasado” |
| **Mutable** | Belief actual, Knowledge estadio, ConfidenceState | UPDATE + audit; o append history |
| **Derivado** | Discovery Score UI, rankings | Recalculable; cache OK con `math_version` |
| **Memoria / local** | Layout chrome, UI prefs | No Scientific Domain |

---

## 5. Frontera Trading (recordatorio)

| Tabla Trading (ej.) | No mezclar |
|---------------------|------------|
| `investment_accounts`, `ledger_entries`, `pending_orders` | Sin `belief`, `discovery_vector` |
| `strategy_definitions` | Solo **FK** desde Scientific; la hipótesis vive en `hypotheses` (Fase 2) |

Paper deploy desde BT: puente aplicación (ya existe); no convierte el BT en Knowledge.

---

## 6. Entregables Fase 1 (ingeniería)

1. Costes reales aplicados en motor → reflejados en equity/`is_metrics` de `backtest_runs` + trial.  
2. Métricas ampliadas en payload (Sharpe… según implementación).  
3. Migración Prisma `research_trials` + escritura en `RunAndSaveBacktest` (y hook optimize cuando sea trivial).  
4. API: devolver `trialId` junto al run.  
5. Tests: costes cambian PnL; trial persistido; \(K\) sumable por instrumento.

---

## 7. Ratificación

- [x] Mapa concepto→tabla  
- [x] `research_trials` ≠ `trial_records`  
- [x] Fase 1 scope vs Fase 2  
- [x] Inmutable / L-T / DOI  
- [x] Estado → **Aceptado**

**Siguiente (histórico):** orden *«adelante con Fase 1»* → código.  
**Baseline:** [ADR-017](./017-baseline-v1-5-research-observatory.md).  
Flujo operativo: [docs/engineering/research-lifecycle.md](../engineering/research-lifecycle.md).
