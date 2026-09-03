# Arranque auditor externo — V1.97 tip (T2 transactional atomicity) (2026-09-03)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato `v1.97-beta` → `363dfcea`** (partida **`v1.96-beta` → `30479e97`** · Python CI **GREEN** [run 33811212221](https://github.com/jvelasca/Bolsa_V1/actions/runs/33811212221) · V1.96 = PASS P0=0 P1=0 · BETA PAPER técnicamente certificada). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.97 (endurecimiento T2, no arquitectura nueva):**

- Par atómico `T2_TRIGGERED` + `T2_EXECUTED` en un solo `begin_nested` / `append_many`
- Validación en memoria de ambos antes de persistir
- Crash mid-pair → rollback del par → retry → exactamente 1+1 eventos, 1 fill, 1 revision, 0 doble submit
- Recovery desde `t2_ready` (leftover): solo `T2_EXECUTED`
- Sin Alembic nuevo (sigue `019`)
- Tag = SHA con stamp documental
- Detect/report; **no** auto-heal

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `respuesta-auditor-v196` · `spec-v197` · `lifecycle_t2_bridge.py` · `lifecycle_event_store.py` · `test_lifecycle_t2_atomicity_v197.py` · `test_lifecycle_event_store_pg.py` (T2 mid-pair) · `test_lifecycle_outbox_worker_pg.py` (T2 reclaim) · [`relevo`](./traspaso-relevo-v1-97-t2-transactional-atomicity-2026-09-03.md).

**Foco:**

1. ¿CI del commit candidato es GREEN (Ruff + Typecheck + lifecycle-pg con crash mid-pair T2)?
2. ¿Imposible (bajo inject) dejar `T2_TRIGGERED` sin `T2_EXECUTED` tras COMMIT?
3. ¿Retry tras crash → 1 trigger + 1 execute + idempotencia Confirm TARGET_2?
4. ¿Freeze intacto? ¿Tag = stamp?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio · unificar ledger · queue_sequence · auto-heal · E2E integrado en esta rebanada · V1.98 por inercia.

**Respuesta:** (pendiente — no inventar PASS).

---
