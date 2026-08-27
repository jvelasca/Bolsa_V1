# RELEVO — V1.21 Operational Coherence & UX Hardening (2026-08-27)

> **Padre:** [`traspaso-relevo-tag-v1-20-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-20-beta-2026-08-27.md) · [ADR-041](../adr/041-operational-coherence.md) · [ADR-040](../adr/040-user-information-architecture.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Estado:** **PUBLICACIÓN** — ver [`traspaso-relevo-tag-v1-21-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-21-beta-2026-08-27.md) · pack [`audit-pack-estado-global-2026-08-27-v121.md`](./audit-pack-estado-global-2026-08-27-v121.md).

---

## Cerrado en V1.21

| Bloque                | Qué                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------- |
| **B1 Universo**       | Mesa/scan/ranking default = `estudio`. Fuera → `discovered`. Trazabilidad en Hoy. Tests UNIVERSE-001/002. |
| **B2 Plan operativo** | `OperationalPlanView` + builders shared; cableado Hoy / drawer / ficha / PositionRoute.                   |
| **B3/B4 Stops**       | `target1AchievedAt` + ExitPlan idempotente; stop vigente label; Confirm reduce marca T1; OP-03/04/05.     |
| **AdminRail**         | Overview/Cuentas/Fiscal/Consola fuera de ⚙; cuenta activa en header. ADR-040 §7.                          |
| **B6 Cuentas**        | Origen seed/user/lab; selector diario sin Lab paper; **Cerrar extras de desarrollo** (OP-08).             |
| **Trail UI**          | `mapTrailPlan` proyectado en OperationalPlanView (peak / stop hint / distancia); advisory only.           |

## Freeze intacto

SEMI · Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · Trading sin barras Hoy · trail ≠ autoridad · OpportunityScore aparcado.

## Verificación

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm test:daily-ops:offline   # 1159 local
pnpm test:decision-spine      # 497
```

## Next (post tag / auditoría)

OpportunityScore / Stress correlación / thaw — solo con epic explícito. Arranque auditor: pack v121 + relevo tag.
