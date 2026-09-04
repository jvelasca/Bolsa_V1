# RELEVO — V2.2 Operator Certification (2026-09-04)

> **Padre:** [relevo V2.1 Operator Journey](./traspaso-relevo-v2-1-operator-journey-2026-09-04.md) · tip [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Estado:** **CERRADO en código** · IDs V2.19–V2.23 · pre-flight vitest **PASS**.  
> **Para quién:** ops · certificación de journeys · no reabrir motor FSM.  
> **Veredicto auditor V2.1-beta:** PASS conceptual · 0 P0 · 0 P1 · 4 P2 de certificación (no features).

## Objetivo

Una sola Operating Truth (`OperatorDecisionV1` en `packages/shared`) proyectada a Mercado · Hoy · Position Card · AUTO · Journal. El operador selecciona un valor en ESTUDIO y, sin salir de MERCADO, entiende qué hacer, con qué riesgo, dónde está la protección, qué hará T1/T2/trailing y cuál es exactamente la próxima acción — la misma decisión en Hoy.

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy moderado **30/30** (nunca 25/25) · **HOY strip congelado:** `Mercado · Datos · Estado · Barrido · Hoy →` y nada más · AUTO Desk: no se añaden controles · `OperatorDecision` = proyección shared, no endpoint/FSM.

## IDs (orden)

| ID        | Entrega                                      | Notas                                                                                          |
| --------- | -------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| **V2.19** | `OperatorDecisionV1` — una Operating Truth   | `buildOperatorDecision` · Hoy CTA vía `mesaNextActionFromPositionOperatingTruth`               |
| **V2.20** | Protección real vs calculada                 | `none` / `emergency` / `technical` · ejecutado ≠ `initialStop` plan · fail-closed persist skip |
| **V2.21** | Remaining quantity en todas las superficies  | AUTO preview + Mission `RESTANTE` + Journal `journal-remaining`                                |
| **V2.22** | NEXT ACTION Porque / Próximo cambio / Caduca | `reasons[]` · `nextChange` · condition/expires ya V2.11                                        |
| **V2.23** | G-OPERATOR-02 / 03 / 04                      | matriz completa · bootstrap ≠ técnico · persist fail → PROTEGER                                |

## Principio

BACKEND / PositionState / ExitPolicy → `packages/shared` projections → React display-only.  
Autoridad de protección = stop **ejecutado** (`trail.currentStop` / `currentStop`), nunca el stop planificado.  
§A.8 intacto: `full_exit` / `reduce` ganan a protect-hint. `protect_hint` fino + HOLD no fuerza PROTEGER. `OPEN_UNPROTECTED` / persist skip **sí**.

## Hecho (este arco)

| ID        | Entrega                            | Evidencia                                                            |
| --------- | ---------------------------------- | -------------------------------------------------------------------- |
| **V2.19** | OperatorDecision facade            | `operator-cabin-view.ts` · `operatorCabinTruthFromPot`               |
| **V2.20** | Protection line + chart bootstrap  | `OperatorProtectionLine` · `stopIsBootstrap` en chart layer          |
| **V2.21** | Remaining AUTO / Mission / Journal | `OperatorAutoPlanPreviewV1.remainingPct` · `mission-step-remaining`  |
| **V2.22** | NEXT ACTION reasons                | `next-action-reasons` · `next-action-next-change`                    |
| **V2.23** | Golden journeys                    | `g-operator-02/03/04-*.test.ts` · 01 extendido con `protection.kind` |

## OUT / next

- ~~V2.3 Mercado polish~~ → [relevo V2.3 Mercado Polish](./traspaso-relevo-v2-3-mercado-polish-2026-09-04.md) **ABIERTO** (V2.24–V2.28)
- Tip `v2.2-*` solo con petición explícita
- Smoke browser ops (criterio 10 s del auditor) — pendiente de sesión ops · también V2.28

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts src/cognitive/protect-stop-source.test.ts src/cognitive/g-operator-01-golden-journey.test.ts src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-04-protect-fail.test.ts src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/position-operating-truth.test.ts
cd apps/web && npx vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/f3-protect-stop-block.test.tsx src/features/charts/operational-plan-chart-levels.test.ts src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts src/features/trading/position-operating-summary.test.tsx
```

## Ops smoke (pendiente)

| Check                                      | RESULT      |
| ------------------------------------------ | ----------- |
| Pre-flight vitest (shared + web)           | **PASS**    |
| OPEN_UNPROTECTED → PROTEGER en Mercado=Hoy | ops         |
| Persist fail → SIN PROTECCIÓN + PROTEGER   | ops         |
| Confirm bootstrap nunca «stop técnico»     | ops (V2.17) |
| RESTANTE visible Position Card / AUTO      | ops         |
| NEXT ACTION Porque + Próximo cambio        | ops         |
