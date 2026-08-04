# OR-lite + Repro+ + Obs/CI (2026-08-04)

> Pre-AUTO sin flip Camino D. Padres: [triage institucional](./audit-ext-institutional-pre-auto-triage-2026-08-04.md) · [thaw checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) · [OR-RE](./risk-engine-or-re-2026-08-04.md).

## OR-lite

| ID | Entrega | Dónde |
|----|---------|--------|
| **OR-S1** | `APP_PASSWORD` obligatorio en demos compartidas | `.env.example`, [ONBOARDING](../ONBOARDING.md), `GET /api/health` → `components.auth` |
| **OR-P2** | Decimal en notional paper / fees | `portfolio_repository.execute_trade`, `ExecuteTrade`, `calculate_trade_fees`, `trading_policy_guard` |
| **OR-T4/T6** | Idempotencia / DecisionSession | Parcial vía Gate memory + Risk Engine; execute AUTO sigue detrás flag |
| **OR-RE** | Risk Engine v0 | Ya documentado aparte |

## Repro+

`CampaignManifestV0` añade:

- `dataset_fingerprint` — SHA256 de universo/ventana/bar_count/ids
- `feature_flags` — snapshot Settings (cost v2, CORE-R, EOD, kill switch, …)
- `payload_hash` — SHA256 del `manifest_ref` sin circularidad
- `git_dirty`, `python_version` (ya en build)

API: `build_campaign_manifest` / `to_manifest_ref`. Tests: `test_campaign_manifest.py`.

## Obs/CI

| Ítem | Entrega |
|------|---------|
| ErrorBoundary | `AppErrorBoundary` alrededor de `PlatformShell` (AuthGate fuera) |
| Gitleaks | `.github/workflows/gitleaks.yml` |
| Worker heartbeat | Redis `bolsa:worker:arq:heartbeat` (TTL 180s); health `components.worker_arq` |

## Fuera de alcance (sigue freeze)

Camino D / `PAPER_D_EXECUTE`, Belief→Coach, `CORE_R_CRON`, Strategy Studio, `COST_MODEL_V2` on-by-default, Vault/JWT TTL, OTel full, Monte Carlo.
