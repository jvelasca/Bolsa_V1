# ADR-032: Operational Core — TradePlan / PositionState / Execution (contrato v1.9)

**Estado:** Proposed/Accepted **docs-only** para v1.9 (**no implementado**)  
**Fecha:** 2026-08-25  
**Contexto:** Tras ADR-031 (tesis ≠ plan ≠ permiso) y la consolidación v1.8.1, el crecimiento thin 5.x/8.x ya no es el camino. Falta el **contrato** del núcleo operativo post-entrada, sin código, sin mappers nuevos, sin `contract:gen`.

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
| **Después**      | `ExitPlan`        | Si ocurre Y, ¿cómo salimos / protegemos? | Parked (no mapper thin aislado)                   |
| **Después**      | `ExitPermission`  | ¿Podemos salir / mutar stop ahora?       | Parked (`EvaluatePositionExits` ≠ producto)       |
| **Envío futuro** | `ExecutionPlan`   | ¿Cómo se envía al broker / paper?        | Parked (no OCO ahora)                             |

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

### 2.2 v1 (parked — no implementar)

Cuando una **fase propia** lo abra, el crecimiento entra **dentro** de TradePlan, no en un mapper hermano:

- `target1` / `target2`
- R/R explícito
- sizing completo: cash, lote, liquidez, cartera (no solo `risk_amount / (entry − stop)`)

**No** en v1 por defecto: trailing broker, OCO, `wyckoffPhase` en contrato, Alembic Wyckoff.

---

## 3. PositionState — «qué ocurre tras entrar»

**Lista de contrato**, no dataclass, no mapper, no tabla.

Campos canónicos (nombres de intención; shape FE/BE se decide en la fase de implementación):

| Campo          | Intención                                             |
| -------------- | ----------------------------------------------------- |
| `entry`        | Precio / zona de entrada materializada                |
| `current`      | Precio / mark actual                                  |
| `initialRisk`  | 1R al entrar (`\|entry − structuralStop\|`)           |
| `currentR`     | R abierto ahora                                       |
| `MFE` / `MAE`  | Excursión favorable / adversa (reales, no solo proxy) |
| `thesisHealth` | Salud de la tesis **con** posición abierta            |
| `protection`   | Protección (stop de protect, BE, reduce)              |
| `target`       | Objetivos vivos (T1/T2) una vez dentro                |
| `trailing`     | Trail / ratchet **de posición**, no del plan previo   |
| `exit status`  | Estado de salida (none / hint / armed / done)         |

Hoy, los bloques `runtime.thesisHealth` / `protectPlan` / `exitRadar` / `mfeMae` / `expectancy` / `trailPlan` / `bracketPlan` (ciclos **5.0–5.3** y **8.0–8.2**) son **stand-in advisory**. **No** son la arquitectura final de PositionState. No mutan `structuralStop`. No son permiso. No se «promueven» a núcleo copiando el mapper thin.

---

## 4. ExitPlan · ExitPermission · ExecutionPlan

- **`ExitPlan`:** plan condicional de salida (simétrico a TradePlan, **después** de entrar). Crece **aquí** cuando arranque la fase — no como `map_exit_plan` aislado hoy.
- **`ExitPermission`:** veto de salida / mutación de stop. Distinto de `check_opening` (apertura). RX1 / `EvaluatePositionExits` con `executeTrades=true` **no** son el producto auto-exit.
- **`ExecutionPlan`:** camino de **envío** futuro (paper / broker). **No** OCO ahora. **No** `PAPER_D_EXECUTE` on. **No** broker live.

Cadena post-entrada completa = PositionState → ExitPlan → ExitPermission → Execution. Ningún eslabón se implementa en este ADR.

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

- Un ADR más no compite con `CURRENT_SYSTEM`: este documento fija **contrato v1.9**; el estado vivo sigue en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md). ADR-031 sigue siendo la política de las **tres capas de apertura**.
- Implementar TradePlan v1 / PositionState / ExitPlan / ExecutionPlan exige **fase propia** (plan D1–D8) que cite este ADR. Hasta entonces: cero runtime.
- El siguiente chat no «continúa 8.3». El siguiente crecimiento de modelo es **dentro** de los objetos de §1–§4, no un thin más.
