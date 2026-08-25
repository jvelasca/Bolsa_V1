# Plan — Ciclo I2 Actionability / Índice Operativo (integridad)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §4–6 · relevo [`traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md`](./traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md) · cierre I1 [`traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md`](./traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md).
> **AsOf:** 2026-08-25 · origin **`05e354c`**; feat I2 **`e31840d`** (local, no push).
> **Estado:** **CERRADO en `e31840d`.** D1–D8 OK.
> **Método:** integridad thin; Ranking ≠ BUY; sin Shadow AUTO; sin broker; sin reabrir 5.x / I1.
> **Nombre:** integridad **I2** ≠ hub Instrumentos histórico (`use-instruments-hub-scores.ts`, ya shipped).
> **Secuencia dueño:** I1 ✅ · **I2 (este)** · I3 Shadow (explícito).

---

## 0. Objetivo

**I2 = SoT de la fórmula IO** sin endpoint de rank ni tocar `check_opening`. Actionability TradePlan (0–1) intacta.

### Qué entra vs qué queda fuera

| Incluye (thin I2)                                                       | Excluye                                      |
| ----------------------------------------------------------------------- | -------------------------------------------- |
| Twin Python `compute_indice_operativo` + echo `indiceOperativo` en chip | Segunda Actionability · ranking HTTP Estudio |
| FE `resolveIndiceOperativo` (server preferente; TS fallback)            | Alembic · `contract:gen` · IO en el gate     |
| Tests paridad + stamp + relevo                                          | Shadow · broker · I1 reopen                  |

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                                                                                                                    |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **No** segunda Actionability. TradePlan 0–1 intacto. I2 = fórmula IO 0–100. Ranking ≠ BUY.                                                                  |
| D2  | Rank Estudio **sigue cliente** (`rankIndiceOperativo`). **No** `POST …/rank`.                                                                               |
| D3  | Twin Python + echo `indiceOperativo` en `composite_to_chip` / `CompositeChipDto` (`fund_distress` de `build_composite_card`). FE: `resolveIndiceOperativo`. |
| D4  | IO ≠ permiso. **No** entra en `check_opening` / Confirm / Fill / HTTP gated trade. Spine I1 intacto.                                                        |
| D5  | Sin Alembic. Sin `contract:gen`. Campo opcional a mano (Pydantic + `@bolsa/shared`).                                                                        |
| D6  | Shadow / `PAPER_D_EXECUTE` **off**. Sin broker.                                                                                                             |
| D7  | Pytest fórmula + echo chip. Vitest resolve/hub/fetch-io. Spine battery **no** tocada (144).                                                                 |
| D8  | Stamp + relevo. Honesty ADR freeze. E1 = park I3 Shadow (explícito) · expectancy · trail · bracket. Ops-only `TRUSTED_PROXIES`.                             |

---

## 2. Arranque (hecho)

```text
Implementar Ciclo I2 Actionability/IO según este plan.
D1=no 2ª actionability · D2=rank cliente · D3=fórmula+echo chip · D4=IO≠permiso · D6=Shadow off.
No Shadow · no broker · no reabrir I1/5.x · no LLM · no contract:gen.
```

---

## 3. Commits

| SHA       | Mensaje                                         |
| --------- | ----------------------------------------------- |
| `e31840d` | feat(spine): ADR-031 Ciclo I2 Actionability/IO. |

## 4. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1 `check_opening` intacto.
