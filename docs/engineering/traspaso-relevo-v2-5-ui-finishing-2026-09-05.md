# RELEVO — V2.5 UI Finishing + Protection honesty (2026-09-05)

> **Padre:** [relevo V2.4 Cabin Coherence](./traspaso-relevo-v2-4-cabin-coherence-2026-09-04.md) · tip producto [`v2.4-beta`](./traspaso-relevo-tag-v2-4-beta-2026-09-04.md) `8fda4d62`.  
> **Estado:** **CERRADO en código** (working tree) · tip `v2.5-beta` **no stampado** · sin bump `1.35.0-beta`.  
> **Para quién:** ops · commit/tip solo con pedido explícito · **NO MÁS PANELES** · no reabrir motor FSM.  
> **Arranque:** [arranque post-V2.35](./arranque-agente-post-v2-35-2026-09-05.md).

## Objetivo

V2.4 cerró Cabin Coherence. V2.5 **no añade funcionalidad de trading**.

Tres cortes:

1. **V2.33** — Protection honesty al nacer (falso positivo OPEN_UNPROTECTED / −5 % / PROTECT_REQUIRED).
2. **V2.34** — Premium UX (tipografía, touch, RESTANTE, Gestión, chart contextual, Journal MFE/MAE).
3. **V2.35** — Certificación UI Truth (golden + e2e mock viewports/touch).

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos · `OperatorDecision` = proyección shared · **NO MÁS PANELES**.

**Semántica V2.33 (opción B):** nacimiento con stop firmado → operatingState `PROTECTED` · Protection phase **Planificado** · NEXT **MANTENER**. `−5 %` / bootstrap solo si no hay `currentStop` ni `initialStop`. Protegido técnico solo tras revisión protect/trail (o trail activo).

## IDs (orden)

| ID        | Entrega                     | Notas                                                                 |
| --------- | --------------------------- | --------------------------------------------------------------------- |
| **V2.33** | Protection honesty al nacer | **hecho** · TS + Py application + analytics · cabin Planificado       |
| **V2.34** | Premium UX finishing        | **hecho** · cabin v2.34 · Chart Focus ~40px · RESTANTE · Journal cols |
| **V2.35** | UI Truth + responsive/touch | **hecho** · `g-operator-05` · e2e mock `gp-e2e-v25`                   |

## V2.33 — cerrado

- `resolvePositionOperatingState` mira `currentStop` / `initialStop` → `PROTECTED`.
- Retirado puente nacimiento → `PROTECT_REQUIRED`.
- `resolveBootstrapProtectStop` solo floor −5 % (no prefiere `initialStop`).
- Cabina: birth stop ≠ ejecutado; `hasProtectRevision` / `hasTrailRevision`.
- G-OPERATOR-03 reescrito: planned → MANTENER · Planificado.

## V2.34 — cerrado

- Tokens hero ~24px / operativa ~15px / meta ~12px · `CABIN_VISUAL_VERSION = v2.34`.
- `ChartFocusToggle` min-h-10 · `ChartPlanContextStrip` (cero paneles).
- RESTANTE hero · Gestión copy explícita · Journal Final/MFE/MAE.

## V2.35 — cerrado

- `g-operator-05-ui-truth-v25.test.ts` — birth Planificado + superficies iguales.
- `gp-e2e-v25-ui-truth-mock.spec.ts` — viewports 1920 / 1366 / 1024 + hit area Chart Focus.
- `doesStopWorsen` LONG/SHORT parity (TS).

## OUT / tip

- Tip `v2.5-beta` — **pendiente** (solo si se pide).
- Commit working tree — **pendiente** (solo si se pide).
- **Reiniciar API Python** para que el wire deje de emitir `PROTECT_REQUIRED` en fills sanos (frontend ya reconstruye; wire antiguo puede quedar en proceso).
- Ops smoke browser 10 s (**V2.3-ops**, paralelo) — sigue pendiente.
- No reabrir V2.28–V2.35 salvo regresión display-only.
- No reabrir motor FSM / PAPER AUTO.
