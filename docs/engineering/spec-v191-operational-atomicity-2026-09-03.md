# Spec — V1.91 Operational Atomicity & Full Confirm Golden (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tag [`v1.91-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.91-beta) → [`4644fef9`](https://github.com/jvelasca/Bolsa_V1/commit/4644fef9) · [run 33748255004](https://github.com/jvelasca/Bolsa_V1/actions/runs/33748255004) **success**.  
> **Padre:** [`respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md`](./respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md).  
> **Partida tip:** `v1.90-beta` → [`0c2e3af7`](https://github.com/jvelasca/Bolsa_V1/commit/0c2e3af7). **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
CONFIRM SEMI paper fill OK
  → PositionState + lifecycle_outbox (SAME TX / COMMIT)
  → drain post-commit (kick) + LifecycleOutboxWorker
  → AppendLifecycleEvent
  → GET snapshot

Golden V1.91 (HTTP):
  Recommendation TRIGGERED
    → ConfirmRecommendationIntent execute=true
    → PAPER ExecuteTrade → transactionId
    → PositionSync (no inject)
    → Outbox → Lifecycle → Snapshot
  OPEN → T1 → EXIT · replay · User B 403
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** Playwright obligatorio en `frontend-ci`.  
AUTO preparado, **no** activado por defecto.

## 1. Entregas

| ID  | Entrega                                                             | Prioridad |
| --- | ------------------------------------------------------------------- | --------- |
| P1  | Atomicidad PositionState + Outbox (misma TX); drain post-COMMIT     | P1        |
| P1  | LifecycleOutboxWorker continuo (`pending→processing→applied\|dead`) | P1        |
| P1  | Golden HTTP Confirm real OPEN→T1→EXIT en `lifecycle-pg`             | P1        |
| P2  | Requeue administrativo `dead→pending`                               | P2        |
| P2  | Mesa: `lifecycleStage` en OperationalPositionDto (mata N+1)         | P2        |
| P2  | Tipar `LifecycleAppendResponseDto` sin `dict[str, Any]`             | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on · timestamp AUTO fill-time · T2_TRIGGERED real-only · Playwright frontend-ci obligatorio

## 3. Criterio de cierre

CI `lifecycle-pg` demuestra golden V1.88 + V1.90 + **V1.91 Confirm HTTP**. Atomicidad: no PositionState sin outbox. Worker repara `pending` sin reinicio. Freeze verde. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.91.
