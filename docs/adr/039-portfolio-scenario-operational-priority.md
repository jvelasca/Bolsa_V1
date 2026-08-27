# ADR-039 — PortfolioScenario + OperationalPriority

> **Status:** Accepted (post AUDITORIA 1) · **AsOf:** 2026-08-27

## Context

V1.19 entregó ranking heurístico y what-if aditivo. AUDITORIA 1 exige separar semántica de riesgo y evitar que heurísticas se conviertan en score definitivo.

## Decision

### Métricas de cartera (P0)

- `portfolioPnLR` — P&L no realizado en R (suma `unrealizedR`).
- `portfolioOpenRiskR` — R en riesgo si stops actuales se ejecutan.
- `portfolioStressRiskR` — cota concurrente stops (`concurrent_stops_v0`); stub de correlación/VaR retirado.
- `portfolioRiskLimitR` — desde perfil/mandato, no hardcoded en UI.

### Operational Priority (Fase B)

Tres ejes antes de un score único:

1. **Quality** — calidad de la oportunidad
2. **Suitability** — encaje con cartera/mandato
3. **Operability** — ejecutable ahora

La heurística legacy (`scoreOperationalPriorityProjection`) queda explícitamente como **orden provisional**.

### Portfolio Scenario (Fase C)

Dominio read-only `PortfolioScenario`:

- ACTUAL / DESPUÉS: exposición, open risk, sector, concentración, mandato, portfolio fit
- Veredicto: `COMPATIBLE` | `NO_RECOMENDADA`
- Sin ejecución — preview antes de Confirm

### Unified Alerts (Fase D)

Inbox único: `MARKET | DECISION | POSITION | RISK | SYSTEM` sobre alertas existentes + agregados.

## Consequences

- [`operational-priority.ts`](../../packages/shared/src/cognitive/operational-priority.ts)
- [`portfolio-scenario.ts`](../../packages/shared/src/cognitive/portfolio-scenario.ts)
- [`unified-alerts.ts`](../../packages/shared/src/cognitive/unified-alerts.ts)
- What-if UI evoluciona a tabla scenario, no suma naive.
- **V1.17.1:** sizing del candidato = TradePlan (`initialRiskR` / `quantity` × distancia / `positionValue`). Sin stub 1R ni notional `* 10`. `sectorConcentration` (HHI sectorial). Unknown sector = warning de dato, no cero.

## Pending

- Correlación / VaR / stress de régimen (fase posterior) — MVP actual = `concurrent_stops_v0` (suma openRiskR con cobertura completa; ≠ VaR, ≠ correlación). Stress **no** gatea scenario verdict, Priority, Confirm ni AUTO.
- Endpoint read-only backend para scenario (opcional)
- Opportunity Engine / best next R
