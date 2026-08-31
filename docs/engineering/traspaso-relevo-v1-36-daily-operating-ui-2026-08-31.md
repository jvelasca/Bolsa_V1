# RELEVO — V1.36 Daily Operating UI (2026-08-31)

> **Padre:** [`plan-v136-daily-operating-ui-2026-08-31.md`](./plan-v136-daily-operating-ui-2026-08-31.md) · V1.35 [`traspaso-relevo-v1-35-position-operating-hardening-2026-08-31.md`](./traspaso-relevo-v1-35-position-operating-hardening-2026-08-31.md).  
> **Estado:** **CERRADO** — slices 1–3 completos (vitest integración cockpit POSICIÓN).  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push).

---

## 0. Qué abre V1.36

Proyección visual de `PositionDecision` en el cockpit Mercado cuando hay posición abierta.

| Pieza                                                                    | Estado          |
| ------------------------------------------------------------------------ | --------------- |
| `position-decision-copy.ts` — labels + frase humana                      | CÓDIGO + vitest |
| `position-state-from-dto.ts` — wire → `PositionStateV1`                  | CÓDIGO          |
| `PositionOperatingSummary` en `OperativaCockpitCard`                     | CÓDIGO          |
| «Stop operativo» en `OperationalPlanView`                                | CÓDIGO          |
| `PositionOperatingSummary` en Hoy (`PositionRoutePanel`) / Journal ficha | CÓDIGO          |
| CTAs `PositionExitDrawerActions` alineados con `decision.action`         | CÓDIGO          |
| Trailing copy «Stop operativo» en `operativa-cockpit-phase`              | CÓDIGO          |
| Tests integración cockpit POSICIÓN (vitest)                              | CÓDIGO          |

**Semántica:** «Stop operativo registrado» ≠ orden stop de broker. Confirm = firma.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-decision-copy.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/position-exit-drawer-actions.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **congelado**. Solo UI + shared client-side projection.

## 2. Next

**V1.37 — Operational Truth:** [`traspaso-relevo-v1-37-operational-truth-2026-08-31.md`](./traspaso-relevo-v1-37-operational-truth-2026-08-31.md).
