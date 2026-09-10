"""V2.28 / A10 (P1-02 real) — adaptador de métricas observadas para la vigilancia real.

Une el cálculo puro (``strategy_observed_metrics``) con el almacén durable de fills
atribuidos (``SimFillFinanceContextStore.list_for_strategy_version``) y produce el puerto
``ObservedMetricsProvider`` que consume ``AutoOrchestrator.watch_active``.

Cierre del P1-02 del audit: la vigilancia deja de invocarse con ``metrics={}``. Las
métricas ya no son «lo que diga el llamante», sino el resultado observado de la ejecución
SIM de ESA versión de estrategia.

Diseño:
* El provider abre su propia sesión por invocación (``session_factory``), igual que el
  resto de adaptadores del worker: el orquestador no conoce sesiones.
* ``min_trades`` configurable por env (``AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES``, default
  10): por debajo de esa muestra, ``compute_observed_metrics`` devuelve ``{}`` y la
  vigilancia observada no decide — exactamente el guard que acordamos.
* Fail-closed: cualquier error de lectura devuelve ``{}`` (sin evidencia observada), nunca
  una métrica fabricada.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from bolsa_application.sim_durable_store import (
    PostgresSimFillFinanceContextStore,
    SimFillFinanceContextStore,
)
from bolsa_application.strategy_observed_metrics import (
    MIN_TRADES_DEFAULT,
    compute_observed_metrics_from_fills,
)

__all__ = [
    "AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES",
    "make_observed_metrics_provider",
    "observed_min_trades",
]

logger = logging.getLogger(__name__)

AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES = "AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES"


def observed_min_trades() -> int:
    """Muestra mínima de round-trips para que el observado sea decisorio (env)."""
    raw = (os.getenv(AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES) or "").strip()
    if not raw:
        return MIN_TRADES_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return MIN_TRADES_DEFAULT
    return value if value > 0 else MIN_TRADES_DEFAULT


def make_observed_metrics_provider(
    session_factory: Any,
    *,
    account_id: str | None = None,
    store_factory: Callable[[Any], SimFillFinanceContextStore] | None = None,
) -> Any:
    """Devuelve ``observed_metrics(version_id) -> dict`` (puerto del orquestador).

    ``store_factory`` permite inyectar el almacén (tests / composición alternativa); por
    defecto construye el store PG sobre la sesión abierta.
    """
    build_store = store_factory or (lambda session: PostgresSimFillFinanceContextStore(session))
    min_trades = observed_min_trades()

    async def _observed(version_id: str) -> dict[str, Any]:
        vid = str(version_id or "").strip()
        if not vid:
            return {}
        try:
            async with session_factory() as session:
                store = build_store(session)
                fills = await store.list_for_strategy_version(
                    vid, account_id=account_id
                )
        except Exception:  # noqa: BLE001 — sin lectura no hay evidencia; no se inventa.
            logger.exception("observed metrics read failed version=%s", vid)
            return {}
        metrics = compute_observed_metrics_from_fills(fills, min_trades=min_trades)
        if metrics is None:
            return {}
        return metrics.as_metrics(min_trades=min_trades)

    return _observed
