# Arranque auditor externo — V1.88 tip (Integrated Golden) (2026-09-02)

Copia en chat nuevo (auditor) tras Release-tag CI GREEN:

---

Eres auditor externo de Bolsa V1 **tip `v1.88-beta`**. Tip funcional **`33685242`**. Partida **`v1.87-beta` → `646b97ac`** (PASS operacional 9,2/10). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.88:**

- Golden HTTP JWT+PG: OPEN→T1→recon drift→resolve/clear→TRAIL→EXIT→CLOSED
- Restart lifespan: stop API → start API → GET ≡ snapshot (stage/accounting/sequenceNo)
- User B → 403
- CI `lifecycle-pg` incluye golden (Alembic from-zero + auth + golden)

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa.

**CI:** tag `v1.88-beta` → `33685242` · GREEN [run 33691233738](https://github.com/jvelasca/Bolsa_V1/actions/runs/33691233738).  
**Docs stamp:** [`a33c4b93`](https://github.com/jvelasca/Bolsa_V1/commit/a33c4b93) (post-GREEN; no retag).

Lee: `CURRENT_SYSTEM.md` · `traspaso-relevo-tag-v1-88-beta` · `respuesta-auditor-v187` · `spec-v188` · código `test_lifecycle_golden_v188.py` · `lifecycle-pg` job.

**Foco:**

1. ¿Restart real (lifespan) conserva snapshot?
2. ¿Recon drift mid-journey no corrompe lifecycle · recovery permite CLOSED?
3. ¿User B 403 · concurrent T1 intacto?
4. ¿Freeze intacto · candidatura a beta PAPER?
5. ¿Qué falta aún para declarar beta estable explotable?

**No pedir:** LIVE · bump · Playwright frontend-ci obligatorio.

**Respuesta:** (pendiente — no inventar PASS).

---
