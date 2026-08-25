# Plan — Ciclo I2 Actionability / Índice Operativo (integridad)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §4–6 · relevo [`traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md`](./traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md) · cierre I1 [`traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md`](./traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md).
> **AsOf:** 2026-08-25 · origin **`05e354c`**; feat I1 **`2bd5cd8`** (local, no push).
> **Estado:** **D1–D8 BORRADOR — esperar OK.** Sin código I2.
> **Método:** integridad thin; Ranking ≠ BUY; sin Shadow AUTO; sin broker; sin reabrir 5.x / I1.
> **Nombre:** integridad **I2** ≠ hub Instrumentos histórico (`use-instruments-hub-scores.ts`, ya shipped).
> **Secuencia dueño:** I1 ✅ · **I2 (este)** · I3 Shadow (explícito).

---

## 0. Objetivo

ADR-031 freeze decía «ranking IO puede seguir en cliente hasta Actionability en servidor». Eso ya no describe el AS-IS:

| Señal                     | Qué es                                                             | Dónde                                      |
| ------------------------- | ------------------------------------------------------------------ | ------------------------------------------ |
| **Actionability**         | 0–1, ladder TradePlan (WATCH … ARMED 0.7 … TRIGGERED ~0.95)        | **Ya server** (`trade_plan.py`, Ciclo 4.3) |
| **Índice Operativo (IO)** | 0–100, ranking Estudio: Composite display + suelo distress FA ≤ 40 | **Cliente** (`operativa-index.ts`)         |

I2 **no** inventa un segundo Actionability ni convierte ranking en BUY.

**I2 = SoT de la fórmula IO** (si D1–D8 OK) sin endpoint de rank ni tocar `check_opening`.

### AS-IS (hechos)

- Fórmula: `computeIndiceOperativo` — Composite 0–100, `distress` → `min(io, 40)`. Rank: `rankIndiceOperativo` sobre membresía Estudio (UI).
- Inputs ya vienen de API: `queryInstrumentComposite` + `queryInstrumentFundamentals` (`useInstrumentsHubScores`).
- Consumidores: `trading-operativa-panel.tsx`, `instruments-page.tsx`, `asesor-opiniones-panel.tsx`, `lists-tab/sort-visualizados-by-io.ts` (+ context `list-recommendation-scores-context.tsx`).
- `CompositeChipDto` tiene `scoreDisplay100` / `technicalDisplay100`. **No** `indiceOperativo`. Distress vive en el chip FA, no en Composite.
- `build_composite_card` **ya** calcula `fund_distress` (Beneish / Score_FUND) y no lo expone en `composite_to_chip`.
- Tests fórmula: `operativa-index.test.ts`.

### Qué entra vs qué queda fuera

| Incluye (thin I2, si OK)                                                 | Excluye                                                                      |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Twin Python de la fórmula IO + echo opcional en chip Composite existente | Segunda Actionability · ranking HTTP Estudio                                 |
| Tests paridad TS/Py · DTO a mano                                         | Alembic · `contract:gen` · join FA chip → Composite HTTP                     |
| Docs + honesty ADR freeze                                                | Fusionar FA+Composite en un solo round-trip FE · Shadow · broker · I1 reopen |

**Parar y replanificar si:** D1 mezcla Actionability con IO, D2 pide rank server del universo Estudio, o IO entra en `check_opening`.

---

## 1. Decisiones (D1–D8 — **BORRADOR, esperar OK**)

| Id  | Propuesta (default)                                                                                                                                                                                                                                                                                 |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **No** segunda Actionability. TradePlan 0–1 intacto. I2 = fórmula IO 0–100. Ranking ≠ BUY.                                                                                                                                                                                                          |
| D2  | Rank Estudio **sigue cliente** (`rankIndiceOperativo`). Membresía Estudio = UI. **No** `POST …/rank`.                                                                                                                                                                                               |
| D3  | Twin Python `compute_indice_operativo` + echo `indiceOperativo` en `composite_to_chip` / `CompositeChipDto` usando `fund_distress` **ya** calculado en `build_composite_card`. Sin HTTP nuevo. Sin fusionar el chip FA. FE: preferir campo server si viene; `computeIndiceOperativo` TS = fallback. |
| D4  | IO ≠ permiso. **No** entra en `check_opening` / Confirm / Fill / HTTP gated trade. Spine I1 intacto.                                                                                                                                                                                                |
| D5  | Sin Alembic. Sin `contract:gen`. Campo opcional a mano (Pydantic + `@bolsa/shared` `CompositeChipDto`, espejo 4.9).                                                                                                                                                                                 |
| D6  | Shadow / `PAPER_D_EXECUTE` **off**. Sin broker.                                                                                                                                                                                                                                                     |
| D7  | Pytest fórmula (paridad vitest) + echo chip. Vitest FE si consume el campo. Spine battery **solo** si se toca propose (no debería).                                                                                                                                                                 |
| D8  | Stamp + relevo. Honesty ADR-031 freeze («IO cliente hasta Actionability server» → Actionability ya server; IO ranking cliente hasta echo). E1 = park I3 Shadow (explícito) · expectancy · trail · bracket. Ops-only `TRUSTED_PROXIES`.                                                              |

**Alternativa D3 (si el echo en Composite se ve gordo):** solo twin Python + tests; FE sigue calculando; rank cliente. Decir explícito si preferís esta.

---

## 2. Arranque (tras OK)

```text
Implementar Ciclo I2 Actionability/IO según este plan.
D1=no 2ª actionability · D2=rank cliente · D3=fórmula+echo chip · D4=IO≠permiso · D6=Shadow off.
No Shadow · no broker · no reabrir I1/5.x · no LLM · no contract:gen.
```

---

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1 `check_opening` intacto.
