# RELEVO — F3 ExitPlan · 2026-08-25

> **Padre:** [`plan-f3-exit-plan-2026-08-25.md`](./plan-f3-exit-plan-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Spine **192**. Cambiar de chat recomendado para F4 / INFRA.
> **Arranque chat nuevo:** este fichero + plan F3 + ADR-032 + gap §4 + `CURRENT_SYSTEM.md` + roadmap v1.9.

---

## 0. Qué quedó hecho

| Pieza                                                                 | Estado       |
| --------------------------------------------------------------------- | ------------ |
| `ExitPlan` objeto nuevo (TS + Py)                                     | **Hecho**    |
| Factory `buildExitPlanFromPosition` / `build_exit_plan_from_position` | **Hecho**    |
| Razones canónicas gap §3 + precedencia                                | **Hecho**    |
| Status `IDLE`/`HINT`/`ARMED`/`TRIGGERED`/`DONE`                       | **Hecho**    |
| `suggestedAction` advisory (≠ orden)                                  | **Hecho**    |
| PositionState write-back / `exitStatus` mutado                        | **No**       |
| Thin 5.x/8.x promocionados                                            | **No**       |
| ExitPermission / ExecutionPlan / wire Confirm                         | **No**       |
| HELP ExitPlan ≠ auto-exit / thin «Salida»                             | **Hecho**    |
| F1 / F2 / F2.1 / C1 / opening                                         | **Intactos** |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- ExitPlan ≠ permiso de salida. PositionState ≠ permiso. TradePlan ≠ permiso de apertura.
- Thin `exitRadar` / «Salida» Hoy **≠** ExitPlan.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **F4 ExecutionPlan→PAPER** (Journal / Replay / Validation; ≠ broker).
2. **Opción B:** INFRA CI-by-tag (antes de `v1.9-beta`).
3. **Opción C:** operar SEMI. No reabrir thin.
4. **No** ExecutionPlan→broker. **No** ExitPermission producto. **No** ActionabilityScore. **No** auto-exit. **No** wire Confirm todavía (salvo plan explícito).

## 3. Docs clave

- [`plan-f3-exit-plan-2026-08-25.md`](./plan-f3-exit-plan-2026-08-25.md)
- [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §3–§4
- ADR-032 · `CURRENT_SYSTEM.md` · roadmap v1.9
