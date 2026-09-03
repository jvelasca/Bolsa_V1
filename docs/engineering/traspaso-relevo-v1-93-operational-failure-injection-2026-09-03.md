# RELEVO — V1.93 Operational Failure Injection (2026-09-03)

> **Padre:** [`respuesta-auditor-v192-lifecycle-concurrency-worker-cert-2026-09-03.md`](./respuesta-auditor-v192-lifecycle-concurrency-worker-cert-2026-09-03.md).  
> **Spec/plan:** [`spec-v193-operational-failure-injection-2026-09-03.md`](./spec-v193-operational-failure-injection-2026-09-03.md) · [`plan-v193-operational-failure-injection-2026-09-03.md`](./plan-v193-operational-failure-injection-2026-09-03.md).  
> **Estado:** **CÓDIGO LISTO** · partida tip [`v1.92-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.92-beta) → [`752918ef`](https://github.com/jvelasca/Bolsa_V1/commit/752918ef).

## Objetivo

Certificar fallos operativos del outbox: ventanas de crash durables (claim ≠ append), idempotencia post-crash, reconnect de sesión PG, reconciliación detect/report PositionState↔Lifecycle, más JWT uniforme en stats y README. Sin features de producto.

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · no `queue_sequence` · integrated E2E opt-in

## Entregas

1. Worker: TX1 claim+commit · TX2 append+mark+commit — DONE
2. Tests PG: crash post-claim · mid-append · idempotent reclaim · 3 workers · reconnect · kick∥worker — DONE (10 passed local)
3. `GET /outbox/stats` JWT + SLA ages · `GET /lifecycle/reconciliation` — DONE
4. Consola: SLA + card recon · README tip vivo — DONE

## Next

Tag `v1.93-beta` + CI GREEN + arranque auditor tip. **Sin** LIVE.
