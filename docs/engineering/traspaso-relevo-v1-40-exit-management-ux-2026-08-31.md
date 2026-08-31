RELEVO — V1.40 Exit Management UX (2026-08-31)

> **Padre:** [`plan-v140-exit-management-ux-2026-08-31.md`](./plan-v140-exit-management-ux-2026-08-31.md) · V1.39 [`traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md`](./traspaso-relevo-v1-39-position-operating-ux-2026-08-31.md).  
> **Estado:** **CERRADO** — ruta visual canónica Entrada → Stop / T1 / T2.  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push).

---

## 0. Qué cierra V1.40

Composición (no motor nuevo): `OperationalTruth` + `buildPositionRouteLevels` → `ExitRouteView`.

| Pieza                                                   | Estado          |
| ------------------------------------------------------- | --------------- |
| `exit-route-view.ts` — `buildExitRouteView`             | CÓDIGO + vitest |
| `same-exit-route-across-surfaces.test.ts`               | CÓDIGO          |
| `ExitRouteView` componente web                          | CÓDIGO          |
| Cockpit POSICIÓN + Journal ficha + `PositionRoutePanel` | CÓDIGO          |
| Roles: Entrada · Proteger (Stop) · T1 · T2 · trailing   | CÓDIGO          |

**Regla:** T1 tocado ≠ gestionado · T2 trailing = propuesta thin · Stop operativo ≠ broker.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/same-exit-route-across-surfaces.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/exit-route-view.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/mesa/mesa-position-row.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 2. Freeze

Confirm = firma · Spine · EntryOperatingTruth · OperationalTruth CTA · `PAPER_D_EXECUTE` off · AUTO execute off · sin drag entry/exit.

## 3. Next (hoja, no implementar aquí)

| Tag   | Nombre     | Notas                                    |
| ----- | ---------- | ---------------------------------------- |
| V1.41 | Daily Desk | Hoy quita paneles; inbox por `attention` |

**V1.41 cerrado:** [`traspaso-relevo-v1-41-daily-desk-2026-08-31.md`](./traspaso-relevo-v1-41-daily-desk-2026-08-31.md).

Fuera: P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad.
