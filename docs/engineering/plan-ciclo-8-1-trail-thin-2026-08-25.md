# Plan — Ciclo 8.1 Trail thin (advisory continuo)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · roadmap [`roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md`](./roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md) · relevo [`traspaso-relevo-ciclo-8-0-expectancy-thin-2026-08-25.md`](./traspaso-relevo-ciclo-8-0-expectancy-thin-2026-08-25.md) §4 E1.
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · feat `655832c` · batería **155**.
> **Método:** espejo 5.1 Protect / 5.2 Exit Radar / 8.0 Expectancy; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** mutar stop; **sin** broker trail; **sin** EvaluatePositionExits; **sin** thaw.
> **Elección thin:** trail **continuo advisory** = ratchet de `suggestedTrailStop` desde peak MFE (cushion 1R). Exit Radar 5.2 tip @ 1.5R (= entry±0.5R) se **alinea**, no se duplica como segunda tip fija. Mutación broker / `structuralStop` = **fuera** (plena / 8.1 plena parked).

---

## 0. Objetivo

Exit Radar (5.2) ya emite `trail_hint` tip @ MFE≥1.5R. Falta la proyección de **trail continuo** (ratchet al crecer MFE) sin motor de ejecución.

**Ciclo 8.1 = advisory thin:** `mapTrailPlan` → `runtime.trailPlan` → Board/Hoy línea «Trail» (métricas, **≠ permiso** · **hint only**).

### Qué entra vs qué queda fuera

| Incluye (thin 8.1)                                                            | Excluye                                               |
| ----------------------------------------------------------------------------- | ----------------------------------------------------- |
| Mapper `mapTrailPlan` / `map_trail_plan`: status `none` \| `tip` \| `ratchet` | Mutar `structuralStop` · trail broker continuo        |
| `suggestedTrailStop` = entry ± (peakMfeR − 1R)×R cuando peakMfeR ≥ 1.5        | EvaluatePositionExits · auto-exit · ExecuteTrade      |
| Eco `runtime.trailPlan` + Board; Hoy **métricas** «Trail»                     | Bracket / T1 parcial (8.2) · thaw / `PAPER_D_EXECUTE` |
| Reusar geometry + `mfeMae.mfeR` (peak) / fallback currentR                    | Reopen Wyckoff · re-map 5.x · expectancy plena        |
| Tests + stamp + relevo 8.1                                                    | Fuse Router+Confirm                                   |

**Frontera documentada (D1):** continuous trail **con** mutación de stop **no** cabe en thin → se entrega el advisory ratchet más fuerte que sigue siendo honesto. Trail broker plena = fase posterior si se nombra.

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                                                       |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Advisory trail thin: ratchet puro peak-MFE → `runtime.trailPlan`. **No** muta stop / broker. Boundary: plena = mutación parked.                |
| D2  | Fórmula: `lockedR = peakMfeR − 1.0`; `suggestedTrailStop = entry + sign×lockedR×R` si peakMfeR ≥ 1.5. Cushion trail = **1R** desde peak.       |
| D3  | Status: `none` (peak&lt;1.5 o sin geometry) · `tip` (1.5≤peak&lt;2.0, alinea Exit Radar tip) · `ratchet` (peak≥2.0, continuo más allá del tip) |
| D4  | Inputs: direction/entry/stop + `peakMfeR` (prefer `mfeMae.mfeR`) + `currentR` opcional. why incluye `not_permission` + `hint_only`.            |
| D5  | Hoy «Trail» métricas si status≠none; **sin** CTA de ejecución                                                                                  |
| D6  | Fill / opening / `check_opening` / Router / PAPER_D / Exit Radar 5.2 intactos                                                                  |
| D7  | JSONB only; sin Alembic / contract:gen                                                                                                         |
| D8  | Stamp + relevo; E1 = park **8.2 bracket** · trail **plena** (broker mutate); push explícito                                                    |

Si D1 incluye mutar stop / EvaluatePositionExits / auto-exit, D6 toca opening, o «trail = permiso»: **parar y replanificar**.

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.x + Attribution 6 + I1–I3 + RX1 + 8.0 intactos · advisory ≠ permiso · 8.2 parked · trail plena parked.
