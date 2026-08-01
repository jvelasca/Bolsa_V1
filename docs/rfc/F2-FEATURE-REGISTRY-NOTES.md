# F2 — Feature Registry (esqueleto RFC-005)

> Operativo. No redefine la constitución.

## Entregado

| Pieza | Ubicación |
|-------|-----------|
| `FeatureDef` / `FeatureSet` / `FeatureSnapshot` | `bolsa_analytics.features.models` |
| `IFeaturePort` | `bolsa_analytics.features.ports` |
| `OnlineFeatureAdapter` | wrap store + PIT mínima + hash P8 |
| Catálogo bootstrap **≥12** | SMA×2, EMA×2, WMA, RSI, ATR, CCI, Stoch, MACD, BB mid, Volume |
| `compute_bridge` | paridad FeatureDef ↔ `compute_spec` |
| Scan consumer | `RunScan` materializa snapshot vía `feature_port` |
| HTTP | `GET /api/features/catalog`, `GET /api/features/latest` |
| Tests | `test_feature_registry_skeleton.py`, `test_feature_registry_golden.py` |

## Pendiente

1. ~~Tipos stub en `@bolsa/shared`~~ → `packages/shared/src/feature-registry.ts`
2. Redis tipado como `RedisFeatureAdapter` (hoy cache factory).
3. Offline / Parquet adapter.
