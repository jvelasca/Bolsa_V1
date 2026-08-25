# RELEVO — Ciclo C5 MFE/Expectancy honesty (v1.8.1) · 2026-08-25

> **Padre:** [`plan-ciclo-c5-metrics-honesty-2026-08-25.md`](./plan-ciclo-c5-metrics-honesty-2026-08-25.md) · C3 [`traspaso-relevo-ciclo-c3-action-queue-2026-08-25.md`](./traspaso-relevo-ciclo-c3-action-queue-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO**. E1 = C4 shape canónico.
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + `packages/shared/src/cognitive/mfe-mae.ts` + `expectancy.ts`.

---

## 0. Qué quedó hecho

| Pieza                                  | Estado                                                                                  |
| -------------------------------------- | --------------------------------------------------------------------------------------- |
| `MfeMae.source`                        | `bars` \| `close_proxy` \| `none` (TS + Python). `why` intacto. Proxy ≠ peak de barras. |
| UI Excursión                           | sufijo `proxy` si `source === "close_proxy"`                                            |
| Expectancy `sampleQuality`             | n<20 insufficient · 20–49 preliminary · 50–99 developing · 100+ useful                  |
| `status: ready`                        | READY_MIN_N=5 **sigue**; **no** significa estadísticamente útil                         |
| UI Expectativa                         | `muestra insuficiente (n=…)` **antes** de `E ±R` si insufficient. Sigue `≠ permiso`.    |
| Parsers `asMfeMae` / `asExpectancy`    | fail-soft: source inferido de `why`; sampleQuality derivado de `n`                      |
| Journal histórica / mezclar proxy+bars | **no**                                                                                  |

## 1. Freeze / siguiente

- **C4** TradePlan reader canónico (`plan-ciclo-c4-shape-canonical-2026-08-25.md`). **Sin** `contract:gen`.
- C1/C3 ActionQueue **intactos** (no reescribir sort). Sin módulos thin nuevos. `PAPER_D_EXECUTE` off · broker **no**.
- **No** mezclar `close_proxy` y `bars` en agregados futuros.

## 2. E1

1. Ciclo **C4** shape canónico: `readCanonicalTradePlan` + `planSource` live/projection.
2. No journal histórica ni expectancy plena.
3. No C3 HTTP ni reabrir 5.x/8.x mappers.
