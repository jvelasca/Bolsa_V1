# Plan — Stress Risk MVP (`concurrent_stops_v0`)

> **AsOf:** 2026-08-27 · **Padre:** [ADR-039](../adr/039-portfolio-scenario-operational-priority.md) · [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md).
> **Estado:** MVP cota concurrente stops — sustituye stub `portfolioStressRiskR`.

## Horizonte

Cerrar la mentira del stub Stress con una cota **honesta** y acotada. No es VaR, no modela correlación, no es permiso.

## Entrega

| Pieza                     | Qué                                                                                                                      |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `sumPortfolioStressRiskR` | Suma `computePositionOpenRiskR` solo con cobertura completa (`qty>0` → openRiskR no null); vacío → `0`; parcial → `null` |
| Kind                      | `concurrent_stops_v0`                                                                                                    |
| UI Mesa                   | Chip Stress + fila what-if: número o `—` + tooltip «cota concurrente stops; sin correlación»                             |
| Docs                      | ADR-039 Pending · este plan · CURRENT_SYSTEM                                                                             |

## Freeze

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY.  
Stress **≠** gate de scenario verdict, Priority, Confirm ni AUTO.

## DoD

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario operational-priority mesa-next-action
pnpm --filter @bolsa/web test -- mesa-hoy
```
