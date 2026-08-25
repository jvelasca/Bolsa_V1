# Audit pack — estado global v1.9-beta (Operational Core)

> **AsOf:** 2026-08-25 · **Tag:** `v1.9-beta` (SHA se pinea tras publish).
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032.
> **Para:** auditoría externa / GitHub Actions Release tag CI.

---

## 0. Veredicto interno

Operational Core **modelado** (código puro + tests): TradePlan v1 → PositionState (+transitions) → ExitPlan → ExitPermission → ExecutionPlan PAPER. INFRA CI-by-tag listo. Producto sigue **BETA / no producción**. Broker **no**. Auto-exit producto **no**. Thin 5.x/8.x **congelados**.

## 1. Batería (local, pre-tag)

| Gate                               | Resultado                                                  |
| ---------------------------------- | ---------------------------------------------------------- |
| `pnpm test:decision-spine`         | **217** passed                                             |
| `pnpm --filter @bolsa/shared test` | **134** passed                                             |
| Release tag CI                     | Se dispara al pushear `v*` (workflow `release-tag-ci.yml`) |

## 2. Qué entra en el tag

- F1 TradePlan v1 · F2/F2.1 PositionState · F3 ExitPlan · F4 ExecutionPlan PAPER · ExitPermission
- `.github/workflows/release-tag-ci.yml`
- Planes + relevos + ADR-032 enmendado · HELP sync

## 3. Qué no entra / parked

- Broker adapter · OCO · wire Confirm/Hoy CTA ExitPermission
- `PAPER_D_EXECUTE` default on · thaw estricto · ActionabilityScore predictivo
- `contract:gen` / Alembic nuevos para estos objetos

## 4. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-032 → código → tests → HELP
PositionState → ExitPlan → ExitPermission → ExecutionPlan(PAPER)
check_opening = apertura; ExitPermission = salida (distintos)
```

## 5. Docs clave

- [`plan-f1-tradeplan-v1-2026-08-25.md`](./plan-f1-tradeplan-v1-2026-08-25.md) … [`plan-exit-permission-2026-08-25.md`](./plan-exit-permission-2026-08-25.md)
- [`plan-infra-ci-by-tag-2026-08-25.md`](./plan-infra-ci-by-tag-2026-08-25.md)
- Relevo tag: [`traspaso-relevo-tag-v1-9-beta-2026-08-25.md`](./traspaso-relevo-tag-v1-9-beta-2026-08-25.md)
