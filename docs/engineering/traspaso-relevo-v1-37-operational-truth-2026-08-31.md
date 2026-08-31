# RELEVO — V1.37 Operational Truth (2026-08-31)

> **Padre:** [`plan-v137-operational-truth-2026-08-31.md`](./plan-v137-operational-truth-2026-08-31.md) · V1.36 [`traspaso-relevo-v1-36-daily-operating-ui-2026-08-31.md`](./traspaso-relevo-v1-36-daily-operating-ui-2026-08-31.md).  
> **Estado:** **CERRADO** — proyección canónica + coherencia Mercado/Hoy/Journal/Operaciones.  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push). V1.36 en main sin tag dedicado.

---

## 0. Qué cierra V1.37

Composición (no motor nuevo): `PositionDecision` + `OperationalPlanView` → `OperationalTruth`.

| Pieza                                                                         | Estado          |
| ----------------------------------------------------------------------------- | --------------- |
| `operational-truth.ts` — `buildOperationalTruth`                              | CÓDIGO + vitest |
| `same-operational-truth-across-surfaces.test.ts`                              | CÓDIGO          |
| Hoy inbox / `MesaPositionRow` CTA / Operaciones label ← `decision.action`     | CÓDIGO          |
| `PositionOperatingSummary` = estado (acción, P&L, recon, asOf, no ejecutada)  | CÓDIGO          |
| `OperationalPlanView` `omitLiveMetrics` cuando va apilado                     | CÓDIGO          |
| Journal ficha: plan de posición (truth) si hay posición; si no, plan de study | CÓDIGO          |

**Regla:** `protect_hint` thin ≠ autoridad de acción. Stop operativo ≠ stop broker. Confirm = firma.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/position-decision-copy.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 2. Freeze

Confirm = firma · Spine · ExitPlan / ExitPermission · `PAPER_D_EXECUTE` off · AUTO execute off · sin drag OCO/entry.

## 3. Next (hoja, no implementar aquí)

| Tag   | Nombre                | Notas                                                            |
| ----- | --------------------- | ---------------------------------------------------------------- |
| V1.39 | Position Operating UX | Una CTA primaria alineada a `truth.decision.action`              |
| V1.40 | Exit Management UX    | Ruta visual Entrada → Stop / T1 (proteger) / T2 (trailing)       |
| V1.41 | Daily Desk            | Hoy **quita** paneles; inbox por `attention`. No segundo Mercado |

**V1.38 cerrado:** [`traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md).

Fuera: P2 Lab (`backtest_risk_policy_from_trading_policy` default Moderado) · móvil · push · thaw estricto.
