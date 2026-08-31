# ADR-043: Position Automation — contrato de autorización de posición (V1.44)

**Estado:** Accepted — **contrato**; foundation **CÓDIGO** (2026-08-31; tipos + JIT + Golden Paths). AUTO execute de posiciones **no**.  
**Fecha:** 2026-08-31  
**Contexto:** Auditorías externas post-`v1.43-beta` → `5dfac890`. TRAIL SEMI PASS. Operating Excellence F2–F8 PASS dentro de alcance. AUTO de gestión de posiciones **no certificado**. El siguiente salto no es UI ni inteligencia: es el contrato simétrico a Confirm para que una policy pueda autorizar mutaciones de posición _antes_ de cualquier AUTO.

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md) · [ADR-042](./042-operating-excellence.md) · spec [`spec-v144-position-automation-2026-08-31.md`](../engineering/spec-v144-position-automation-2026-08-31.md).

---

## 1. Decisión

Se acepta el spec V1.44 como **contrato de Position Automation**. Este ADR no cablea ExecutionRouter de posición ni enciende `PAPER_D_EXECUTE`.

```text
ExitPlan (evento)
  → PositionPolicyDecision (qué autoriza la policy *ahora*)
  → ExitPermission JIT (¿se puede hacer *ahora*?)
  → [V1.45] Execution → Fill → PositionRevision
```

SEMI permanece: Proposal → Human Confirm → PositionRevision.

**No** se crean motores: ni PositionEngine2, ni TrailingEngine, ni AutoExitEngine.

Tesis ≠ plan ≠ permiso ≠ ejecución permanece. IA / algoritmo ≠ autoridad. Trail calculado ≠ `currentStop`.

## 2. Objetos (no entidades de persistencia)

| Objeto                   | Rol                     | Relación                                    |
| ------------------------ | ----------------------- | ------------------------------------------- |
| `PositionEvent`          | Evento canónico tipado  | Vista de `ExitReasonV1`                     |
| `PositionPolicyDecision` | Autorización de policy  | Compone `OperatingPolicy` + ExitPlan        |
| `ExitPermission` JIT     | ¿Ahora?                 | Extiende F5; no fusiona con `check_opening` |
| `PositionRevision`       | Historia de stop/status | Ya existe; ≠ Journal ≠ ExecutionRecord      |

`origin=trail` deriva de `ExitReasonV1 === "TRAIL"` (`revisionOriginFromExitReason`), no de un string de UI.

## 3. JIT

Toda autorización AUTO futura re-evalúa el estado **actual** (portfolio, frescura, sesión, recon), no el snapshot del TradePlan. Fail-closed si el contexto JIT se exige y falta. Acción protectora (stop tocado / invalidation) tiene política distinta a T1/TRAIL en dato stale o mercado cerrado.

OR-4 intacto: drift bloquea **entradas**; protective exit ALLOWED.

## 4. T1+T2 mismo tick

Contrato: `TARGET_2` reached no dispara reduce T1 + reduce T2. Ya implementado en `collectReasons`; V1.44 lo fija como Golden Path.

## 5. Versionado

Cinco verdades: product · git tag · package · schema · API. [`versioning.md`](../engineering/versioning.md). Product `V1.44-beta`. Package `1.35.0-beta` congelado. Tip certificado sigue `v1.43-beta` hasta tag explícito.

## 6. Consecuencias

- Spec canónico: [`spec-v144-position-automation-2026-08-31.md`](../engineering/spec-v144-position-automation-2026-08-31.md).
- Plan: [`plan-v144-position-automation-foundation-2026-08-31.md`](../engineering/plan-v144-position-automation-foundation-2026-08-31.md).
- PASS V1.43 (TRAIL SEMI) **no** se reinterpreta como AUTO posición certificado.
- V1.45 = PAPER AUTO position (execute). Lab P2 / OCO / LIVE / broker trail parked.

## 7. Fuera

AUTO execute · auto-promote · Lab P2 · OCO · broker trailing · thaw LIVE · Alembic · bump package · nav L1 · seis estados visuales de Trail · GP-AUTO-01 E2E PAPER.
