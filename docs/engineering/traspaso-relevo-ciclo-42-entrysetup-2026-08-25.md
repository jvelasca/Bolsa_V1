# RELEVO — Ciclo 4.2 `EntrySetup` (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md`](./traspaso-relevo-ciclo-41-no-new-longs-2026-08-25.md).
> **Plan:** [`plan-ciclo-42-entrysetup-2026-08-25.md`](./plan-ciclo-42-entrysetup-2026-08-25.md) (D1–D6 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** `a7eeaee` (local). `origin/main` aún `f646d2a`. **Pendiente push.**
> **Arranque chat nuevo:** pegar este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 1. Qué se cerró (4.0 → 4.2 en origin/local)

| Ciclo | SHA (feat)         | Qué                                                                                           |
| ----- | ------------------ | --------------------------------------------------------------------------------------------- |
| 4.0   | `1cbd021` (origin) | stop ATR×1.5 + swing lejano · `entry_ready` bias · size equity                                |
| 4.1   | `97f4862` (origin) | `NO_NEW_LONGS` long + `risk_off`/`crisis` → `BLOCKED`/`regime`                                |
| 4.2   | `a7eeaee` (local)  | `EntrySetup` breakout/pullback/wyckoff/none · ready = TA **y** setup≠none · JSON `entrySetup` |

4.2: prioridad breakout > pullback > wyckoff. **Sin** `ARMED`. **Sin** `contract:gen`. `check_opening` intacto. Stop/size/régimen intactos.

## 2. Batería 4.2

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **81 passed** (antes 79)

## 3. Commits locales pendientes de push

| SHA       | Mensaje                                                         |
| --------- | --------------------------------------------------------------- |
| `a7eeaee` | feat(spine): ADR-031 Ciclo 4.2 EntrySetup refining entry_ready. |
| (stamp)   | docs post-commit si aplica en este handoff                      |

## 4. Siguiente (E1) — chat nuevo

1. **Push** `a7eeaee` (+ stamp) solo si el propietario lo pide.
2. `ARMED` / Wyckoff formal — **prohibido** sin plan 4.3+.
3. No abrir: F9-B · purge · `PAPER_D_EXECUTE` · broker · thesis health / MFE · qty Confirm.

## 5. Freeze / no tocado

LAB ≠ TRADING · LLM no ejecuta · F9-B PARKED · Purge MONITOR · sin `contract:gen`.
