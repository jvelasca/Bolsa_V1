# Decision Spine — cadena AS-IS (file:line) y matriz de prueba

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **AsOf:** 2026-08-24 · ancla working tree DS-03 (post audit-stamp `5100d23`). Secuencia ciclo: U6 `9e9a346` · DS-05 `15e86a4` · ops `5100d23` · **DS-03 mandate** (working tree). Prove + H5 + UX mesa U0–U6 + **DS-05 freshness** + **DS-03 mandate** en spine.
> **Alcance:** mapa de la columna que **ya existe**. No inventa `InvestmentDecision` / `OrderProposal` / orquestador.
> **Suite:** `pnpm test:decision-spine`.

---

## 1. Cadena (un objeto, dos autorizaciones)

```
Assessment (TA/FA/macro)
    → run_decision_runtime                 analytics/.../decision_runtime.py:256
    → DecisionPackageTa / DecisionPackageV1
         knowledge/decision_package_ta.py:34
         packages/shared/src/cognitive/decision-package.ts:39
    → evaluate_policy_gate / MaxConcentration+MaxSectorExposure
         analytics/.../policy_gate.py:57 · :153 · :175
    → compute_portfolio_fit                analytics/.../portfolio_fit.py:67
    → check_opening                        application/risk_engine.py:57
         + DS-05 data freshness (last_bar / require_fresh_data)
         + DS-03 account mandate (tenure BD / require_account_mandate)
         trading_policy_guard.py:174 (Fit → gate)
    → SEMI: ConfirmRecommendationIntent    confirm_recommendation.py
         check_opening en _risk_allows_opening (aperturas)
         proposal_sector = instruments.sector (H1)
         summary lanza → risk_veto (H2)
         profile = accounts.active_profile_id → profile_store (H5)
         ohlcv.get_latest_bar_date → freshness (DS-05)
         mandates.get_open_mandate → tenure (DS-03)
    → AUTO: ExecutionRouter._execute_paper_trade
         execution_router.py  check_opening DENY → skipped, no ExecuteTrade
         signal.timestamp + require_fresh_data (DS-05)
         mandate repo + require_account_mandate (DS-03)
         proposal_sector = hit.sector
    → HTTP: ExecuteGatedPortfolioTrade     execute_gated_portfolio_trade.py
         buy → allow_opening_fill → check_opening; sell skip
    → ExecuteTrade                         accounts/trade.py
```

Daily Decision Board (`GetDecisionBoard`, `/decision-board`) es **vista**; no decide.

---

## 2. Matriz «probado / no cubierto»

| Id       | Caso                              | Estado                                                                                                                                                 |
| -------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| DS-01    | Apertura SEMI permitida           | Cubierto: `test_confirm_apertura_cesta_permite_fill` · package match                                                                                   |
| DS-02    | Risk BLOCK SEMI                   | Cubierto: cesta veto · H2 summary fail-closed                                                                                                          |
| DS-04    | Concentración / sector BLOCK      | Cubierto: `test_risk_engine_portfolio_fit` · H1 SEMI sector · H5 profile conservative                                                                  |
| DS-05    | Stale data BLOCK                  | **Cubierto:** `check_opening` freshness gate · AUTO `test_ds05_auto_stale…` · SEMI stale/fresh/ohlcv-fail · unit `test_risk_engine`                    |
| DS-06    | SEMI + package identidad          | Cubierto: D2 match/conflict                                                                                                                            |
| DS-08    | AUTO + risk BLOCK no ejecuta      | Cubierto: `test_decision_spine.py` (router DENY → 0 ExecuteTrade)                                                                                      |
| DS-09    | Confirm duplicado                 | Cubierto: idempotency `decision_id`                                                                                                                    |
| DS-11    | Cesta re-evaluada en confirm      | Cubierto: Escalón 3                                                                                                                                    |
| H5       | SEMI profile → check_opening      | Cubierto: `test_confirm_apertura_profile_conservative_veto` · `…_profile_none_allows`                                                                  |
| Golden   | Runtime + Fit veredicto estable   | Cubierto: `test_golden_decision_scenario.py`                                                                                                           |
| DS-03    | Mandate de cuenta BLOCK           | **Cubierto:** `check_opening` mandate gate · tenure BD `mandate_tenures` · AUTO `test_ds03_auto…` · SEMI no-tenure/open/fail · unit `test_risk_engine` |
| DS-07    | AUTO fill ALLOW                   | Implícito en router; no es el hueco DS-08                                                                                                              |
| DS-12–15 | expiry / partial / broker / recon | **Fuera** (no broker)                                                                                                                                  |
| Residual | Composite `portfolioConstraints`  | Sigue `not_evaluated`; Fit vive al lado — **doc honesty**; no wire en esta rebanada                                                                    |
| Residual | ExecuteTrade HTTP                 | **I1 cerrado:** buy gated (`allow_opening_fill`); sell skip; Router AUTO no fusionado                                                                  |
| Residual | HTTP Router `paper_auto`          | **I3:** `/route` + scan-execute exigen `PAPER_D_EXECUTE` (403); inform/alert/live_auto no; **no thaw**                                                 |
| Residual | Exits `full_auto` → Router        | **RX1:** `evaluate-exits` execute + linked `paper_auto` → mismo env (403); eval-only OK; **no** auto-exit producto · **no thaw**                       |
| Residual | H3 orphan apertures               | **Cerrado ADR-031:** store cableado → `orphan_opening_blocked`; tests sin store = legado                                                               |

---

## 3. Qué no es esta columna

Ranking Estudio cliente · Daily Mission / Confirm All · OrderProposal nuevo · Decision Journal · Attribution · `evaluate_investment_decision` orquestador · LLM → orden.
