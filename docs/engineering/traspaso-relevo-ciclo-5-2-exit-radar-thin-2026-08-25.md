# RELEVO — Ciclo 5.2 Exit Radar thin (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-5-1-protect-t1-thin-2026-08-25.md`](./traspaso-relevo-ciclo-5-1-protect-t1-thin-2026-08-25.md).
> **Plan:** [`plan-ciclo-5-2-exit-radar-thin-2026-08-25.md`](./plan-ciclo-5-2-exit-radar-thin-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** `50004da` = `origin/main`. Feat `e813aa3` **PUSHEADO**.
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + ADR-031 §5–6.

---

## 1. Qué se cerró

| Pieza   | Qué                                                                    |
| ------- | ---------------------------------------------------------------------- |
| Mapper  | `mapExitRadar` / `map_exit_radar` — prioridad exit > time_stop > trail |
| Propose | `runtime.exitRadar` (+ echo) desde thesis/protect/expiresAt            |
| Board   | Extract/DTO/session view `exitRadar`                                   |
| Hoy     | Dialog «Salida» si status ≠ none                                       |
| Batería | spine **130** (+ exit_radar suite)                                     |

**Sin** Alembic · **sin** `contract:gen` · **sin** auto-exit · **sin** EvaluatePositionExits · **sin** mutar stop · `check_opening` intacto.

## 2. Batería

- `pnpm test:decision-spine` → **130 passed**
- vitest exit-radar + hoy-queue + hoy-command-strip: OK

## 3. Commits

| SHA       | Mensaje                                             |
| --------- | --------------------------------------------------- |
| `e813aa3` | feat(spine): ADR-031 Ciclo 5.2 Exit Radar thin.     |
| _(stamp)_ | docs: stamp living SoT after Ciclo 5.2 (`e813aa3`). |

## 4. E1

1. ~~Commit feat~~ · Push + stamp docs.
2. Siguiente: **MFE thin** o cierre línea 5.x → integridad ExecuteTrade.
3. Park: Actionability/IO · Shadow AUTO · trailing continuo / bracket.
4. Ops-only: `TRUSTED_PROXIES` · secret scanning UI.

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.0/5.1 intactos · advisory ≠ permiso · integridad ExecuteTrade **después** del crecimiento 5.x.
