# RELEVO — Ciclo 8.1 Trail thin (2026-08-25)

> **Padre:** [`roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md`](./roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md) · plan [`plan-ciclo-8-1-trail-thin-2026-08-25.md`](./plan-ciclo-8-1-trail-thin-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD tip:** local (ahead origin). Feat `655832c`. **No push.**
> **Estado:** **CERRADO** — 8.1 Trail thin advisory. Park → **8.2 bracket** · trail **plena** (broker mutate).
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6 + roadmap 8.x.

---

## 1. Qué se cerró

| Pieza   | Qué                                                                                                     |
| ------- | ------------------------------------------------------------------------------------------------------- |
| Mapper  | `mapTrailPlan` / `map_trail_plan` — ratchet peakMfeR−1R; status none/tip/ratchet; hint only · ≠ permiso |
| Propose | `runtime.trailPlan` desde geometry + `mfeMae.mfeR` (peak)                                               |
| Board   | Extract/DTO/session view `trailPlan`                                                                    |
| Hoy     | Bloque «Trail» métricas si status ≠ none (sin CTA)                                                      |
| Batería | spine **155** (+ trail_plan suite)                                                                      |

**Boundary (D1):** trail continuo **con** mutación de `structuralStop` / broker **no** cabe en thin → advisory ratchet. Exit Radar tip @ 1.5R se **alinea** (`lockedR=0.5`), no se duplica.

**Sin** Alembic · **sin** `contract:gen` · **sin** mutar stop · **sin** EvaluatePositionExits · `check_opening` intacto · `PAPER_D_EXECUTE` **off**.

---

## 2. Batería

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **155 passed**
- vitest trail-plan + hoy-queue + hoy-command-strip: OK

---

## 3. Commits

| SHA       | Mensaje                                    |
| --------- | ------------------------------------------ |
| `655832c` | feat(spine): ADR-031 Ciclo 8.1 Trail thin. |
| _(stamp)_ | docs: stamp living SoT after Ciclo 8.1.    |

**No push.**

---

## 4. E1

1. ~~Commit~~ · Push solo si se pide.
2. **Park 8.2** Bracket / T1 parcial.
3. Trail **plena** (broker / mutar stop) solo si se nombra.
4. Expectancy **plena** (journal) solo si se nombra.
5. Thaw AUTO solo con «thaw» + ADR-023. Ops-only: `TRUSTED_PROXIES`.

---

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO **off** · `PAPER_D_EXECUTE` **off** · 5.x + Attribution 6 + I1–I3 + RX1 + 8.0 intactos · trail thin ≠ permiso · 8.2 + trail plena parked.
