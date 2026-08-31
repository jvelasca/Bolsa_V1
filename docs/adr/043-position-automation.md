# ADR-043: Position Automation — contrato de autorización de posición (V1.44)

**Estado:** Accepted — **contrato V1.44** + **execute PAPER V1.45** (2026-08-31). LIVE **no**. `PAPER_D_EXECUTE` default **off**.  
**Fecha:** 2026-08-31  
**Contexto:** Tip `v1.44-beta` → `db346a11` cerró Policy + JIT sin execute. V1.45 cablea orquestador Policy → Permission → protect persist | Router reduce/exit → PositionRevision en PAPER.

**Depende de:** [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md) · [ADR-042](./042-operating-excellence.md) · spec [`spec-v144-position-automation-2026-08-31.md`](../engineering/spec-v144-position-automation-2026-08-31.md) · [`spec-v145-paper-auto-position-2026-08-31.md`](../engineering/spec-v145-paper-auto-position-2026-08-31.md).

---

## 1. Decisión

Se acepta el spec V1.44 como **contrato** y el spec V1.45 como **execute PAPER** (orquestador canónico; Lab `evaluate-exits` no es SoT). No se enciende `PAPER_D_EXECUTE` por defecto.

```text
ExitPlan (evento)
  → PositionPolicyDecision (qué autoriza la policy *ahora*)
  → ExitPermission JIT (¿se puede hacer *ahora*?)
  → Execution PAPER (protect persist | Router reduce/exit) → Fill → PositionRevision
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

Cinco verdades: product · git tag · package · schema · API. [`versioning.md`](../engineering/versioning.md). Product `V1.45-beta`. Package `1.35.0-beta` congelado. Tip certificado sigue `v1.44-beta` → `db346a11` hasta tag `v1.45-beta`.

## 6. Consecuencias

- Spec contrato: [`spec-v144-position-automation-2026-08-31.md`](../engineering/spec-v144-position-automation-2026-08-31.md).
- Spec execute: [`spec-v145-paper-auto-position-2026-08-31.md`](../engineering/spec-v145-paper-auto-position-2026-08-31.md).
- Plan: [`plan-v145-paper-auto-position-2026-08-31.md`](../engineering/plan-v145-paper-auto-position-2026-08-31.md).
- PASS V1.44 = contrato; PASS V1.45 = execute PAPER opt-in. **No** LIVE.

## 7. Fuera

auto-promote · Lab P2 · OCO · broker trailing · thaw LIVE · Alembic · bump package · nav L1 · `PAPER_D_EXECUTE` default on · browser E2E Daily Journal · retrofit Lab como SoT.
