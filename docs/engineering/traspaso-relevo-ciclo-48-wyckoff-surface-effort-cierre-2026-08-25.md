# RELEVO — Ciclo 4.8 Wyckoff surface + effort (cierre SETUP) (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-47-wyckoff-thesis-binding-2026-08-25.md`](./traspaso-relevo-ciclo-47-wyckoff-thesis-binding-2026-08-25.md).
> **Plan:** [`plan-ciclo-48-wyckoff-surface-effort-cierre-2026-08-25.md`](./plan-ciclo-48-wyckoff-surface-effort-cierre-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD:** stamp docs (este commit). Feat `b381d06` **PUSHEADO** con el push.
> **Arranque chat nuevo:** pegar este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 1. Qué se cerró (4.0 → 4.8)

| Ciclo | SHA (feat)         | Qué                                                                                        |
| ----- | ------------------ | ------------------------------------------------------------------------------------------ |
| 4.0   | `1cbd021` (origin) | stop ATR×1.5 + swing lejano · `entry_ready` bias · size equity                             |
| 4.1   | `97f4862` (origin) | `NO_NEW_LONGS` long + `risk_off`/`crisis` → `BLOCKED`/`regime`                             |
| 4.2   | `a7eeaee` (origin) | `EntrySetup` breakout/pullback/wyckoff/none · ready = TA **y** setup≠none                  |
| 4.3   | `4eb99a2` (origin) | `ARMED` = stop + setup≠none + !ready · qty 0 · actionability 0.7                           |
| 4.4   | `7003ddf` (origin) | Wyckoff formal: spring + reclaim estricto (`k×ATR=0.25` **o** fuera rango spring); SOS     |
| 4.5   | `baaa9b4` (origin) | LPS etiqueta + SM single-window (`spring→reclaim→sos?→lps?`); sin gate; sin `wyckoffPhase` |
| 4.6   | `fb6e801` (origin) | `_locate_wyckoff_spring` lookback 40; reclaim/SOS/LPS sobre spring vivo; hielo cerrado     |
| 4.7   | `604fd90` (origin) | `_resolve_wyckoff_spring` + `wyckoffSpringAnchor` en sesión; hielo roto no resucita        |
| 4.8   | `b381d06`          | effort etiqueta en anchor · echo F3 · Hoy Setup · **línea SETUP Wyckoff CERRADA**          |

4.8: `_wyckoff_effort_evidence` (volumen → rango) en `wyckoffSpringAnchor.effort`. Propose echo top-level. Hoy dialog «Setup» (`entrySetup` + fase + effort). `SemiF3View.to_dict` anida `extra` (Board→Hoy ve payload). Classify / ARMED / ready / binding **intactos**. **Sin** Alembic. **Sin** `wyckoffPhase` TradePlan. **Sin** `contract:gen`. `check_opening` intacto.

## 2. Batería 4.8

- ruff touched Python: limpio
- `pnpm test:decision-spine` → **104 passed** (antes 100)
- vitest `@bolsa/shared` hoy-queue + Hoy strip: OK (rebuild shared)

## 3. Commits

| SHA       | Mensaje                                                         |
| --------- | --------------------------------------------------------------- |
| `b381d06` | feat(spine): ADR-031 Ciclo 4.8 Wyckoff surface + effort cierre. |
| _(stamp)_ | docs: stamp living SoT after Ciclo 4.8 (`b381d06`).             |

Push: `7ada26d..` → `origin/main` (incl. update-last).

## 4. Siguiente (E1) — chat nuevo

1. ~~Commit~~ · ~~Push~~.
2. **Línea SETUP Wyckoff 4.0–4.8 cerrada** — no abrir 4.9 Wyckoff / Alembic / `wyckoffPhase` contrato por defecto.
3. Elegir **otro arco** ADR-031 (mesa/attribution/integrity…). **No** Ciclo 5 PM · F9-B · purge · broker · `PAPER_D_EXECUTE` · thesis health / MFE · qty Confirm.

## 5. Freeze / no tocado

LAB ≠ TRADING · LLM no ejecuta · F9-B PARKED · Purge MONITOR · sin `contract:gen` · línea Wyckoff SETUP **cerrada**.
