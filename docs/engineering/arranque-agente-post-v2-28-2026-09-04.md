# ARRANQUE — siguiente agente · post V2.28 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** histórico · V2.29 **hecho** · next = [arranque post-V2.29](./arranque-agente-post-v2-29-2026-09-04.md) → **V2.30**.

## Estado al relevo

| Corte                         | Estado                          |
| ----------------------------- | ------------------------------- |
| V2.27 Journal spine + MFE/MAE | **hecho**                       |
| V2.28 PLAN DE POSICIÓN        | **hecho en código**             |
| V2.3-ops smoke 10 s           | pendiente sesión ops (paralelo) |
| V2.29 Protection State        | **SIGUIENTE**                   |
| Tip `v2.4-*`                  | solo con petición explícita     |

## Primer ID a implementar

**V2.29 — Protection State**

- Planificado / confirmado / enviado / protegido · sin «propuesta thin».
- Separar PLAN vs EJECUCIÓN en la línea de protección (stop planificado ≠ orden confirmada).
- Freeze intacto · display-only · sin controles AUTO nuevos · sin Journal redo · sin segundo Mission/Exit Route (V2.28).

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.28 (no rehacer PLAN)

- `packages/shared/src/cognitive/operator-cabin-view.ts` — `buildOperatorPositionPlan` · `buildOperatorPositionPlanFromDecision`
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — `OperatorPositionPlan`
- `apps/web/src/features/trading/decision-surface-compact.tsx` — Journey HUD L3 = PLAN · L4 ¿Por qué?/AUTO
- `apps/web/src/features/trading/operativa-cockpit-card.tsx` — sin `ExitRouteView` duplicado · AUTO en L4

## Archivos a tocar en V2.29 (orientativo)

- `packages/shared/src/cognitive/operator-cabin-view.ts` — `OperatorProtectionStateV1` / honesty pipeline
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — `OperatorProtectionLine`
- Surfaces que muestran stop planificado vs ejecutado (Mercado · Gráfico · Hoy)

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/g-operator-02-golden-journey.test.ts
cd apps/web && npx vitest run src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/trading/operativa-cockpit-card.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-28-2026-09-04.md` y el relevo V2.4. Arranca **V2.29** Protection State (planificado / confirmado / enviado / protegido). Freeze intacto. NO MÁS PANELES. No tip sin pedirlo.

## Stamp

| Pieza               | Valor               |
| ------------------- | ------------------- |
| Branch              | `main`              |
| Tip GitHub `v2.4-*` | no (salvo petición) |
