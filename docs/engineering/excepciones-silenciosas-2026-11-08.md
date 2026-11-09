# Excepciones silenciosas y ratchet Ruff S110/S112 — 2026-11-08

Cierre de `p2-exceptions` (Fase 2.2 del plan de remediación). Objetivo: que ningún
`except Exception: pass|continue` de producción vuelva a tragarse un error sin dejar rastro,
sin convertir el repo en una guerra de `BLE001` (277+ casos, ruido).

## Qué se cambió

- Los `except Exception:` con cuerpo `pass`/`continue` de `packages/py` y `apps/api-python`
  (no-test) se sustituyeron por `logger.debug(<contexto>, exc_info=True)`.
  - Nivel **DEBUG**: el comportamiento observable del motor no cambia (`Δ motor = 0`); el
    error sigue siendo best-effort, pero queda en el log con traza.
  - Mensaje en castellano y con el contexto del punto (`"sondeo de proveedores falló"`,
    `"auditoría de sesión ignorada"`, ...), no un `"error"` genérico.
- **Ningún sitio quedó declarado con `noqa: S110` en producción**: no hizo falta. El único
  `pass` legítimo era el cierre de tareas en `MarketProviderWatcher.aclose()`, que ahora
  distingue `asyncio.CancelledError` (silencio real, es el camino normal de `cancel()`) de
  una excepción inesperada (se registra a DEBUG).
- Tests: el ratchet **no** aplica a `**/tests/**`. Un `except` de limpieza en un test no
  necesita log y el aserto es la evidencia; exigir `exc_info` ahí solo añadiría ruido.

Módulos tocados (23):

```
apps/api-python/src/bolsa_api/api/v1/routes/portfolio.py
apps/api-python/src/bolsa_api/api/v1/routes/predictions.py
apps/api-python/src/bolsa_api/background/paper_auto_engine_worker.py
packages/py/application/src/bolsa_application/auto_v2_entry.py
packages/py/application/src/bolsa_application/broker_venue_runtime.py
packages/py/application/src/bolsa_application/confirm/submit_intent.py
packages/py/application/src/bolsa_application/confirm_recommendation.py
packages/py/application/src/bolsa_application/execution_router.py
packages/py/application/src/bolsa_application/get_instrument_composite.py
packages/py/application/src/bolsa_application/get_instrument_data_status.py
packages/py/application/src/bolsa_application/get_instrument_fundamentals.py
packages/py/application/src/bolsa_application/journal_writer.py
packages/py/application/src/bolsa_application/market_indices.py
packages/py/application/src/bolsa_application/market_providers.py
packages/py/application/src/bolsa_application/opening_fill_handle.py
packages/py/application/src/bolsa_application/prediction_persistence.py
packages/py/application/src/bolsa_application/propose_recommendation.py
packages/py/application/src/bolsa_application/risk_runtime.py
packages/py/application/src/bolsa_application/strategy_observed_metrics.py
packages/py/infrastructure/src/bolsa_infrastructure/cache/redis_feature_cache.py
packages/py/market/src/bolsa_market/indices/discovery.py
packages/py/market/src/bolsa_market/news_snapshot.py
packages/py/market/src/bolsa_market/yahoo_client.py
```

Entre ellos están los tres que citaba el informe: `redis_feature_cache.py`,
`risk_runtime.py` y `news_snapshot.py`.

## El ratchet

En `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "S110", "S112"]
ignore = ["E501"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S110", "S112"]
```

- `S110` = `try-except-pass`, `S112` = `try-except-continue`.
- Solo esos dos de la familia `S`: `BLE001` global sigue apagado a propósito.
- `noqa` sigue siendo posible, pero ahora es una decisión visible en el diff, no un descuido.

## Verificación

```
uv run ruff check packages/py apps/api-python --config pyproject.toml
# All checks passed!
```

Barrido de confirmación (0 resultados):

```
rg -U "except (Exception|BaseException)[^\n]*:\s*\n\s+(pass|continue)\b" \
   packages/py apps/api-python -g '!**/tests/**'
rg "noqa: S11[02]" packages/py apps/api-python -g '!**/tests/**'
```

Tests: suite completa de `packages/py` + `apps/api-python` en verde tras el cambio
(5.394 + 1.805 tests; el único fallo intermedio fue el guard de tamaño de
`confirm_recommendation.py`, resuelto sin subir el fichero de 1.100 líneas).

## Límites declarados

- El log es **DEBUG**: en producción con `LOG_LEVEL=INFO` estas trazas no se ven. Es
  deliberado — el objetivo es que la información exista y sea activable, no inundar el log
  de operativa normal. Quien depure un `except` sube el nivel de ese logger.
- No se convirtió `except Exception` en una excepción más estrecha salvo donde el tipo era
  evidente (`CancelledError` en `market_providers.aclose`). Estrechar 41 bloques sin conocer
  cada camino de fallo habría cambiado comportamiento, y la fase exige `Δ motor = 0`.
- El ratchet **no** detecta `except Exception: return None` ni `except Exception: continue`
  escrito en una sola línea con `;`. El barrido `rg` de arriba cubre el caso multilínea; una
  regla propia para el resto queda fuera de alcance.
