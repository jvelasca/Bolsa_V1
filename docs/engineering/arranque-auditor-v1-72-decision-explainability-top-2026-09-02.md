# Arranque auditor — V1.72 Decision Explainability TOP (2026-09-02)

> **Padre:** [`spec-v172-decision-explainability-top-2026-09-02.md`](./spec-v172-decision-explainability-top-2026-09-02.md) · partida **V1.71** (`b70849bd`)

## Punta de partida

- Producto: **V1.71** Identity & Certification, **aprobada**
- Brecha: Why V1.66 era secciones KV, no ficha TOP (score X/10 · LONG ≠ COMPRAR · factors fail-closed · mark+distancia)

## Qué auditar

| GP         | Evidencia                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------------------------- |
| GP-V172-01 | `packages/shared/src/cognitive/decision-explain-view.ts` schema `1.1.0` · goldens LONG≠COMPRAR · unknown≠pass |
| GP-V172-02 | `decision-explain-panel.tsx` testids score/direction/factor-\*/entry-distance · copy autorización             |
| GP-V172-03 | `buildOperationalPlanFromStudy(..., { markPrice })` · EntryCompact Precio actual/Distancia · sin Ideal/Máxima |
| GP-V172-04 | `packages/py/analytics/.../decision_explain_view.py` + `test_decision_explain_view.py`                        |
| GP-V172-05 | Headline `T2_READY` = «T2 alcanzado» · frase «mesa MONITOR» · mapping desk **intacto**                        |

## Pre-flight (local 2026-09-02)

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/decision-explain-view.test.ts src/cognitive/operational-plan-view.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts
# → 30 passed

pnpm --filter @bolsa/web exec vitest run src/features/trading/decision-explain-panel.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/position-decision-surface.test.ts src/features/trading/decision-surface-compact.test.tsx
# → 32 passed

python -m pytest packages/py/analytics/tests/test_decision_explain_view.py -q
# → 3 passed

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

Browser Mercado (`/trading`): cockpit AAF → «¿Por qué?» → hero `AAF · 5,9/10` · chip `ESPERAR` · factors unknown = «sin dato» · autorización «Ranking ≠ BUY» · **sin COMPRAR**. HUD why no se abre.

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- Ideal/Máxima (el motor no los emite)
- Multi-instrumento / Entry→Position E2E (**V1.73**)
