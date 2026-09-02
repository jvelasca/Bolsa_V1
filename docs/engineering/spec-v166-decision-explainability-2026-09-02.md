# Spec — V1.66 Decision Explainability (Why)

> **AsOf:** 2026-09-02 · **Estado:** **EN CURSO**.  
> **Padre:** [`spec-v165-operational-identity-dto-2026-09-02.md`](./spec-v165-operational-identity-dto-2026-09-02.md) · partida **V1.65** (`60148885`). **No** LIVE.

Capa determinista **Estado → Acción → Por qué** sobre Decision Surface. El motor decide; la UI explica. **Sin** LLM en hot path.

```text
P0  GP-V166-01 — DecisionExplainViewV1 + buildDecisionExplainView (shared)
P0  GP-V166-02 — formatTradePlanWhyNot canónico (dedupe hoy-command-strip)
P0  GP-V166-03 — DecisionExplainPanel + wire operativa-cockpit-card
P1  GP-V166-04 — cross-surface snapshot test (same fixture → same explain)
P1  GP-V166-05 — reemplazar stub operativa-cockpit-why-body
P1  GP-V166-06 — posición: secondaryConditions + policy en explain
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.65 intacto.

## 1. IN

| ID         | Comportamiento                                                                                                 |
| ---------- | -------------------------------------------------------------------------------------------------------------- |
| GP-V166-01 | `buildDecisionExplainView(study, opts)` → secciones thesis/signals/conditions/invalidators/policy/traceability |
| GP-V166-02 | `formatTradePlanWhyNot` en `@bolsa/shared`; hoy-command-strip importa shared                                   |
| GP-V166-03 | Panel Mercado renderiza explain view; `onOpenWhy` ya no muestra stub                                           |
| GP-V166-04 | Misma fixture → mismo snapshot en test shared                                                                  |
| GP-V166-05 | `data-testid="decision-explain-panel"` sustituye why-body stub                                                 |
| GP-V166-06 | Posición: incluye `secondaryConditions` de POT en explain                                                      |

## 2. OUT

LLM Explainability Proxy · Decision Replay · HUD why · nuevas tablas · mutar campos de decisión.

## 3. Pre-flight

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/decision-explain-view.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/decision-explain-panel.test.tsx src/features/trading/operativa-cockpit-card.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```
