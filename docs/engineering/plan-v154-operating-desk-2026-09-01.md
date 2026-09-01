# Plan — V1.54 Operating Desk

> **Padre:** [`spec-v154-operating-desk-2026-09-01.md`](./spec-v154-operating-desk-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CÓDIGO**.

| ID  | Entrega                                                                          | Estado |
| --- | -------------------------------------------------------------------------------- | ------ |
| D0  | spec/plan/relevo V1.54 + index/CURRENT_SYSTEM/ADR-043                            | DONE   |
| P1  | Shared: `autoDesk` + `CandidateSnapshot` → inbox `EntryOpportunity`              | DONE   |
| P2  | Shared: cubo 🔴 excepciones (birth_failed · recon · UNKNOWN) + GP-DESK-UI-01..06 | DONE   |
| P3  | Web: `mesa-hoy-page` wire `autoDesk` · `daily-desk-inbox` rows                   | DONE   |
| P4  | GP-DESK-UI-07..09 vitest (shared bulk; web smoke mínimo)                         | DONE   |

## Criterios

```bash
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk.test.ts src/daily-desk-auto-projection.test.ts src/cognitive/paper-daily-report.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts
pytest packages/py/application/tests/test_paper_daily_report.py packages/py/application/tests/test_paper_desk_golden_session_estudio.py packages/py/application/tests/test_paper_desk_lifecycle.py -q
uv run ruff check packages/py/application/src/bolsa_application/paper_daily_report.py --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

Pre-flight **GREEN** (shared 27 · web 28 · pytest 17 · ruff · tsc).

## No hacer

Redesign inbox · scheduler · LIVE · bump package · rankingEngineId · browser E2E · backend motor · encender `PAPER_D_EXECUTE` default · CAOS rewrite.
