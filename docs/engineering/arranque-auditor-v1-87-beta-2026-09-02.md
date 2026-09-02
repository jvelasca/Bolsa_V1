# Arranque auditor externo — V1.87 tip (Operational Integration) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor) **tras** Release-tag CI GREEN:

---

Eres auditor externo de Bolsa V1 **tip `v1.87-beta`**. Producto bajo revisión **`V1.87-beta`** tip funcional **`646b97ac`**. Partida certificada previa **`v1.86-beta` → `baaa7034`** (Release-tag CI GREEN · arquitectura **9,0/10** · explotable **7,5/10** · **NO** beta estable · P0 auth HTTP · P1 sequence/Alembic/DTO). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.87 = Auth + Concurrency + Alembic real):**

- **V1.86** cerró Event Store PG + ENTRY accounting (base)
- **V1.87** Operational Integration:
  - JWT obligatorio en POST/GET `/api/lifecycle/*` · ownership account/position → 401/403/404
  - `sequence_no` + `lifecycle_aggregates` FOR UPDATE · `UNIQUE(position_id, sequence_no)` · ORDER BY sequence
  - Alembic 015 ensure-indexes · 016 sequence · job `lifecycle-pg` hace `upgrade head` (sin `metadata.create`)
  - DTO `extra="forbid"` · Decimal domain→DB · IntegrityError (`fill_id` ≠ `event_id`)
  - Tests: concurrent append · auth isolation · migration-from-zero

**Regla absoluta:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto. **No** V1.88 golden integrado obligatorio · **no** LIVE · **no** unificar ledger/mesa.

**Contexto CI (2026-09-02):** tag `v1.87-beta` → `646b97ac` · Release-tag CI **GREEN** ([run 33689747400](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400)). Previo: `v1.86-beta` → `baaa7034` ([run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402)).

**GitHub (auditor):**

- Código tip: [`v1.87-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.87-beta) → commit `646b97ac`
- Previo: [`v1.86-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta) → `baaa7034`
- Auditoría V1.86 (input): [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-87-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-87-beta-2026-09-02.md)
3. [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md)
4. Spec: [`spec-v187-lifecycle-operational-certification-2026-09-02.md`](./spec-v187-lifecycle-operational-certification-2026-09-02.md)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) (`lifecycle-pg` con `alembic upgrade head`)
6. Código: `routes/lifecycle.py` · `request_principal.py` · `lifecycle_event_store.py` · `016_lifecycle_sequence.py` · `015_lifecycle_events.py` · `bolsa_domain/lifecycle`

**Preguntas de foco:**

1. ¿Sin JWT → 401 · dueño OK · ajeno → 403 · `accountId` no es autoridad?
2. ¿Dos T1 concurrentes → exactamente uno · `sequence_no` determinista · ORDER BY sequence?
3. ¿`lifecycle-pg` certifica Alembic from-zero (no `metadata.create`) · head 016?
4. ¿Typo DTO (`quanity`) → 422 · Decimal end-to-end · fill_id UNIQUE ≠ event_id_conflict?
5. ¿Freeze intacto · mesa mock no sustituida · no LIVE · no V1.88?

**Deuda aparcada:** V1.88 golden integrado + restart API + recon · LIVE · bump · thaw estricto · unificar ledger · `last_price_for_stage` producción.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
