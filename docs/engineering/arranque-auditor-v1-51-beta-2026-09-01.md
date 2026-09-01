# Arranque auditor externo — V1.51 Entry → Fill → Position (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.51 Entry → Paper Fill → Position** product **`V1.51-beta`** tip **`ab6a5bc6`** (previo certificado **`v1.50-beta` → `96623755`**, audit PASS). V1.50 cerró CandidateSnapshot / reason codes / GP-DESK-04/05/06. V1.51 nace **PositionState** tras fill PAPER de apertura AUTO reutilizando OI-1 `PersistPositionFromFill`, con `decisionId` = `signal.id` y `trade_plan_snapshot` enriquecido. **No** Golden Session birth+exit completo (V1.52). **No** UI Mesa. **No** LIVE. `PAPER_D_EXECUTE` default **off**.

**Contexto CI (2026-09-01):** tag `v1.51-beta` → `ab6a5bc6` · Release-tag CI **GREEN** ([run 33492794600](https://github.com/jvelasca/Bolsa_V1/actions/runs/33492794600)) · pre-flight local verde.

**GitHub (auditor):**

- Código tip: [`v1.51-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.51-beta) → commit `ab6a5bc6`
- Rama: [`stage/v151-entry-fill-position-2026-09-01`](https://github.com/jvelasca/Bolsa_V1/tree/stage/v151-entry-fill-position-2026-09-01)
- Previo: [`v1.50-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.50-beta) → `96623755`

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md`](./traspaso-relevo-v1-51-entry-fill-position-2026-09-01.md)
3. [`docs/engineering/spec-v151-entry-fill-position-2026-09-01.md`](./spec-v151-entry-fill-position-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md)
4. Padre V1.50: [`traspaso-relevo-tag-v1-50-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-50-beta-2026-09-01.md)

**Preguntas de foco:**

1. ¿Tras `trade_executed` de apertura `paper_auto` + TradePlan TRIGGERED nace Position vía **mismo** `PersistPositionFromFill` (no segundo factory)?
2. ¿`trade_plan_id` / `decisionId` del snapshot = `signal.id` (alineado a CandidateSnapshot)?
3. ¿El snapshot lleva entry/stop/T1/T2/risk y enrich `templateId`/`autoSource` (sin Alembic)?
4. ¿GP-DESK-07: execute → insert Position; segunda misma `open_transaction_id` no duplica; Gate DENY / `no_tradeplan` → 0 Positions?
5. ¿Fallo de persist **no** revierte el ledger (`trade_executed` + `position_birth_failed`)?
6. ¿DI del Router inyecta el mismo store que Confirm?
7. ¿Protect/reduce/exit / PositionTick V1.48 / GP-DESK-03..06 intactos?
8. ¿Confirm SEMI / package `1.35.0-beta` / sin LIVE / sin UI Mesa / `PAPER_D_EXECUTE` default off?

**Deuda aparcada:** V1.52 Golden Session completa · UI Mesa · scheduler · LIVE · Paper-D desk entry · OCO · package bump.

**No pedir:** nav L1 · `PAPER_D_EXECUTE` default on · LIVE · bump package · segundo motor de ranking · Alembic.

---
