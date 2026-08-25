# RELEVO — F2 PositionState · 2026-08-25

> **Padre:** [`plan-f2-position-state-2026-08-25.md`](./plan-f2-position-state-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Spine **172**. Cambiar de chat recomendado para F3 / INFRA / F2.1.
> **Arranque chat nuevo:** este fichero + plan F2 + ADR-032 + gap §3 + `CURRENT_SYSTEM.md` + roadmap v1.9.

---

## 0. Qué quedó hecho

| Pieza                                                           | Estado                |
| --------------------------------------------------------------- | --------------------- |
| `PositionState` shared + Python                                 | **Hecho**             |
| `buildPositionStateFromFill` / `build_position_state_from_fill` | **Hecho** → `OPEN`    |
| `tradePlanId` = `decisionId`                                    | **Hecho**             |
| Geometry plan-vs-fill · stubs thin                              | **Hecho**             |
| Thin 5.x/8.x promocionados                                      | **No**                |
| ExitPlan / ExecutionPlan / Alembic / `contract:gen`             | **No**                |
| Wire Confirm/opening/Hoy CTA                                    | **No** (factory pura) |
| HELP PositionState ≠ TradePlan                                  | **Hecho**             |
| F1 / C1 / opening                                               | **Intactos**          |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- PositionState ≠ permiso de salida. TradePlan ≠ permiso de apertura.

## 2. E1 — fork (chat nuevo)

1. **Opción A:** plan D1–D8 **F3 ExitPlan** (razones canónicas; ≠ execution).
2. **Opción B:** **F2.1** transiciones `PARTIAL` / `PROTECTED` / `CLOSED` + mark/unrealizedR (sin ExitPlan).
3. **Opción C:** INFRA CI-by-tag.
4. **Opción D:** operar SEMI. No reabrir thin.
5. **No** ExecutionPlan→broker. **No** ActionabilityScore. **No** auto-exit producto.

## 3. Docs clave

- [`plan-f2-position-state-2026-08-25.md`](./plan-f2-position-state-2026-08-25.md)
- [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §3
- ADR-032 · `CURRENT_SYSTEM.md` · roadmap v1.9
