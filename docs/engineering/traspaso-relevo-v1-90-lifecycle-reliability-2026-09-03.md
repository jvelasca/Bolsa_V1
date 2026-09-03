# RELEVO — V1.90 Lifecycle Reliability (2026-09-03)

> **Padre:** [`respuesta-auditor-v189-paper-desk-truth-2026-09-03.md`](./respuesta-auditor-v189-paper-desk-truth-2026-09-03.md).  
> **Spec/plan:** [`spec-v190-lifecycle-reliability-2026-09-03.md`](./spec-v190-lifecycle-reliability-2026-09-03.md) · [`plan-v190-lifecycle-reliability-2026-09-03.md`](./plan-v190-lifecycle-reliability-2026-09-03.md).  
> **Estado:** EN CURSO · partida `v1.89-beta` → `58806be1`.

## Objetivo

Hardening operacional Confirm→Fill→PositionSync→Lifecycle + cable AUTO→sidecar. Sin nuevas features de producto.

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · integrated E2E opt-in

## Entregas

1. Golden Confirm real (OPEN/T1/EXIT/replay) en `lifecycle-pg`
2. Idempotencia estable (sin `now()` en payload)
3. Outbox durable + drain
4. AUTO → AppendLifecycleEvent (tests flag on)
5. SHORT ratchet + reject recommend_short
6. Mesa vocabulario + OpenAPI tipado

## Next tras GREEN

Tag `v1.90-beta` · arranque auditor externo · criterio beta PAPER explotable.
