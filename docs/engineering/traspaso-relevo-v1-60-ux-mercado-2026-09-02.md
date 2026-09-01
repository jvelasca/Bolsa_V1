# RELEVO — V1.60 UX Mercado (tarjeta estrella DECISIÓN) (2026-09-02)

> **Padre:** [`spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md) · [`plan-v160-ux-mercado-2026-09-02.md`](./plan-v160-ux-mercado-2026-09-02.md) · partida **`v1.59-beta` → `b5c5c6ab`**.  
> **Estado:** **CERRADA** — tag **`v1.60-beta` → `7ac8ad9b`** (no bump package · no LIVE).  
> **Arranque auditor:** [`arranque-auditor-v1-60-ux-mercado-2026-09-02.md`](./arranque-auditor-v1-60-ux-mercado-2026-09-02.md).

---

## 0. Qué cierra

| Pieza                                                                                       | Estado |
| ------------------------------------------------------------------------------------------- | ------ |
| GP-V160-01 — `PositionOperationalStarCard` + `usePositionOperationalView` (POV canónico)    | DONE   |
| GP-V160-02 — `T2_READY` ≠ `T2_EXECUTED` · `RECONCILIATION_DRIFT` copy/fase/recon chip       | DONE   |
| GP-V160-03 — `stopHistory` colapsable (5 orígenes + deltas)                                 | DONE   |
| GP-V160-04 — vitest + `operativa-cockpit-pov-state` · `operativa-cockpit-stop-history`      | DONE   |
| Wire cockpit — star card sobre `PositionOperatingSummary` · fase `Posición · T2 listo` etc. | DONE   |

V1.59 integration **7/7** intacta · V1.58 application block **13** passed · panel DECISIÓN layout F5 intacto (una CTA primaria · Confirm = firma).

## 1. Pre-flight (local, 2026-09-02)

| Suite                                       | Resultado     |
| ------------------------------------------- | ------------- |
| shared vitest POV + operational-context     | **18** passed |
| web vitest phase + cockpit + hook           | **40** passed |
| pytest V1.59 integration (`-m integration`) | **7** passed  |
| pytest V1.58 block (adversarial + INV)      | **13** passed |
| tsc `@bolsa/web`                            | OK            |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta` · sin scheduler · sin Alembic · sin segundo Mercado.

## 3. Next

1. **NO LIVE** · scheduler · package bump · encolar STRUCTURAL_STOP a apertura (LIVE gap) · CI integration job en Release-tag (parked).
2. Thaw Accept (0/5 PASS) · TRUSTED_PROXIES IPs de producción (`BLOCKED_ON_OWNER`).
