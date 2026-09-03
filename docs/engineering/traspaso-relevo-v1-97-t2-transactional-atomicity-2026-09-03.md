# RELEVO — V1.97 T2 Transactional Atomicity (2026-09-03)

> **Padre:** [`respuesta-auditor-v196-final-beta-certification-2026-09-03.md`](./respuesta-auditor-v196-final-beta-certification-2026-09-03.md).  
> **Spec/plan:** [`spec-v197-t2-transactional-atomicity-2026-09-03.md`](./spec-v197-t2-transactional-atomicity-2026-09-03.md) · [`plan-v197-t2-transactional-atomicity-2026-09-03.md`](./plan-v197-t2-transactional-atomicity-2026-09-03.md).  
> **Estado:** **ABIERTA** · candidata tip `v1.97-beta`.  
> **Partida:** tip [`v1.96-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.96-beta) → [`30479e97`](https://github.com/jvelasca/Bolsa_V1/commit/30479e97) · [run 33808076820](https://github.com/jvelasca/Bolsa_V1/actions/runs/33808076820).

## Objetivo

Cerrar los 2 P2 de V1.96: atomicidad del par T2_TRIGGERED+T2_EXECUTED + certificación crash/replay + stamp documental en el tip.

## Freeze

NO LIVE · no bump · `PAPER_D_EXECUTE` off · no unificar ledger · no `queue_sequence` · no heartbeat · no auto-heal · integrated E2E opt-in

## Entregas

1. `append_many` + un savepoint para el par T2 — DONE
2. `AppendLifecycleEvent` inserta el par desde `t1_executed` (SEMI + AUTO + outbox) — DONE
3. Batería crash mid-pair / retry (unit + PG store + worker) — DONE
4. CURRENT_SYSTEM + tag sobre stamp — DOING

## Next

Tras CI GREEN: stamp SHA/run · tag `v1.97-beta` · arranque auditor. **Sin** LIVE. Después: Beta Stabilization (no arquitectura nueva).
