# RELEVO — V2.3 Mercado Polish (2026-09-04)

> **Padre:** [relevo V2.2 Operator Certification](./traspaso-relevo-v2-2-operator-certification-2026-09-04.md) · tip [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Estado:** **ABIERTO** · IDs V2.24–V2.28 · **V2.24–V2.26 hechos** · tip código [`d434ebe2`](https://github.com/jvelasca/Bolsa_V1/commit/d434ebe2) · next agente = V2.27.  
> **Para quién:** ops · UX operativa · no reabrir motor FSM · no tip `v2.3-*` salvo petición explícita.  
> **Partida:** V2.2 CERRADO en código (Operating Truth + golden 02/03/04) · smoke browser V2.2 aún pendiente ops.  
> **Arranque nuevo agente:** [arranque post-V2.26](./arranque-agente-post-v2-26-2026-09-04.md).

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

| ID        | Entrega                                             | Notas                                                                                             |
| --------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| **V2.24** | Composición 4 niveles en DECISIÓN                   | Layout explícito L1→L4 · sin reordenar autoridad · testids por nivel                              |
| **V2.25** | Densidad · tipografía · espaciado · color semántico | Jerarquía de tamaños · estados vacíos/loading/error · a11y teclado · responsive cabina            |
| **V2.26** | Escalera trailing visual                            | Entrada→Stop→T1→T2→Trail en Position Card / chart · % ExitPolicy 30/30 · no hardcode 25/25        |
| **V2.27** | Journal spine + MFE/MAE                             | TESIS→…→RESULTADO · Initial Risk · Realized/Final R · MFE · MAE · SoT `decision_sessions` intacto |
| **V2.28** | Ops smoke criterio 10 s                             | Browser: valor ESTUDIO → entiende acción/riesgo/protección/plan sin salir de MERCADO              |

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

## OUT / next

- **Siguiente agente:** [arranque post-V2.26](./arranque-agente-post-v2-26-2026-09-04.md) → **V2.27** Journal spine + MFE/MAE
- V2.28 Ops smoke criterio 10 s (sesión ops; puede ir en paralelo)
- Tip `v2.3-*` solo con petición explícita post-smoke
- No reabrir certificación V2.19–V2.23 salvo regresión
- V2.26 auditable en GitHub tras push de este corte

## Pre-flight (partida = suite V2.2)

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts src/cognitive/protect-stop-source.test.ts src/cognitive/g-operator-01-golden-journey.test.ts src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-04-protect-fail.test.ts src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/position-operating-truth.test.ts
cd apps/web && npx vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/f3-protect-stop-block.test.tsx src/features/charts/operational-plan-chart-levels.test.ts src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts src/features/trading/position-operating-summary.test.tsx
```

## Ops smoke (pendiente)

| Check                                         | RESULT  |
| --------------------------------------------- | ------- |
| Pre-flight vitest (shared + web)              | partida |
| L1 NEXT ACTION dominante · L2–L4 legibles     | ops     |
| Escalera T1/T2/trailing visible post-posición | ops     |
| Journal MFE/MAE + R en ficha cerrada          | ops     |
| Criterio 10 s (auditor) sin salir de MERCADO  | ops     |
