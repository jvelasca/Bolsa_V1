# Plan V1.17–V1.21 — Sesión operativa diaria (post AUDITORIA 1 + 2)

> **AsOf:** 2026-08-27 · **Baseline:** `main` post `v1.16-beta` (`f16119b`).
> **Padre:** ADR-037 · ADR-038 · ADR-039 · [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md).
> **Estado:** **CERRADO — tag `v1.17-beta`** (sesión operativa diaria). Pendiente CI GREEN + triage auditor externo.
> **Producto:** BETA · Confirm = única firma · AUTO off · `PAPER_D_EXECUTE` off.

## Horizonte (qué manda)

El ciclo convierte el SEMI diario en una sesión de ~20 segundos: **qué ocurre → qué hago con MIS posiciones → qué podría hacer → ¿encaja? → scenario → Confirm**.

No es paper_auto, no es Lab, no es backtest. Freeze V1.16 intacto (DEX/OR/Confirm core; no `GET /api/mesa/today`).

## Fases de este ciclo

| Fase | Entrega                                                                                               | Estado    |
| ---- | ----------------------------------------------------------------------------------------------------- | --------- |
| P0   | `instrument_data_status` en `ExecuteGatedPortfolioTrade` (HTTP buy = mismo sanity que Confirm/Fill)   | **Hecho** |
| F1   | Mesa 3 niveles (ocurre / debo / podría); header duplicado fusionado; `aria-live="polite"` en atención | **Hecho** |
| F2   | Suitability real: `candidateSector` + `sectorExposurePct` → veredicto **NO OPERAR** visible           | **Hecho** |
| F3   | Scenario ACTUAL/DESPUÉS con posiciones, open risk, sector, límite mandato; copy **no permiso**        | **Hecho** |
| F4   | `InvestmentPositionAggregate` + ruta viva en Libro `/operations`                                      | **Hecho** |

## Freeze (intacto)

Confirm · DEX-1…5 · OR · PAPER_D_EXECUTE off · AUTO off · BETA. No dry-run `check_opening` HTTP. Stress/correlación sigue stub.

## Backlog AUTO (explícito — no este ciclo)

Caminos que **no** tocan la sesión diaria. Reabrir solo cuando el producto sea automatización:

| Hallazgo AUDITORIA 2                                        | Por qué no ahora                                                              |
| ----------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `execution_router.py` `check_opening` sin `sanity_warnings` | AUTO / paper_auto; AUTO off                                                   |
| EdgeReport no veta `paper_auto`                             | AUTO; `auto_live=False` es honesto                                            |
| Redis pickle sin SHA256                                     | caché ML Lab                                                                  |
| Backtest ≠ TradingPolicy                                    | Lab / estrategia — impacto alto **antes de AUTO**, no antes de la mesa de hoy |

## Tests mínimos

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics data-freshness investment-position-aggregate operational-priority portfolio-scenario mesa-next-action mesa-operable-ranking
pnpm --filter @bolsa/web test -- mesa-hoy
python -m pytest packages/py/application/tests/test_opening_permission.py packages/py/application/tests/test_execute_gated_portfolio_trade.py -q
```

## DoD (antes de pedir auditoría)

- HTTP buy veta sanity split/dividendo; gap-only no veta
- Mesa responde las 3 preguntas sin stack de 8 tarjetas equivalentes
- NVDA quality alta + sector saturado → NO OPERAR
- Scenario ACTUAL/DESPUÉS con open risk de mandato; copy no-permiso
- Libro muestra ruta viva; Next Action sale del agregado
- Confirm/DEX diff vacío salvo DI `instrument_data_status` en HTTP trade
- **No tag** hasta aviso owner

## Relevos

- P0: [`traspaso-relevo-sesion-operativa-p0-http-sanity-2026-08-27.md`](./traspaso-relevo-sesion-operativa-p0-http-sanity-2026-08-27.md)
- F1: [`traspaso-relevo-sesion-operativa-f1-mesa-3-niveles-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f1-mesa-3-niveles-2026-08-27.md)
- F2: [`traspaso-relevo-sesion-operativa-f2-suitability-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f2-suitability-2026-08-27.md)
- F3: [`traspaso-relevo-sesion-operativa-f3-scenario-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f3-scenario-2026-08-27.md)
- F4: [`traspaso-relevo-sesion-operativa-f4-libro-ruta-2026-08-27.md`](./traspaso-relevo-sesion-operativa-f4-libro-ruta-2026-08-27.md)
