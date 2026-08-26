# RELEVO — Mesa desk backend F5 (MD-5) · 2026-08-26

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) §F5 · apertura [`traspaso-relevo-mesa-desk-v116-apertura-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-apertura-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **F5 CERRADO (tests + docs)** · sin commit · sin tag.
> **Scope:** backend paralelo auditoría V1.15 — **no** backtest TradingPolicy.

---

## 0. Por qué este relevo

Cierre MD-5 / F5 del plan Mesa desk: batería pytest para cambios backend sin commit (pickle checksum, prod allowlist, `PAPER_D_EXECUTE` en Router, sanity DS-05 API), doc `require_role`, y decisión honesta sobre wiring E2E de `sanity_warnings`.

## 1. Qué quedó hecho

| ID   | Entrega                                          | Estado                    | Evidencia                                                                  |
| ---- | ------------------------------------------------ | ------------------------- | -------------------------------------------------------------------------- |
| F5-A | Pickle SHA256 antes de load                      | **Hecho** (código previo) | `lightgbm_direction.py` · `test_lightgbm_checksum.py`                      |
| F5-B | `is_production_environment()` allowlist          | **Hecho**                 | `config.py` · `test_config_production.py` · `test_auth.py` (cookie Secure) |
| F5-C | `PAPER_D_EXECUTE` en `Router.execute()`          | **Hecho**                 | `require_http_paper_auto_env` en `execute()` · `test_execution_router.py`  |
| F5-D | `PAPER_D_ACCOUNT_ID` fail-closed                 | **Hecho** (código previo) | `paper_d_propose.py` · `test_paper_d_propose.py` (existente)               |
| F5-E | EdgeReport denominador sin ausentes              | **Hecho** (código previo) | `edge_report.py` · `test_lab_edge_report.py` (existente)                   |
| F5-F | sanity → DS-05 helper                            | **Hecho (API)**           | `sanity.py` · `risk_engine.py` · `test_sanity_opening_veto.py`             |
| F5-G | Cablear `sanity_warnings` → runtime Confirm/AUTO | **P1 — no cableado**      | Ver §3                                                                     |
| F5-H | Tests nuevos pytest                              | **Hecho**                 | Ver §2                                                                     |
| F5-I | `require_role` en CURRENT_SYSTEM                 | **Hecho**                 | `docs/CURRENT_SYSTEM.md` §Auth                                             |
| F5-J | Backtest `BacktestRiskPolicy`                    | **Fuera tag**             | Sin cambios (owner)                                                        |

## 2. Comandos reproducibles

```bash
python -m pytest \
  packages/py/analytics/tests/test_lightgbm_checksum.py \
  packages/py/infrastructure/tests/test_config_production.py \
  packages/py/market/tests/test_sanity_opening_veto.py \
  packages/py/application/tests/test_execution_router.py \
  packages/py/application/tests/test_risk_engine.py \
  packages/py/application/tests/test_paper_d_propose.py \
  packages/py/application/tests/test_paper_auto_http_gate.py \
  packages/py/analytics/tests/test_lab_edge_report.py \
  apps/api-python/tests/test_auth.py -q
```

**Resultado (2026-08-26):** **72 passed**, 0 failed (~48s).

## 3. Limitación P1 — `sanity_warnings` E2E

**Decisión:** no half-wiring en este epic.

- **API lista:** `check_opening(..., sanity_warnings=...)` + `sanity_opening_veto_reason()` en `bolsa_market.sanity`.
- **Datos disponibles:** `GetInstrumentDataStatus` ya calcula `sanity_warnings` desde `run_sanity_checks` (HTTP instrument status / chip DS-05 UI).
- **Gap:** ningún camino de apertura runtime pasa esas warnings hoy:
  - `opening_permission.allow_opening_fill` → `check_opening` **sin** `sanity_warnings`
  - `OpeningGateCoordinator` (Confirm DEX-4) **sin** lookup de sanity
  - `ExecutionRouter._execute_paper_trade` **sin** `sanity_warnings`
- **Cierre E2E (post-tag):** inyectar warnings desde OHLCV/status en `allow_opening_fill` + Router AUTO cuando `require_fresh_data=True`; tests spine SEMI/AUTO con warning split simulado.

## 4. Archivos tocados (sin commit)

| Archivo                                                      | Cambio                                   |
| ------------------------------------------------------------ | ---------------------------------------- |
| `packages/py/analytics/tests/test_lightgbm_checksum.py`      | **nuevo**                                |
| `packages/py/infrastructure/tests/test_config_production.py` | **nuevo**                                |
| `packages/py/market/tests/test_sanity_opening_veto.py`       | **nuevo**                                |
| `packages/py/application/tests/test_execution_router.py`     | gate `PAPER_D_EXECUTE`                   |
| `packages/py/application/tests/test_paper_d_propose.py`      | fix `PAPER_D_ACCOUNT_ID` en test execute |
| `docs/CURRENT_SYSTEM.md`                                     | párrafo `require_role`                   |

Backend sin commit (pre-existente en working tree): `lightgbm_direction.py`, `config.py`, `session.py`, `execution_router.py`, `paper_d_propose.py`, `edge_report.py`, `sanity.py`, `risk_engine.py`.

## 5. Freeze intacto

- Confirm = firma · AUTO off · `PAPER_D_EXECUTE` default **off** · LIVE experimental.
- Router gate solo bloquea `paper_auto` sin env; spine tests llaman `_execute_paper_trade` directo (documentado en `paper_auto_http_gate.py`).
- **No** commit · **No** tag · **No** backtest TradingPolicy alignment.

## 6. Next (otros agentes / F6)

- F1 matriz tests Mesa + smoke browser.
- F6 `pnpm test:decision-spine` integrado.
- F7 CHANGELOG + pack v116 + relevo tag (owner gate).
