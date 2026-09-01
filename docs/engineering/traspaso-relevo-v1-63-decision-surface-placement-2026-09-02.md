# RELEVO — V1.63 Decision Surface Placement (2026-09-02)

> **Padre:** [`spec-v163-decision-surface-placement-2026-09-02.md`](./spec-v163-decision-surface-placement-2026-09-02.md) · [`plan-v163-decision-surface-placement-2026-09-02.md`](./plan-v163-decision-surface-placement-2026-09-02.md) · partida **V1.62** (sin tag).  
> **Estado:** **CERRADA** (no tag · no bump package · no LIVE).  
> **Arranque auditor:** [`arranque-auditor-v1-63-decision-surface-placement-2026-09-02.md`](./arranque-auditor-v1-63-decision-surface-placement-2026-09-02.md).

---

## 0. Qué cierra

| Pieza                                                                 | Estado |
| --------------------------------------------------------------------- | ------ |
| GP-V163-01 — pref `bolsa-mercado-decision-surface-v1` default `panel` | DONE   |
| GP-V163-02 — modo panel sin regresión V1.61/V1.62                     | DONE   |
| GP-V163-03 — modo chart: hint panel; sin duplicar superficie          | DONE   |
| GP-V163-04 — `ChartDecisionSurfaceHud` en gráfico                     | DONE   |
| GP-V163-05 — ACCIÓN CTA en ambos modos                                | DONE   |
| GP-V163-06 — toggle cockpit + config Mercado sincronizados            | DONE   |

V1.62 + V1.61 + V1.59 + V1.58 intactos.

## 1. Pre-flight (local, 2026-09-02)

| Suite                                    | Resultado     |
| ---------------------------------------- | ------------- |
| web V1.63 vitest (prefs + cockpit + hud) | **28** passed |
| shared entry cross-surface               | **10** passed |
| pytest V1.59 integration                 | **7** passed  |
| pytest V1.58 block                       | **13** passed |
| tsc `@bolsa/web`                         | OK            |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 3. Next

1. **V1.64** Browser E2E integrado — [`spec-v164`](./spec-v164-browser-e2e-integrated-2026-09-02.md).
2. LISTA→GRÁFICO→ACCIÓN unificado (parked).
3. **NO LIVE** · DTO HTTP POV · Paper Autonomous Desk.
