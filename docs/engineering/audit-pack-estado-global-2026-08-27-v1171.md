# Audit pack — estado global v1.17.1 (Hardening + refinamiento Mesa)

> **AsOf:** 2026-08-27 · **Tag:** **`v1.17.1-beta` → `e0ae633`**. Partida **`v1.17-beta` → `62ebc4f`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · plan [`plan-v1171-hardening-2026-08-27.md`](./plan-v1171-hardening-2026-08-27.md) · ADR-038 · ADR-039 · pack previo [`audit-pack-estado-global-2026-08-27-v117.md`](./audit-pack-estado-global-2026-08-27-v117.md).
> **Para:** auditoría cruzada post-hardening · Release tag CI.

---

## 0. Veredicto interno

Ciclo **V1.17.1 Hardening de honestidad** **CERRADO** (+ refinamiento Mesa corto). Cierra mentiras numéricas y huecos AUTO que el pack v117 dejó como deuda. **No** añade Stress Risk, Opportunity Engine ni D1 backtest. DEX-1…DEX-5 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **OFF**. AUTO **off**. LIVE **experimental**. Producto **BETA**.

| Epic  | Nombre                                               | Estado  |
| ----- | ---------------------------------------------------- | ------- |
| H1    | TradePlan SoT sizing (`candidateRiskR` / notional)   | CERRADO |
| H2    | `originalPlan` vs `currentPlan` + `direction`        | CERRADO |
| H3    | Unknown sector → warning + `sectorConcentration`     | CERRADO |
| H4    | Router sanity + `enforce_edge_thresholds` paper_auto | CERRADO |
| H5    | Redis feature cache SHA256 v2 + compose DEV ONLY     | CERRADO |
| H6    | Mesa refetch data-status + `isError` queries         | CERRADO |
| R1–R5 | Refino Mesa (overlay board, sector, UX honesty)      | CERRADO |

**Mensaje clave:** v1.17 hizo usable la mesa diaria; v1.17.1 **deja de inventar R/notional**, separa plan de fill vs plan actual, y alinea paper_auto con sanity/EdgeReport **sin** convertir paper en live.

---

## 1. Scorecard

| Epic     | Cierra                                                           | Evidencia                                                        |
| -------- | ---------------------------------------------------------------- | ---------------------------------------------------------------- |
| **H1**   | Sin stub 1R / sin `*10`; incompleto → `INSUFFICIENT_DATA`        | `portfolio-scenario` · `portfolio-risk-metrics` · geometry study |
| **H2**   | Study día-3 no pisa original; DTO `plannedEntry`/`initialStop`   | `investment-position-aggregate` · `extra_mappers` · ruta UI      |
| **H3**   | Unknown > 0 → warning; UI muestra Unknown                        | `portfolio-scenario` · `mesa-what-if-panel`                      |
| **H4**   | Split veta paper_auto; luck/missing edge veta; `auto_live=False` | `execution_router` · `test_decision_spine` · gate_decision       |
| **H5**   | Prefijo `bolsa:features:v2:` · verify antes de `loads`           | `redis_feature_cache` · tests checksum                           |
| **H6**   | Portfolio error → header degraded                                | `mesa-next-action` · `mesa-hoy-page`                             |
| **R1**   | Board TradePlan vivo → sizing scenario                           | `enrichMesaCandidates` · overlay                                 |
| **R2**   | Sector coalesce + Priority penaliza null/Unknown                 | `PositionDto.sector` · `operational-priority`                    |
| **R3–5** | What-if ámbar · chip sin posiciones · badge Acción               | Mesa UI                                                          |

---

## 2. Batería (local, 2026-08-27)

| Gate                       | Resultado               |
| -------------------------- | ----------------------- |
| `pnpm test:decision-spine` | **495** passed          |
| Shared DoD refine          | **49** passed (5 files) |
| Web `mesa-hoy`             | **13** passed           |
| Pytest H4/H5 dirigido      | **36+** passed          |

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario investment-position-aggregate operational-priority mesa-next-action mesa-hoy-model
pnpm --filter @bolsa/web test -- mesa-hoy
python -m pytest packages/py/application/tests/test_execution_router.py packages/py/application/tests/test_execute_gated_portfolio_trade.py packages/py/application/tests/test_decision_spine.py packages/py/analytics/tests/test_cognitive_d1_d3.py packages/py/analytics/tests/test_evidence_engine_d3.py packages/py/infrastructure/tests/test_redis_feature_cache.py -q
pnpm test:decision-spine
# expect: 495 passed
```

Spine: **489** (v1.17) → **495** (hardening H4 + luck/lookup tests).

---

## 3. Freeze (intacto)

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · BETA · Scenario ≠ permiso · Ranking ≠ BUY · Stress sigue stub · LLM no ejecuta.

---

## 4. Deuda restante (explícita)

| ID      | Limitación                         | Severidad       |
| ------- | ---------------------------------- | --------------- |
| STRESS  | `portfolioStressRiskR` stub        | Producto V1.19+ |
| OPP     | Opportunity Engine                 | Producto        |
| V118    | Position → DecisionPackage durable | ADR-038         |
| LAB-B   | Backtest ≠ TradingPolicy           | Lab             |
| THAW    | Accept estricto 60d/50/70/55       | Deuda larga     |
| AUTO-ON | AUTO on / LIVE producción          | Freeze          |

---

## 5. Qué **no** entra

Stress/correlación · Opportunity Engine · thaw · AUTO ON · ExecutionContext refactor · Quality weights 35/35/30 · Primary Action mega-rediseño · `contract:gen`.
