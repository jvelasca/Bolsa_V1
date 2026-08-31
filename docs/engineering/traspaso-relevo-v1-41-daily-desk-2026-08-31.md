RELEVO — V1.41 Daily Desk (2026-08-31)

> **Padre:** [`plan-v141-daily-desk-2026-08-31.md`](./plan-v141-daily-desk-2026-08-31.md) · V1.40 [`traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md`](./traspaso-relevo-v1-40-exit-management-ux-2026-08-31.md).  
> **Estado:** **CERRADO** — Hoy inbox por attention; paneles fuera del chrome.  
> **Tag previo:** `v1.35-beta` → `ab07e1e4` (local, sin push).

---

## 0. Qué cierra V1.41

Composición (no motor nuevo): `OperationalTruth.attention` + firmas pendientes + cola board → `DailyDeskInbox`.

| Pieza                                              | Estado          |
| -------------------------------------------------- | --------------- |
| `daily-desk.ts` — `buildDailyDeskInbox`            | CÓDIGO + vitest |
| `DailyDeskInbox` componente web                    | CÓDIGO          |
| Hoy resumen: un inbox (sin 4 paneles)              | CÓDIGO          |
| Oportunidades / Consola en footer + «Ver detalles» | CÓDIGO          |
| Deep-links `?view=` intactos                       | CÓDIGO          |

**Regla:** Hoy ≠ Mercado · inbox por `attention` · Ranking ≠ BUY · Confirm = firma.

## 1. Pre-flight cierre

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 2. Freeze

Confirm = firma · Spine · EntryOperatingTruth · OperationalTruth · ExitRoute · `PAPER_D_EXECUTE` off · AUTO execute off · sin drag entry/exit.

## 3. Next (hoja)

Serie V1.35→V1.41 cerrada (Position Hardening → Daily Desk). Fuera de esta hoja: P2 Lab · móvil · push · thaw estricto · OCO · segundo Mercado.
