# RELEVO — V2.7 Operator Hardening (arm honesty · touch · cert visual) (2026-09-05)

> **Padre:** [relevo V2.6 Pixel Premium](./traspaso-relevo-v2-6-pixel-premium-2026-09-05.md) · tip [`v2.6-beta`](./traspaso-relevo-tag-v2-6-beta-2026-09-05.md) `50abd31d`.  
> **Estado:** **CÓDIGO CERRADO** · V2.39–V2.41 implementados · **sin tip `v2.7-*`** · sin bump package (pendiente pedido explícito).  
> **Para quién:** auditoría operador · **NO MÁS PANELES** · no reabrir motor FSM · no reabrir V2.33–V2.38 salvo regresión display.  
> **Arranque original:** [arranque V2.7 / V2.39](./arranque-agente-v2-7-2026-09-05.md).

## Objetivo

V2.6 cerró Pixel Premium + UI Truth Hoy (display-only).  
V2.7 **no añade funcionalidad de trading** ni paneles. Endurece la semántica operativa que congelaremos hacia LIVE y cierra deuda UX P2 descubierta en el walk:

1. **V2.39** — AUTO arm honesty (misma puerta A3 que Cuentas). ✅
2. **V2.40** — Touch targets cabina (~40px) en controles primarios. ✅
3. **V2.41** — Certificación visual operador (densidad / a11y / e2e). ✅

## Freeze intacto

NO LIVE · package `1.36.0-beta` sin bump hasta tip · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · **AUTO sin controles de trading nuevos** · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos**.

**Excepción explícita V2.39:** no es un control nuevo de trading. Aplica el armado A3 ya existente en Cuentas (`tryArmAuto` + frase `ACTIVAR AUTO`) a AUTO Desk. Arm ≠ Execute. Confirm sigue siendo la única firma de orden.

**Orden escalera:** Entrada → Protección → T1 → T2 → Gestión/trailing → Salida · RESTANTE (no reordenar).

## Entrega (2026-09-05)

| ID        | Entrega                                                                                                                                                                        | Evidencia                                           |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| **V2.39** | `DemoBookAutoArmForm` compartido · AUTO Desk → `tryArmAuto` (sin forjar phrase)                                                                                                | vitest auto-desk + demo-book-mode + auto-arm        |
| **V2.40** | `CABIN_TOUCH_TARGET` en AUTO modes · L1 DECISIÓN · Confirm Intent/Execute                                                                                                      | vitest cabin-visual + position-exit · e2e hit ≥36px |
| **V2.41** | Hoy Posiciones empty honesto · Chart Focus sin gate chartReady · tips ≥32px · DECISIÓN minWidth 260 / default 28% · secciones colapsadas · tabIndex chart tabs · e2e 1024+AUTO | shared daily-desk · mesa-tip · gp-e2e-v25/v26       |

## Pre-flight local (no CI GitHub)

```bash
cd packages/shared && pnpm exec vitest run src/cognitive/daily-desk.test.ts src/cognitive/g-operator-02-golden-journey.test.ts src/cognitive/g-operator-03-protect-journey.test.ts src/cognitive/g-operator-05-ui-truth-v25.test.ts src/cognitive/operator-cabin-view.test.ts
cd apps/web && pnpm exec vitest run src/features/trading/decision-surface-journey.test.tsx src/features/trading/operator-cabin-ui.test.tsx src/features/trading/cabin-visual.test.ts src/features/trading/auto-desk-panel.test.tsx src/features/trading/demo-book-mode-panel.test.tsx src/features/trading/demo-book-auto-arm.test.ts src/features/trading/position-exit-drawer-actions.test.tsx src/features/charts/chart-focus-toggle.test.tsx src/features/help/mesa-tip-button.test.tsx
```

Última corrida: shared **61/61** · web **37/37** PASS. No afirmar CI GitHub GREEN.

## OUT / Next

- Auditoría walk browser (1024 / 1366 / 1920) sobre este commit.
- Tip `v2.7-beta` + bump solo con pedido explícito.
- Seed ops (stop estructural / Journal MFE·MAE) sigue fuera de producto V2.7 — paralelo ops.
