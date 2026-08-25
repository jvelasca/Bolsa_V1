# RELEVO — F1 TradePlan v1 · 2026-08-25

> **Padre:** [`plan-f1-tradeplan-v1-2026-08-25.md`](./plan-f1-tradeplan-v1-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Spine **167**. Cambiar de chat recomendado para F2 o INFRA.
> **Arranque chat nuevo:** este fichero + plan F1 + ADR-032 + gap §2 + `CURRENT_SYSTEM.md` + roadmap v1.9.

---

## 0. Qué quedó hecho

| Pieza                                     | Estado                                        |
| ----------------------------------------- | --------------------------------------------- |
| Campos gap §1 en TradePlan                | **Hecho** — builder + `to_dict` + tipo shared |
| `thesisId` / `entryCondition`             | **Hecho**                                     |
| T1/T2 / `initialRiskR` / `expectedRR`     | **Hecho** (±1R/±2R; null sin geometry)        |
| `riskAmount` / `positionValue`            | **Hecho**                                     |
| `portfolioFit` snapshot                   | **Hecho** — veto sigue en `check_opening`     |
| `executionConstraints`                    | **Hecho** (`expiresAt`)                       |
| PositionState / ExitPlan / ExecutionPlan  | **No**                                        |
| `contract:gen` / Alembic / mapper hermano | **No**                                        |
| HELP (T1/T2 ≠ permiso)                    | **Hecho**                                     |
| C1 Hoy / thin 5.x/8.x / opening           | **Intactos**                                  |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. Broker live **no**. Thaw estricto **FAIL**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso.
- Thin 5.x/8.x **congelados**. Actionability = ordinal. Dedup Hoy por símbolo **intacta**.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **F2 PositionState** citando ADR-032 + gap §2. Requiere `tradePlanId`. **No** promover thin 5.x/8.x.
2. **Opción B:** INFRA CI-by-tag (`on: push tags`, sin path-filter, gates spine+shared). Independiente. Antes de un futuro `v1.9-beta`.
3. **Opción C:** operar SEMI con TradePlan v1. No reabrir thin.
4. **No** ExitPlan/ExecutionPlan sin F2. **No** ActionabilityScore. **No** Ciclo 8.3.

## 3. Docs clave

- [`plan-f1-tradeplan-v1-2026-08-25.md`](./plan-f1-tradeplan-v1-2026-08-25.md)
- [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §2
- [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md)
- ADR-032 · `CURRENT_SYSTEM.md`
