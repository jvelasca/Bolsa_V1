# Respuesta auditor — V1.91 (Operational Atomicity) (2026-09-03)

> **Padre:** [`arranque-auditor-v1-91-operational-atomicity-2026-09-03.md`](./arranque-auditor-v1-91-operational-atomicity-2026-09-03.md) · [`traspaso-relevo-tag-v1-91-beta-2026-09-03.md`](./traspaso-relevo-tag-v1-91-beta-2026-09-03.md).  
> **Tip auditado:** `v1.91-beta` → [`4644fef9`](https://github.com/jvelasca/Bolsa_V1/commit/4644fef9) · CI GREEN [run 33748255004](https://github.com/jvelasca/Bolsa_V1/actions/runs/33748255004).  
> **Partida:** V1.90 PASS arquitectónico [`0c2e3af7`](https://github.com/jvelasca/Bolsa_V1/commit/0c2e3af7) · [`respuesta-auditor-v190`](./respuesta-auditor-v190-lifecycle-reliability-2026-09-03.md).

## Veredicto

**V1.91 = PASS arquitectónico fuerte · ~9,1–9,6/10 por área** · **P0 = 0** · **P1 = 2** · **P2 = 4** · **explotabilidad beta PAPER = NO todavía** (falta certificación worker real + orden multi-worker).

Cierra los tres P1 de V1.90: atomicidad PositionState+Outbox misma TX, LifecycleOutboxWorker continuo, Golden Confirm HTTP real OPEN→T1→EXIT. Requeue dead, Mesa sin N+1 y tipado append DTO también PASS.

## Hallazgos aceptados

### P1 (bloquean beta PAPER definitivo)

1. **CI no certifica el LifecycleOutboxWorker real** — Golden V1.91 hace drain manual («worker not in ASGI test»); unitarios prueban `claim_batch`/`mark_*` pero no `start_lifecycle_outbox_worker()` ni el loop con PostgreSQL. Riesgo: `scheduler_worker` no arranca el worker y CI no lo detecta.
2. **Carrera multi-worker por posición** — `FOR UPDATE SKIP LOCKED` bloquea filas, no posiciones. Worker A puede reclamar T1 y Worker B EXIT de la misma posición → FSM `time_regression`/`illegal_transition` → `dead` sin fallo del fill. Solución preferida: claim con máximo 1 evento por `position_id` (cabeza de cola FIFO).

### P2

3. Aserción débil Golden: `errors == 0 or applied >= 0` (segunda rama siempre verdadera).
4. Replay OPEN no afirma explícitamente no-segundo-`transactionId` / no-segundo-broker.
5. Faltan métricas operativas outbox (`pending`/`processing`/`dead`/`oldest_pending_age`) en Consola.
6. Documentación global / tip audit stamp (CURRENT_SYSTEM ya refleja V1.91 en working tree; gap era tip vs docs stamp).

### Verificado (PASS)

- Atomicidad PositionState+Outbox · flush sin commit interior · enqueue no swallow · worker continuo + SKIP LOCKED + stale reclaim 120s + backoff · Golden Confirm HTTP · requeue dead ownership · Mesa `lifecycleStage` · append DTO tipado · AUTO sidecar sin autoridad · Ledger ≠ Lifecycle · JWT/ownership · CI GREEN (lifecycle-pg incluido).

## Freeze verificado

Confirm = firma · `PAPER_D_EXECUTE` off · **no LIVE** · package `1.35.0-beta` · sin unificar ledger · integrated E2E opt-in.

## Next

**V1.92 — Lifecycle Concurrency & Worker Certification** · FIFO claim por posición · certificar worker real PG · crash/stale reclaim · aserción Golden · métricas outbox Consola · **sin** features de producto · **sin** LIVE · **sin** bump · **sin** `PAPER_D_EXECUTE` on.
