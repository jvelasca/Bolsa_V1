# ADR 018: Fase 2 — Evidence Store v0 (activación)

## Estado

**Aceptado** — 2026-07-27  
**Tipo:** activación de fase / contratos de persistencia científica.  
**Extiende:** [ADR-017](./017-baseline-v1-5-research-observatory.md) (Baseline v1.5), [ADR-016](./016-research-persistence-model.md), [ADR-011](./011-quantitative-research-platform.md), [ADR-012](./012-scientific-validation-knowledge-evolution.md).

---

## 1. Contexto

ADR-017 congeló Evidence / Belief / Knowledge hasta madurez empírica del laboratorio.  
El track de producto lab (Optimizar P3–P9) está **cerrado y documentado**.  
Directiva operativa (2026-07-27): abrir **Fase 2** por slices, empezando por el Evidence Store.

---

## 2. Decisión

1. **Descongelar Fase 2** por slices **P2.A→P2.F** (Evidence → Hypothesis → Belief → Knowledge → Tree → MKL stub).  
2. **Discovery, Planner, Decay/Pruning** siguen **fuera**.  
3. Contratos **separados** (ADR-011): no fusionar Evidence + Belief + Knowledge en un blob.  
4. Tablas: `hypotheses`, `research_evidence`, `hypothesis_beliefs` + `belief_history`, `knowledge_nodes`, `research_tree_edges`, `mkl_sync_events`.  
5. Clasificación de nivel **lab-adaptada** (ADR-012): D/C/B; A no automático.  
6. Emisión trial → Evidence (+ Belief si `hypothesis_id`).  
7. Consolidation **explícita**; Tree auto SUPPORTS/GENERALIZES; MKL sync stub (`not_auto_live`).  
8. Batería obligatoria: `pnpm test:fase2`.

---

## 3. Fuera de alcance (tras P2.F)

- Decay / Pruning / Discovery / Planner  
- Landscape real (solo ack stub)  
- UI Observatory de Belief/Knowledge/Tree  
- MKL live que autorice órdenes  
- Reinterpretar EdgeReport cognitivo como Knowledge  

---

## 4. Criterio de “hecho” P2.A

- Migración Prisma + modelos SQLAlchemy  
- Clasificador + persistencia + hooks BT/optimize  
- API list/detail  
- Tests de pieza + conjunto en verde  
- Sync en [research-lifecycle.md](../engineering/research-lifecycle.md)

---

## 5. Ratificación

- [x] Activación Fase 2 acotada a Evidence v0  
- [x] Separación Evidence ≠ Belief ≠ Knowledge  
- [x] Estado → **Aceptado**
