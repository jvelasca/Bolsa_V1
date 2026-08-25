# RELEVO — Ciclo I2 Actionability / Índice Operativo (integridad post-I1)

> **Padre:** [`traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md`](./traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md).
> **Plan:** [`plan-ciclo-i2-actionability-io-2026-08-25.md`](./plan-ciclo-i2-actionability-io-2026-08-25.md) (D1–D8 OK).
> **AsOf:** 2026-08-25.
> **HEAD origin:** `05e354c`. Feat I2 **`e31840d`** (local, no push). Stamp SHA en update-last.
> **Estado:** **CERRADO en `e31840d`.** Integridad parked (I3 Shadow solo explícito).
> **Fase:** **integridad**.
> **Nombre:** no confundir con hub Instrumentos (`instruments-hub-scores.ts`).

---

## 0. Contexto

**I1 CERRADO** (`2bd5cd8`). Actionability TradePlan ya era server (4.3). I2 cierra la **fórmula IO**.

## 1. Qué se cerró (I2)

| Pieza   | Qué                                                                                    |
| ------- | -------------------------------------------------------------------------------------- |
| Fórmula | `compute_indice_operativo` — Composite 0–100 + suelo distress ≤ 40 (paridad TS)        |
| Echo    | `indiceOperativo` en card + chip Composite (`fund_distress` de `build_composite_card`) |
| FE      | `resolveIndiceOperativo` (server preferente; `computeIndiceOperativo` fallback)        |
| Rank    | `rankIndiceOperativo` **sigue cliente**. Sin HTTP de rank. IO ≠ permiso.               |

**Sin** Shadow AUTO · **sin** broker · **sin** Alembic / `contract:gen` · **sin** tocar `check_opening` / I1.

## 2. Batería

- pytest `test_indice_operativo` + `test_composite_score_f3` + `test_get_instrument_composite_f3` → **10 passed**
- vitest operativa-index + hub-scores + fetch-io → **11 passed**
- ruff I2 touched: 0
- `pnpm test:decision-spine` **no** tocada (**144**)

## 3. Commits

| SHA       | Mensaje                                         |
| --------- | ----------------------------------------------- |
| `e31840d` | feat(spine): ADR-031 Ciclo I2 Actionability/IO. |

Stamp docs: este ciclo (SHA en update-last). **No push** salvo decisión explícita.

## 4. E1

1. ~~Feat I2~~ · stamp SHA · push (decisión explícita).
2. Park: Shadow AUTO (**I3, solo si explícito**) · expectancy plena · trail continuo · bracket.
3. Ops-only: `TRUSTED_PROXIES` · secret scanning UI.

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1 intacto.
