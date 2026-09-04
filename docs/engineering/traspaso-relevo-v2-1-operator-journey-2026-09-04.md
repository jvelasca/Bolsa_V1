# RELEVO — V2.1 Cabina operativa / Operator Journey (2026-09-04)

> **Padre:** [relevo V2.x Product UX](./traspaso-relevo-v2-x-product-ux-2026-09-04.md) (auditoría tip `5cc982e` · veredicto: dirección correcta, UX ~8,7/10, 0 P0).  
> **Estado:** **CERRADO en código** · tip partida [`5cc982e`](https://github.com/jvelasca/Bolsa_V1/commit/5cc982e) · IDs V2.10–V2.18 · smoke browser **PASS** · tip producto [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) (≠ motor `v2.0-beta`).  
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
- ~~Smoke browser ops~~ **PASS** (2026-09-04)
- ~~**V2.17**~~ Confirm bootstrap ámbar visible sin Avanzado
- ~~**V2.18**~~ ADR-040 thaw: strip `Hoy →` en `TradingHealthStrip` (enlace only · L1 intacta)
- ~~Heal PRINCIPAL lifecycle~~ ops local: `POSITION_OPENED` BBVA `0f59aac9-…` → reconcile clean (DB; no código)
- Tip GitHub `v2.1-beta` → [relevo tip](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) (pedido explícito post-smoke)
- ~~Veredicto auditor V2.1-beta~~ **PASS conceptual** (0 P0 · 0 P1 · 4 P2 certificación) · 2026-09-04
- **Next:** [relevo V2.2 Operator Certification](./traspaso-relevo-v2-2-operator-certification-2026-09-04.md)

## Hecho (este arco)

| ID        | Entrega                              | Evidencia                                                      |
| --------- | ------------------------------------ | -------------------------------------------------------------- |
| **V2.10** | Stop técnico ≠ bootstrap 5 %         | `protect-stop-source.ts` · `protectKind` · Confirm ámbar       |
| **V2.11** | Fachada NEXT ACTION + densidad       | `resolveOperatorNextAction` · condition/expires · Avanzado     |
| **V2.12** | Position Card + Risk sizing          | qty / valor / distancia / realizado %                          |
| **V2.13** | AUTO Desk «qué hará AUTO»            | `buildOperatorAutoPlanPreview`                                 |
| **V2.14** | Gráfico trigger + bootstrap advisory | `operational-plan-chart-levels.ts`                             |
| **V2.15** | G-OPERATOR-01                        | `g-operator-01-golden-journey.test.ts`                         |
| **V2.16** | Hoy Exception Desk                   | `exceptionSummary` · colapsar HOLD                             |
| **V2.17** | Confirm bootstrap ámbar visible      | `F3ProtectStopBlock` fuera de Avanzado (`supervised-f3-panel`) |
| **V2.18** | Strip Hoy-en-Mercado (ADR-040 thaw)  | `trading-hoy-strip` → `/mesa` · L1 Hoy intacta                 |

## Pre-flight

```bash
cd packages/shared && npm run build && npx vitest run src/cognitive/operator-cabin-view.test.ts src/cognitive/daily-desk.test.ts src/cognitive/protect-stop-source.test.ts src/cognitive/g-operator-01-golden-journey.test.ts
cd apps/web && npx vitest run src/features/operations/propose-position-exit.test.ts src/features/trading/f3-protect-stop-block.test.tsx src/features/charts/operational-plan-chart-levels.test.ts src/features/trading/decision-surface-journey.test.tsx src/features/mesa/mesa-hoy-view.test.ts
```

## Ops smoke (2026-09-04)

| Check                               | Evidencia                                                                                                                                                                                                                                                                                                                                                                                                                     | RESULT   |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Pre-flight vitest (shared+web)      | shared 38 · web 39                                                                                                                                                                                                                                                                                                                                                                                                            | **PASS** |
| Bootstrap Confirm ámbar (**V2.10**) | Cuenta limpia `debug-opening` (`516fc66a90ae40a0bdb83eecd`) · BMY `OPEN_UNPROTECTED` · CTA Proteger «emergencia −5 %» · Confirm drawer · **Ajustes avanzados** → `data-testid=f3-protect-stop` `data-protect-kind=bootstrap` · banner `f3-protect-bootstrap-banner` · copy «Posición sin protección» / «Stop de emergencia sugerido: −5 %» · stop 64.69 · clases ámbar `border-amber-600/50 bg-amber-500/10` · **sin firmar** | **PASS** |
| NEXT ACTION condition (**V2.11**)   | Misma cabina: `next-action-title`=PROTEGER · `data-pov-state=OPEN_UNPROTECTED` · `next-action-condition` «Aplicar stop de emergencia (−5 %) o definir stop técnico»                                                                                                                                                                                                                                                           | **PASS** |
| Hoy exception summary (**V2.16**)   | `/mesa` · `daily-desk-exception-summary` «🔴 1 requieren atención · 🟠 0 oportunidades · 🟢 1 posiciones OK» · `posiciones`/`no_operar` `data-collapsed=1` · atención expandida                                                                                                                                                                                                                                               | **PASS** |

### Smoke notes (ops)

- PRINCIPAL: heal lifecycle 2026-09-04 (`POSITION_OPENED` BBVA) → OR-4 reconcile **clean** (antes `risk_veto` por drift).
- Fixture OK: cuenta vacía + mandato BMY + `POST /portfolio/trade` buy sin stop → `OPEN_UNPROTECTED`.
- Bloque ámbar V2.10 (+ **V2.17**): `F3ProtectStopBlock` visible en Confirm **sin** abrir Ajustes avanzados; ticket preview sigue en Avanzado.

## Post-V2.1 verdict (ADR-040)

- **NO** colapsar Hoy en Mercado — 5 puertas L1 intactas (ADR-040 §10).
- ~~Strip compacto~~ **thaw V2.18:** `Hoy →` en `TradingHealthStrip` = enlace only (`data-testid=trading-hoy-strip`).
- Tip GitHub `v2.1-beta` pedido explícitamente → relevo tip.
