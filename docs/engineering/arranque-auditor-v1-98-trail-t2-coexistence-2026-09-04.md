# Arranque auditor externo — V1.98 tip (trail + T2 coexistence) (2026-09-04)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato `v1.98-beta` → `7b5b1052`** (partida **`v1.97-beta` → `2e9d4675`** · push CI **GREEN** Python/Frontend/Gitleaks · feature trail+T2). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.98 (alinear FSM con ExitPolicy, no arquitectura nueva):**

- Trail + T2 **conviven** tras T1: N ratchets en `trailing`, `trailing`→`T2_TRIGGERED`, `t2_executed`→`TRAIL_APPLIED`
- `t2_ready` puede `POSITION_CLOSED` (recovery); `t2_ready`+trail sigue ilegal
- Geometría TRAIL vs **último fill**, no mark mock 106/110
- `needs_atomic_t2_pair` también desde `trailing`
- `stop_worsens` única en dominio; analytics delegan
- Sync TS mock + SHORT trail_relaxation
- Sin Alembic nuevo (sigue `019`)

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `spec-v198` · `bolsa_domain/lifecycle/__init__.py` (`TRANSITIONS`, `last_fill_price`, `stop_worsens`) · `lifecycle_t2_bridge.py` · `apps/web/e2e/helpers/lifecycle-events.ts` · `test_lifecycle_events.py` · `test_lifecycle_t2_atomicity_v197.py` (test trailing) · [`relevo`](./traspaso-relevo-v1-98-trail-t2-coexistence-2026-09-04.md).

**Foco:**

1. ¿Tras `TRAIL_APPLIED` un `TARGET_2` puede registrar `T2_TRIGGERED`+`T2_EXECUTED` atómicos?
2. ¿2º ratchet no deja `illegal_transition` / `dead_head`?
3. ¿Trail con `newStop=220` y último fill `230` pasa (mock 106 no bloquea)?
4. ¿Helper e2e SHORT trail_relaxation simétrico al kernel Python?
5. ¿Freeze intacto? ¿SEMI protect→TRAIL sigue residual (no cableado)?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio · unificar ledger · SEMI protect sidecar · open→T2 · LineagePath flags · V1.99 por inercia.

**Respuesta:** (pendiente — no inventar PASS).

---
