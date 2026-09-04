# RELEVO — V2.6 Pixel Premium + UI Truth Hoy (2026-09-05)

> **Padre:** [relevo V2.5 UI Finishing](./traspaso-relevo-v2-5-ui-finishing-2026-09-05.md) · tip [`v2.5-beta`](./traspaso-relevo-tag-v2-5-beta-2026-09-05.md) `df57f0a9`.  
> **Estado:** **CERRADO en código** · tip `v2.6-beta` / bump `1.36.0-beta` **pendiente stamp** (pedido auditoría externa).  
> **Para quién:** tip/stamp · **NO MÁS PANELES** · no reabrir motor FSM · no reabrir V2.33–V2.38 salvo regresión.  
> **Arranque:** [arranque post-V2.38](./arranque-agente-post-v2-38-2026-09-05.md).

## Objetivo

V2.5 cerró Protection honesty + Premium UX + UI Truth birth.  
V2.6 **no añade funcionalidad de trading**. Tres cortes pixel-level:

1. **V2.36** — AUTO timeline visual (= misma escalera que PLAN, no lista plana).
2. **V2.37** — Numbers-first en cabina/AUTO (tokens; menos micro-labels).
3. **V2.38** — UI Truth Hoy↔Mercado (niveles iguales; CTA mesa mapeada, no string identity).

## Freeze intacto (salvo bump autorizado)

NO LIVE · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES** · birth stop = Planificado + MANTENER · Chart Focus / RESTANTE / Protection honesty **intactos**.

**Orden escalera:** Entrada → Protección → T1 → T2 → Gestión/trailing → Salida · RESTANTE (no reordenar TRAILING antes de T2).

## IDs (orden)

| ID        | Entrega                       | Notas                                                                  |
| --------- | ----------------------------- | ---------------------------------------------------------------------- |
| **V2.36** | AUTO timeline = Position Plan | **hecho** · `auto-desk-panel` → `OperatorPositionPlan` · sin controles |
| **V2.37** | Numbers-first cabin/AUTO      | **hecho** · `CABIN_VISUAL_VERSION = v2.37`                             |
| **V2.38** | UI Truth Hoy↔Mercado          | **hecho** · `g-operator-05` + `gp-e2e-v26` mock                        |

## OUT

- Tip `v2.6-beta` + package `1.36.0-beta` (pedido auditoría externa) — stamp pendiente.
- No reabrir V2.28–V2.38 salvo regresión display-only.
- No reabrir motor FSM / PAPER AUTO.
