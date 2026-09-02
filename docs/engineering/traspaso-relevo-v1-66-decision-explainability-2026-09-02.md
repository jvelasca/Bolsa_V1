# RELEVO — V1.66 Decision Explainability (2026-09-02)

> **Padre:** [`spec-v166-decision-explainability-2026-09-02.md`](./spec-v166-decision-explainability-2026-09-02.md) · partida **V1.65** (`60148885`).

---

## 0. Qué cierra

| Pieza                                                 | Estado |
| ----------------------------------------------------- | ------ |
| GP-V166-01 — `DecisionExplainViewV1` + builder shared | DONE   |
| GP-V166-02 — `formatTradePlanWhyNot` canónico         | DONE   |
| GP-V166-03 — `DecisionExplainPanel` + cockpit wire    | DONE   |
| GP-V166-04 — cross-surface snapshot test              | DONE   |
| GP-V166-05 — stub why-body reemplazado                | DONE   |
| GP-V166-06 — secondaryConditions en explain posición  | DONE   |

## 1. Pre-flight

| Suite                                  | Resultado     |
| -------------------------------------- | ------------- |
| shared `decision-explain-view.test.ts` | **5** passed  |
| web explain + cockpit                  | **24** passed |
| tsc `@bolsa/web`                       | OK            |

## 2. Next

1. **V1.67** Browser E2E Mercado real + aislamiento DB
2. **V1.68** Paper Autonomous Desk
