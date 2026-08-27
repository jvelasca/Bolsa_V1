# Plan V1.17.1 — Hardening de honestidad

> **AsOf:** 2026-08-27 · **Baseline:** tag `v1.17-beta` (`62ebc4f`).
> **Padre:** [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md) · ADR-038 · ADR-039.
> **Estado:** **batería DoD verde · tag `v1.17.1-beta`** — Spine **495**.
> **Producto:** BETA · Confirm = única firma · AUTO off · `PAPER_D_EXECUTE` off.

## Horizonte

Cerrar mentiras numéricas y huecos AUTO que el pack V1.17 dejó explícitos. No añade Stress Risk, Opportunity Engine ni D1 backtest.

## Entregas

| Fase | Qué cierra                                                                                                                  |
| ---- | --------------------------------------------------------------------------------------------------------------------------- |
| H1   | TradePlan SoT: `candidateRiskR` / notional; `computePositionOpenRiskR` sin fallback 1R                                      |
| H2   | `originalPlan` vs `currentPlan`; `direction` formal; DTO `plannedEntry`/`initialStop`                                       |
| H3   | Unknown sector → warning; `sectorConcentration`                                                                             |
| H4   | Router `sanity_warnings` + `enforce_edge_thresholds` paper_auto (sin `auto_live=True`); `entry_short` → `unsupported_short` |
| H5   | Redis feature cache SHA256 (`bolsa:features:v2:`) + comentario docker-compose DEV ONLY                                      |
| H6   | Mesa refetch data-status + `isError` de portfolio/summary/studies/kill/selfEval                                             |

## Freeze

Confirm · DEX-1…5 · PAPER_D_EXECUTE off · AUTO off · BETA. Scenario ≠ permiso. Ranking ≠ BUY. Stress sigue stub.

## Tests

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario investment-position-aggregate operational-priority mesa-next-action
pnpm --filter @bolsa/web test -- mesa-hoy
python -m pytest packages/py/application/tests/test_execution_router.py packages/py/application/tests/test_execute_gated_portfolio_trade.py packages/py/application/tests/test_decision_spine.py packages/py/analytics/tests/test_cognitive_d1_d3.py packages/py/analytics/tests/test_evidence_engine_d3.py packages/py/infrastructure/tests/test_redis_feature_cache.py packages/py/application/tests/test_decision_journal_studies.py -q
pnpm test:decision-spine
```

## DoD

- Scenario sin `* 10` ni stub 1R; incompleto → `INSUFFICIENT_DATA`
- Study mutado no pisa original plan
- Unknown genera warning
- paper_auto veta split y EdgeReport ausente; `auto_live` sigue False
- Redis rechaza checksum
- Mesa no oculta error de portfolio
- **No tag** hasta aviso owner → **tag `v1.17.1-beta`** al publicar
