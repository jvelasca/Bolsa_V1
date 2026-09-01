# RELEVO — V1.61 Market Decision Surface (posición) (2026-09-02)

> **Padre:** [`spec-v161-market-decision-surface-2026-09-02.md`](./spec-v161-market-decision-surface-2026-09-02.md) · [`plan-v161-market-decision-surface-2026-09-02.md`](./plan-v161-market-decision-surface-2026-09-02.md) · partida **`v1.60-beta` → `7ac8ad9b`**.  
> **Estado:** **CERRADA** (no tag · no bump package · no LIVE).  
> **Arranque auditor:** [`arranque-auditor-v1-61-market-decision-surface-2026-09-02.md`](./arranque-auditor-v1-61-market-decision-surface-2026-09-02.md).

---

## 0. Qué cierra

| Pieza                                                                          | Estado |
| ------------------------------------------------------------------------------ | ------ |
| GP-V161-01 — `mapPortfolioReconToPovRecon` fail-closed (unknown → unavailable) | DONE   |
| GP-V161-02 — tono visual `data-tone` según `operatingState`                    | DONE   |
| GP-V161-03 — una Decision Surface (sin StarCard + Summary apilados)            | DONE   |
| GP-V161-04 — Primary Action Honesty (ninguna → COMPRAR)                        | DONE   |
| GP-V161-05 — copy DECISIÓN vs EJECUCIÓN                                        | DONE   |
| GP-V161-06 — cross-surface POV facts (builders)                                | DONE   |
| Hook `{ view, source }` + aviso DEV fallback                                   | DONE   |
| GP-V160-01..04 — compat testids POV / stop history                             | DONE   |

V1.59 integration **7/7** intacta · V1.58 application block **13** passed · panel DECISIÓN layout F5 intacto (una CTA primaria · Confirm = firma).

## 1. Pre-flight (local, 2026-09-02)

| Suite                                                   | Resultado     |
| ------------------------------------------------------- | ------------- |
| shared vitest POV + operational-context + cross-surface | **26** passed |
| web vitest phase + cockpit + hook + decision-surface    | **51** passed |
| pytest V1.59 integration (`-m integration`)             | **7** passed  |
| pytest V1.58 block (adversarial + INV)                  | **13** passed |
| tsc `@bolsa/web`                                        | OK            |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta` · sin scheduler · sin Alembic · sin segundo Mercado.

## 3. Next

1. **V1.63** Browser E2E → FastAPI → PostgreSQL (journeys UI-01..03).
2. Mercado LISTA→GRÁFICO→ACCIÓN unificado (parked).
3. **NO LIVE** · scheduler · package bump · DTO HTTP POV Python.
