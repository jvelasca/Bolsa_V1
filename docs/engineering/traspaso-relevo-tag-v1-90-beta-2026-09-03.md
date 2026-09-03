# RELEVO — tag v1.90-beta → auditoría / beta-paper gate (2026-09-03)

> **Padre:** [`traspaso-relevo-v1-90-lifecycle-reliability-2026-09-03.md`](./traspaso-relevo-v1-90-lifecycle-reliability-2026-09-03.md).  
> **Estado:** tip funcional pendiente CI GREEN tras push del tag.  
> **Partida:** V1.89 PASS arquitectónico [`58806be1`](https://github.com/jvelasca/Bolsa_V1/commit/58806be1) · [`respuesta-auditor-v189`](./respuesta-auditor-v189-paper-desk-truth-2026-09-03.md).

## Release

| Pieza       | Valor                                           |
| ----------- | ----------------------------------------------- |
| Tag tip     | `v1.90-beta` (Lifecycle Reliability)            |
| CI          | Release-tag (incl. lifecycle-pg + golden V1.90) |
| Pre-release | tras push del tag                               |

## Hecho certificado (código)

- Golden Confirm PositionSync → outbox/lifecycle PG → GET snapshot (OPEN/T1/EXIT/replay)
- Idempotencia sin `now()` · outbox durable + drain lifespan
- AUTO → AppendLifecycleEvent (tests flag on; runtime `PAPER_D_EXECUTE` off)
- SHORT trail ratchet · reject `recommend_short` en mapper
- Mesa labels operativos · OpenAPI tipado snapshot

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · integrated E2E opt-in

## Next

Release-tag CI GREEN → stamp SHA en docs · arranque auditor externo tip V1.90 · criterio **beta estable PAPER**.
