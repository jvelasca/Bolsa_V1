RELEVO — V1.39 Position Operating UX (2026-08-31)

> **Padre:** [`plan-v139-position-operating-ux-2026-08-31.md`](./plan-v139-position-operating-ux-2026-08-31.md) · V1.38 [`traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-38-entry-operating-ux-2026-08-31.md).  
> **Estado:** **CERRADO** — CTA primaria posición + coherencia Mercado/Hoy/Journal/Operaciones.  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push).

---

## 0. Qué cierra V1.39

Composición (no motor nuevo): `PositionDecision` → `primaryCta` en `OperationalTruth`.

| Pieza                                                             | Estado          |
| ----------------------------------------------------------------- | --------------- |
| `positionOperatingCtaFromDecision` — `PositionOperatingCtaV1`     | CÓDIGO + vitest |
| `OperationalTruthV1.primaryCta` + snapshot `ctaLabel` / `ctaKind` | CÓDIGO + vitest |
| `same-operational-truth-across-surfaces.test.ts` (CTA)            | CÓDIGO          |
| Cockpit POSICIÓN: `PositionExitDrawerActions` `primaryOnly`       | CÓDIGO          |
| `PositionOperatingSummary` ← `primaryCta`                         | CÓDIGO          |
| Hoy fila / inbox / Operaciones ← `truth.primaryCta`               | CÓDIGO          |

**Regla:** una CTA primaria = `truth.primaryCta` · protect_hint thin ≠ autoridad · Confirm = firma.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/position-decision-copy.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 2. Freeze

Confirm = firma · Spine · EntryOperatingTruth · OperationalTruth niveles · `PAPER_D_EXECUTE` off · AUTO execute off · sin drag entry/exit.

## 3. Next (hoja, no implementar aquí)

| Tag   | Nombre             | Notas                                    |
| ----- | ------------------ | ---------------------------------------- |
| V1.40 | Exit Management UX | Ruta visual Entrada → Stop / T1 / T2     |
| V1.41 | Daily Desk         | Hoy quita paneles; inbox por `attention` |

**V1.40 cerrado:** [`traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md`](./traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md).

Fuera: P2 Lab · móvil · push · thaw estricto · drag entry/exit · banda secundaria reduce/salir en cockpit.
