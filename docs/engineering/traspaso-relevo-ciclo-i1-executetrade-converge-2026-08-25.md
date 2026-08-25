# RELEVO — Ciclo I1 ExecuteTrade converge (integridad post-5.x)

> **Padre:** [`traspaso-relevo-ciclo-5-3-mfe-mae-thin-2026-08-25.md`](./traspaso-relevo-ciclo-5-3-mfe-mae-thin-2026-08-25.md) · honesty [`traspaso-relevo-ciclo-7-spine-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-7-spine-honesty-2026-08-25.md).
> **Plan:** [`plan-ciclo-i1-executetrade-converge-2026-08-25.md`](./plan-ciclo-i1-executetrade-converge-2026-08-25.md) (**BORRADOR — pendiente D1–D8**).
> **AsOf:** 2026-08-25.
> **HEAD tip:** `05e354c` = `origin/main`. Feat 5.3 `fd44a03` · stamp `0af42c5`.
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + ADR-031 §4–6 · Ciclo 7 (mapa 3+1).
> **Fase:** **integridad** (crecimiento 5.0–5.3 **cerrado**).

---

## 0. Contexto para el agente nuevo

**Crecimiento APP 5.x CERRADO** en origin:

| Ciclo | Feat      | Qué                      |
| ----- | --------- | ------------------------ |
| 5.0   | `a2f32bb` | Thesis Health advisory   |
| 5.1   | `12d05d2` | Protect/T1 advisory      |
| 5.2   | `e813aa3` | Exit Radar advisory      |
| 5.3   | `fd44a03` | MFE/MAE metrics (no CTA) |

Batería: `pnpm test:decision-spine` → **135**.

**AS-IS ExecuteTrade (Ciclo 7 honesty):** 3 call-sites spine (`ConfirmRecommendationIntent` · `ExecutionRouter` · `FillPendingOrder`) + 1 HTTP crudo `POST /portfolio/trade` **sin** `check_opening`. Convergencia era **parked M–L**; ahora es **I1**.

## 1. Objetivo de esta fase (borrador)

Unificar / endurecer el camino a ledger paper: el puerto crudo no debe saltarse permiso; spine sites siguen pasando por `check_opening` donde ya aplica.

**No** Shadow AUTO · **no** Actionability/IO server (I2) · **no** broker live · **no** reabrir 5.x / Wyckoff.

## 2. E1 (después de I1)

1. Actionability / Ranking IO server (I2) — si thin.
2. Shadow AUTO — solo decisión explícita (I3).
3. Park: expectancy plena · trail continuo · bracket.
4. Ops-only: `TRUSTED_PROXIES` · secret scanning UI.

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · sin money path live.
