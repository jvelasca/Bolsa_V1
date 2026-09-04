# RELEVO — V2.1 Cabina operativa / Operator Journey (2026-09-04)

> **Padre:** [relevo V2.x Product UX](./traspaso-relevo-v2-x-product-ux-2026-09-04.md) (auditoría tip `5cc982e` · veredicto: dirección correcta, UX ~8,7/10, 0 P0).  
> **Estado:** **CERRADO en código** · tip partida [`5cc982e`](https://github.com/jvelasca/Bolsa_V1/commit/5cc982e) · IDs V2.10–V2.16 implementados · **sin tip GitHub** `v2.x-*` / `v2.1-*` (≠ tip motor `v2.0-beta`).  
> **Para quién:** ops · follow-on producto · no reabrir motor FSM.

## Objetivo

Pasar de «la UI expresa el concepto» a **consola operativa**: integrar NEXT ACTION · Riesgo · Plan · Misión · AUTO · gráfico alrededor de una sola Operating Truth (`shared` → proyección React). Primer commit obligatorio = separar stop técnico vs bootstrap 5 %.

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · no colapso L1 (ADR-040) · no tip `v2.x-*` salvo petición explícita.

## IDs (orden)

| ID        | Entrega                                  | Notas                                                                |
| --------- | ---------------------------------------- | -------------------------------------------------------------------- |
| **V2.10** | Stop técnico ≠ bootstrap 5 %             | `protectKind` · copy emergencia · shared `protect-stop-source`       |
| **V2.11** | Fachada NEXT ACTION + densidad 3 niveles | `resolveOperatorNextAction` · condition/expires · Avanzado colapsado |
| **V2.12** | Position Card + Risk Box sizing          | qty / valor / % cartera desde journey + sizing                       |
| **V2.13** | AUTO Desk «qué hará AUTO»                | preview por instrumento desde ExitPolicy                             |
| **V2.14** | Gráfico operativo                        | línea trigger · bootstrap advisory (no rojo técnico)                 |
| **V2.15** | G-OPERATOR-01                            | matrix WAIT_TRIGGER → EXIT                                           |
| **V2.16** | Hoy Exception Desk                       | conteos · colapsar HOLD / no_operar                                  |

## Principio

BACKEND / PositionState / ExitPolicy → `packages/shared` projections → React display-only.  
T1/T2 % = `ExitPolicy` (moderado 30/30), **nunca** hardcode 25/25 en UI.  
No inventar `OPEN_UNPLANNED` en FSM; lenguaje operador sobre `OPEN_UNPROTECTED` / `PROTECTED` / …

## OUT / next

- ~~Veredicto auditor V2.x~~ → relevo V2.x CERRADO con PASS conceptual (sin tip producto)
- ~~Implementar V2.10…V2.16~~ **hecho en código** (este relevo)
- Tip GitHub solo si se pide explícitamente
- Colapso L1 (ADR-040) aparcado hasta smoke ops + veredicto post-V2.1
- Smoke browser ops: bootstrap Confirm ámbar · NEXT ACTION condition · Hoy exception summary

## Hecho (este arco)

| ID        | Entrega                              | Evidencia                                                  |
| --------- | ------------------------------------ | ---------------------------------------------------------- |
| **V2.10** | Stop técnico ≠ bootstrap 5 %         | `protect-stop-source.ts` · `protectKind` · Confirm ámbar   |
| **V2.11** | Fachada NEXT ACTION + densidad       | `resolveOperatorNextAction` · condition/expires · Avanzado |
| **V2.12** | Position Card + Risk sizing          | qty / valor / distancia / realizado %                      |
| **V2.13** | AUTO Desk «qué hará AUTO»            | `buildOperatorAutoPlanPreview`                             |
| **V2.14** | Gráfico trigger + bootstrap advisory | `operational-plan-chart-levels.ts`                         |
| **V2.15** | G-OPERATOR-01                        | `g-operator-01-golden-journey.test.ts`                     |
| **V2.16** | Hoy Exception Desk                   | `exceptionSummary` · colapsar HOLD                         |

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts src/cognitive/protect-stop-source.test.ts src/cognitive/g-operator-01-golden-journey.test.ts
cd apps/web && npx vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/f3-protect-stop-block.test.tsx src/features/charts/operational-plan-chart-levels.test.ts src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```
