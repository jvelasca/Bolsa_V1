# ARRANQUE — siguiente agente · post V2.26 (2026-09-04)

> **Superseded:** tras V2.27 usar [arranque post-V2.27](./arranque-agente-post-v2-27-2026-09-04.md) · [relevo V2.4](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md).  
> **Leer primero:** [relevo V2.3 Mercado Polish](./traspaso-relevo-v2-3-mercado-polish-2026-09-04.md) · padre [V2.2 Certification](./traspaso-relevo-v2-2-operator-certification-2026-09-04.md).  
> **Tip producto previo:** [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Código en `main`:** tip push [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) (V2.2 + V2.24–V2.26).  
> **Para quién:** histórico · V2.27 **hecho** · next = V2.28 PLAN DE POSICIÓN.

## Estado al relevo

| Corte                                     | Estado                                                                             |
| ----------------------------------------- | ---------------------------------------------------------------------------------- |
| V2.2 Operator Certification (V2.19–V2.23) | **hecho en código** · golden G-OPERATOR-02/03/04                                   |
| V2.24 Composición 4 niveles               | **hecho**                                                                          |
| V2.25 Densidad / a11y / status            | **hecho**                                                                          |
| V2.26 Escalera trailing visual            | **hecho** · tip [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) |
| V2.27 Journal spine + MFE/MAE             | **hecho** · ver [arranque post-V2.27](./arranque-agente-post-v2-27-2026-09-04.md)  |
| V2.3-ops smoke 10 s                       | pendiente sesión ops                                                               |
| Tip `v2.3-*`                              | solo con petición explícita                                                        |

## Primer ID a implementar

**V2.27 — Journal spine + MFE/MAE** _(cerrado — no reabrir)_

- Cadena visible: TESIS → DECISIÓN → ENTRADA → RIESGO → T1 → T2 → TRAILING → EXIT → RESULTADO
- Métricas: Initial Risk · Realized R · Final R · **MFE** · **MAE**
- SoT learning = `decision_sessions` (no inventar segundo ledger)
- Display-only · reutilizar proyección shared cuando exista; Hoy ya tiene `hoy-mfe-mae` como referencia de copy
- Superficie principal: `apps/web/src/features/decision-journal/*`
- Freeze intacto (NO LIVE · no FSM · ExitPolicy 30/30 · no controles AUTO nuevos · HOY strip congelado)

## Freeze (copiar al chat)

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip `Mercado · Datos · Estado · Barrido · Hoy →` · AUTO sin controles nuevos · `OperatorDecision` = proyección shared.

## Archivos clave ya tocados (no rehacer)

- `packages/shared/src/cognitive/operator-cabin-view.ts` — `OperatorDecisionV1` · `buildOperatorExitLadder` · protection/remaining
- `apps/web/src/features/trading/operator-cabin-ui.tsx` — L1–L4 · ladder · status · focus ring
- `apps/web/src/features/trading/decision-surface-compact.tsx` · `operativa-cockpit-card.tsx`
- `apps/web/src/features/charts/operational-plan-chart-levels.ts` — títulos `T1 · 30%`
- Goldens: `g-operator-02/03/04-*.test.ts`
- Journal V2.27: `journal-spine-view.ts` · `decision-ficha-panel.tsx`

## Pre-flight mínimo antes de tocar Journal

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/g-operator-02-golden-journey.test.ts
cd apps/web && npx vitest run src/features/trading/operator-cabin-ui.test.tsx src/features/trading/decision-surface-journey.test.tsx src/features/charts/operational-plan-chart-levels.test.ts
```

## Prompt sugerido al abrir chat

> Lee `docs/engineering/arranque-agente-post-v2-27-2026-09-04.md` y el relevo V2.4. Arranca **V2.28** PLAN DE POSICIÓN. Freeze intacto. NO MÁS PANELES.

## Stamp push

| Pieza                           | Valor                                                              |
| ------------------------------- | ------------------------------------------------------------------ |
| Commit tip (V2.2 + V2.24–V2.26) | [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) |
| Branch                          | `main`                                                             |
| Tip GitHub `v2.3-*`             | no (salvo petición)                                                |
