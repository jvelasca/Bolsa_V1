# Arranque auditor externo — V1.90 tip (Lifecycle Reliability) (2026-09-03)

Copia en chat nuevo (auditor) tras Release-tag CI GREEN:

---

Eres auditor externo de Bolsa V1 **tip `v1.90-beta`**. Partida **`v1.89-beta` → `58806be1`** (PASS arquitectónico · NO beta PAPER). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.90:**

- Golden Confirm PAPER → PositionSync → outbox/lifecycle PG → GET snapshot (OPEN/T1/EXIT + replay)
- Idempotencia sin `now()`; timestamp de ejecución
- Outbox durable (fail-soft sin pérdida)
- AUTO escribe sidecar (tests con flag on; runtime flag off)
- SHORT trail ratchet + reject `recommend_short` en mapper
- Mesa labels operativos · OpenAPI tipado snapshot

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `respuesta-auditor-v189` · `spec-v190` · `lifecycle_from_fill.py` · `lifecycle_from_auto.py` · `confirm/position_sync.py` · `test_lifecycle_golden_v190.py` · mesa-position-row · openapi lifecycle snapshot.

**Foco:**

1. ¿Confirm real escribe sidecar en CI (no solo POST /events)?
2. ¿Replay sin filled_at es idempotent?
3. ¿Outbox repara PositionState OK + lifecycle fail?
4. ¿AUTO test deja rastro T1/T2/TRAIL/EXIT?
5. ¿Freeze intacto? ¿Candidata beta PAPER explotable?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio · unificar ledger.

**Respuesta:** (pendiente — no inventar PASS).

---
