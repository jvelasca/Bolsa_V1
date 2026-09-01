# Plan — V1.56 Hardening Residuals

> **Padre:** [`spec-v156-hardening-residuals-2026-09-01.md`](./spec-v156-hardening-residuals-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-01.  
> **Estado:** **CERRADO** (2026-09-01) — partida `v1.55-beta` → `c23091d9`.

| ID  | Entrega                                            | Estado |
| --- | -------------------------------------------------- | ------ |
| D0  | spec/plan V1.56                                    | DONE   |
| P0a | GP-SESSION-07e assert + fix ciclo T2 si hace falta | DONE   |
| P0b | GP-SESSION-10r pytest resolve/clear                | DONE   |
| P1  | Playwright GP-E2E-01..02 + script `e2e`            | DONE   |

Local post close-out: pytest **26** (+ GP-SESSION-10r) · tsc OK · `E2E_RUN=1` playwright **2/2** · skip-by-default sin stack.

## Criterios

```bash
pytest packages/py/application/tests/test_paper_desk_golden_session_estudio.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_lifecycle.py packages/py/application/tests/test_paper_daily_report.py -q
pnpm --filter @bolsa/shared exec vitest run src/cognitive/daily-desk.test.ts src/daily-desk-auto-projection.test.ts src/cognitive/paper-daily-report.test.ts src/cognitive/position-operational-view.test.ts src/cognitive/operational-context.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/daily-desk-inbox.test.tsx src/features/mesa/mesa-hoy-page.test.ts src/features/operational-console/operational-console-page.test.tsx
uv run ruff check packages/py/application/src/bolsa_application --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/web e2e
```

## No hacer

LIVE · bump package · encender `PAPER_D_EXECUTE` default · scheduler · Release-tag CI job Playwright · motores nuevos.
