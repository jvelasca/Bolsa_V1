# RELEVO — Ciclo 8.0 Expectancy thin (2026-08-25)

> **Padre:** [`roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md`](./roadmap-ciclo-8-crecimiento-expectancy-trail-bracket-2026-08-25.md) · plan [`plan-ciclo-8-0-expectancy-thin-2026-08-25.md`](./plan-ciclo-8-0-expectancy-thin-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD tip:** local (ahead origin). Feat `cf880eb` · stamp `827132c`. **No push.**
> **Estado:** **CERRADO** — 8.0 Expectancy thin. Park → **8.1 trail** · **8.2 bracket**.
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6 + roadmap 8.x.

---

## 1. Qué se cerró

| Pieza   | Qué                                                                                       |
| ------- | ----------------------------------------------------------------------------------------- |
| Mapper  | `mapExpectancy` / `map_expectancy` — media R por setup; status none/thin/ready; ≠ permiso |
| Propose | `runtime.expectancy` live proxy (`entrySetup` + `mfeMae.currentR`)                        |
| Board   | Extract/DTO/session view `expectancy`                                                     |
| Hoy     | Bloque «Expectativa» métricas si status ≠ none (sin CTA)                                  |
| Batería | spine **149** (+ expectancy suite)                                                        |

**Sin** Alembic · **sin** `contract:gen` · **sin** journal histórica · **sin** trail/bracket · `check_opening` intacto · `PAPER_D_EXECUTE` **off**.

**Elección thin documentada:** agregador puro listo para N samples; propose alimenta 1 sample live (honest `thin`). Expectancy plena = journal scan posterior.

---

## 2. Batería

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **149 passed**
- vitest expectancy + hoy-queue + hoy-command-strip: OK

---

## 3. Commits

| SHA       | Mensaje                                             |
| --------- | --------------------------------------------------- |
| `cf880eb` | feat(spine): ADR-031 Ciclo 8.0 Expectancy thin.     |
| `827132c` | docs: stamp living SoT after Ciclo 8.0 (`cf880eb`). |

**No push.**

---

## 4. E1

1. ~~Commit~~ · Push solo si se pide.
2. **Park 8.1** Trail continuo · **8.2** Bracket / T1 parcial.
3. Expectancy **plena** (journal aggregate) solo si se nombra (mapper ya acepta N).
4. Thaw AUTO solo con «thaw» + ADR-023. Ops-only: `TRUSTED_PROXIES`.

---

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO **off** · `PAPER_D_EXECUTE` **off** · 5.x + Attribution 6 + I1–I3 + RX1 intactos · expectancy thin ≠ permiso · 8.1/8.2 parked.
