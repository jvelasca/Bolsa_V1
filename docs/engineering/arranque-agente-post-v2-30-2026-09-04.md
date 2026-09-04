# ARRANQUE — siguiente agente · post V2.30 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** histórico · V2.31 **hecho** · next = [arranque post-V2.31](./arranque-agente-post-v2-31-2026-09-04.md) → **V2.32**.

## Estado al relevo

| Corte                           | Estado                                                                        |
| ------------------------------- | ----------------------------------------------------------------------------- |
| V2.28 PLAN DE POSICIÓN          | **hecho**                                                                     |
| V2.29 Protection State          | **hecho**                                                                     |
| V2.30 Chart Focus               | **hecho en código**                                                           |
| V2.3-ops smoke 10 s             | pendiente sesión ops (paralelo)                                               |
| V2.31 Premium Visual System     | **hecho** · [arranque post-V2.31](./arranque-agente-post-v2-31-2026-09-04.md) |
| V2.32 Golden Operator Journey 2 | **SIGUIENTE**                                                                 |
| Tip `v2.4-*`                    | solo con petición explícita                                                   |

## Primer ID a implementar

**V2.31 — Premium Visual System**

- Tipografía en 3 tamaños claros (héroe / operativa / meta).
- Números financieros legibles (tabular · peso · color semántico sin ruido).
- Menos texto a 10px; menos cards decorativas.
- Freeze intacto · display-only · sin controles AUTO nuevos · sin Journal redo · sin segundo Mission/Exit Route · Protection / Chart Focus intactos.

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.30 (no rehacer Chart Focus)

- `apps/web/src/features/charts/chart-focus-prefs.ts` — `simple` \| `completo`
- `apps/web/src/features/charts/chart-focus-toggle.tsx` — chrome overlay
- `apps/web/src/features/charts/operational-plan-chart-levels.ts` — filtro + T1 dimmed
- `apps/web/src/features/charts/chart-operational-plan-levels-layer.tsx` — `focusMode` wire
- `apps/web/src/features/charts/ohlcv-chart.tsx` — toggle sin panel nuevo

## Archivos a tocar en V2.31 (orientativo)

- Tokens tipográficos / CSS variables de cabina (`operator-cabin-ui`, decision surface)
- Números financieros compartidos (formatters + clases)
- Reducir cards / `text-[10px]` en superficies Mercado nivel A–B

## Pre-flight mínimo

```bash
cd apps/web && npx vitest run src/features/charts/operational-plan-chart-levels.test.ts src/features/charts/chart-focus-prefs.test.ts src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-30-2026-09-04.md` y el relevo V2.4. Arranca **V2.31** Premium Visual System (tipografía 3 tamaños · números financieros · menos 10px/cards). Freeze intacto. NO MÁS PANELES. No tip sin pedirlo.

## Stamp

| Pieza               | Valor               |
| ------------------- | ------------------- |
| Branch              | `main`              |
| Tip GitHub `v2.4-*` | no (salvo petición) |
