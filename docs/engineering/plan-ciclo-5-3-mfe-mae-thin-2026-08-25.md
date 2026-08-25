# Plan — Ciclo 5.3 MFE/MAE thin (excursion advisory)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 (MFE/MAE / expectancy plena parked; **esta** rebanada abre solo MFE/MAE **advisory thin**) · relevo [`traspaso-relevo-ciclo-5-2-exit-radar-thin-2026-08-25.md`](./traspaso-relevo-ciclo-5-2-exit-radar-thin-2026-08-25.md) §4 E1 · síntesis subagente AS-IS [MFE thin](4fd3a2df-b391-4694-9d57-049838b3140a).
> **AsOf:** 2026-08-25 · HEAD **`0af42c5`** = `origin/main`; feat **`fd44a03`**.
> **Estado:** **CERRADO en origin** (`fd44a03` vía `0af42c5`). D1–D8 OK · batería **135**.
> **Método:** espejo 5.0–5.2; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** expectancy agregada; **sin** mutar stop; **sin** ExecuteTrade converge.
> **Secuencia:** 5.0 F ✅ · 5.1 E ✅ · 5.2 Exit ✅ · **5.3 (este)** · cierre línea 5.x → integridad.

---

## 0. Objetivo

Protect (5.1) y Exit Radar (5.2) usan un **proxy** `rMultiple` = excursion del **lastClose** en R. No hay MAE ni peak MFE desde barras. Attribution plena (expectancy por setup) sigue parked.

**Ciclo 5.3 = advisory metrics:** mapper `mfeMae` con **mfeR + maeR** (peak desde barras si hay; si no, close proxy) → `runtime` / Board / Hoy **línea de métricas** (no CTA). **No** ejecuta, **no** trail tip, **no** expectancy.

### Qué entra vs qué queda fuera

| Incluye (thin 5.3)                                                       | Excluye                                             |
| ------------------------------------------------------------------------ | --------------------------------------------------- |
| Mapper `mapMfeMae` / `map_mfe_mae`: `mfeR`, `maeR`, status display-only  | Expectancy / P&L por setup · series históricas      |
| Peak favorable/adverse desde high/low de barras cargadas; fallback close | Mutar `structuralStop` · trail broker · auto-exit   |
| Eco `runtime.mfeMae` + Board; Hoy **métricas** (no dialog «MFE»)         | Journal MFE plena · Alembic · `contract:gen`        |
| Tests + stamp + relevo 5.3                                               | ExecuteTrade converge · Shadow AUTO · Actionability |

**Frontera:** métricas ≠ permiso. ≠ protect (T1/BE). ≠ exit (trail/time/exit). ≠ journal setup (Ciclo 6).

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                     |
| --- | ------------------------------------------------------------ |
| D1  | Advisory metrics thin (mfeR+maeR)                            |
| D2  | Peak MFE desde barras; else close_proxy                      |
| D3  | Peak MAE / R (≥0)                                            |
| D4  | Bands: adverse mae≥1 · favorable mfe≥1.5 · else observe/none |
| D5  | Hoy línea «Excursión»; no CTA                                |
| D6  | Fill / opening / ExecuteTrade intactos                       |
| D7  | JSONB only; sin Alembic / contract:gen / journal MFE         |
| D8  | Stamp + relevo; E1 = cierre 5.x → ExecuteTrade               |

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.0–5.2 intactos · advisory ≠ permiso · integridad ExecuteTrade **tras** cierre 5.x.
