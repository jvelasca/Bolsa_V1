# Arranque auditor externo — V1.86 tip (Lifecycle Event Store) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor) **tras** Release-tag CI GREEN:

---

Eres auditor externo de Bolsa V1 **tip `v1.86-beta`**. Producto bajo revisión **`V1.86-beta`** tip funcional **`baaa7034`**. Docs stamp en `main`: **(rellenar tras stamp)**. Partida certificada previa **`v1.85-beta` → `665242a3`** (Release-tag CI GREEN · PASS modelo mock **9,25/10** · **NO** beta estable · P1=5). El tip **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance del stack a auditar (V1.86 = Event Store real + P1-01…05):**

- **V1.85** cerró FSM/mock integrity (base)
- **V1.86** Lifecycle Event Store:
  - ENTRY fill en `POSITION_OPENED` · equity = initial + realized + unrealized
  - Idempotencia estricta (`event_id_conflict`) · CLOSE replay estable
  - Identity envelope · payload económico · trail LONG
  - PostgreSQL `lifecycle_events` append-only · FastAPI POST/GET `/api/lifecycle/*`
  - Job CI `lifecycle-pg` · GP-V186 mock · filtro `+gp-v186`

**Regla absoluta:** **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto. **No** V1.87 integrated · **no** LIVE · **no** unificar ledger/mesa.

**Contexto CI (2026-09-02):** tag `v1.86-beta` → `baaa7034` · Release-tag CI **GREEN** ([run 33686297402](https://github.com/jvelasca/Bolsa_V1/actions/runs/33686297402)). Previo: `v1.85-beta` → `665242a3` ([run 33663836923](https://github.com/jvelasca/Bolsa_V1/actions/runs/33663836923)).

**GitHub (auditor):**

- Código tip: [`v1.86-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.86-beta) → commit `baaa7034`
- Previo: [`v1.85-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.85-beta) → `665242a3`
- Auditoría V1.85 (input): [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-86-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-86-beta-2026-09-02.md)
3. [`respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md`](./respuesta-auditor-v185-lifecycle-integrity-2026-09-02.md)
4. Spec: [`spec-v186-lifecycle-event-store-2026-09-02.md`](./spec-v186-lifecycle-event-store-2026-09-02.md)
5. Workflow: [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) (`lifecycle-pg` · `+gp-v186`)
6. Código: `bolsa_domain/lifecycle` · `lifecycle_event_store.py` · `015_lifecycle_events.py` · `routes/lifecycle.py` · `lifecycle-events.ts` · `gp-v186-*.spec.ts`

**Preguntas de foco:**

1. ¿OPEN debita caja (100000→99000) · CLOSED trail cash/equity 100055 · invariante equity?
2. ¿Mismo eventId + payload distinto → 409 `event_id_conflict` · mismo payload → 200 idempotent (incl. CLOSE con remaining=0)?
3. ¿Identity/payload/trail rechazan corrupción?
4. ¿PG: sesión fresca → mismo snapshot · job `lifecycle-pg` GREEN obligatorio?
5. ¿Freeze intacto · mesa mock no sustituida · no LIVE · no V1.87?

**Deuda aparcada:** V1.87 integrated · LIVE · bump · thaw estricto · unificar ledger.

**No pedir:** LIVE · bump package · Playwright en `frontend-ci` · integrated obligatorio · `PAPER_D_EXECUTE` default on.

**Respuesta auditor:** (pendiente — este arranque es el input; no inventar PASS).

---
