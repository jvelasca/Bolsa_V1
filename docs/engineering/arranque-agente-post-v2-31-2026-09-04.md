# ARRANQUE — siguiente agente · post V2.31 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** histórico · V2.32 **hecho** · next = [arranque post-V2.32](./arranque-agente-post-v2-32-2026-09-04.md) · tip `v2.4-*` solo con petición.

## Estado al relevo

| Corte                           | Estado                                                                        |
| ------------------------------- | ----------------------------------------------------------------------------- |
| V2.28 PLAN DE POSICIÓN          | **hecho**                                                                     |
| V2.29 Protection State          | **hecho**                                                                     |
| V2.30 Chart Focus               | **hecho**                                                                     |
| V2.31 Premium Visual System     | **hecho**                                                                     |
| V2.32 Golden Operator Journey 2 | **hecho** · [arranque post-V2.32](./arranque-agente-post-v2-32-2026-09-04.md) |
| V2.3-ops smoke 10 s             | pendiente sesión ops (paralelo)                                               |
| Tip `v2.4-*`                    | solo con petición explícita                                                   |

## Primer ID a implementar

**V2.32 — Golden Operator Journey 2** (histórico — ya cerrado)

- Cadena ESTUDIO → … → EXIT visible y contractual en Mercado · Gráfico · NEXT · Risk · Plan · AUTO · Hoy · Journal.
- Mismo stop / T1 / T2 / remaining / next action en todas las superficies (test contractual).
- Freeze intacto · display-only · sin controles AUTO nuevos · sin paneles nuevos · Visual System / Chart Focus / PLAN / Protection intactos.

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.31 (no rehacer Visual System)

- `apps/web/src/features/trading/cabin-visual.ts` — 3 tamaños `hero` / `operativa` / `meta` · `CABIN_NUM` tabular
- `apps/web/src/index.css` — `--cabin-type-*` · `.cabin-type-hero|operativa|meta`
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — NEXT ACTION héroe · Risk Box sin card anidada · plan sin rungs-card
- `apps/web/src/features/trading/decision-surface-compact.tsx` · `operativa-cockpit-card.tsx` — A–B sin 9px/10px

## Archivos a tocar en V2.32 (orientativo)

- Goldens `packages/shared/src/cognitive/g-operator-*.test.ts` (ampliar journey 2)
- Superficies contractuales: Mercado cockpit · chart HUD · Hoy · Journal ficha · AUTO posture (display only)
- Tests journey existentes: `decision-surface-journey.test.tsx` · `g-operator-02/03/04`

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && npx vitest run src/features/trading/cabin-visual.test.ts src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-31-2026-09-04.md` y el relevo V2.4. Arranca **V2.32** Golden Operator Journey 2 (ESTUDIO→EXIT contractual en Mercado · Gráfico · NEXT · Risk · Plan · AUTO · Hoy · Journal). Freeze intacto. NO MÁS PANELES. No tip sin pedirlo.

## Stamp

| Pieza               | Valor               |
| ------------------- | ------------------- |
| Branch              | `main`              |
| Tip GitHub `v2.4-*` | no (salvo petición) |
