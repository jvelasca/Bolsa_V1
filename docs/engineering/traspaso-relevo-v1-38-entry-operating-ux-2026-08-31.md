# RELEVO — V1.38 Entry Operating UX (2026-08-31)

> **Padre:** [`plan-v138-entry-operating-ux-2026-08-31.md`](./plan-v138-entry-operating-ux-2026-08-31.md) · V1.37 [`traspaso-relevo-v1-37-operational-truth-2026-08-31.md`](./traspaso-relevo-v1-37-operational-truth-2026-08-31.md).  
> **Estado:** **CERRADO** — proyección canónica entrada + coherencia Mercado/Hoy/Journal.  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push).

---

## 0. Qué cierra V1.38

Composición (no motor nuevo): fase cockpit + `OperationalPlanView` + sizing study → `EntryOperatingTruth`.

| Pieza                                                            | Estado          |
| ---------------------------------------------------------------- | --------------- |
| `entry-operating-truth.ts` — `buildEntryOperatingTruth`          | CÓDIGO + vitest |
| `mercado-cockpit-phase.ts` movido a shared                       | CÓDIGO          |
| `same-entry-operating-truth-across-surfaces.test.ts`             | CÓDIGO          |
| CTAs: Preparar operación / Revisar y confirmar / Ver operaciones | CÓDIGO          |
| `EntryOperatingSummary` en cockpit + Journal                     | CÓDIGO          |
| Hoy candidatos ← `mapCandidateNextAction` → entry truth          | CÓDIGO          |

**Regla:** PREPARADA / DISPARADA / PROPUESTA / CONFIRMADA. Ranking ≠ BUY. Confirm = firma.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/same-entry-operating-truth-across-surfaces.test.ts src/cognitive/same-operational-truth-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/entry-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/trading/operativa-cockpit-phase.test.ts src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 2. Freeze

Confirm = firma · Spine · OperationalTruth posición · `PAPER_D_EXECUTE` off · AUTO execute off · sin drag entry.

## 3. Next (hoja, no implementar aquí)

| Tag   | Nombre                | Notas                                      |
| ----- | --------------------- | ------------------------------------------ |
| V1.39 | Position Operating UX | Una CTA primaria alineada a `truth.action` |
| V1.40 | Exit Management UX    | Ruta visual Entrada → Stop / T1 / T2       |
| V1.41 | Daily Desk            | Hoy quita paneles; inbox por `attention`   |

**V1.39 cerrado:** [`traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md).

Fuera: P2 Lab · móvil · push · thaw estricto · drag entry.
