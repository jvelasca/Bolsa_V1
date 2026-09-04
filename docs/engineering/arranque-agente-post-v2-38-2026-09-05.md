# ARRANQUE — siguiente agente · post V2.38 (2026-09-05)

> **Leer primero:** [relevo V2.6 Pixel Premium](./traspaso-relevo-v2-6-pixel-premium-2026-09-05.md).  
> **Tip producto vigente:** [2.6-beta](./traspaso-relevo-tag-v2-6-beta-2026-09-05.md) `50abd31d` / package `1.36.0-beta`.  
> **Para quién:** agente nuevo · V2.6 display-only · **NO MÁS PANELES** · no reabrir motor FSM · no rehacer IDs V2.33–V2.38 salvo regresión.

## Estado al relevo

| Corte                                | Estado                                 |
| ------------------------------------ | -------------------------------------- |
| V2.33–V2.35 (V2.5)                   | tip `v2.5-beta` → `df57f0a9`           |
| V2.36 AUTO timeline                  | **hecho** (código)                     |
| V2.37 Numbers-first                  | **hecho** (`cabin-visual` v2.37)       |
| V2.38 UI Truth Hoy↔Mercado           | **hecho** (`g-operator-05` + e2e mock) |
| Tip `v2.6-beta` / bump `1.36.0-beta` | **hecho** → `50abd31d`                 |

## Primer ID a implementar

**Ninguno de producto en V2.6** — arco cerrado en código tras stamp.

Si regresión: freeze intacto · display-only · NO MÁS PANELES.

## Freeze (copiar al chat)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty intactos · escalera T1→T2→trail (no reordenar).

## Archivos clave V2.36–V2.38 (no rehacer)

- `apps/web/src/features/trading/auto-desk-panel.tsx` — AUTO = `OperatorPositionPlan`
- `apps/web/src/features/trading/cabin-visual.ts` — `v2.37`
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — numbers-first ladder
- `packages/shared/src/cognitive/g-operator-05-ui-truth-v25.test.ts` — Hoy↔Mercado
- `apps/web/e2e/gp-e2e-v26-ui-truth-hoy-mock.spec.ts`

## Pre-flight mínimo

```bash
cd packages/shared && pnpm exec vitest run src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-05-ui-truth-v25.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && pnpm exec vitest run src/features/trading/decision-surface-journey.test.tsx src/features/trading/operator-cabin-ui.test.tsx src/features/trading/cabin-visual.test.ts src/features/trading/auto-desk-panel.test.tsx src/features/charts/chart-focus-toggle.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-38-2026-09-05.md` y el relevo V2.6. Freeze intacto. NO MÁS PANELES. No reabrir V2.33–V2.38 salvo regresión display-only.
