# ARRANQUE — siguiente agente · post V2.32 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md) (**CERRADO en código**).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** agente nuevo · V2.4 cerrado · tip [`v2.4-beta`](./traspaso-relevo-tag-v2-4-beta-2026-09-04.md) `8fda4d62` · ops smoke 10 s paralelo · **NO MÁS PANELES** · no reabrir motor FSM · no rehacer IDs V2.28–V2.32 salvo regresión.

## Estado al relevo

| Corte                           | Estado                          |
| ------------------------------- | ------------------------------- |
| V2.28 PLAN DE POSICIÓN          | **hecho**                       |
| V2.29 Protection State          | **hecho**                       |
| V2.30 Chart Focus               | **hecho**                       |
| V2.31 Premium Visual System     | **hecho**                       |
| V2.32 Golden Operator Journey 2 | **hecho en código**             |
| V2.3-ops smoke 10 s             | pendiente sesión ops (paralelo) |
| Tip `v2.4-beta`                 | **hecho** → `8fda4d62`          |

## Primer ID a implementar

**Ninguno de producto en V2.4** — arco cerrado.

Si ops: smoke browser 10 s (criterio auditor V2.3-ops).  
Si regresión: freeze intacto · display-only · NO MÁS PANELES.  
Tip `v2.4-beta` ya stampado → `8fda4d62` (no bump `1.35.0-beta`).

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.32 (no rehacer Journey 2)

- `packages/shared/src/cognitive/operator-cabin-view.ts` — `buildOperatorJourney2Surfaces` · AUTO `closed`
- `packages/shared/src/cognitive/g-operator-02-golden-journey.test.ts` — Journey 2 contractual
- `packages/shared/src/cognitive/position-operating-truth.ts` — `remainingQuantity` en thin POT
- `apps/web/src/features/trading/decision-surface-compact.tsx` — stamp `data-operator-journey="v2.32"`
- `apps/web/src/features/trading/position-operating-summary.tsx` — stamp Journal

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && npx vitest run src/features/trading/decision-surface-journey.test.tsx src/features/trading/position-operating-summary.test.tsx src/features/charts/operational-plan-chart-levels.test.ts
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-32-2026-09-04.md` y el relevo V2.4 (cerrado). No tip sin pedirlo. Freeze intacto. NO MÁS PANELES.

## Stamp

| Pieza                  | Valor                                                              |
| ---------------------- | ------------------------------------------------------------------ |
| Branch                 | `main`                                                             |
| Tip GitHub `v2.4-beta` | [`8fda4d62`](https://github.com/jvelasca/Bolsa_V1/commit/8fda4d62) |
