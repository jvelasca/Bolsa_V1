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
        # V2.32.1 (P1-01): recorte temporal del LAB para el hold-out shadow.
        "date_to",
        # V2.39 (incremento 4): si el LAB debe calcular y persistir el regimen de mercado
        # del trial (derivado de sus barras). Estructural, no de grid: lo inyecta el worker
        # segun ``AUTO_ORCHESTRATOR_ADAPTIVE_REGIME``. Con OFF no se calcula regimen.
        "emit_regime",
    }
)

# V2.32.1 (auditoría P1-02): defaults estructurales de ventana aplicables a TODAS las
# familias. ``cpcv_groups``/``walk_forward_folds`` NO se incluyen aquí; desde V2.34/A14
# las familias declarativas los reciben vía ``_DECLARATIVE_LAB_DEFAULTS`` porque el
# motor ya soporta CPCV/WF sobre definiciones declarativas.
_STRUCTURAL_LAB_DEFAULTS: dict[str, Any] = {
    "bar_limit": 400,
}

# V2.34/A14: defaults estructurales para familias DECLARATIVAS (catálogo de Discovery o
# gramática). A diferencia de las H0, estas familias sí soportan CPCV/WF desde A14
# (``RunSmaGridOptimize._run_cpcv/_run_walk_forward`` con ``definition`` declaran una
# rama declarativa), así que se les habilita el CPCV/WF por defecto para que los gates
# ``robustness``/``walk_forward`` dejen de quedar NOT_EVALUATED. Valores conservadores:
# ``cpcv_groups=4`` (> CPCV_MIN_GROUPS) y 3 folds WF. El candidato puede sobreescribirlos.
_DECLARATIVE_LAB_DEFAULTS: dict[str, Any] = {
    "cpcv_groups": 4,
    "walk_forward_folds": 3,
}

_GRID_KEYS = frozenset(
    {
        "fast_periods",
        "slow_periods",
        "periods",
        "oversold_levels",
        "overbought_levels",
        "macd_triples",
        "max_trials",
        # V2.34/A14: grid gramatical de la candidata (hermanos del plan). No es un
        # parámetro de grid H0 pero viaja igual hasta el optimizador declarativo.
        "grammar_variants",
    }
)

# V2.38 (incremento 3): claves de etiquetado del Discovery que NO son parametros de
# grid ni de corrida, pero deben propagarse hasta el trial persistido para poder agregar
# la evidencia por region de parametros. Hoy solo la region (bucket determinista v0).
_REGION_KEYS = frozenset({"discovery_param_region"})


@dataclass(frozen=True, slots=True)
class LabOptimizeResult:
    """Resultado del LAB del AUTO: el optimizador real + su identidad persistida.

    Deliberadamente **no** es un ``OptimizeSmaGridResult`` porque ese dataclass no
    tiene ``optimization_run_id``/``edge_report_id``. Se exponen los campos que
    ``evaluate_optimize_result`` lee (``trials``, ``cpcv``, ``pbo``, ``walk_forward``,
    ``edge_report``) más la identidad para auditoría.

    V2.32.1 (auditoría P1-01): ``lab_bars_used`` es la ventana de barras que usó el
    LAB. El orquestador la emplea para calcular el ``lab_end`` del hold-out estricto
    del shadow (la ventana shadow debe empezar *después* de la última barra del LAB).
    """

    result: Any
    optimization_run_id: str | None = None
    edge_report_id: str | None = None
    lab_bars_used: int | None = None

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
        emit_regime: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._build_use_case = build_use_case
        self._grid_defaults = dict(grid_defaults or AUTO_LAB_GRID_DEFAULTS)
        # V2.39 (incremento 4): si el LAB debe calcular y persistir el regimen de mercado
        # del trial. El composition root lo fija segun ``AUTO_ORCHESTRATOR_ADAPTIVE_REGIME``
        # (OFF por defecto). Con OFF, el trial se persiste sin regimen ⇒ equivalencia real
        # con V2.38.1 (ninguna dimension nueva en la evidencia).
        self._emit_regime = bool(emit_regime)

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
            lab_bars_used=_lab_bars_used(params, result),
        )

    def _merge_params(self, family: str, candidate_params: dict[str, Any]) -> dict[str, Any]:
        """Grid por defecto de la familia + overrides libres del candidato."""
        from bolsa_application.optimize import (
            STRATEGY_FAMILY_MACD,
            STRATEGY_FAMILY_RSI,
            STRATEGY_FAMILY_SMA,
        )

        # V2.32.1 (P1-02): el default estructural de ventana (``bar_limit``) se aplica a
        # TODAS las familias, incluidas las declarativas del Discovery, para que el corte
        # LAB/hold-out sea coherente. ``cpcv_groups``/``walk_forward_folds`` NO se fuerzan
        # aquí: solo las familias H0 los soportan (las declarativas los reciben del
        # catálogo o del candidato, y con ellos los gates robustness/walk_forward/oos
        # dejan de quedar NOT_EVALUATED).
        merged: dict[str, Any] = dict(_STRUCTURAL_LAB_DEFAULTS)
        merged.update(self._grid_defaults.get(family, {}))
        for key, value in dict(candidate_params or {}).items():
            if key in _LAB_RUN_KEYS or key in _GRID_KEYS:
                merged[key] = value
            elif key in _REGION_KEYS:
                # V2.38 (incremento 3): la region de parametros no es un parametro de
                # corrida; se propaga para que el trial persistido quede etiquetado y la
                # evidencia pueda agregarse por region (ver ``optimization_runs``).
                merged[key] = value
            elif key == "definition":
                # V2.31/A11: la definición declarativa del Discovery no es un parámetro
                # de grid; se propaga aparte (ver ``__call__``).
                merged[key] = value
        # V2.39 (incremento 4): el flag de regimen lo fija SIEMPRE el composition root,
        # no la candidata (la politica de rollout es del operador y debe ser fail-closed).
        # Se reafirma despues de los overrides para que una candidata no pueda encenderlo.
        merged["emit_regime"] = self._emit_regime
        if family in {STRATEGY_FAMILY_SMA, STRATEGY_FAMILY_RSI, STRATEGY_FAMILY_MACD}:
            return _prune_grid_to_window(family, merged)
        # V2.34/A14: familia declarativa (catálogo de Discovery o gramática). El motor
        # YA soporta CPCV/WF sobre definiciones declarativas
        # (``_run_declarative_partial_on_bars``), así que se aplican los defaults
        # estructurales para que ``robustness``/``walk_forward`` se midan de verdad.
        # El candidato puede sobreescribirlos (vienen de ``candidate_params``).
        for key, value in _DECLARATIVE_LAB_DEFAULTS.items():
            merged.setdefault(key, value)
        # El grid lo aporta el catálogo/gramática dentro del LAB; no se recorta por
        # warm-up de familia H0.
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


def _lab_bars_used(params: dict[str, Any], result: Any) -> int | None:
    """Ventana real de barras del LAB (para el ``lab_end`` del hold-out shadow).

    Prioriza el ``bar_count`` que el propio resultado del LAB reporta (las barras que
    de verdad cargó); si no está, cae al ``bar_limit`` solicitado. ``None`` si no se
    puede determinar (el shadow resolverá fail-closed: sin ``lab_end`` no hay
    separación demostrable).
    """
    bar_count = getattr(result, "bar_count", None)
    if isinstance(bar_count, int) and bar_count > 0:
        return bar_count
    bar_limit = params.get("bar_limit")
    if isinstance(bar_limit, int) and bar_limit > 0:
        return bar_limit
    return None
