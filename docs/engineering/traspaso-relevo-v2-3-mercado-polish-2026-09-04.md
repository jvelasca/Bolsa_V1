# RELEVO — V2.3 Mercado Polish (2026-09-04)

> **Padre:** [relevo V2.2 Operator Certification](./traspaso-relevo-v2-2-operator-certification-2026-09-04.md) · tip [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Estado:** **CERRADO en código** · IDs V2.24–V2.27 · tip previo [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) · V2.27 Journal spine entregado.  
> **Para quién:** ops · UX operativa · no reabrir motor FSM · no tip `v2.3-*` salvo petición explícita.  
> **Partida:** V2.2 CERRADO · smoke browser **V2.3-ops** (criterio 10 s) aún pendiente sesión ops.  
> **Next:** [V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md) · [arranque post-V2.27](./arranque-agente-post-v2-27-2026-09-04.md).

## Objetivo

Pasar de «los bloques existen y están certificados» a **cabina legible en 10 s**: jerarquía definitiva de 4 niveles, densidad controlada, escalera T1→T2→trailing visible, Journal con MFE/MAE y métricas de resultado. Sin features de motor; sin segundo FSM; sin controles AUTO nuevos; sin incrustar Hoy en Mercado.

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy moderado **30/30** (nunca 25/25) · **HOY strip congelado:** `Mercado · Datos · Estado · Barrido · Hoy →` y nada más · AUTO Desk: **no** se añaden controles · `OperatorDecision` = proyección shared (V2.19+), no endpoint/FSM · autoridad de protección = stop **ejecutado**.

## Composición 4 niveles (auditor §6)

| Nivel | Pregunta           | Superficie canónica                                     |
| ----- | ------------------ | ------------------------------------------------------- |
| **1** | ¿Qué hago ahora?   | NEXT ACTION (héroe)                                     |
| **2** | ¿Con qué riesgo?   | Risk Box · ENTRY · STOP · SIZE · RISK € · R/R           |
| **3** | ¿Qué pasa después? | Mission / AUTO preview · T1 · T2 · TRAILING · EXIT      |
| **4** | ¿Por qué?          | Tesis · indicadores · IA · Journal (colapsado / enlace) |

Todo lo demás (Avanzado, jerga motor, debug) queda bajo nivel 4 o colapsado.

## IDs (orden)

| ID           | Entrega                                             | Notas                                                                                     |
| ------------ | --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **V2.24**    | Composición 4 niveles en DECISIÓN                   | Layout explícito L1→L4 · sin reordenar autoridad · testids por nivel                      |
| **V2.25**    | Densidad · tipografía · espaciado · color semántico | Jerarquía de tamaños · estados vacíos/loading/error · a11y teclado · responsive cabina    |
| **V2.26**    | Escalera trailing visual                            | Entrada→Stop→T1→T2·Trail · % ExitPolicy 30/30 · no hardcode 25/25                         |
| **V2.27**    | Journal spine + MFE/MAE                             | TESIS→…→RESULTADO · Initial Risk · Realized/Final R · MFE · MAE · SoT `decision_sessions` |
| **V2.3-ops** | Ops smoke criterio 10 s                             | Browser (sesión ops, paralelo) · **no** es el ID de producto V2.28 de V2.4                |

> **Nota ID:** el producto **V2.28** = PLAN DE POSICIÓN vive en [V2.4](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md). El smoke 10 s se etiqueta **V2.3-ops** para no colisionar.

## Principio

BACKEND / PositionState / ExitPolicy → `packages/shared` projections → React **display-only**.  
V2.3 es **polish de composición**, no nueva Operating Truth. Reutilizar `OperatorDecisionV1` / `buildOperatorDecision` / protection / remaining / nextAction reasons de V2.2.  
§A.8 intacto. HOY = Exception Desk (enlace only). Journal = memoria + learning; no segunda mesa.

## Hecho (este arco)

| ID        | Entrega                          | Evidencia                                                                                         |
| --------- | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| **V2.24** | Composición 4 niveles DECISIÓN   | `OperatorCabinLevel` · journey HUD L1–L4 · entry L1–L4 · cockpit `data-cabin-composition`         |
| **V2.25** | Densidad · color · a11y · status | `CABIN_TYPE` / `CABIN_FOCUS_RING` · protección semántica · `OperatorCabinStatus` · mission active |
| **V2.26** | Escalera trailing visual         | `buildOperatorExitLadder` · `OperatorExitLadder` · chart `T1 · 30%` / `T2 · 30%` (ExitPolicy)     |
| **V2.27** | Journal spine + MFE/MAE          | `buildJournalSpineView` · ficha `journal-spine` / `journal-mfe-mae` · eco `runtime.mfeMae`        |

## OUT / next

- **Siguiente agente:** [arranque post-V2.27](./arranque-agente-post-v2-27-2026-09-04.md) → **V2.28** PLAN DE POSICIÓN (V2.4)
- **V2.3-ops** smoke browser 10 s (sesión ops; paralelo; no bloquea V2.4)
- Tip `v2.3-*` solo con petición explícita post-smoke
- No reabrir certificación V2.19–V2.23 salvo regresión
- **NO MÁS PANELES** en Mercado — coherencia de cabina = V2.4

## Pre-flight (partida = suite V2.2 + Journal)

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/journal-spine-view.test.ts src/cognitive/g-operator-02-golden-journey.test.ts
cd apps/web && npx vitest run src/features/decision-journal/decision-ficha-panel.test.ts src/features/decision-journal/decision-ficha-panel.render.test.tsx src/features/trading/operator-cabin-ui.test.tsx
```

## Ops smoke (pendiente)

| Check                                         | RESULT  |
| --------------------------------------------- | ------- |
| Pre-flight vitest (shared + web)              | partida |
| L1 NEXT ACTION dominante · L2–L4 legibles     | ops     |
| Escalera T1/T2/trailing visible post-posición | ops     |
| Journal MFE/MAE + R en ficha cerrada          | ops     |
| Criterio 10 s (auditor) sin salir de MERCADO  | ops     |
