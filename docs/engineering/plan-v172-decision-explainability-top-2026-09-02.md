# Plan — V1.72 Decision Explainability TOP

> **Padre:** [`spec-v172-decision-explainability-top-2026-09-02.md`](./spec-v172-decision-explainability-top-2026-09-02.md).  
> **Estado:** **CERRADA** — partida **V1.71** (`b70849bd`).

| ID  | Entrega                                            | Estado |
| --- | -------------------------------------------------- | ------ |
| D0  | spec/plan V1.72                                    | DONE   |
| P0  | shared DecisionExplainView 1.1.0 + goldens         | DONE   |
| P0  | DecisionExplainPanel TOP + Entry mark/distancia    | DONE   |
| P1  | Python espejo + goldens                            | DONE   |
| P1  | T2_READY copy (headline, mapping intacto) + relevo | DONE   |

## Entregables

1. `packages/shared/src/cognitive/decision-explain-view.ts` schema `1.1.0`
2. `buildOperationalPlanFromStudy(..., { markPrice })` + `buildEntryOperatingTruth({ markPrice })`
3. `apps/web/.../decision-explain-panel.tsx` layout TOP
4. `decision-surface-compact.tsx` Precio actual + Distancia (sin Ideal/Máxima)
5. `packages/py/analytics/.../decision_explain_view.py` + pytest
6. Headline `T2_READY` = «T2 alcanzado»; frase «mesa MONITOR»
7. Docs cierre: arranque auditor + relevo + CURRENT_SYSTEM
