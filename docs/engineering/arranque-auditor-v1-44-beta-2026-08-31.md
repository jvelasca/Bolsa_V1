# Arranque auditor externo — V1.44 Position Automation Contract (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.44 Position Automation Contract** tip **`v1.44-beta` → `57cf41a3`** (foundation sobre tip certificado **`v1.43-beta` → `5dfac890`**). Audita ese tip (o el peeled del tag), no una copia anterior.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-44-position-automation-2026-08-31.md`](./traspaso-relevo-v1-44-position-automation-2026-08-31.md)
3. [`docs/engineering/spec-v144-position-automation-2026-08-31.md`](./spec-v144-position-automation-2026-08-31.md) · [ADR-043](../adr/043-position-automation.md)
4. Previo: [`traspaso-relevo-tag-v1-43-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-43-beta-2026-08-31.md) · [`arranque-auditor-v1-43-beta-2026-08-31.md`](./arranque-auditor-v1-43-beta-2026-08-31.md) · [ADR-042](../adr/042-operating-excellence.md)

**Preguntas de foco (contrato de autorización — no AUTO execute, no motores nuevos):**

1. ¿`decidePositionPolicy` es autorización (HOLD/PROTECT/TRAIL/REDUCE/EXIT + `policyId`/`asOf`) y **no** ejecuta ni llama a ExecutionRouter?
2. ¿Conservador / moderado / `aggressive_swing` salen de `OperatingPolicy.exit` (T1 50/30/0 · T2 100/30/30) sin un segundo motor?
3. ¿JIT `checkExitPermission` con `autoExecute`: stale / mercado cerrado / drift DENY; STOP protectivo ALLOW; SEMI humano intacto (H2)?
4. ¿`requireJitContext` fail-closed si el dato JIT falta en AUTO, y gate off si se omite (compat)?
5. ¿GP-AUTO-01 walk (T1 → reduce revision → TRAIL `origin=trail` → T2 → CLOSED → TradeStory) **sin** submit/Router?
6. ¿Casos malos: UNKNOWN never retry · fill parcial una posición · T1+T2 → solo `TARGET_2` · T1 mercado cerrado → `queue_next_session` · recon drift bloquea entradas y permite protective exit?
7. ¿`revisionOriginFromExitReason` es el único mapeo TRAIL→`origin=trail` (no strings `TRAILING`/`TRAIL_STOP`)?
8. ¿Freeze intacto: Confirm = firma · `PAPER_D_EXECUTE` off · sin auto-promote · sin Lab P2 · money path (`execution_router` / Confirm / `check_opening`) intocado?
9. ¿La documentación dice explícitamente: PASS V1.43 TRAIL SEMI ≠ AUTO de gestión de posiciones certificado ≠ LIVE?

**Deuda aparcada:** AUTO execute posición (V1.45) · Lab P2 · broker trailing / OCO · thaw LIVE · auto-promote · package bump · Alembic · GP-AUTO-01 E2E PAPER · OpportunityScore.

**No pedir:** nav L1 nueva · motores PositionEngine2 / TrailingEngine · cablear Router de posición · encender `PAPER_D_EXECUTE` · simulaciones E2E de la APP.

---
