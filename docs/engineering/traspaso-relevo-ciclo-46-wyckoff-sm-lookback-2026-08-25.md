# RELEVO — Ciclo 4.6 SM Wyckoff lookback (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-45-wyckoff-lps-sm-2026-08-25.md`](./traspaso-relevo-ciclo-45-wyckoff-lps-sm-2026-08-25.md).
> **Plan:** [`plan-ciclo-46-wyckoff-sm-multi-sesion-2026-08-25.md`](./plan-ciclo-46-wyckoff-sm-multi-sesion-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** `dd5b8e8` = `origin/main`. Feat `fb6e801` **PUSHEADO**.
> **Arranque chat nuevo:** pegar este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 1. Qué se cerró (4.0 → 4.6)

| Ciclo | SHA (feat)         | Qué                                                                                        |
| ----- | ------------------ | ------------------------------------------------------------------------------------------ |
| 4.0   | `1cbd021` (origin) | stop ATR×1.5 + swing lejano · `entry_ready` bias · size equity                             |
| 4.1   | `97f4862` (origin) | `NO_NEW_LONGS` long + `risk_off`/`crisis` → `BLOCKED`/`regime`                             |
| 4.2   | `a7eeaee` (origin) | `EntrySetup` breakout/pullback/wyckoff/none · ready = TA **y** setup≠none                  |
| 4.3   | `4eb99a2` (origin) | `ARMED` = stop + setup≠none + !ready · qty 0 · actionability 0.7                           |
| 4.4   | `7003ddf` (origin) | Wyckoff formal: spring + reclaim estricto (`k×ATR=0.25` **o** fuera rango spring); SOS     |
| 4.5   | `baaa9b4` (origin) | LPS etiqueta + SM single-window (`spring→reclaim→sos?→lps?`); sin gate; sin `wyckoffPhase` |
| 4.6   | `fb6e801`          | `_locate_wyckoff_spring` lookback 40; reclaim/SOS/LPS sobre spring vivo; hielo cerrado     |

4.6: `EntrySetup=wyckoff` = spring **localizado** + reclaim 4.4 + hielo intacto (cerradas). LPS/SOS evidencia. Prioridad breakout > pullback > wyckoff intacta. Ladder ARMED 4.3 intacta. **Sin** store/Alembic. **Sin** `wyckoffPhase`. **Sin** `contract:gen`. `check_opening` intacto.

## 2. Batería 4.6

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **94 passed** (antes 92)

## 3. Commits

| SHA       | Mensaje                                             |
| --------- | --------------------------------------------------- |
| `fb6e801` | feat(spine): ADR-031 Ciclo 4.6 SM Wyckoff lookback. |
| `dd5b8e8` | docs: stamp living SoT after Ciclo 4.6 (`fb6e801`). |

Push: `daa5353..` → `origin/main` (incl. update-last).

## 4. Siguiente (E1) — chat nuevo

1. ~~Commit~~ · ~~Push~~.
2. Persistencia fase Wyckoff / thesis binding — **prohibido** sin plan 4.7+.
3. No abrir: F9-B · purge · `PAPER_D_EXECUTE` · broker · thesis health / MFE · qty Confirm · Ciclo 5 PM.

## 5. Freeze / no tocado

LAB ≠ TRADING · LLM no ejecuta · F9-B PARKED · Purge MONITOR · sin `contract:gen`.
