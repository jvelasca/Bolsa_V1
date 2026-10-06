# Evidencia `v2.88.63-beta` — `NÚCLEO`: **el test M0 vigila el worker AUTO**

**Objeto:** el siguiente chat o un auditor externo.

**Producto:** `V2.88.63-beta` · **Package:** `2.11.63-beta` · **AsOf:** 2026-10-06 · **Nature:** `test de barrera`. **Δ AUTO decision/execution motor = 0**.

**Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** sin cambio.

**Padre:** [`v2.88.62`](../v2.88.62/README.md).

## Qué añade

`test_a8_m0_auto_live_invariant` recorre `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` con el mismo análisis AST que los módulos de `bolsa_application`. Si el worker importa o nombra `IBrokerAdapter`, `resolve_broker_adapter` o `XtbBrokerAdapter`, el test falla.

No cambia el motor, el libro ni el contrato HTTP.

## Falsación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El worker está en la lista que el test parsea. | Quitar `auto_simulation_worker.py` de `_AUTO_PATHS` y el caso deja de existir. |
| 2 | Un símbolo LIVE en ese fichero rompe el test. | Añadir `XtbBrokerAdapter` como atributo o import y `pytest` de ese fichero deja de estar en verde. |

## Test

`pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py` — **12 passed**.
