# ADR-032: Operational Core — TradePlan / PositionState / Execution (contrato v1.9)

**Estado:** Accepted — **F1–F4 + ExitPermission + INFRA implementados** (2026-08-25); broker adapter sigue parked  
**Fecha:** 2026-08-25  
**Enmienda:** 2026-08-25 — F1–F4 + ExitPermission + CI-by-tag. Gap campos: [`adr-032-audit-gap-2026-08-25.md`](../engineering/adr-032-audit-gap-2026-08-25.md). **Enmienda 2:** 2026-08-25 — factories ≠ autoridad; constitución v1.10 = [ADR-033](./033-operational-authority-position-persistence.md) · gap [`adr-032-ops-authority-gap-2026-08-25.md`](../engineering/adr-032-ops-authority-gap-2026-08-25.md).  
**Contexto:** Cadena post-entrada **modelada**. Autoridad persistente + honesty pending = ADR-033 (no este ADR).

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [RFC-008](../rfc/008-cognitive-decision-architecture.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [roadmap v1.8.1](../engineering/roadmap-v181-operational-consolidation-2026-08-25.md).

---

## 1. Decisión

Dos tiempos, un solo spine. **No** se crea un segundo motor. **No** se implementa en este ADR.

```text
Antes de entrar:  DecisionPackage → TradePlan → check_opening
Después:          PositionState → ExitPlan → ExitPermission → Execution
```

| Tiempo           | Objeto            | Pregunta                                 | Hoy (v1.8.x)                                      |
| ---------------- | ----------------- | ---------------------------------------- | ------------------------------------------------- |
| **Antes**        | `DecisionPackage` | ¿Qué creemos?                            | Runtime / tesis (ADR-031)                         |
| **Antes**        | `TradePlan`       | ¿Qué haríamos **si** entramos?           | **v0 viva** (WATCH…EXPIRED + stop + qty + whyNot) |
| **Antes**        | `check_opening`   | ¿Podemos llenar ahora?                   | Único veto de fill (SEMI = AUTO)                  |
| **Después**      | `PositionState`   | ¿Qué ocurre **tras** entrar?             | **Contrato**; thin 5.x/8.x = stand-in, no SoT     |
| **Después**      | `ExitPlan`        | Si ocurre Y, ¿cómo salimos / protegemos? | **F3** razones canónicas; ≠ execution             |
| **Después**      | `ExitPermission`  | ¿Podemos salir / mutar stop ahora?       | **Implementado** (`check_exit_permission`)        |
| **Envío futuro** | `ExecutionPlan`   | ¿Cómo se envía al broker / paper?        | **F4** PAPER only; broker blocked                 |

Este documento **acepta el contrato**. No genera tipos, dataclasses, tablas ni mappers.

---

## 2. TradePlan — «qué haríamos si entramos»

### 2.1 v0 (autoridad actual — no tocar en este ADR)

Campos canónicos vivos (ADR-031 + ciclos 4.0–4.9 + C1):

- `status`: `WATCH` \| `ARMED` \| `TRIGGERED` \| `BLOCKED` \| `EXPIRED`
- `entry`, `structuralStop`, `quantity`, `whyNot[]`, `entrySetup`
- identidad (`decisionId`, `instrumentId`, dirección), `expiresAt`, `executionAllowed`, `riskPct`
- `opportunityScore` (calidad/oportunidad; **no** es BUY)
- `actionability` v0 = **ordinal de `status`**, no score predictivo (WATCH ~0.4 / ARMED 0.7 / TRIGGERED ~0.95)

BUY operativo sigue = `TradePlan.status == TRIGGERED` **y** `check_opening` ALLOW **y** firma humana (SEMI). Ranking / TOP / dictamen **no** son BUY.

### 2.2 v1 (F1 — implementado 2026-08-25)

Crecimiento **dentro** de TradePlan, no en un mapper hermano. Contrato de campos (auditoría ext v1.8.1; plan [`plan-f1-tradeplan-v1-2026-08-25.md`](../engineering/plan-f1-tradeplan-v1-2026-08-25.md)):

| Campo                                     | Notas                                                                      |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| `instrument` / `direction`                | Alias de identidad v0; no duplicar SoT                                     |
| `thesisId`                                | Vínculo tesis ≠ plan; default = `decisionId`                               |
| `entry` · `entryCondition`                | Condición evaluable (`ready`/`wait`/`none`); `entrySetup` v0 no desaparece |
| `structuralStop`                          | Conservar                                                                  |
| `target1` / `target2`                     | ±1R / ±2R en el plan                                                       |
| `initialRiskR` · `riskPct` · `riskAmount` | Riesgo explícito + sizing                                                  |
| `quantity` · `positionValue`              | Size + nocional                                                            |
| `expectedRR`                              | R/R vs T1                                                                  |
| `expiresAt`                               | Conservar                                                                  |
| `portfolioFit`                            | Snapshot; el veto sigue en `check_opening`                                 |
| `executionConstraints`                    | TTL — **no** es orden                                                      |

**No** en v1: trailing broker, OCO, `wyckoffPhase` en contrato, Alembic Wyckoff, ActionabilityScore predictivo.

---

## 3. PositionState — «qué ocurre tras entrar» (**F2 + F2.1**)

Factory pura `build_position_state_from_fill` / `buildPositionStateFromFill` → `OPEN`. Transiciones F2.1: `applyMark` / `applyReduce` / `applyCurrentStop` → `PARTIAL` / `PROTECTED` (BE geométrico) / `CLOSED`. Planes: [`plan-f2-position-state-2026-08-25.md`](../engineering/plan-f2-position-state-2026-08-25.md) · [`plan-f2-1-position-state-transitions-2026-08-25.md`](../engineering/plan-f2-1-position-state-transitions-2026-08-25.md). **No** Alembic · **no** `contract:gen` · thin 5.x/8.x **no** promocionados · **no** ExitPlan.

| Campo                                                          | Intención                                                                         |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `positionId` · `tradePlanId`                                   | Identidad (`tradePlanId` = `decisionId` del plan)                                 |
| `status`                                                       | `OPEN` \| `PARTIAL` \| `PROTECTED` \| `CLOSED` (F2 emite OPEN; F2.1 transiciones) |
| `plannedEntry` / `actualEntry`                                 | Plan vs fill                                                                      |
| `initialStop` / `currentStop`                                  | Foto al nacer; F2.1 `applyCurrentStop` (BE → PROTECTED)                           |
| `initialRisk`                                                  | `\|actualEntry − initialStop\|`                                                   |
| `realizedR` / `unrealizedR`                                    | 0 / null al abrir; F2.1 mark + reduce                                             |
| `quantity` / `remainingQuantity`                               | Size al fill                                                                      |
| `target1` / `target2`                                          | Del TradePlan F1                                                                  |
| `MFE` / `MAE`                                                  | Slot con `source: none` (C5)                                                      |
| `thesisHealth` / `protectionState` / `trailing` / `exitStatus` | Stubs `none` — ≠ mappers thin                                                     |
| `createdAt` / `updatedAt`                                      | Auditoría temporal                                                                |

Los bloques `runtime.thesisHealth` / `protectPlan` / … siguen **stand-in advisory**. No mutan stops. No son permiso.

---

## 4. ExitPlan · ExitPermission · ExecutionPlan

- **`ExitPlan` (F3 — implementado 2026-08-25):** plan condicional de salida (simétrico a TradePlan, **después** de entrar). Factory `build_exit_plan_from_position` / `buildExitPlanFromPosition`. Razones canónicas: `STRUCTURAL_STOP` · `THESIS_INVALIDATION` · `TARGET_1` · `TARGET_2` · `TRAIL` · `TIME_STOP` · `PORTFOLIO_RISK` · `MANUAL`. Status `IDLE`/`HINT`/`ARMED`/`TRIGGERED`/`DONE`. `suggestedAction` advisory. Plan: [`plan-f3-exit-plan-2026-08-25.md`](../engineering/plan-f3-exit-plan-2026-08-25.md). **ExitPlan ≠ execution.** **No** muta PositionState. Thin exitRadar **≠** ExitPlan.
- **`ExitPermission` (implementado 2026-08-25):** veto de salida / mutación de stop. `check_exit_permission` / `checkExitPermission`. Distinto de `check_opening` (apertura). Plan: [`plan-exit-permission-2026-08-25.md`](../engineering/plan-exit-permission-2026-08-25.md). RX1 / `EvaluatePositionExits` con `executeTrades=true` **no** son el producto auto-exit. ALLOW ≠ ExecuteTrade.
- **`ExecutionPlan` (F4 — implementado 2026-08-25):** camino de **envío PAPER**. Factory `build_execution_plan_from_exit_plan` / `buildExecutionPlanFromExitPlan`. Pipeline `PAPER_READY` → Journal → Replay → Validation. Broker → `BLOCKED` (`broker_not_allowed`). Plan: [`plan-f4-execution-plan-paper-2026-08-25.md`](../engineering/plan-f4-execution-plan-paper-2026-08-25.md). **No** OCO. **No** `PAPER_D_EXECUTE` on. **No** ExecuteTrade. **No** broker live. El LLM **nunca** emite una orden.

Cadena post-entrada = PositionState → ExitPlan → ExitPermission → Execution. Broker adapter + wire producto siguen parked.

---

## 5. Freeze de módulos thin

**Prohibido** añadir como mappers thin aislados:

`TargetPlan` · `LiquidityPlan` · `PositionPlan` · `EntryPlan` · `ExitPlan` (como slice 5.x/8.x más)

La línea 5.0–5.3 y 8.0–8.2 está **CERRADA**. El crecimiento futuro va **dentro** de:

- TradePlan **v1** (targets, R/R, sizing completo)
- **PositionState** (vida de la posición)
- **ExitPlan** (salida, cuando exista fase)

No un Frankenstein de `runtime.*Plan` más.

---

## 6. Autoridad de scores (no se mezclan)

```text
OpportunityScore  →  Actionability v0  →  TradePlanStatus  →  Permission (check_opening)
                     (ordinal de status;
                      NO score predictivo)
```

| Señal                     | Qué es                                      | Qué **no** es          |
| ------------------------- | ------------------------------------------- | ---------------------- |
| Ranking Estudio (cliente) | Ordenación de lista                         | Permiso / BUY          |
| IO server (Ciclo I2)      | Fórmula `indiceOperativo` en chip Composite | Actionability / BUY    |
| `OpportunityScore`        | Calidad / oportunidad de la tesis           | Permiso                |
| `Actionability` v0        | Ordinal de `TradePlan.status`               | Score predictivo / BUY |
| `TradePlan.status`        | Plan condicional                            | Fill                   |
| `check_opening`           | Permiso de apertura                         | Ranking                |

**Ranking Estudio (cliente) ≠ IO server (I2) ≠ Actionability ≠ BUY.**

---

## 7. NO TRADE es de primera clase

**0 BUY + N WATCH / BLOCKED / ARMED puede ser un día excelente.**

Elevación de ADR-031 §1: _«0 operaciones hoy con gates correctos es una métrica de calidad, no un fallo.»_

Un día con gates honestos y cola en WATCH/BLOCKED/ARMED **sin** fills no se reporta como sub-actividad, ni se «arregla» relajando `check_opening`, ni se convierte Hoy en motor de BUY. La métrica de calidad del spine es **integridad del veto**, no el recuento de operaciones.

---

## 8. No contaminar el modelo con DEMO / thaw

**No** optimizar TradePlan, PositionState, scores ni umbrales usando números DEMO o de thaw **estricto**.

P3–P5 (precisión BUY, recall, MaxDD trading) en el perfil estricto están **FAIL** / contaminados (0 SEMI live, prec null, recall 0 %, MaxDD inválido o no comparable). BETA-D (P1'–P5' + W2–W4) **no** es evidencia para rediseñar el núcleo. Thaw estricto sigue deuda; `PAPER_D_EXECUTE` default off; broker live no.

---

## 9. Tickets parked (fase propia; no este ADR)

| Ticket                        | Qué                                             | Qué no                           |
| ----------------------------- | ----------------------------------------------- | -------------------------------- |
| **ENTRY-SETUP-02**            | Endurecer semántica `pullback`                  | Nuevo `EntryPlan` mapper         |
| Lot rounding                  | `floor(qty / lot) * lot`                        | Cambiar fórmula v0 de size ahora |
| Sizing cash / liquidez / fees | Parte de TradePlan **v1**                       | Thin `LiquidityPlan`             |
| `wyckoffPhase` en contrato FE | **NO**                                          | Ni v0 ni v1 por defecto          |
| Alembic tabla Wyckoff         | **NO**                                          | Anchor JSONB 4.7 sigue thin      |
| TradePlan v1 código           | Targets / R/R / sizing completo                 | Este ADR                         |
| PositionState código          | Dataclass / DTO / persistencia                  | Este ADR                         |
| OCO / broker / auto-exit      | ExecutionPlan + ExitPermission en fases futuras | Este ADR                         |

---

## 10. Freeze vigente (este ADR)

LAB ≠ TRADING · LLM **no** ejecuta · Ranking ≠ BUY · SETUP Wyckoff **cerrada** · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 intactos · `PAPER_D_EXECUTE` **off** · **no** broker · **no** `contract:gen` · **no** mappers nuevos · **no** Alembic en este slice.

C2 Alembic-only y C3–C6 de v1.8.1 **no** implementan PositionState.

---

## 11. Consecuencias

- Un ADR más no compite con `CURRENT_SYSTEM`: este documento fija **contrato v1.9 (modelo)**; el estado vivo sigue en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md). ADR-031 = tres capas de apertura. **Autoridad post-fill** = [ADR-033](./033-operational-authority-position-persistence.md).
- Implementar TradePlan v1 / PositionState / ExitPlan / ExecutionPlan exigió fase propia bajo este ADR. **CERRADO.** No reabrir para campos extra del auditor de discontinuidad.
- El siguiente chat no «continúa wire ExitPermission» ni construye la consola. Siguiente = **H1** honesty pending (roadmap v1.10).
- **ActionIdentity** (v1.9, no Hoy ahora): `instrument + positionId + actionType`. Dedup por `symbol` en Hoy v1.8.1 **intacta**.
- **ActionabilityScore v1** (predictivo) **prohibido** hasta existir Opportunity + Setup + Entry quality + Risk + R/R + Portfolio fit + Freshness + Liquidity. Hoy = ordinal de `status`.
- Conceptos críticos (Spine, TradePlan, AUTO, Hoy, Risk gate): consistencia **CODE + TEST + HELP + ADR**.
