# ADR-043: Position Automation — contrato de autorización de posición (V1.44)

**Estado:** Accepted — **contrato V1.44** + **execute PAPER V1.45** + **Paper Desk cycle V1.46** + **Runtime Truth V1.47** + **Event Continuity V1.48** + **Entry AUTO V1.49** (auditoría: cableado PASS) + **Entry Decision Integrity V1.50 CÓDIGO** (sin tag). LIVE **no**. `PAPER_D_EXECUTE` default **off**.  
**Fecha:** 2026-08-31  
**Contexto:** Tip `v1.44-beta` → `db346a11` cerró Policy + JIT sin execute. V1.45 cablea orquestador Policy → Permission → protect persist | Router reduce/exit → PositionRevision en PAPER. V1.46 añade `PaperDeskCycle` (EntryTick **stub** + PositionTick) + `autoDesk` — foundation. V1.47 endurece Runtime Truth: `OperationalContext` / MarketSnapshot, GET no muta, mark fail-closed. V1.48 cierra identidad de evento durable (`events[]` / `eventId`), CAS TRAIL, ExecutionSnapshot y Golden Session PAPER. V1.49 cablea EntryTick real (`EstudioPaperDeskEntry` → Estudio rank → TradePlan → `check_opening`). V1.50 transporta `CandidateSnapshot` + reason codes + `template_id` → policy (GP-DESK-04/05/06).

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

**H2 kill switch (intencional):** SEMI humano en desriesgo (protect/reduce/full_exit) **ALLOW** con kill activo. AUTO (`auto_execute=true`) **DENY** `kill_switch` incluso si la acción es protectora. Motivo: el kill declara el sistema no fiable; no se confía en que AUTO calcule un stop o una salida. PaperDeskCycle y HTTP execute-auto inyectan `effective_kill_switch()`; no se deja el flag en `False` por omisión.

OR-4 intacto: drift bloquea **entradas**; protective exit ALLOWED (salvo kill switch AUTO, arriba).

Fill PAPER de un stop protector con mercado cerrado = último close (`last_close`), no precio de apertura. Contrato V1.44; sesgo vs LIVE aparcado a Lab P2.

## 4. T1+T2 mismo tick

Contrato: `TARGET_2` reached no dispara reduce T1 + reduce T2. Ya implementado en `collectReasons`; V1.44 lo fija como Golden Path.

## 5. Versionado

Cinco verdades: product · git tag · package · schema · API. [`versioning.md`](../engineering/versioning.md). Product `V1.50-beta`. Package `1.35.0-beta` congelado. Tip `v1.50-beta` → `96623755` (CI pendiente; previo `v1.49-beta` → `c8975c9d`).

## 6. Consecuencias

- Spec contrato: [`spec-v144-position-automation-2026-08-31.md`](../engineering/spec-v144-position-automation-2026-08-31.md).
- Spec execute: [`spec-v145-paper-auto-position-2026-08-31.md`](../engineering/spec-v145-paper-auto-position-2026-08-31.md).
- Spec desk: [`spec-v146-paper-desk-foundation-2026-08-31.md`](../engineering/spec-v146-paper-desk-foundation-2026-08-31.md) · Runtime Truth [`spec-v147-paper-desk-runtime-truth-2026-09-01.md`](../engineering/spec-v147-paper-desk-runtime-truth-2026-09-01.md) · Event Continuity [`spec-v148-paper-desk-event-continuity-2026-09-01.md`](../engineering/spec-v148-paper-desk-event-continuity-2026-09-01.md) · Entry AUTO [`spec-v149-paper-desk-entry-auto-2026-09-01.md`](../engineering/spec-v149-paper-desk-entry-auto-2026-09-01.md) · Entry Decision Integrity [`spec-v150-entry-decision-integrity-2026-09-01.md`](../engineering/spec-v150-entry-decision-integrity-2026-09-01.md) (**CÓDIGO**, sin tag).
- Plan: [`plan-v145-paper-auto-position-2026-08-31.md`](../engineering/plan-v145-paper-auto-position-2026-08-31.md) · [`plan-v146-paper-desk-foundation-2026-08-31.md`](../engineering/plan-v146-paper-desk-foundation-2026-08-31.md) · [`plan-v147-paper-desk-runtime-truth-2026-09-01.md`](../engineering/plan-v147-paper-desk-runtime-truth-2026-09-01.md) · [`plan-v148-paper-desk-event-continuity-2026-09-01.md`](../engineering/plan-v148-paper-desk-event-continuity-2026-09-01.md) · [`plan-v149-paper-desk-entry-auto-2026-09-01.md`](../engineering/plan-v149-paper-desk-entry-auto-2026-09-01.md) · [`plan-v150-entry-decision-integrity-2026-09-01.md`](../engineering/plan-v150-entry-decision-integrity-2026-09-01.md).
- PASS V1.44 = contrato; PASS V1.45 = execute PAPER opt-in; V1.46 = foundation; V1.47 = Runtime Truth; V1.48 = Event Continuity; V1.49 = Entry AUTO (Estudio, cableado). V1.50 = integridad de decisión (snapshot + GPs) **CÓDIGO**. **No** LIVE · **no** DeskRunner multi-día · Paper-D desk entry **fuera**.

## 7. Fuera

auto-promote · Lab P2 · OCO · broker trailing · thaw LIVE · Alembic · bump package · nav L1 · `PAPER_D_EXECUTE` default on · browser E2E Daily Journal · retrofit Lab como SoT.
