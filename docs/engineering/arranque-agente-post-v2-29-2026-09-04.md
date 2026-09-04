# ARRANQUE — siguiente agente · post V2.29 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** histórico · V2.30 **hecho** · next = [arranque post-V2.30](./arranque-agente-post-v2-30-2026-09-04.md) → **V2.31**.

## Estado al relevo

| Corte                  | Estado                                                                        |
| ---------------------- | ----------------------------------------------------------------------------- |
| V2.28 PLAN DE POSICIÓN | **hecho**                                                                     |
| V2.29 Protection State | **hecho en código**                                                           |
| V2.3-ops smoke 10 s    | pendiente sesión ops (paralelo)                                               |
| V2.30 Chart Focus      | **hecho** · [arranque post-V2.30](./arranque-agente-post-v2-30-2026-09-04.md) |
| Tip `v2.4-*`           | solo con petición explícita                                                   |

## Primer ID a implementar

**V2.30 — Chart Focus**

- Modo Simple / Completo en gráfico.
- T1 alcanzado discreto (sin ruido visual).
- Freeze intacto · display-only · sin controles AUTO nuevos · sin Journal redo · sin segundo Mission/Exit Route · Protection State intacto.

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.29 (no rehacer Protection)

- `packages/shared/src/cognitive/operator-cabin-view.ts` — `phase` / `phaseLabel` / `plannedStop` · `resolveOperatorProtectionPhase`
- `packages/shared/src/cognitive/mesa-protection-state.ts` — Planificado / Enviado / Protegido · Sugerido ≠ Propuesta
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — `OperatorProtectionLine` PLAN vs EJECUCIÓN
- `apps/web/src/features/trading/exit-route-view.tsx` — sin «propuesta thin»

## Archivos a tocar en V2.30 (orientativo)

- Chart HUD / decision surface density (`decision-surface-compact` hud variant)
- Preferencias Mercado chart focus / simple mode
- Markers T1 alcanzado en gráfico

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/mesa-protection-state.test.ts src/cognitive/g-operator-03-protect-journey.test.ts
cd apps/web && npx vitest run src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-page.test.ts
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-29-2026-09-04.md` y el relevo V2.4. Arranca **V2.30** Chart Focus (Simple / Completo · T1 alcanzado discreto). Freeze intacto. NO MÁS PANELES. No tip sin pedirlo.

## Stamp

| Pieza               | Valor               |
| ------------------- | ------------------- |
| Branch              | `main`              |
| Tip GitHub `v2.4-*` | no (salvo petición) |
