# Arranque auditor externo — V1.50 Entry Decision Integrity (2026-09-01)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **V1.50 Entry Decision Integrity** product **`V1.50-beta`** tip **`96623755`** (previo tip **`v1.49-beta` → `c8975c9d`**). V1.49 cableó EntryTick Estudio. V1.50 transporta la decisión completa (`CandidateSnapshot` + `decisionId` + `reasonCode` + `template_id` → policy) y cierra GP-DESK-04/05/06. **No** Fill→Position (V1.51). **No** LIVE. `PAPER_D_EXECUTE` default **off**.

**Contexto CI (2026-09-01):** tag `v1.50-beta` → `96623755` · Release-tag CI **pendiente al push**. Pre-flight local verde (vitest 7 · pytest 83 desk-block · ruff · tsc).

**GitHub (auditor):**

- Código tip: [`v1.50-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.50-beta) → commit `96623755`
- Docs + arranque (HEAD): rama [`stage/v150-entry-decision-integrity-2026-09-01`](https://github.com/jvelasca/Bolsa_V1/tree/stage/v150-entry-decision-integrity-2026-09-01)
- Previo V1.49: [`v1.49-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.49-beta) → `c8975c9d`

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md`](./traspaso-relevo-v1-50-entry-decision-integrity-2026-09-01.md)
3. [`docs/engineering/spec-v150-entry-decision-integrity-2026-09-01.md`](./spec-v150-entry-decision-integrity-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md)
4. Auditoría padre: [`respuesta-auditor-v149-entry-auto-2026-09-01.md`](./respuesta-auditor-v149-entry-auto-2026-09-01.md)

**Preguntas de foco:**

1. ¿El adapter **transporta** `hits[]` de `ProposeEstudioAutoOpenings` (TradePlan entry/stop/T1/T2/risk) y no solo `proposedCount`?
2. ¿`decisionId` estable por propuesta (`signal.id`)? ¿`reasonCode` + `humanMessage` (no solo `notes` libres)?
3. ¿Ranking canónico (alarma > dictamen + stars) — **sin** motor Composite 9.2? ¿GP-DESK-04: maxCandidates=2 → solo A,B con plan intacto?
4. ¿`template_id` deja de ignorarse (`OperatingPolicy` en EntryTick + `policy_version` al propose)?
5. ¿Empty ≠ unavailable (`ENTRY_UNIVERSE_EMPTY` vs `unavailable` + `ENTRY_UNIVERSE_UNAVAILABLE`)? ¿Infra → `unavailable`, no «0 oportunidades»?
6. ¿GP-DESK-05: TRIGGERED + gate DENY → `executed_count=0`, sin ExecutionIntent (`ENTRY_RISK_LIMIT`)?
7. ¿GP-DESK-06: stop inválido / `no_stop` → skip `ENTRY_INVALID_STOP`, nunca BUY? Ranking ≠ autorización.
8. ¿No se duplica ranking / TradePlan / OpeningGate en PaperDesk?
9. ¿GP-DESK-03 y Golden Session / CAOS V1.48 intactos?
10. ¿Confirm SEMI / package `1.35.0-beta` / sin LIVE / sin Fill→Position / `PAPER_D_EXECUTE` default off?

**Deuda aparcada:** V1.51 Fill→Position · V1.52 Golden Session · UI Mesa · scheduler · LIVE · OCO.

**No pedir:** nav L1 · `PAPER_D_EXECUTE` default on · LIVE · bump package · motor de ranking nuevo.

---
