# Arranque auditor externo — V1.48 Paper Desk Event Continuity (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.48 Paper Desk Event Continuity** product **`V1.48-beta`** tip **`d5852e8d`** (previo tip **`v1.47-beta` → `77f96ead`**). V1.47 es Runtime Truth. V1.48 cierra identidad de eventos, ExecutionTruth y una Golden Session PAPER. **No** AUTO completo: EntryTick sigue **HonestStub**. Audita continuidad operativa, no Entry AUTO ni LIVE.

**Contexto CI (2026-09-01):** tag `v1.48-beta` pusheado → `d5852e8d` · Release-tag CI **GREEN** ([run 33479307015](https://github.com/jvelasca/Bolsa_V1/actions/runs/33479307015)) · pre-flight local verde (vitest 7 · pytest 62 · ruff · tsc).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-48-paper-desk-event-continuity-2026-09-01.md`](./traspaso-relevo-v1-48-paper-desk-event-continuity-2026-09-01.md)
3. [`docs/engineering/spec-v148-paper-desk-event-continuity-2026-09-01.md`](./spec-v148-paper-desk-event-continuity-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md)
4. Previo: [`traspaso-relevo-v1-47-paper-desk-runtime-truth-2026-09-01.md`](./traspaso-relevo-v1-47-paper-desk-runtime-truth-2026-09-01.md)

**Preguntas de foco:**

1. ¿TRAIL V1.47 **no** usaba `positionId|eventType|asOf|sequence|action`? ¿La identidad TRAIL es stop-delta + `events[]` / `eventId`?
2. ¿Dos TRAIL del mismo día (182 luego 185) generan **dos** `eventId` y dos revisiones (CAOS-03)? ¿El mismo TRAIL dos veces = una revisión (CAOS-02)?
3. ¿Dos workers el mismo TRAIL ganan por CAS `current_stop`, no por `if key in set` (CAOS-10)?
4. ¿REDUCE/EXIT reclama evento **antes** del sell y usa `eventId` como `idempotency_key`? ¿Claim `None` → `event_claim_failed` (nunca `positionId`)? ¿REDUCE sin qty → `missing_reduce_quantity` (no vende remaining)?
5. ¿`ExecutionSnapshot` se rellena (submit_intents) y un intent unresolved impide segundo sell (`intent_unresolved`)? ¿Lookup de intents que falla es fail-open (snapshot vacío) con backstop UNIQUE `eventId`?
6. ¿Recon `unavailable` ≠ `drift` (excepción de lookup no finge drift)? ¿Entry fail-closed en ambos? ¿Protective exit ALLOWED **salvo** kill switch AUTO?
7. ¿`status=protected` APPLIED → `nextAction=MONITOR`, no `SUBIR_STOP`? ¿Dry-run TRAIL → `executedAction=DRY_RUN` y `SUBIR_STOP`? ¿`decisionAction` separado?
8. ¿Golden Session: protect → T1 → TRAIL×2 → exit + journal projection? ¿EntryTick sigue HonestStub?
9. ¿PaperDeskCycle y HTTP execute-auto pasan `effective_kill_switch()`? ¿AUTO + kill DENY protect y exit (CAOS kill)?
10. ¿CAOS-07 stale es un test **propio** (no mezclado en CAOS-06)? ¿Crash antes del claim recupera un solo sell? ¿Mark MISSING → `data_unavailable` sin sell?
11. ¿Fill protector con mercado cerrado = último close (contrato V1.44, **no** cola a apertura)? ¿`aggressive_swing` T1 0% = HOLD de diseño?
12. ¿El runtime decide **antes** de persistir `events[]` (dry-run no escribe el log)? ¿`sequence` no entra en el hash?
13. ¿Confirm SEMI / package `1.35.0-beta` / sin LIVE / sin Alembic tabla nueva / sin scheduler / `PAPER_D_EXECUTE` default off?

**Deuda aparcada:** EntryTick Estudio/Paper-D pleno (V1.49) · MarketProfile · freshness matrix · scheduler · UI Mercado · LIVE · OCO.

**No pedir:** nav L1 · `PAPER_D_EXECUTE` default on · LIVE · Entry AUTO real · DeskRunner semanas.

---
