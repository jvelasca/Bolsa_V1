# Arranque auditor externo — V1.91 tip (Operational Atomicity) (2026-09-03)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **tip `v1.91-beta`** (cuando exista stamp). Partida **`v1.90-beta` → `0c2e3af7`** (PASS arquitectónico · NO beta PAPER · P1=3). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.91:**

- Atomicidad PositionState + lifecycle_outbox (misma TX); drain post-COMMIT
- LifecycleOutboxWorker continuo (`pending→processing→applied|dead`) + backoff
- Golden HTTP Confirm real OPEN→T1→EXIT→snapshot (sin inyectar PositionSync)
- Requeue `dead→pending` · Mesa `lifecycleStage` en DTO · tipar append response

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `respuesta-auditor-v190` · `spec-v191` · `confirm/position_sync.py` · `lifecycle_outbox.py` · `lifecycle_outbox_worker.py` · `test_lifecycle_golden_v191.py` · OperationalPositionDto · [`relevo`](./traspaso-relevo-v1-91-operational-atomicity-2026-09-03.md).

**Foco:**

1. ¿Confirm HTTP real escribe sidecar en CI (no solo PositionSync inject)?
2. ¿PositionState OK sin outbox es imposible tras commit?
3. ¿Worker repara pending sin reinicio de API?
4. ¿Requeue dead auditado? ¿Mesa sin N+1 snapshot?
5. ¿Freeze intacto? ¿Candidata beta PAPER explotable?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio · unificar ledger.

**Respuesta:** (pendiente — no inventar PASS).

---
