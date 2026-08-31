# Arranque auditor externo — v1.43-beta (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.43-beta` → `5dfac890`** (trail SEMI Confirm→`PositionRevision` `origin=trail`→`currentStop` sobre tip `v1.42-beta` → `5e3fb1a4`).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-43-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-43-beta-2026-08-31.md)
3. [`docs/engineering/traspaso-relevo-v1-43-trail-revision-2026-08-31.md`](./traspaso-relevo-v1-43-trail-revision-2026-08-31.md)
4. [ADR-042](../adr/042-operating-excellence.md) · [`spec-v142-operating-excellence-2026-08-31.md`](./spec-v142-operating-excellence-2026-08-31.md)
5. Previo: [`traspaso-relevo-tag-v1-42-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-42-beta-2026-08-31.md) · [`arranque-auditor-v1-42-beta-2026-08-31.md`](./arranque-auditor-v1-42-beta-2026-08-31.md)

**Preguntas de foco (V1.43 trail durable — no motores nuevos ni broker trail):**

1. ¿Confirm protect con `primaryReason=TRAIL` encola/`PersistPositionFromProtect` con `origin=trail` · reason `trail_confirm`?
2. ¿Hasta Confirm+revision el hint **no** es `currentStop` ni autoridad de CTA?
3. ¿Tras stop = hint: TradeStory / POT / ExecutionState proyectan applied y limpian `trail_hint_not_applied`?
4. ¿GP-08 + honesty #20 SEMI + Journey J05 coherentes con la regla hint≠applied?
5. ¿Freeze intacto: Confirm = firma · `PAPER_D_EXECUTE` off · sin auto-promote · sin thaw LIVE · Spine/Router/propose HTTP/nav L1 intocados?
6. ¿Las 8 preguntas de [`arranque-auditor-v1-42-beta-2026-08-31.md`](./arranque-auditor-v1-42-beta-2026-08-31.md) siguen PASS sobre este tip?
7. ¿Release-tag CI del tip `v1.43-beta` GREEN?

**Deuda aparcada:** auto-promote · broker trailing / OCO · Lab P2 · thaw LIVE · OpportunityScore · segundo Mercado · package bump · `protect_hint` thin como CTA sin Confirm.

**No pedir:** nav L1 nueva · Alembic/tabla nueva · motores nuevos · simulaciones E2E completas de la APP.

---
