# Plan — Ciclo 8.2 Bracket thin (advisory picture)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · roadmap [`roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md`](./roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md) · relevo [`traspaso-relevo-ciclo-8-1-trail-thin-2026-08-25.md`](./traspaso-relevo-ciclo-8-1-trail-thin-2026-08-25.md) §4 E1.
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería **159**.
> **Método:** espejo 5.1 Protect / 8.0–8.1; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** broker OCO; **sin** ejecución de piernas; **sin** EvaluatePositionExits; **sin** thaw.
> **Elección thin:** bracket **picture advisory** = entry / stop / T1(1R) / T2(2R) + fracciones de pierna display-only. T1 **alinea** Protect 5.1 (`entry±1R`). OCO broker / salida escalonada ejecutada = **fuera** (plena parked).

---

## 0. Objetivo

Protect (5.1) ya emite T1 = entry±1R. Falta la **foto estructural** de bracket (entrada · stop · T1 · T2 opcional · sizing de piernas) sin motor de ejecución.

**Ciclo 8.2 = advisory thin:** `mapBracketPlan` → `runtime.bracketPlan` → Board/Hoy línea «Bracket» (métricas, **≠ permiso** · **hint only** · **display only**).

### Qué entra vs qué queda fuera

| Incluye (thin 8.2)                                                                | Excluye                                                     |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| Mapper `mapBracketPlan` / `map_bracket_plan`: status `none` \| `picture`          | Broker OCO · órdenes bracket · ejecución de piernas T1/T2   |
| T1 = entry±1R (alinea Protect 5.1); T2 = entry±2R; `legT1/T2QtyFrac` display-only | Mutar stop · ExecuteTrade · EvaluatePositionExits           |
| Eco `runtime.bracketPlan` + Board; Hoy **métricas** «Bracket»                     | Trail/expectancy plena · thaw / `PAPER_D_EXECUTE`           |
| Reusar geometry entry/stop del tradePlan                                          | Reopen Wyckoff · fuse Router/Confirm · check_opening change |
| Tests + stamp + relevo 8.2                                                        | `contract:gen` / Alembic                                    |

**Frontera documentada (D1):** true broker bracket / OCO / piernas ejecutadas **no** cabe en thin → se entrega el advisory picture más fuerte que sigue siendo honesto. Bracket broker plena = fase posterior si se nombra.

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                                                                                 |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | Advisory bracket thin: picture puro geometry → `runtime.bracketPlan`. **No** OCO / broker. Boundary: plena = órdenes parked.                                             |
| D2  | Fórmula: R=\|entry−stop\|; T1=entry±1×R; T2=entry±2×R. Fracciones pierna default 0.5 / 0.5 (**display-only**).                                                           |
| D3  | Status: `none` (sin geometry) · `picture` (entry+stop+direction válidos). why: `aligned_protect_t1` + `display_only` + `not_permission` + `hint_only` + `no_broker_oco`. |
| D4  | Inputs: direction / entry / structuralStop. Sin qty broker; sin openQty obligatorio.                                                                                     |
| D5  | Hoy «Bracket» métricas si status≠none; **sin** CTA de ejecución                                                                                                          |
| D6  | Fill / opening / `check_opening` / Router / PAPER_D / Protect 5.1 / Trail 8.1 intactos                                                                                   |
| D7  | JSONB only; sin Alembic / contract:gen                                                                                                                                   |
| D8  | Stamp + relevo; E1 = park expectancy/trail/bracket **plena**; growth thin 8.0–8.2 **cerrada**; push explícito                                                            |

Si D1 incluye OCO / ExecuteTrade, D6 toca opening, o «bracket = permiso»: **parar y replanificar**.

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.x + Attribution 6 + I1–I3 + RX1 + 8.0/8.1 intactos · advisory ≠ permiso · bracket/trail/expectancy plena parked.
