# Plan — F1 TradePlan v1 (Operational Core)

> **Padre:** [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md) · ADR-032 · gap [`adr-032-audit-gap-2026-08-25.md`](./adr-032-audit-gap-2026-08-25.md) §1 · relevo [`traspaso-relevo-audit-ext-v181-cierre-apertura-v19-2026-08-25.md`](./traspaso-relevo-audit-ext-v181-cierre-apertura-v19-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO** (D1–D8 OK) · batería spine **167**.
> **Método:** crecimiento **dentro** de TradePlan (no mapper hermano). Tesis ≠ plan ≠ permiso. Sin PositionState / ExitPlan / ExecutionPlan. Sin `contract:gen`. Sin Alembic. Sin thaw. Sin broker.

---

## 0. Objetivo

Extender el plan condicional pre-entrada con el contrato auditor (gap §1): targets, R/R, sizing explícito, snapshot de fit, constraints de ejecución — **sin** abrir post-entrada ni permiso.

### Qué entra vs qué queda fuera

| Incluye (F1)                                                                         | Excluye                                        |
| ------------------------------------------------------------------------------------ | ---------------------------------------------- |
| Campos gap §1 **en** TradePlan (shared + builder propose/echo)                       | PositionState · ExitPlan · ExecutionPlan       |
| `thesisId` junto a `decisionId` (no sustituir a ciegas)                              | Mapper thin nuevo (`TargetPlan`, etc.)         |
| `entryCondition` evaluable; `entrySetup` v0 **conservado**                           | Mutar `structuralStop` · OCO · trailing broker |
| `target1`/`target2` · `initialRiskR` · `riskAmount` · `positionValue` · `expectedRR` | ActionabilityScore predictivo                  |
| `portfolioFit` **snapshot** (veto sigue en `check_opening`)                          | `wyckoffPhase` contrato · Alembic Wyckoff      |
| `executionConstraints` (TTL/liquidez/horario) — **≠ orden**                          | `contract:gen` · OpenAPI DTO formal            |
| Tests familia A/B (decision + risk) + stamp CURRENT_SYSTEM + HELP                    | F2+ · CI-by-tag (INFRA paralelo, otro slice)   |

---

## 1. Decisiones (D1–D8) — OK

| Id  | Decisión                                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Campos gap §1 **dentro** de TradePlan. Cero `map_*` hermano. Thin 5.x/8.x congelados.                                                 |
| D2  | `decisionId` + `thesisId` (default = decisionId). Tipo TS ampliado in-place.                                                          |
| D3  | `entrySetup` intacto. `entryCondition` = `ready` \| `wait` \| `none`. Status semántica sin cambio.                                    |
| D4  | `initialRiskR` / `riskAmount` / `positionValue` / `expectedRR`. qty F3 no pisada.                                                     |
| D5  | `target1`/`target2` = ±1R/±2R en el plan. No OCO. No mutar stop.                                                                      |
| D6  | `portfolioFit` snapshot; veto en `check_opening`. `executionConstraints` ≠ orden.                                                     |
| D7  | Builder Python + tipo shared + echo propose/Board. Sin `contract:gen`/Alembic. HELP: T1/T2 del plan ≠ permiso. Actionability ordinal. |
| D8  | Tests + stamp + relevo. E1 = F2 PositionState plan **o** INFRA CI-by-tag.                                                             |

---

## 2. Ficheros tocados

- `packages/py/analytics/.../trade_plan.py` · `packages/py/application/tests/test_trade_plan.py`
- `packages/shared/src/cognitive/trade-plan.ts`
- HELP `hoy-en-la-mesa` · `help-content-as-of`
- Stamp: `CURRENT_SYSTEM.md` · CHANGELOG · roadmap · relevo F1

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · C1 Hoy honesty · dedup Hoy por símbolo.
