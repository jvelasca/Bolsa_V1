# Plan — Ciclo C5 MFE/Expectancy honesty (v1.8.1)

> **Padre:** [`roadmap-v181-operational-consolidation-2026-08-25.md`](./roadmap-v181-operational-consolidation-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO**.
> **Método:** advisory honesty; Ranking ≠ BUY; C1/C3 intactos; sin journal histórica; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Separar MFE de barras vs close_proxy. Mostrar sample-quality de expectancy para no tratar `n=1` como evidencia.

### Qué entra vs qué queda fuera

| Incluye (C5)                                                   | Excluye                   |
| -------------------------------------------------------------- | ------------------------- |
| `MfeMae.source`: `bars` \| `close_proxy` \| `none` (TS+Python) | Journal histórica plena   |
| UI Excursión: sufijo `proxy` si close_proxy                    | Mezclar proxy+bars en agg |
| `sampleQuality` insufficient/preliminary/developing/useful     | `status: ready` = útil    |
| UI: «muestra insuficiente (n=…)» antes de E±R si insufficient  | Trail/bracket/permiso     |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                                                     |
| --- | ---------------------------------------------------------------------------------------------------------------------------- |
| D1  | Campo `source` en MfeMae. `why` se mantiene. Proxy no se presenta como peak de barras.                                       |
| D2  | UI Excursión: sufijo `proxy` si `source === "close_proxy"`.                                                                  |
| D3  | `sampleQuality`: n&lt;20 insufficient · 20–49 preliminary · 50–99 developing · 100+ useful. `ready` ≠ estadísticamente útil. |
| D4  | UI: insufficient → texto muestra **antes** de `E +0.8R`. Sigue `≠ permiso`.                                                  |
| D5  | Advisory ≠ permiso. No journal histórica. Documentar no mezclar proxy y bars.                                                |
| D6  | Tests TS + `test_mfe_mae.py` / `test_expectancy.py` + strip Hoy si hay test.                                                 |
| D7  | `asMfeMae` / `asExpectancy` parsean campos nuevos (fail-soft).                                                               |
| D8  | Relevo C5. E1 = C4.                                                                                                          |

Umbrales n son convención de honestidad, no ciencia cerrada.

---

## 2. Ficheros

- `packages/shared/src/cognitive/mfe-mae.ts` · `expectancy.ts` · `hoy-queue.ts` (parsers)
- `packages/py/analytics/src/bolsa_analytics/cognitive/mfe_mae.py` · `expectancy.py`
- tests analytics + `packages/shared/src/*.test.ts`
- `apps/web/src/features/trading/hoy-command-strip.tsx` (+ test strip si existe)

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · C1/C3 intactos · advisory ≠ permiso · `PAPER_D_EXECUTE` off.
