# RELEVO — Ciclo C4 TradePlan shape canónico (v1.8.1) · 2026-08-25

> **Padre:** [`plan-ciclo-c4-shape-canonical-2026-08-25.md`](./plan-ciclo-c4-shape-canonical-2026-08-25.md) · C5 [`traspaso-relevo-ciclo-c5-metrics-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-c5-metrics-honesty-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO**. E1 = C6 coordinador.
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + `packages/shared/src/cognitive/hoy-queue.ts`.

---

## 0. Qué quedó hecho

| Pieza                                       | Estado                                                                                              |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `readCanonicalTradePlan`                    | sesiones = `session.tradePlan`; F3 = `extra.payload.tradePlan`                                      |
| Fallbacks                                   | `extra.tradePlan` · payload top-level · `tradePlan` en fila F3 — marcados `legacy`, **no** borrados |
| `HoyQueueItem.planSource`                   | `live` si hay objeto TradePlan (canónico o fallback); `projection` si no                            |
| C1                                          | intacto: sin plan → WATCH, nunca BUY/ARMED; `whyNot: legacy_projection`                             |
| C3 / C5                                     | sort ActionQueue y source/sampleQuality **intactos**                                                |
| OpenAPI / `contract:gen` / Pydantic DTO     | **no**                                                                                              |
| Confirm / propose / spine / `check_opening` | **intactos**                                                                                        |
| Tests                                       | payload anidado vivo · legacy fallback vivo · sin plan → projection                                 |

## 1. Freeze / siguiente

- **C6** stamp pack v1.8.1 (coordinador). **No** tag `v1.8.1-beta` ni push sin palabra del dueño.
- C1/C3/C5 intactos. Sin módulos thin nuevos. `PAPER_D_EXECUTE` off · broker **no**.
- Contrato fuerte TradePlan = ADR-032 / v1.9 (docs-only).

## 2. E1

1. Ciclo **C6** (`plan-ciclo-c6-stamp-v181-2026-08-25.md`): pack documental · `pnpm test:decision-spine` · vitest shared · fail-closed `db:push`.
2. No `contract:gen`. No borrar fallbacks legacy.
3. Tag parked.
