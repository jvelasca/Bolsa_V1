# RELEVO — V2.4 Cabin Coherence (2026-09-04)

> **Padre:** [relevo V2.3 Mercado Polish](./traspaso-relevo-v2-3-mercado-polish-2026-09-04.md) · tip producto [`v2.1-beta`](./traspaso-relevo-tag-v2-1-beta-2026-09-04.md) `5f095d67`.  
> **Estado:** **CERRADO en código** · tip [`v2.4-beta`](./traspaso-relevo-tag-v2-4-beta-2026-09-04.md) → [`8fda4d62`](https://github.com/jvelasca/Bolsa_V1/commit/8fda4d62) · ops smoke 10 s paralelo.  
> **Para quién:** ops · no reabrir motor FSM ni paneles.  
> **Arranque:** [arranque post-V2.32](./arranque-agente-post-v2-32-2026-09-04.md).

## Objetivo

V2.26 cerró la cabina de 4 niveles + Operating Truth. V2.27 cerró Journal spine + MFE/MAE.  
V2.4 **no añade paneles**. Une superficies duplicadas, aclara PLAN vs EJECUCIÓN, reduce jerga, mejora jerarquía visual y certifica el journey completo.

## Freeze intacto

NO LIVE · no bump `1.35.0-beta` · `PAPER_D_EXECUTE` default off · no `TRANSITIONS` · no segundo FSM · Confirm = firma · Ranking ≠ BUY · chrome DECISIÓN (ADR-042) · 5 puertas L1 (ADR-040) · ExitPolicy **30/30** · HOY strip congelado · AUTO sin controles nuevos en esta rama · `OperatorDecision` = proyección shared.

**Regla dura:** NO MÁS PANELES en Mercado. Subordinar / fusionar / colapsar.

## IDs (orden)

| ID        | Entrega                   | Notas                                                                                                 |
| --------- | ------------------------- | ----------------------------------------------------------------------------------------------------- |
| **V2.28** | PLAN DE POSICIÓN          | **hecho** · Mission + Exit Route → `OperatorPositionPlan`                                             |
| **V2.29** | Protection State          | **hecho** · Planificado / Confirmado / Enviado / Protegido · sin «propuesta thin»                     |
| **V2.30** | Chart Focus               | **hecho** · Simple / Completo · T1 alcanzado discreto                                                 |
| **V2.31** | Premium Visual System     | **hecho** · 3 tamaños · números tabulares · menos 10px/cards                                          |
| **V2.32** | Golden Operator Journey 2 | **hecho** · ESTUDIO→EXIT contractual en Mercado · Gráfico · NEXT · Risk · Plan · AUTO · Hoy · Journal |

**Paralelo (no ID de producto):** [V2.3-ops](./traspaso-relevo-v2-3-mercado-polish-2026-09-04.md) smoke browser 10 s.

## V2.32 — cerrado (certificación)

- `buildOperatorJourney2Surfaces` · `operatorJourney2LevelsEqual` en `operator-cabin-view.ts`.
- Golden `g-operator-02` ampliado: cadena ESTUDIO→…→EXIT con mismo stop / T1 / T2 / remaining / next action.
- AUTO preview honra `closed` → remaining 0 (alineado con `OperatorDecision`).
- Journal thin POT: `remainingQuantity` en `operatorCabinTruthFromPot`.
- Stamp `data-operator-journey="v2.32"` en journey HUD Mercado + Journal summary.
- Tests web: `decision-surface-journey` · chart levels · `position-operating-summary`.

## OUT / tip

- Tip [`v2.4-beta`](./traspaso-relevo-tag-v2-4-beta-2026-09-04.md) → [`8fda4d62`](https://github.com/jvelasca/Bolsa_V1/commit/8fda4d62) **hecho**.
- Ops smoke browser 10 s (**V2.3-ops**, paralelo).
- No reabrir Journal / PLAN DE POSICIÓN / Protection State / Chart Focus / Premium Visual System / Journey 2 salvo regresión.
- No reabrir motor FSM / Operating Truth builders salvo proyección display.
