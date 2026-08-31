# Arranque auditor externo — V1.45 PAPER AUTO position (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.45 PAPER AUTO position execute** tip **`v1.45-beta` → `6ca5ec12`** (sobre tip certificado **`v1.44-beta` → `db346a11`**). Audita ese tip (o el peeled del tag), no una copia anterior.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-45-paper-auto-position-2026-08-31.md`](./traspaso-relevo-v1-45-paper-auto-position-2026-08-31.md)
3. [`docs/engineering/spec-v145-paper-auto-position-2026-08-31.md`](./spec-v145-paper-auto-position-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md)
4. Previo: [`traspaso-relevo-tag-v1-44-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-44-beta-2026-08-31.md) · [`arranque-auditor-v1-44-beta-2026-08-31.md`](./arranque-auditor-v1-44-beta-2026-08-31.md)

**Preguntas de foco:**

1. ¿`ExecutePositionPolicyAuto` hace Policy → JIT Permission **antes** de mutar, y HOLD/DENY no tocan ledger/posición?
2. ¿PROTECT/TRAIL van a `PersistPositionFromProtect` con `revision_origin_from_exit_reason` (TRAIL→trail)?
3. ¿REDUCE/EXIT usan sell PAPER con qty (Router `resolve_exit_sell_quantity`) y luego `PersistPositionFromExit`?
4. ¿`PAPER_D_EXECUTE` off → DENY `paper_auto_env_blocked` / HTTP 403; default repo off?
5. ¿GP-AUTO-01 E2E pytest: T1 reduce → TRAIL → T2 → close remainder → CLOSED?
6. ¿Lab `evaluate-exits` **no** es SoT canónico (sigue intacto / no retrofit obligatorio)?
7. ¿Confirm SEMI / money path aperturas / package `1.35.0-beta` / sin LIVE / sin Alembic / sin auto-promote?
8. ¿HTTP `POST /position-automation/execute-auto` exige env (salvo dryRun) y `executionPolicyId` para reduce/exit?

**Deuda aparcada:** tag v1.45 · browser E2E · Lab retrofit · OCO · thaw LIVE · OpportunityScore.

**No pedir:** nav L1 · flip `PAPER_D_EXECUTE` default on · LIVE · PositionEngine2.

---
