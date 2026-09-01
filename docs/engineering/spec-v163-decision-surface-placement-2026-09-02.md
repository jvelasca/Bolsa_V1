# Spec — V1.63 Decision Surface Placement (panel vs gráfico)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v162-entry-decision-surface-2026-09-02.md`](./spec-v162-entry-decision-surface-2026-09-02.md) · tip certificado previo **V1.62**. **No** LIVE.

El usuario elige dónde ver el **estado operativo** (entrada V1.62 + posición V1.61): panel DECISIÓN completo o HUD compacto en el gráfico.

```text
P0  GP-V163-01 — pref localStorage `bolsa-mercado-decision-surface-v1` (default panel)
P0  GP-V163-02 — panel: superficies visibles; hint oculto
P0  GP-V163-03 — chart: hint en panel; sin duplicar superficie en ESTADO
P0  GP-V163-04 — chart: `chart-decision-surface-hud` con fixture entrada/posición
P1  GP-V163-05 — ACCIÓN CTA en ambos modos; sin COMPRAR
P1  GP-V163-06 — toggle cockpit y config plataforma comparten pref
```

## 0. Freeze

Igual V1.62: Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · **solo UI Mercado**.

## 1. IN

| ID         | Comportamiento                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------- |
| GP-V163-01 | `{ placement: "panel" \| "chart" }` default `panel`                                                   |
| GP-V163-02 | `panel`: `entry-decision-surface` / `position-operational-star-card` en ESTADO                        |
| GP-V163-03 | `chart`: hint «Estado operativo en el gráfico · ACCIÓN sigue aquí»; sin cards en ESTADO               |
| GP-V163-04 | HUD flotante top-left en `ohlcv-chart` gated por `showOperationalPlanLevels && placement === "chart"` |
| GP-V163-05 | CTA primaria en `decision-accion` en ambos modos                                                      |
| GP-V163-06 | `DecisionSurfacePlacementToggle` en cockpit + card Mercado en configuración                           |

**Siempre en panel:** CONTEXTO · ACCIÓN · ¿Por qué? — HUD display-only.

## 2. OUT

Arrastrar niveles desde HUD · sync cross-device · LISTA→GRÁFICO→ACCIÓN · Browser E2E.

## 3. Pre-flight

```bash
pnpm --filter @bolsa/web exec vitest run src/features/trading/mercado-decision-surface-prefs.test.ts src/features/trading/operativa-cockpit-card.test.tsx src/features/charts/chart-decision-surface-hud.test.tsx
pnpm --filter @bolsa/shared exec vitest run src/cognitive/entry-operating-truth.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_inv_operational_truth.py -q
pnpm --filter @bolsa/web exec tsc --noEmit
```
