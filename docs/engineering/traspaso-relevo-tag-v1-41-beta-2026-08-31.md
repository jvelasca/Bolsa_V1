# RELEVO — tag v1.41-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-41-daily-desk-2026-08-31.md`](./traspaso-relevo-v1-41-daily-desk-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **SUPERSEDIDO por `v1.41.1-beta`** — tip `v1.41-beta` → `4247f0f0` · auditoría UX **PASS** · CI tag **RED** (Ruff I001).  
> **Arranque auditor (histórico):** [`arranque-auditor-v1-41-beta-2026-08-31.md`](./arranque-auditor-v1-41-beta-2026-08-31.md).  
> **Tip vigente:** [`traspaso-relevo-tag-v1-41-1-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-1-beta-2026-08-31.md).  
> **Fuera:** P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad · segundo Mercado · drag entry/exit.

---

## 0. Confirmación

Serie de proyección canónica **sin motores nuevos ni backend operativo**:

| Tag   | Nombre                | Entrega clave                              |
| ----- | --------------------- | ------------------------------------------ |
| V1.37 | Operational Truth     | `buildOperationalTruth` cross-surface      |
| V1.38 | Entry Operating UX    | `EntryOperatingTruth` PREPARADA→CONFIRMADA |
| V1.39 | Position Operating UX | CTA primaria `truth.primaryCta`            |
| V1.40 | Exit Management UX    | `ExitRouteView` Entrada→Stop/T1/T2         |
| V1.41 | Daily Desk            | Hoy inbox por `attention`; quita paneles   |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · `protect_hint` thin ≠ autoridad.

## 1. Release

| Pieza    | Valor                                                                                                              |
| -------- | ------------------------------------------------------------------------------------------------------------------ |
| Tag tip  | `v1.41-beta` → `4247f0f0`                                                                                          |
| Previo   | `v1.35-beta` → `ab07e1e4` · tip main previo `43b5aade` (V1.36)                                                     |
| Relevo   | [`traspaso-relevo-v1-41-daily-desk-2026-08-31.md`](./traspaso-relevo-v1-41-daily-desk-2026-08-31.md)               |
| Padre UX | [`traspaso-relevo-v1-37-operational-truth-2026-08-31.md`](./traspaso-relevo-v1-37-operational-truth-2026-08-31.md) |

## 2. Pre-flight tip (local)

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/same-operational-truth-across-surfaces.test.ts src/cognitive/same-entry-operating-truth-across-surfaces.test.ts src/cognitive/same-exit-route-across-surfaces.test.ts src/cognitive/daily-desk.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/trading/position-operating-summary.test.tsx src/features/trading/entry-operating-summary.test.tsx src/features/trading/exit-route-view.test.tsx src/features/trading/operativa-cockpit-card.test.tsx src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
```

Backend operativo **intocado**.

## 3. Auditoría externa (2026-08-31)

**Veredicto: PASS.** Seis preguntas de foco OK · freeze intacto · `packages/py` + `apps/api-python` sin diff de comportamiento vs `v1.35-beta` en la serie UX · pre-flight 24+42 tests + `tsc` verdes. Deuda aparcada sin promover. Nit AsOf header corregido en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).

**CI tag:** Release-tag / Python CI **RED** en `v1.41-beta` (Ruff I001 `position_decision.py`) → tip vigente [`v1.41.1-beta`](./traspaso-relevo-tag-v1-41-1-beta-2026-08-31.md) (sin retag).
