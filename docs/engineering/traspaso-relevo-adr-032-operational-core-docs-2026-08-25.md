# RELEVO — ADR-032 Operational Core docs-only (v1.9 contrato) · 2026-08-25

> **Padre:** [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) §1 (Architecture / adr).  
> **Política:** [`docs/adr/032-operational-core-tradeplan-positionstate-execution.md`](../adr/032-operational-core-tradeplan-positionstate-execution.md).  
> **SoT corto:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **AsOf:** 2026-08-25.  
> **HEAD:** `659e6c4` (C1). Este slice = **solo docs**; sin commit.  
> **Estado:** **CERRADO (docs-only).** No hay runtime.  
> **Arranque chat nuevo:** este fichero + ADR-032 + `CURRENT_SYSTEM.md` + ADR-031.

---

## 0. Qué quedó hecho

Contrato v1.9 **aceptado en papel**, no implementado:

```text
Antes de entrar:  DecisionPackage → TradePlan → check_opening
Después:          PositionState → ExitPlan → ExitPermission → Execution
```

Stamps: CURRENT_SYSTEM (AsOf + 1 bullet) · ADR-031 §6 → ADR-032 · engineering-index · CHANGELOG Unreleased.

## 1. Freeze / siguiente

- **Cero** mappers thin nuevos (`TargetPlan` / `LiquidityPlan` / `PositionPlan` / `EntryPlan` / `ExitPlan` aislados).
- **Cero** Python/TS runtime · **no** `contract:gen` · **no** Alembic · **no** LLM.
- `PAPER_D_EXECUTE` **off** · broker **no** · no OCO.
- TradePlan **v0** sigue viva. TradePlan v1 / PositionState código = fase propia (cite ADR-032).
- NO TRADE first-class. No optimizar el modelo con DEMO / P3–P5.

## 2. E1 (chat nuevo)

1. Seguir v1.8.1 (C2 Alembic / C3 ActionQueue / …) **o** operar SEMI.
2. **No** abrir TradePlan v1 / PositionState / ExecutionPlan sin plan D1–D8 que cite ADR-032.
3. **No** «Ciclo 8.3».
