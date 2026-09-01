## Summary

External audit stack **V1.52 → V1.54** on tip `v1.54-beta` (`e057a8cc`).

### V1.52 Position Lifecycle

- TargetLeg JSONB + revision enrich (decisionId/policyId)
- Lab execute **DENY** with env on
- GP-EXIT / crash recovery; regresión V1.51 identities

### V1.53 Golden Session

- Pytest GP-SESSION-01..04: Estudio 09:00 → full PAPER session → `PaperDailyReport`
- Reuses V1.48 PositionTick + V1.51 birth + V1.52 legs

### V1.54 Operating Desk

- UI: `autoDesk` → Daily Desk inbox (`EntryOpportunity` thin; **AUTO ≠ COMPRAR**)
- Wire: `PaperDailyReport` `autoDesk.candidates` + `exceptionFacts`
- GP-DESK-UI-01..09; cubo ⚠ excepciones (birth_failed, recon drift, UNKNOWN)

**Partida certificada:** `v1.51-beta` → `5eb8e6de` (audit PASS 9.1). **No LIVE.** `PAPER_D_EXECUTE` default off. Package `1.35.0-beta`.

**Lectura auditor:** `docs/engineering/arranque-auditor-v1-54-beta-2026-09-01.md`
