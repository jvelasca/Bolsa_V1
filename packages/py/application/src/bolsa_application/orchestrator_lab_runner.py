"""V2.27 / A10 — cableado real del LABORATORIO al Auto Orchestrator.

El ``AutoOrchestrator`` depende de ``run_optimize: Callable[[StrategyCandidate], Awaitable[Any]]``
(``OptimizeRunner`` en ``auto_orchestrator``). El use-case real del LAB,
``RunSmaGridOptimizeAndSave.execute``, **no** encaja con esa firma: es keyword-only,
recibe ``instrument_id`` + grid params (no un ``StrategyCandidate``) y devuelve una
tupla ``(OptimizeSmaGridResult, OptimizationRunRecord)``.

Este módulo aporta el adaptador que cierra esa distancia:

* Descompone el ``StrategyCandidate`` (instrumento + familia normalizada + grid).
* Ejecuta el LAB real y **persiste** el ``optimization_run`` (auditable).
* Devuelve un resultado compatible con ``evaluate_optimize_result`` que además
  expone ``optimization_run_id`` y ``edge_report_id``.

Sin red, sin IA y sin decisión cuantitativa propia: toda la semántica sigue en
``RunSmaGridOptimize`` + ``evaluate_optimize_result``. Fail-closed: los errores de
dominio (instrumento ausente, barras insuficientes) se traducen a ``None`` ("sin
evidencia"); jamás se inventa una evaluación.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import StrategyCandidate

__all__ = [
    "AUTO_LAB_GRID_DEFAULTS",
    "LabOptimizeRunner",
    "LabOptimizeResult",
]

logger = logging.getLogger(__name__)

# Grids por defecto por familia (familias-first: SMA/RSI/MACD). Sobreescribibles por
# candidata (``candidate.params``) y por env desde el composition root.
#
# IMPORTANTE: los periodos deben caber en la ventana de barras disponible, o
# ``assert_grid_warmup`` aborta la búsqueda y el LAB devuelve "sin trials"
# (backtest NOT_EVALUATED ⇒ nunca promociona). ``_prune_grid_to_window`` recorta los
# periodos que no caben en ``bar_limit`` antes de llamar al LAB.
AUTO_LAB_GRID_DEFAULTS: dict[str, dict[str, Any]] = {
    "sma_crossover": {
        "fast_periods": [10, 20, 30],
        "slow_periods": [50, 100, 150],
        "max_trials": 60,
        "bar_limit": 400,
    },
    "rsi_mean_reversion": {
        "periods": [7, 14, 21],
        "oversold_levels": [20.0, 30.0],
        "overbought_levels": [70.0, 80.0],
        "max_trials": 60,
        "bar_limit": 400,
    },
    "macd_signal_cross": {
        "macd_triples": [(12, 26, 9), (8, 21, 5)],
        "max_trials": 60,
        "bar_limit": 400,
    },
    # Alias tolerados por ``normalize_strategy_family``: el adaptador normaliza antes
    # de buscar el grid, así que estos son solo defensivos.
    "sma": {
        "fast_periods": [10, 20, 30],
        "slow_periods": [50, 100, 150],
        "max_trials": 60,
        "bar_limit": 400,
    },
}

# Parámetros estructurales del LAB (no del grid de búsqueda).
_LAB_RUN_KEYS = frozenset(
    {
        "initial_cash",
        "bar_limit",
        "timeframe",
        "engine",
        "oos_pct",
        "walk_forward_folds",
        "cpcv_groups",
        "cpcv_purge_bars",
        "cpcv_embargo_bars",
    }
)

_GRID_KEYS = frozenset(
    {
        "fast_periods",
        "slow_periods",
        "periods",
        "oversold_levels",
        "overbought_levels",
        "macd_triples",
        "max_trials",
    }
)


@dataclass(frozen=True, slots=True)
class LabOptimizeResult:
    """Resultado del LAB del AUTO: el optimizador real + su identidad persistida.

    Deliberadamente **no** es un ``OptimizeSmaGridResult`` porque ese dataclass no
    tiene ``optimization_run_id``/``edge_report_id``. Se exponen los campos que
    ``evaluate_optimize_result`` lee (``trials``, ``cpcv``, ``pbo``, ``walk_forward``,
    ``edge_report``) más la identidad para auditoría.
    """

    result: Any
    optimization_run_id: str | None = None
    edge_report_id: str | None = None

    @property
    def trials(self) -> Any:
        return getattr(self.result, "trials", None)

    @property
    def cpcv(self) -> Any:
        return getattr(self.result, "cpcv", None)

    @property
    def pbo(self) -> Any:
        return getattr(self.result, "pbo", None)

    @property
    def walk_forward(self) -> Any:
        return getattr(self.result, "walk_forward", None)

    @property
    def edge_report(self) -> Any:
        return getattr(self.result, "edge_report", None)

    def __getattr__(self, name: str) -> Any:
        # Delegación al resultado real para cualquier otro campo (instrument_id, engine…).
        # ``result`` se resuelve vía object.__getattribute__ para no recursar cuando el
        # atributo aún no está inicializado.
        result = object.__getattribute__(self, "result")
        return getattr(result, name)


class LabOptimizeRunner:
    """Adapta ``StrategyCandidate`` → ``RunSmaGridOptimizeAndSave`` (``OptimizeRunner``).

    Recibe el ``session_factory`` y un ``build_use_case(session)``: abre una sesión
    por llamada, construye el use-case dentro de ella y lo ejecuta. Así el adaptador
    no retiene una ``AsyncSession`` ni depende de factories globales, y respeta el
    patrón "una sesión por operación" del composition root del worker.
    """

    def __init__(
        self,
        session_factory: Callable[[], Any],
        build_use_case: Callable[[Any], Any],
        *,
        grid_defaults: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._build_use_case = build_use_case
        self._grid_defaults = dict(grid_defaults or AUTO_LAB_GRID_DEFAULTS)

    async def __call__(self, candidate: StrategyCandidate) -> LabOptimizeResult | None:
        family = _normalize_family(candidate.strategy_family)
        params = self._merge_params(family, candidate.params)
        # V2.31/A11 (Discovery): la candidata puede traer una definición declarativa
        # (familia del catálogo). En ese caso el LAB optimiza por reglas declarativas;
        # la definición viaja en ``params['definition']`` (no es un parámetro de grid).
        definition = params.pop("definition", None)
        if definition is None and isinstance(candidate.params, dict):
            raw_definition = candidate.params.get("definition")
            if isinstance(raw_definition, dict):
                definition = raw_definition

        try:
            async with self._session_factory() as session:
                use_case = self._build_use_case(session)
                outcome = await use_case.execute(
                    instrument_id=candidate.instrument_id,
                    strategy_family=family,
                    definition=definition,
                    **params,
                )
        except ValueError:
            # Errores de dominio del LAB (instrumento no encontrado / barras
            # insuficientes): "sin evidencia", no un fallo del ciclo.
            logger.info(
                "auto_orchestrator lab: sin evidencia candidate=%s instrument=%s",
                candidate.id,
                candidate.instrument_id,
            )
            return None

        result, run = _unwrap(outcome)
        if result is None:
            return None
        return LabOptimizeResult(
            result=result,
            optimization_run_id=getattr(run, "id", None),
            edge_report_id=_edge_report_id(result),
        )

    def _merge_params(self, family: str, candidate_params: dict[str, Any]) -> dict[str, Any]:
        """Grid por defecto de la familia + overrides libres del candidato."""
        from bolsa_application.optimize import (
            STRATEGY_FAMILY_MACD,
            STRATEGY_FAMILY_RSI,
            STRATEGY_FAMILY_SMA,
        )

        merged: dict[str, Any] = dict(self._grid_defaults.get(family, {}))
        for key, value in dict(candidate_params or {}).items():
            if key in _LAB_RUN_KEYS or key in _GRID_KEYS:
                merged[key] = value
            elif key == "definition":
                # V2.31/A11: la definición declarativa del Discovery no es un parámetro
                # de grid; se propaga aparte (ver ``__call__``).
                merged[key] = value
        if family in {STRATEGY_FAMILY_SMA, STRATEGY_FAMILY_RSI, STRATEGY_FAMILY_MACD}:
            return _prune_grid_to_window(family, merged)
        # Familia declarativa del Discovery: el grid lo aporta el catálogo dentro del
        # LAB (``RunSmaGridOptimize._run_rules``); no se recorta por warm-up de familia.
        return merged


def _prune_grid_to_window(family: str, params: dict[str, Any]) -> dict[str, Any]:
    """Recorta los periodos del grid que no caben en la ventana de barras.

    El LAB aborta con ``WarmupInsufficientError`` si el warm-up máximo del grid supera
    las barras disponibles, devolviendo "sin trials" (backtest NOT_EVALUATED). En vez
    de fallar en silencio, se descartan los periodos que no caben; si el grid queda
    vacío, se deja tal cual y el LAB decide (fail-closed honesto).
    """
    window = params.get("bar_limit")
    if not isinstance(window, int) or window <= 0:
        return params

    from bolsa_analytics.warmup_matrix import min_bars_for

    pruned = dict(params)
    if family in {"sma_crossover", "sma"}:
        fast = list(params.get("fast_periods") or [])
        slow = list(params.get("slow_periods") or [])
        valid = [
            (f, s)
            for f in fast
            for s in slow
            if f < s and int(min_bars_for("sma", {"fast": int(f), "slow": int(s)})) <= window
        ]
        if valid:
            pruned["fast_periods"] = sorted({f for f, _ in valid})
            pruned["slow_periods"] = sorted({s for _, s in valid})
    elif family == "macd_signal_cross":
        triples = list(params.get("macd_triples") or [])
        valid_triples = [
            t
            for t in triples
            if isinstance(t, (list, tuple))
            and len(t) == 3
            and int(min_bars_for("macd", {"fast": int(t[0]), "slow": int(t[1]), "signal": int(t[2])}))
            <= window
        ]
        if valid_triples:
            pruned["macd_triples"] = valid_triples
    elif family == "rsi_mean_reversion":
        periods = list(params.get("periods") or [])
        valid_periods = [
            p for p in periods if int(min_bars_for("rsi", {"period": int(p)})) <= window
        ]
        if valid_periods:
            pruned["periods"] = valid_periods
    return pruned


def _normalize_family(raw: str | None) -> str:
    """Normaliza la familia; si es desconocida, deja que el LAB decida (fail-closed)."""
    try:
        from bolsa_application.optimize import normalize_strategy_family

        return normalize_strategy_family(raw)
    except Exception:  # noqa: BLE001 — familia libre: el LAB validará y fallará honesto.
        return str(raw or "").strip().lower()


def _unwrap(outcome: Any) -> tuple[Any, Any]:
    """Acepta tanto ``(result, run)`` de *AndSave* como un ``result`` suelto."""
    if isinstance(outcome, tuple) and len(outcome) == 2:
        return outcome[0], outcome[1]
    return outcome, None


def _edge_report_id(result: Any) -> str | None:
    edge_report = getattr(result, "edge_report", None)
    if isinstance(edge_report, dict):
        raw = edge_report.get("persistedEdgeReportId") or edge_report.get("id")
        if isinstance(raw, str) and raw:
            return raw
    return None
