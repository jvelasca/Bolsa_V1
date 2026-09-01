# Plan — V1.55 Operational Hardening

> **Padre:** [`spec-v155-operational-hardening-2026-09-01.md`](./spec-v155-operational-hardening-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CERRADO** — tag `v1.55-beta` → `c23091d9` · [cierre-apertura](./traspaso-relevo-cierre-v155-apertura-siguiente-2026-09-01.md).

| ID  | Entrega                                           | Estado |
| --- | ------------------------------------------------- | ------ |
| D0  | spec/plan/relevo V1.55 + CURRENT_SYSTEM + ADR-043 | DONE   |
| P0a | GP-SESSION-01..04 invariantes                     | DONE   |
| P0b | GP-SESSION-05..10                                 | DONE   |
| P0c | GP-GOLDEN-DAY-01                                  | DONE   |
| P1  | PositionOperationalView + stopHistory + eventos   | DONE   |
| P2a | PaperDailyReport secciones                        | DONE   |
| P2b | Mesa 5 cubos + Consola + CTA única                | DONE   |

## Criterios

```bash
pytest packages/py/application/tests/test_paper_desk_golden_session_estudio.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_lifecycle.py packages/py/application/tests/test_paper_daily_report.py -q
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk.test.ts src/daily-desk-auto-projection.test.ts src/cognitive/paper-daily-report.test.ts src/cognitive/position-operational-view.test.ts src/cognitive/operational-context.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts src/features/operational-console/operational-console-page.test.tsx
uv run ruff check packages/py/application/src/bolsa_application --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

## No hacer

LIVE · bump package · encender `PAPER_D_EXECUTE` default · scheduler · browser E2E · motores nuevos.
