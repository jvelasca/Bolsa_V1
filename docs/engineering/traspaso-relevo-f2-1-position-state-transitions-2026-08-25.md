# RELEVO — F2.1 PositionState transitions · 2026-08-25

> **Padre:** [`plan-f2-1-position-state-transitions-2026-08-25.md`](./plan-f2-1-position-state-transitions-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Spine **180**. Cambiar de chat recomendado para F3 / INFRA.
> **Arranque chat nuevo:** este fichero + plan F2.1 + ADR-032 + gap §3 + `CURRENT_SYSTEM.md` + roadmap v1.9.

---

## 0. Qué quedó hecho

| Pieza                                                                        | Estado       |
| ---------------------------------------------------------------------------- | ------------ |
| `applyMark` / `apply_position_mark` → `unrealizedR` + MFE/MAE proxy          | **Hecho**    |
| `applyReduce` / `apply_position_reduce` → `PARTIAL` / `CLOSED` + `realizedR` | **Hecho**    |
| `applyCurrentStop` / `apply_position_current_stop` → BE `PROTECTED`          | **Hecho**    |
| Precedencia CLOSED > PROTECTED > PARTIAL > OPEN                              | **Hecho**    |
| Factory F2 `from_fill`                                                       | **Intacta**  |
| Thin 5.x/8.x promocionados                                                   | **No**       |
| ExitPlan / wire Confirm / Alembic / `contract:gen`                           | **No**       |
| HELP ciclo + mark/reduce ≠ orden                                             | **Hecho**    |
| F1 / C1 / opening                                                            | **Intactos** |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- PositionState ≠ permiso de salida. TradePlan ≠ permiso de apertura.
- `PROTECTED` = hecho geométrico BE — **no** razón F3.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **F3 ExitPlan** (razones canónicas; ≠ execution).
2. **Opción B:** INFRA CI-by-tag (antes de `v1.9-beta`).
3. **Opción C:** operar SEMI. No reabrir thin.
4. **No** ExecutionPlan→broker. **No** ActionabilityScore. **No** auto-exit producto. **No** wire Confirm todavía (salvo plan explícito).

## 3. Docs clave

- [`plan-f2-1-position-state-transitions-2026-08-25.md`](./plan-f2-1-position-state-transitions-2026-08-25.md)
- [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §3
- ADR-032 · `CURRENT_SYSTEM.md` · roadmap v1.9
