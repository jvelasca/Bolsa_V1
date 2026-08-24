# RELEVO — Ciclo 4.3 `ARMED` (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-42-entrysetup-2026-08-25.md`](./traspaso-relevo-ciclo-42-entrysetup-2026-08-25.md).
> **Plan:** [`plan-ciclo-43-armed-entrysetup-2026-08-25.md`](./plan-ciclo-43-armed-entrysetup-2026-08-25.md) (D1–D7 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** `f02429b` (ahead of origin). Feat `4eb99a2` · stamp `f02429b`.
> **Arranque chat nuevo:** pegar este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 1. Qué se cerró (4.0 → 4.3)

| Ciclo | SHA (feat)         | Qué                                                                                           |
| ----- | ------------------ | --------------------------------------------------------------------------------------------- |
| 4.0   | `1cbd021` (origin) | stop ATR×1.5 + swing lejano · `entry_ready` bias · size equity                                |
| 4.1   | `97f4862` (origin) | `NO_NEW_LONGS` long + `risk_off`/`crisis` → `BLOCKED`/`regime`                                |
| 4.2   | `a7eeaee` (origin) | `EntrySetup` breakout/pullback/wyckoff/none · ready = TA **y** setup≠none · JSON `entrySetup` |
| 4.3   | `4eb99a2` (local)  | `ARMED` = stop + setup≠none + !ready · qty 0 · `whyNot: entry` · actionability 0.7            |

4.3: ladder `WATCH` → `ARMED` → `TRIGGERED`. Wyckoff **stub** 4.2. **Sin** fases formales. **Sin** `contract:gen`. `check_opening` intacto. Stop/size/régimen/EntrySetup priority intactos.

## 2. Batería 4.3

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **84 passed** (antes 81)

## 3. Commits

| SHA       | Mensaje                                                |
| --------- | ------------------------------------------------------ |
| `4eb99a2` | feat(spine): ADR-031 Ciclo 4.3 ARMED readiness ladder. |
| `f02429b` | docs: stamp living SoT after Ciclo 4.3 (`4eb99a2`).    |

## 4. Siguiente (E1) — chat nuevo

1. ~~Commit feat~~ · ~~stamp docs~~ · Push.
2. Wyckoff formal — **prohibido** sin plan 4.4+.
3. No abrir: F9-B · purge · `PAPER_D_EXECUTE` · broker · thesis health / MFE · qty Confirm.

## 5. Freeze / no tocado

LAB ≠ TRADING · LLM no ejecuta · F9-B PARKED · Purge MONITOR · sin `contract:gen`.
