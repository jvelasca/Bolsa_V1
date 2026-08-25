# Plan — Ciclo 8.0 Expectancy thin (advisory)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · roadmap [`roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md`](./roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md) · relevo integridad E1.4.
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · feat `cf880eb` · batería **149**.
> **Método:** espejo 5.3 / Ciclo 6; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** trail/bracket; **sin** journal histórica plena; **sin** thaw.
> **Elección thin:** agregado puro setup+R (media R = expectancy clásica en R) sobre samples; propose alimenta **live proxy** (1 sample: `entrySetup` + `mfeMae.currentR`). El mismo mapper servirá expectancy plena cuando haya N samples de journal.

---

## 0. Objetivo

Attribution (6) y MFE/MAE (5.3) existen; no hay superficie de **expectancy** por setup. «Expectancy plena» = agregado histórico journal/fills — **fuera** de 8.0.

**Ciclo 8.0 = advisory thin:** `mapExpectancy` → `runtime.expectancy` → Board/Hoy línea «Expectativa» (métricas, **≠ permiso**). Propose usa live proxy (n=1 → status `thin`).

### Qué entra vs qué queda fuera

| Incluye (thin 8.0)                                                       | Excluye                                           |
| ------------------------------------------------------------------------ | ------------------------------------------------- |
| Mapper `mapExpectancy` / `map_expectancy`: n · expectancyR · winRate · … | Trail continuo (8.1) · bracket (8.2)              |
| Focus por `entrySetup`; live sample desde MFE `currentR`                 | Scan journal histórico · Alembic · `contract:gen` |
| Eco runtime + Board; Hoy **métricas** «Expectativa»                      | Auto-exit · mutar stop · ExecuteTrade · thaw      |
| Tests + stamp + relevo 8.0                                               | Reopen Wyckoff / re-map 5.0–5.3                   |

**Frontera:** expectancy ≠ permiso. ≠ Excursión (5.3). ≠ Protect/Exit. ≠ Attribution plena.

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------- |
| D1  | Advisory expectancy thin: agregador puro samples `{entrySetup, rMultiple}` → `runtime.expectancy`              |
| D2  | `expectancyR` = media de R (= winRate×avgWin − lossRate×\|avgLoss\|); exponer winRate / avgWinR / avgLossR / n |
| D3  | Focus `entrySetup` (Attribution); sample live = setup + `mfeMae.currentR` cuando ambos existen                 |
| D4  | Status: `none` (sin samples) · `thin` (1≤n\<5) · `ready` (n≥5, sigue advisory ≠ plena) · why `not_permission`  |
| D5  | Hoy «Expectativa» métricas si status≠none; sin CTA de ejecución                                                |
| D6  | Fill / opening / `check_opening` / Router / PAPER_D intactos                                                   |
| D7  | JSONB only; sin Alembic / contract:gen / journal scan                                                          |
| D8  | Stamp + relevo; E1 = park **8.1 trail** · **8.2 bracket**; push explícito                                      |

Si D1 incluye trail/bracket, D3 = Alembic, D4 = `contract:gen`, D6 toca opening, o «expectancy = permiso»: **parar y replanificar**.

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.x + Attribution 6 + I1–I3 + RX1 intactos · advisory ≠ permiso · 8.1/8.2 parked.
