# ARRANQUE — siguiente agente · post V2.35 (2026-09-05)

> **Leer primero:** [relevo V2.5 UI Finishing](./traspaso-relevo-v2-5-ui-finishing-2026-09-05.md) (**CERRADO en código**).  
> **Tip producto vigente:** [`v2.5-beta`](./traspaso-relevo-tag-v2-5-beta-2026-09-05.md) `df57f0a9`.  
> **Para quién:** agente nuevo · V2.5 cerrado · tip [`v2.5-beta`](./traspaso-relevo-tag-v2-5-beta-2026-09-05.md) `df57f0a9` · **NO MÁS PANELES** · no reabrir motor FSM · no rehacer IDs V2.33–V2.35 salvo regresión.

## Estado al relevo

| Corte                             | Estado                 |
| --------------------------------- | ---------------------- |
| V2.33 Protection honesty          | **hecho**              |
| V2.34 Premium UX                  | **hecho**              |
| V2.35 UI Truth + responsive/touch | **hecho**              |
| Tip `v2.5-beta`                   | **hecho** → `df57f0a9` |
| Commit working tree V2.5          | **hecho** → `df57f0a9` |
| Reinicio API Python (wire POV)    | **hecho** (ops)        |
| V2.3-ops smoke 10 s               | **PASS**               |
| Tip `v2.4-beta`                   | vigente → `8fda4d62`   |

## Primer ID a implementar

**Ninguno de producto en V2.5** - arco cerrado.

Tip `v2.5-beta` ya stampado → `df57f0a9` (no bump `1.35.0-beta`).  
Si regresión: freeze intacto · display-only · NO MÁS PANELES.

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER (no −5 % si hay structural stop).

## Archivos clave V2.33–V2.35 (no rehacer)

- `packages/shared/src/cognitive/operational-context.ts` — stop estructural → `PROTECTED`
- `packages/shared/src/cognitive/protect-stop-source.ts` — bootstrap = solo floor −5 %
- `packages/shared/src/cognitive/operator-cabin-view.ts` — Planificado vs ejecutado · Gestión copy
- `packages/shared/src/cognitive/g-operator-05-ui-truth-v25.test.ts` — UI Truth birth
- `packages/py/application/.../operational_context.py` + `paper_desk_cycle.py` · analytics POV
- `apps/web/src/features/trading/cabin-visual.ts` — `v2.34`
- `apps/web/src/features/charts/chart-focus-toggle.tsx` · `chart-plan-context-strip.tsx`
- `apps/web/e2e/gp-e2e-v25-ui-truth-mock.spec.ts`

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-05-ui-truth-v25.test.ts src/cognitive/protect-stop-source.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && npx vitest run src/features/trading/decision-surface-journey.test.tsx src/features/trading/position-operating-summary.test.tsx src/features/charts/chart-focus-toggle.test.tsx src/features/trading/cabin-visual.test.ts src/features/decision-journal/decision-ficha-panel.render.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-35-2026-09-05.md` y el relevo V2.5 (cerrado · tip `v2.5-beta` → `df57f0a9`). Freeze intacto. NO MÁS PANELES. No reabrir V2.33–V2.35 salvo regresión display-only.

## Stamp

| Pieza                  | Valor                                                              |
| ---------------------- | ------------------------------------------------------------------ |
| Branch                 | `main`                                                             |
| Tip GitHub `v2.5-beta` | [`df57f0a9`](https://github.com/jvelasca/Bolsa_V1/commit/df57f0a9) |
| Tip previo `v2.4-beta` | [`8fda4d62`](https://github.com/jvelasca/Bolsa_V1/commit/8fda4d62) |
