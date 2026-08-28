# RELEVO — V1.25 Operational safety (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **PUBLICACIÓN** — tag `v1.25-beta` → `f8e53f57`.
> **Padre:** [`traspaso-relevo-v1-24-honesty-2026-08-28.md`](./traspaso-relevo-v1-24-honesty-2026-08-28.md) · [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md) · [ADR-040 §10](../adr/040-user-information-architecture.md).
> **Tag relevo:** [`traspaso-relevo-tag-v1-25-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-25-beta-2026-08-28.md).

---

## 0. Qué cierra V1.25

| Pieza                                                                          | Estado                                  |
| ------------------------------------------------------------------------------ | --------------------------------------- |
| Sizing único desde TradePlan TRIGGERED (`resolveSupervisedOpeningQuantity`)    | CÓDIGO + tests                          |
| Propose paths sin `suggestQuantityFromCash` como SoT cuando hay plan TRIGGERED | CÓDIGO                                  |
| Ticket Confirm slim: riesgo € + R + % cartera en default                       | CÓDIGO + tests                          |
| Stop editable con recálculo y firma (`signedStop`)                             | CÓDIGO + tests (TS + Python paridad)    |
| What-if Antes → Después en ticket (`buildConfirmPortfolioScenario`)            | CÓDIGO + tests                          |
| Assessments / trailing bajo «Ajustes avanzados»                                | CÓDIGO                                  |
| Override obligatorio cuando excede plan (`F3RiskSignatureBlock`)               | CÓDIGO (heredado V1.24, cableado V1.25) |
| Marco Operative Flow + contrato normativo Confirm                              | DOCS                                    |
| ADR-040 §10 enmienda Operative Flow                                            | DOCS                                    |

## 1. Freeze heredado (intactos)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado · DEX-1…5 · nav L1 congelada · shell Mercado LISTAS\|GRÁFICO\|OPERATIVA · sin drag gráfico · sin móvil · BETA.

## 2. Fuera de V1.25 (deuda / siguiente epic)

No mezclar sin palabra explícita:

| Prioridad | Tema                                                                           |
| --------- | ------------------------------------------------------------------------------ |
| V1.26     | Position lifecycle (post-fill, T1 gestionado, ruta operativa)                  |
| V1.27     | Mercado operativo (drag, órdenes en gráfico)                                   |
| V1.28     | UX 10/10 (command palette, hotkeys, densidad)                                  |
| Lab       | Backtest `risk_policy` nunca pasado desde `backtests.py`                       |
| Producto  | Grid Cobertura 180 · batch propose · OpportunityScore · VaR/correlación · thaw |

## 3. Arranque mañana

1. Leer este relevo + [`traspaso-relevo-tag-v1-25-beta-2026-08-28.md`](./traspaso-relevo-tag-v1-25-beta-2026-08-28.md) + marco [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md).
2. Confirmar CI tag GREEN; si falta, pin URL en el tag relevo.
3. Elegir **un** epic (recomendado: V1.26 position lifecycle **o** Lab backtest risk_policy — no ambos).
4. No reabrir sizing paralelo ni `% caja` como mandato en openings supervisados.

## 4. Verificación local (pre-tag)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline
pnpm test:decision-spine
```

Tests focalizados V1.25: `confirm-opening-sizing` · `confirm-portfolio-scenario` · `risk-signature` (signedStop) · `f3-trade-plan-risk-first-block` · `supervised-opening-sizing` · `supervised-f3-panel.v125`.
