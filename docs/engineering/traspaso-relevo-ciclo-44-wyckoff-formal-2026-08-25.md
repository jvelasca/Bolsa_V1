# RELEVO — Ciclo 4.4 Wyckoff formal (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-43-armed-2026-08-25.md`](./traspaso-relevo-ciclo-43-armed-2026-08-25.md).
> **Plan:** [`plan-ciclo-44-wyckoff-formal-2026-08-25.md`](./plan-ciclo-44-wyckoff-formal-2026-08-25.md) (D1–D7 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** `2135fc5` = `origin/main`. Feat `7003ddf` **PUSHEADO**.
> **Arranque chat nuevo:** pegar este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 1. Qué se cerró (4.0 → 4.4)

| Ciclo | SHA (feat)         | Qué                                                                                                           |
| ----- | ------------------ | ------------------------------------------------------------------------------------------------------------- |
| 4.0   | `1cbd021` (origin) | stop ATR×1.5 + swing lejano · `entry_ready` bias · size equity                                                |
| 4.1   | `97f4862` (origin) | `NO_NEW_LONGS` long + `risk_off`/`crisis` → `BLOCKED`/`regime`                                                |
| 4.2   | `a7eeaee` (origin) | `EntrySetup` breakout/pullback/wyckoff/none · ready = TA **y** setup≠none                                     |
| 4.3   | `4eb99a2` (origin) | `ARMED` = stop + setup≠none + !ready · qty 0 · actionability 0.7                                              |
| 4.4   | `7003ddf` (origin) | Wyckoff formal: spring + reclaim estricto (`k×ATR=0.25` **o** fuera rango spring); SOS etiqueta; LPS diferido |

4.4: prioridad breakout > pullback > wyckoff intacta. Ladder ARMED 4.3 intacta. **Sin** `wyckoffPhase`. **Sin** `contract:gen`. `check_opening` intacto.

## 2. Batería 4.4

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **88 passed** (antes 84)

## 3. Commits (en origin)

| SHA       | Mensaje                                                       |
| --------- | ------------------------------------------------------------- |
| `7003ddf` | feat(spine): ADR-031 Ciclo 4.4 Wyckoff formal spring reclaim. |
| `2135fc5` | docs: stamp living SoT after Ciclo 4.4 (`7003ddf`).           |

Push: `3bef923..2135fc5` → `origin/main`.

## 4. Siguiente (E1) — chat nuevo

1. ~~Commit~~ · ~~Push~~.
2. LPS / SM Wyckoff — **prohibido** sin plan 4.5+.
3. No abrir: F9-B · purge · `PAPER_D_EXECUTE` · broker · thesis health / MFE · qty Confirm · Ciclo 5 PM.

## 5. Freeze / no tocado

LAB ≠ TRADING · LLM no ejecuta · F9-B PARKED · Purge MONITOR · sin `contract:gen`.
