# Spec — V1.90 Lifecycle Reliability (2026-09-03)

> **AsOf:** 2026-09-03 · **Estado:** IMPLEMENTADA (pendiente tag CI GREEN).  
> **Padre:** [`respuesta-auditor-v189-paper-desk-truth-2026-09-03.md`](./respuesta-auditor-v189-paper-desk-truth-2026-09-03.md).  
> **Partida tip:** `v1.89-beta` → [`58806be1`](https://github.com/jvelasca/Bolsa_V1/commit/58806be1). **No** LIVE · **no** bump · **no** unificar cash ledger · `PAPER_D_EXECUTE` **off**.

```text
CONFIRM SEMI paper fill OK
  → PositionSync (PositionState)
  → lifecycle_outbox (same TX)
  → drain → AppendLifecycleEvent
  → GET snapshot

AUTO (test / when wired; PAPER_D_EXECUTE still off in runtime)
  → Persist protect|exit
  → same outbox / AppendLifecycleEvent
```

## 0. Freeze

Confirm = firma · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin bump `1.35.0-beta`.  
**No** fusionar accounting lifecycle con cash ledger.  
**No** Playwright obligatorio en `frontend-ci`.

## 1. Entregas

| ID  | Entrega                                                           | Prioridad |
| --- | ----------------------------------------------------------------- | --------- |
| P0  | Golden Confirm PAPER → PositionSync → lifecycle PG → GET snapshot | P0        |
| P0  | Idempotencia: sin `now()`; timestamp de ejecución/ledger          | P0        |
| P0  | Outbox durable + drain/retry (fail-soft sin pérdida)              | P0        |
| P1  | AUTO mapper + hook AppendLifecycleEvent (tests con flag on)       | P1        |
| P1  | SHORT trail ratchet + reject `recommend_short` en mapper Confirm  | P1        |
| P2  | Mesa stage → vocabulario operativo                                | P2        |
| P2  | OpenAPI tipado snapshot + `client.GET`                            | P2        |

## 2. OUT

- LIVE · bump · unificar ledger · `PAPER_D_EXECUTE` on en runtime · T2 parcial SEMI

## 3. Criterio de cierre

CI `lifecycle-pg` demuestra golden V1.88 **y** V1.90 Confirm→sidecar. Outbox repara fail-soft. AUTO test escribe T1/T2/TRAIL/EXIT. Mesa labels + OpenAPI. Freeze checklist verde. **Aún no** declarar «beta PAPER explotable» hasta auditoría tip V1.90.
