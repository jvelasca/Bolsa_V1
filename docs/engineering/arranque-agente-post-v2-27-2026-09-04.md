# ARRANQUE — siguiente agente · post V2.27 (2026-09-04)

> **Leer primero:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md) · padre [V2.3 Mercado Polish](./traspaso-relevo-v2-3-mercado-polish-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Para quién:** histórico · V2.28 **hecho** · next = [arranque post-V2.28](./arranque-agente-post-v2-28-2026-09-04.md) → **V2.29**.

## Estado al relevo

| Corte                                     | Estado                                                                             |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| V2.2 Operator Certification (V2.19–V2.23) | **hecho**                                                                          |
| V2.24–V2.26 Mercado polish UI             | **hecho** · tip [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) |
| V2.27 Journal spine + MFE/MAE             | **hecho en código**                                                                |
| V2.3-ops smoke 10 s                       | pendiente sesión ops (paralelo)                                                    |
| V2.28 PLAN DE POSICIÓN                    | **SIGUIENTE**                                                                      |
| Tip `v2.3-*` / `v2.4-*`                   | solo con petición explícita                                                        |

## Primer ID a implementar

**V2.28 — PLAN DE POSICIÓN**

- Fusionar Position Mission + Exit Route en una sola superficie «PLAN DE LA POSICIÓN».
- RESTANTE % central (ya en AUTO / ladder — no duplicar lógica; proyectar).
- Cabina: NEXT ACTION → RIESGO → PLAN → ¿POR QUÉ? / AUTO plegados.
- Freeze intacto · display-only · sin controles AUTO nuevos · sin Journal redo.

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip `Mercado · Datos · Estado · Barrido · Hoy →` · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

## Archivos clave V2.27 (no rehacer Journal)

- `packages/shared/src/cognitive/journal-spine-view.ts` — `buildJournalSpineView` · RESULTADO
- `apps/web/src/features/decision-journal/decision-ficha-panel.tsx` — `journal-spine` · `journal-mfe-mae`
- Eco sesión: `decision_journal_studies.py` · `mfeMae` / `learningVerdict`

## Archivos a tocar en V2.28 (orientativo)

- `apps/web/src/features/trading/operator-cabin-ui.tsx` · mission / exit ladder
- `apps/web/src/features/trading/exit-route-view.tsx` · `operativa-cockpit-card.tsx`
- `packages/shared/src/cognitive/exit-route-view.ts` · `operator-cabin-view.ts` (proyección, no FSM)

## Pre-flight mínimo

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/journal-spine-view.test.ts src/cognitive/operator-cabin-view.test.ts src/cognitive/g-operator-02-golden-journey.test.ts
cd apps/web && npx vitest run src/features/decision-journal/decision-ficha-panel.render.test.tsx src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-27-2026-09-04.md` y el relevo V2.4. Arranca **V2.28** PLAN DE POSICIÓN (fusionar Mission + Exit Route). Freeze intacto. NO MÁS PANELES. No tip sin pedirlo.

## Stamp

| Pieza               | Valor               |
| ------------------- | ------------------- |
| Branch              | `main`              |
| Tip GitHub `v2.4-*` | no (salvo petición) |
