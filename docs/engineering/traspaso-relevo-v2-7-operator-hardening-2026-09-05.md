# RELEVO — V2.7 Operator Hardening (arm honesty · touch · cert visual) (2026-09-05)

> **Padre:** [relevo V2.6 Pixel Premium](./traspaso-relevo-v2-6-pixel-premium-2026-09-05.md) · tip [`v2.6-beta`](./traspaso-relevo-tag-v2-6-beta-2026-09-05.md) `50abd31d`.  
> **Estado:** **CERRADO** · tip [`v2.7-beta`](./traspaso-relevo-tag-v2-7-beta-2026-09-05.md) · package `1.37.0-beta`.  
> **Para quién:** auditoría operador · **NO MÁS PANELES** · no reabrir motor FSM · no reabrir V2.33–V2.41 salvo regresión display.  
> **Arranque original:** [arranque V2.7 / V2.39](./arranque-agente-v2-7-2026-09-05.md) · **post-tip:** [arranque post-V2.41](./arranque-agente-post-v2-41-2026-09-05.md).

## Objetivo

V2.6 cerró Pixel Premium + UI Truth Hoy (display-only).  
V2.7 **no añade funcionalidad de trading** ni paneles. Endurece la semántica operativa hacia LIVE y cierra deuda UX P2 del walk:

1. **V2.39** — AUTO arm honesty (misma puerta A3 que Cuentas). ✅
2. **V2.40** — Touch targets cabina (~40px) en controles primarios. ✅
3. **V2.41** — Certificación visual operador (densidad / a11y / e2e). ✅

## Freeze intacto

NO LIVE · package `1.37.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · **AUTO sin controles de trading nuevos** · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos**.

**Excepción V2.39:** armado A3 existente (`tryArmAuto` + `ACTIVAR AUTO`) en AUTO Desk. Arm ≠ Execute. Confirm = única firma.

**Orden escalera:** Entrada → Protección → T1 → T2 → Gestión/trailing → Salida · RESTANTE (no reordenar).

## Entrega

| ID        | Entrega                                                               | Evidencia                                    |
| --------- | --------------------------------------------------------------------- | -------------------------------------------- |
| **V2.39** | `DemoBookAutoArmForm` · AUTO Desk → `tryArmAuto`                      | vitest auto-desk + demo-book-mode + auto-arm |
| **V2.40** | `CABIN_TOUCH_TARGET` AUTO · L1 · Confirm                              | vitest + e2e hit ≥36px                       |
| **V2.41** | Hoy empty honesty · Chart Focus @1024 · tips · densidad · focus · e2e | daily-desk · mesa-tip · gp-e2e-v25/v26       |

## Pre-flight local (no CI GitHub)

shared **61/61** · web **37/37** PASS. No afirmar CI GitHub GREEN sin status checks del SHA tip.

## OUT / Next

- Tip [`v2.7-beta`](./traspaso-relevo-tag-v2-7-beta-2026-09-05.md) + bump `1.37.0-beta` — stamp en relevo tag.
- Seed ops (stop estructural / Journal MFE·MAE) paralelo.
- No reabrir motor FSM / PAPER AUTO execute.
