# Plan — V1.63 Decision Surface Placement

> **Padre:** [`spec-v163-decision-surface-placement-2026-09-02.md`](./spec-v163-decision-surface-placement-2026-09-02.md).  
> **Estado:** **CERRADA**.

| ID  | Entrega                                 | Estado |
| --- | --------------------------------------- | ------ |
| D0  | spec/plan V1.63                         | DONE   |
| P0  | prefs + hook + UI_PREFS doc             | DONE   |
| P0  | DecisionSurfaceCompact + refactor cards | DONE   |
| P0  | ChartDecisionSurfaceHud + wire chart    | DONE   |
| P0  | toggle cockpit + hint chart mode        | DONE   |
| P1  | sección Mercado en configuración        | DONE   |
| P1  | GP-V163-01..06 tests                    | DONE   |
| R1  | pre-flight + relevo                     | DONE   |

## Orden

1. `mercado-decision-surface-prefs.ts` + `useMercadoDecisionSurfacePrefs`
2. `decision-surface-compact.tsx` — refactor entry/position cards
3. `chart-decision-surface-hud.tsx` + `ohlcv-chart` / `chart-workspace-page`
4. `operativa-cockpit-card` toggle + hint
5. `general-settings-section` card Mercado
6. Tests + relevo
