# Audit pack — estado global v1.17 (Sesión operativa diaria)

> **AsOf:** 2026-08-27 · **Tag:** **`v1.17-beta` → `62ebc4f`** (feature) · stamp docs en HEAD. Partida **`v1.16-beta` → `f16119b`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · plan [`plan-v117-v121-operational-depth-2026-08-27.md`](./plan-v117-v121-operational-depth-2026-08-27.md) · ADR-037 §7 · ADR-038 · ADR-039 · pack previo [`audit-pack-estado-global-2026-08-26-v116.md`](./audit-pack-estado-global-2026-08-26-v116.md).
> **Para:** auditoría externa / GitHub Actions Release tag CI · cierre ciclo **Sesión operativa 2.0** (post AUDITORIA 1 + 2).

---

## 0. Veredicto interno

Ciclo **Sesión operativa diaria** **CERRADO en código** (P0 + F1…F4 + docs + arranque F5 `pg_isready`). Convierte el SEMI diario en sesión ~20 s en `/mesa` sin tocar Confirm/DEX/SubmitIntent (salvo DI `instrument_data_status` en HTTP trade). DEX-1…DEX-5 **intactos**. Producto sigue **BETA / no producción**. Confirm = **única** firma. Accept estricto **NO**. `PAPER_D_EXECUTE` repo **OFF**. LIVE **experimental**. AUTO **off**.

| Epic | Nombre                                         | Estado  |
| ---- | ---------------------------------------------- | ------- |
| P0   | HTTP trade sanity (`instrument_data_status`)   | CERRADO |
| F1   | Mesa 3 niveles (ocurre / debo / podría)        | CERRADO |
| F2   | Suitability real (sector + Priority)           | CERRADO |
| F3   | Scenario ACTUAL/DESPUÉS honesto (no permiso)   | CERRADO |
| F4   | Libro ruta viva + Next Action del agregado     | CERRADO |
| Ops  | F5 cold-start: wait `pg_isready` (no solo TCP) | CERRADO |

**Mensaje clave:** v1.16 endureció el desk; v1.17 **cierra el hueco de firma HTTP** y hace usable la profundidad post-AUDITORIA 1 en la home diaria. Hallazgos AUDITORIA 2 de AUTO/Lab (Router sanity, EdgeReport `paper_auto`, Redis pickle SHA256, backtest≠TradingPolicy) quedan **explícitos como deuda AUTO**, no de mesa.

---

## 1. Scorecard P0 / F1…F4

| Epic   | Cierra                                                  | Evidencia principal                                                                      | Spine   |
| ------ | ------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------- |
| **P0** | Buy HTTP veta split/dividendo; gap-only no              | `execute_gated_portfolio_trade` · DI dependencies · `test_execute_gated_portfolio_trade` | **489** |
| **F1** | 3 niveles UI; incidente primero; atención `polite`      | `mesa-level-section` · `mesa-hoy-page` · `mesa-attention-queue`                          | —       |
| **F2** | Tech overload → NO OPERAR; TRIGGERED holgado → OPERABLE | `operational-priority` · `mesa-candidates-panel`                                         | —       |
| **F3** | ACTUAL/DESPUÉS + límite mandato + copy no-permiso       | `portfolio-scenario` · `mesa-what-if-panel`                                              | —       |
| **F4** | Ruta + Next Action agregado en `/operations`            | `operations-panel` · `buildInvestmentPositionAggregate`                                  | —       |

Orden ADR-037 **intacto** (incidente primero). Tres niveles = proyección visual (§7 amendment).

---

## 2. Batería (local, pre-tag / 2026-08-27)

| Gate                       | Resultado                                          |
| -------------------------- | -------------------------------------------------- |
| `pnpm test:decision-spine` | **489** passed                                     |
| Shared cognitive DoD       | **53** passed (7 files)                            |
| Web `mesa-hoy`             | **12** passed                                      |
| Opening + gated trade      | **19** passed                                      |
| Smoke browser              | Mesa 3 niveles · scenario copy · Libro carga       |
| Release tag CI             | `release-tag-ci.yml` — al pushear tag `v1.17-beta` |

```bash
pnpm test:decision-spine
# expect: 489 passed

pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics data-freshness investment-position-aggregate operational-priority portfolio-scenario mesa-next-action mesa-operable-ranking
# expect: 53 passed

pnpm --filter @bolsa/web test -- mesa-hoy
# expect: 12 passed

python -m pytest packages/py/application/tests/test_opening_permission.py packages/py/application/tests/test_execute_gated_portfolio_trade.py -q
# expect: 19 passed
```

Spine progression: **485** (v1.16) → **489** (HTTP sanity + opening tests en spine).

---

## 3. Qué entra en el tag

- **P0:** `ExecuteGatedPortfolioTrade` + DI `instrument_data_status` (mismo SoT Confirm/Fill).
- **F1:** `MesaLevelSection` · alertas en nivel 1 · `MesaDailyHeader` fuera de `/mesa` · atención `aria-live="polite"`.
- **F2:** `computeSectorExposurePct` · `candidateSector` / `sectorByInstrumentId` · UI **NO OPERAR · no encaja**.
- **F3:** `buildPortfolioScenario` + `portfolioRiskLimitR` · copy _Estimación de cartera, no permiso_.
- **F4:** `PositionRoutePanel` en Libro · Next Action vía agregado.
- **Ops:** `pg_isready` en `db-ensure` / `docker.mjs` (1.er F5 cold Docker).
- Docs: plan v117 · ADR-037 §7 · ADR-038/039 · relevos P0/F1–F4 · este pack · relevo tag.
- Confirm/DEX/SubmitIntent **sin cambio de contrato** (solo wiring DI HTTP).

---

## 4. Qué no entra / parked (candidatas post-v1.17)

| Excluido / parked                                | Severidad           | Notas                         |
| ------------------------------------------------ | ------------------- | ----------------------------- |
| **Router `sanity_warnings`**                     | Deuda AUTO          | AUTO off; no mesa             |
| **EdgeReport no veta `paper_auto`**              | Deuda AUTO          | `auto_live=False` honesto     |
| **Redis pickle SHA256**                          | Lab                 | caché ML                      |
| **Backtest ≠ TradingPolicy**                     | Lab                 | ciclo Lab, no Mesa            |
| Dry-run `check_opening` en scenario              | Post-estabilización | tocaría Confirm/DEX semántica |
| Stress/correlación                               | Stub                | `portfolioStressRiskR` stub   |
| `GET /api/mesa/today`                            | Freeze V1.16        | —                             |
| Accept estricto / thaw / AUTO on / LIVE accepted | Deuda               | palabra **thaw**              |
| Reabrir DEX-1…5 u OR a ciegas                    | —                   | No                            |

---

## 5. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-037 (§7 niveles) · ADR-038 · ADR-039 → código → tests → HELP

Confirm SEMI = firma
HTTP buy = mismo allow_opening_fill (+ sanity)
Scenario / Priority = proyección; ≠ permiso
DEX-1…DEX-5 intactos
```

---

## 6. Freeze (v1.17)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · Confirm = firma · thin 5.x/8.x congelados · OI/OR/DEX **no se reabren** a ciegas · `PAPER_D_EXECUTE` **off** · mesa default **paper** · LIVE experimental · Accept estricto **parked** · AUTO **off** · sin HTTP nuevo Mesa · **BETA / no producción**.

---

## 7. Docs clave (lectura auditor)

| Tipo                  | Documento                                                                                                 |
| --------------------- | --------------------------------------------------------------------------------------------------------- |
| SoT vivo              | [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)                                                               |
| Plan ciclo            | [`plan-v117-v121-operational-depth-2026-08-27.md`](./plan-v117-v121-operational-depth-2026-08-27.md)      |
| ADR Mesa              | [`037-mesa-hoy-operational-ux.md`](../adr/037-mesa-hoy-operational-ux.md) (§7)                            |
| ADR Position          | [`038-position-operational-memory.md`](../adr/038-position-operational-memory.md)                         |
| ADR Priority/Scenario | [`039-portfolio-scenario-operational-priority.md`](../adr/039-portfolio-scenario-operational-priority.md) |
| Relevo tag            | [`traspaso-relevo-tag-v1-17-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-17-beta-2026-08-27.md)          |
| P0…F4                 | `traspaso-relevo-sesion-operativa-*-2026-08-27.md`                                                        |
| Pack prev.            | [`audit-pack-estado-global-2026-08-26-v116.md`](./audit-pack-estado-global-2026-08-26-v116.md)            |
| Arranque              | [`DEV_STARTUP.md`](../DEV_STARTUP.md) (`pg_isready`)                                                      |

---

## 8. Checklist auditor (E1)

1. Checkout **`v1.17-beta`** (SHA stamp en CURRENT_SYSTEM / este pack).
2. Verificar GitHub Actions **`release-tag-ci.yml`** GREEN en el push del tag.
3. `pnpm test:decision-spine` → **489** passed.
4. DoD §2 shared 53 · mesa-hoy 12 · opening+gated 19.
5. Contrastar ADR-037 §7 + ADR-038/039 + relevos P0/F1–F4 con código.
6. Confirmar freeze §6 y limitaciones §4 (deuda AUTO explícita, no oculta).
7. Opcional UI: `/mesa` tres niveles · Simular impacto copy no-permiso · `/operations` con ruta si hay plan.
8. Emitir triage/findings (candidatas §4).

**Preguntas que este pack no resuelve:** Router sanity · EdgeReport paper_auto · Redis SHA256 · backtest=TradingPolicy · dry-run gates scenario · thaw · AUTO on · `GET /api/mesa/today`.
