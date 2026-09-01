# RELEVO — V1.64 Browser E2E Integrated (2026-09-02)

> **Padre:** [`spec-v164-browser-e2e-integrated-2026-09-02.md`](./spec-v164-browser-e2e-integrated-2026-09-02.md) · [`plan-v164-browser-e2e-integrated-2026-09-02.md`](./plan-v164-browser-e2e-integrated-2026-09-02.md) · partida **V1.63** (sin tag).  
> **Estado:** **CERRADA** (no tag · no bump package · no LIVE).  
> **Arranque auditor:** [`arranque-auditor-v1-64-browser-e2e-integrated-2026-09-02.md`](./arranque-auditor-v1-64-browser-e2e-integrated-2026-09-02.md).

---

## 0. Qué cierra

| Pieza                                                    | Estado  |
| -------------------------------------------------------- | ------- |
| GP-V164-UI-01 — Journal browser contra API real (opt-in) | DONE    |
| GP-V164-UI-02 — Consola browser contra API real (opt-in) | DONE    |
| GP-V164-UI-03 — Mercado panel/chart (`GP-E2E-03` mock)   | DONE    |
| `e2e/integration.ts` + fixtures Mercado                  | DONE    |
| GP-E2E-01..02 mock                                       | intacto |

V1.63 + V1.59 + V1.58 intactos.

## 1. Pre-flight (local, 2026-09-02)

| Suite                                       | Resultado                              |
| ------------------------------------------- | -------------------------------------- |
| Playwright mock `E2E_RUN=1` (GP-E2E-01..03) | **3** passed · 2 skipped (integración) |
| web V1.63 vitest                            | **28** passed                          |
| pytest V1.59 integration                    | **7** passed                           |
| pytest V1.58 block                          | **13** passed                          |
| tsc `@bolsa/web`                            | OK                                     |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 3. Next

1. **V1.65** LISTA→GRÁFICO→ACCIÓN unificado (parked).
2. CI Playwright en Release-tag (opt-in).
3. **NO LIVE** · DTO HTTP POV · Paper Autonomous Desk.
