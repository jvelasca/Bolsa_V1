# Roadmap — v1.8.1 Operational Consolidation

> **Padre:** auditoría externa post-tag `v1.8.0-beta` (`8c8b789`) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · ADR-031.
> **AsOf:** 2026-08-25.
> **Estado:** fase **ABIERTA**. C1 = P0 (Hoy honesty + HELP). Resto parked hasta cierre de cada slice.
> **Método:** consolidar el modelo operativo **antes** de añadir capas. **No** más módulos thin (TargetPlan, PositionPlan, LiquidityPlan, …). **No** thaw estricto. **No** broker. **No** LLM.

---

## 0. Por qué esta fase

v1.8 tomó la decisión correcta (tesis ≠ plan ≠ permiso) y trató Thesis Health / Protect / Exit / MFE / Expectancy / Trail / Bracket como thin/advisory. Seguir añadiendo módulos ahora produce _Frankenstein TradePlan_.

Objetivo de fase: **Operational Consolidation**, no crecimiento.

Autoridad normativa (no cycle plans):

```text
CURRENT_SYSTEM → ADR → código → tests
```

Planes / handoffs / `plan-ciclo-*` = **contexto histórico**.

---

## 1. Secuencia

| Slice  | Nombre                    | Qué                                                                                      | Estado                |
| ------ | ------------------------- | ---------------------------------------------------------------------------------------- | --------------------- |
| **C1** | Hoy honesty + HELP        | F3 sin TradePlan → WATCH (nunca BUY) · whyNot heurístico `legacy_projection` · HELP v1.8 | **CERRADO `659e6c4`** |
| **C2** | Alembic única autoridad   | Retirar/renombrar `db:push` / `db:migrate` Prisma públicos                               | **CÓDIGO LISTO**      |
| **C3** | ActionQueue               | Prioridad determinista · cola completa ≠ slice UI top-N                                  | **CÓDIGO LISTO**      |
| **C4** | Contratos / shape drift   | TradePlan DTO canónico · ir reduciendo payload/extra/runtime dual                        | parked                |
| **C5** | Honesty métricas          | MFE real ≠ proxy · Expectancy sample-quality en UI                                       | parked                |
| **C6** | Stamp + tag `v1.8.1-beta` | Audit pack · CHANGELOG · tag                                                             | parked                |

**Fuera de v1.8.1 (v1.9 Operational Core):** TradePlan v1 (target / R/R / sizing completo) · PositionState · ExitPlan. **No** Wyckoff 2 · **no** Expectancy/Trail/Bracket 2.

Contrato conceptual a fijar **en docs** (sin implementar aún):

```text
TradePlan     → qué haríamos si entramos
PositionState → qué ocurre después de entrar
ExecutionPlan → cómo se envía (futuro)
```

---

## 2. Freeze de fase

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** (no un mapper más) · I1–I3 + RX1 intactos · Shadow AUTO **off** · `PAPER_D_EXECUTE` **off** · thaw estricto **FAIL** (no optimizar el modelo con demo) · broker live **no**.
