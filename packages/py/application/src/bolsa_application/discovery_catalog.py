"""V2.31 / A11 — catálogo de descubrimiento de estrategias (StatementDiscoveryEngine).

El LABORATORIO (``RunSmaGridOptimize``) solo optimizaba **tres familias** fijas
(``SUPPORTED_FAMILIES`` = SMA crossover / RSI mean-reversion / MACD signal cross),
mientras el motor de indicadores ofrece 33 ``definitionId``. Este módulo es el
**search space curado** que conecta ambos mundos: declara, de forma determinista y
sin red/IA/DB, las plantillas de reglas declarativas (``StrategyDefinitionV1``) sobre
las que el Discovery Engine genera candidatas.

Diseño (auditoría V2.30 §19/P2-03): NO se explora 30 indicadores x miles de
combinaciones (multiple testing, PBO, coste). Se declaran **familias acotadas** con
un espacio de parámetros pequeño y justificado, agrupadas en tres ramas:

    Trend      → cruces/seguimiento de tendencia (SMA/EMA, Donchian, SuperTrend, ADX, Ichimoku)
    Momentum   → osciladores de momento (RSI, MACD, Stoch, StochRSI, Williams %R, ROC)
    Volatility → volatilidad / reversión a la media (Bollinger)

Cada plantilla produce reglas en el MISMO esquema que consume
``evaluate_strategy_last_bar`` / ``evaluate_rules_signals``:

* ``indicator_cross``      — ``leftSpec`` cruza a ``rightSpec`` (bullish/bearish)
* ``indicator_compare``    — ``leftSpec`` < / > ``rightValue``
* ``price_vs_indicator``   — el precio cruza/compara con una banda de indicador

``template(params)`` es una función pura ``dict -> dict`` que materializa la
definición ejecutable para un punto del grid. Fail-closed: si faltan parámetros
obligatorios, ``template`` devuelve ``None`` y el punto no se convierte en candidata.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DISCOVERY_FAMILIES",
    "CatalogLane",
    "DiscoveryBudget",
    "DiscoveryBudgetAllocator",
    "DiscoveryFamily",
    "GrammarLane",
    "LaneAllocation",
    "PARENT_MOMENTUM",
    "PARENT_TREND",
    "PARENT_VOLATILITY",
    "families_by_parent",
    "family_by_name",
    "iter_param_points",
]

PARENT_TREND = "trend"
PARENT_MOMENTUM = "momentum"
PARENT_VOLATILITY = "volatility"

# Tipo de la plantilla: materializa una definición ejecutable desde un punto del grid.
# Devuelve ``None`` si el punto no es construible (fail-closed, no se inventa señal).
DefinitionTemplate = Callable[[Mapping[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True, slots=True)
class DiscoveryFamily:
    """Una plantilla de estrategia descubrible + su espacio de parámetros acotado.

    ``indicator_ids`` documenta qué ``definitionId`` de ``bolsa_analytics.indicators``
    usa la plantilla (auditoría / trazabilidad). ``param_space`` es un grid pequeño:
    el producto cartesiano de sus listas ES el número de puntos a evaluar por familia
    (acotado por ``DiscoveryBudget``).
    """

    name: str
    parent: str
    description: str
    indicator_ids: tuple[str, ...]
    param_space: dict[str, tuple[Any, ...]]
    template: DefinitionTemplate
    min_bars_hint: int = 60
    tags: tuple[str, ...] = field(default_factory=tuple)

    def param_points(self) -> list[dict[str, Any]]:
        """Producto cartesiano determinista del espacio de parámetros."""
        return iter_param_points(self.param_space)


def iter_param_points(param_space: Mapping[str, Sequence[Any]]) -> list[dict[str, Any]]:
    """Producto cartesiano estable (orden de las claves del mapping) de un grid.

    Determinista: el mismo ``param_space`` produce siempre la misma lista y en el
    mismo orden, de modo que las ``candidate_id`` del Discovery son reproducibles.
    """
    names = list(param_space.keys())
    if not names:
        return [{}]
    points: list[dict[str, Any]] = [{}]
    for name in names:
        values = list(param_space[name])
        if not values:
            return []
        points = [{**point, name: value} for point in points for value in values]
    return points


# ── Helpers de construcción de reglas (puras) ─────────────────────────────────


def _spec(definition_id: str, **parameters: Any) -> dict[str, Any]:
    return {"definitionId": definition_id, "parameters": dict(parameters)}


def _cross(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    direction: str,
    signal_kind: str,
) -> dict[str, Any]:
    return {
        "type": "indicator_cross",
        "leftSpec": left,
        "rightSpec": right,
        "direction": direction,
        "signalKind": signal_kind,
    }


def _compare(
    left: dict[str, Any],
    *,
    operator: str,
    right_value: float,
    signal_kind: str,
) -> dict[str, Any]:
    return {
        "type": "indicator_compare",
        "leftSpec": left,
        "operator": operator,
        "rightValue": right_value,
        "signalKind": signal_kind,
    }


def _price_vs(
    indicator: dict[str, Any],
    *,
    operator: str,
    signal_kind: str,
) -> dict[str, Any]:
    return {
        "type": "price_vs_indicator",
        "indicatorSpec": indicator,
        "operator": operator,
        "signalKind": signal_kind,
    }


def _definition(
    preset_key: str,
    specs: list[dict[str, Any]],
    *,
    entries: list[dict[str, Any]],
    exits: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "presetKey": preset_key,
        "indicatorSpecs": specs,
        "entries": {"operator": "all", "rules": entries},
        "exits": {"operator": "all", "rules": exits},
    }


# ── Plantillas Trend ──────────────────────────────────────────────────────────


def _tpl_ema_crossover(params: Mapping[str, Any]) -> dict[str, Any] | None:
    fast = params.get("fastPeriod")
    slow = params.get("slowPeriod")
    if not isinstance(fast, int) or not isinstance(slow, int) or fast <= 0 or slow <= 0:
        return None
    if fast >= slow:
        return None
    fast_spec = _spec("ema", period=fast)
    slow_spec = _spec("ema", period=slow)
    return _definition(
        "ema_crossover",
        [fast_spec, slow_spec],
        entries=[_cross(fast_spec, slow_spec, direction="bullish", signal_kind="entry_long")],
        exits=[_cross(fast_spec, slow_spec, direction="bearish", signal_kind="exit")],
    )


def _tpl_donchian_breakout(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    if not isinstance(period, int) or period <= 0:
        return None
    upper = _spec("dc", period=period, line="upper")
    lower = _spec("dc", period=period, line="lower")
    return _definition(
        "donchian_breakout",
        [upper, lower],
        entries=[_price_vs(upper, operator="gt", signal_kind="entry_long")],
        exits=[_price_vs(lower, operator="lt", signal_kind="exit")],
    )


def _tpl_supertrend_follow(params: Mapping[str, Any]) -> dict[str, Any] | None:
    atr_period = params.get("atrPeriod")
    multiplier = params.get("multiplier")
    if not isinstance(atr_period, int) or atr_period <= 0:
        return None
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
        return None
    if float(multiplier) <= 0:
        return None
    st = _spec("st", atrPeriod=atr_period, multiplier=float(multiplier))
    return _definition(
        "supertrend_follow",
        [st],
        entries=[_price_vs(st, operator="gt", signal_kind="entry_long")],
        exits=[_price_vs(st, operator="lt", signal_kind="exit")],
    )


def _tpl_adx_di_trend(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    threshold = params.get("threshold")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return None
    adx = _spec("adx", period=period, line="main")
    plus_di = _spec("adx", period=period, line="plus_di")
    minus_di = _spec("adx", period=period, line="minus_di")
    return _definition(
        "adx_di_trend",
        [adx, plus_di, minus_di],
        entries=[
            _compare(adx, operator="gt", right_value=float(threshold), signal_kind="entry_long"),
            {
                "type": "indicator_vs_indicator",
                "leftSpec": plus_di,
                "rightSpec": minus_di,
                "operator": "gt",
                "signalKind": "entry_long",
            },
        ],
        exits=[
            {
                "type": "indicator_vs_indicator",
                "leftSpec": plus_di,
                "rightSpec": minus_di,
                "operator": "lt",
                "signalKind": "exit",
            }
        ],
    )


def _tpl_sar_flip(params: Mapping[str, Any]) -> dict[str, Any] | None:
    step = params.get("step")
    max_step = params.get("maxStep")
    if not isinstance(step, (int, float)) or isinstance(step, bool) or float(step) <= 0:
        return None
    if not isinstance(max_step, (int, float)) or isinstance(max_step, bool):
        return None
    if float(max_step) <= 0:
        return None
    sar = _spec("sar", step=float(step), maxStep=float(max_step))
    return _definition(
        "sar_flip",
        [sar],
        entries=[_price_vs(sar, operator="gt", signal_kind="entry_long")],
        exits=[_price_vs(sar, operator="lt", signal_kind="exit")],
    )


def _tpl_ichimoku_tk_cross(params: Mapping[str, Any]) -> dict[str, Any] | None:
    tenkan = params.get("tenkanPeriod")
    kijun = params.get("kijunPeriod")
    if not isinstance(tenkan, int) or not isinstance(kijun, int):
        return None
    if tenkan <= 0 or kijun <= 0 or tenkan >= kijun:
        return None
    tenkan_spec = _spec("ich", tenkanPeriod=tenkan, kijunPeriod=kijun, line="tenkan")
    kijun_spec = _spec("ich", tenkanPeriod=tenkan, kijunPeriod=kijun, line="kijun")
    return _definition(
        "ichimoku_tk_cross",
        [tenkan_spec, kijun_spec],
        entries=[_cross(tenkan_spec, kijun_spec, direction="bullish", signal_kind="entry_long")],
        exits=[_cross(tenkan_spec, kijun_spec, direction="bearish", signal_kind="exit")],
    )


# ── Plantillas Momentum ───────────────────────────────────────────────────────


def _tpl_rsi_reversion(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    oversold = params.get("oversold")
    overbought = params.get("overbought")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(oversold, (int, float)) or isinstance(oversold, bool):
        return None
    if not isinstance(overbought, (int, float)) or isinstance(overbought, bool):
        return None
    if float(oversold) >= float(overbought):
        return None
    rsi = _spec("rsi", period=period)
    return _definition(
        "rsi_mean_reversion",
        [rsi],
        entries=[
            _compare(rsi, operator="lt", right_value=float(oversold), signal_kind="entry_long")
        ],
        exits=[
            _compare(rsi, operator="gt", right_value=float(overbought), signal_kind="exit")
        ],
    )


def _tpl_macd_signal_cross(params: Mapping[str, Any]) -> dict[str, Any] | None:
    fast = params.get("fastPeriod")
    slow = params.get("slowPeriod")
    signal = params.get("signalPeriod")
    if not all(isinstance(v, int) and v > 0 for v in (fast, slow, signal)):
        return None
    if fast >= slow:  # type: ignore[operator]
        return None
    base = {"fastPeriod": fast, "slowPeriod": slow, "signalPeriod": signal}
    main_spec = _spec("macd", line="main", **base)
    signal_spec = _spec("macd", line="signal", **base)
    return _definition(
        "macd_signal_cross",
        [main_spec, signal_spec],
        entries=[_cross(main_spec, signal_spec, direction="bullish", signal_kind="entry_long")],
        exits=[_cross(main_spec, signal_spec, direction="bearish", signal_kind="exit")],
    )


def _tpl_stoch_oversold(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    oversold = params.get("oversold")
    overbought = params.get("overbought")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(oversold, (int, float)) or isinstance(oversold, bool):
        return None
    if not isinstance(overbought, (int, float)) or isinstance(overbought, bool):
        return None
    if float(oversold) >= float(overbought):
        return None
    stoch = _spec("stoch", kPeriod=period)
    return _definition(
        "stoch_oversold",
        [stoch],
        entries=[
            _compare(stoch, operator="lt", right_value=float(oversold), signal_kind="entry_long")
        ],
        exits=[
            _compare(stoch, operator="gt", right_value=float(overbought), signal_kind="exit")
        ],
    )


def _tpl_stoch_rsi_reversion(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    oversold = params.get("oversold")
    overbought = params.get("overbought")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(oversold, (int, float)) or isinstance(oversold, bool):
        return None
    if not isinstance(overbought, (int, float)) or isinstance(overbought, bool):
        return None
    if float(oversold) >= float(overbought):
        return None
    srsi = _spec("srsi", period=period)
    return _definition(
        "stoch_rsi_reversion",
        [srsi],
        entries=[
            _compare(srsi, operator="lt", right_value=float(oversold), signal_kind="entry_long")
        ],
        exits=[
            _compare(srsi, operator="gt", right_value=float(overbought), signal_kind="exit")
        ],
    )


def _tpl_williams_r_reversion(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    oversold = params.get("oversold")
    overbought = params.get("overbought")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(oversold, (int, float)) or isinstance(oversold, bool):
        return None
    if not isinstance(overbought, (int, float)) or isinstance(overbought, bool):
        return None
    if float(oversold) >= float(overbought):
        return None
    willr = _spec("willr", period=period)
    return _definition(
        "williams_r_reversion",
        [willr],
        entries=[
            _compare(willr, operator="lt", right_value=float(oversold), signal_kind="entry_long")
        ],
        exits=[
            _compare(willr, operator="gt", right_value=float(overbought), signal_kind="exit")
        ],
    )


def _tpl_roc_momentum(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    threshold = params.get("threshold")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool):
        return None
    roc = _spec("roc", period=period)
    return _definition(
        "roc_momentum",
        [roc],
        entries=[
            _compare(roc, operator="gt", right_value=float(threshold), signal_kind="entry_long")
        ],
        exits=[
            _compare(roc, operator="lt", right_value=-float(threshold), signal_kind="exit")
        ],
    )


# ── Plantillas Volatility ─────────────────────────────────────────────────────


def _tpl_bb_reversion(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    std_dev = params.get("stdDev")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(std_dev, (int, float)) or isinstance(std_dev, bool):
        return None
    if float(std_dev) <= 0:
        return None
    lower = _spec("bb", period=period, stdDev=float(std_dev), line="lower")
    mid = _spec("bb", period=period, stdDev=float(std_dev), line="mid")
    return _definition(
        "bb_reversion",
        [lower, mid],
        entries=[_price_vs(lower, operator="lt", signal_kind="entry_long")],
        exits=[_price_vs(mid, operator="gt", signal_kind="exit")],
    )


def _tpl_bb_breakout(params: Mapping[str, Any]) -> dict[str, Any] | None:
    period = params.get("period")
    std_dev = params.get("stdDev")
    if not isinstance(period, int) or period <= 0:
        return None
    if not isinstance(std_dev, (int, float)) or isinstance(std_dev, bool):
        return None
    if float(std_dev) <= 0:
        return None
    upper = _spec("bb", period=period, stdDev=float(std_dev), line="upper")
    mid = _spec("bb", period=period, stdDev=float(std_dev), line="mid")
    return _definition(
        "bb_breakout",
        [upper, mid],
        entries=[_price_vs(upper, operator="gt", signal_kind="entry_long")],
        exits=[_price_vs(mid, operator="lt", signal_kind="exit")],
    )


# ── Catálogo (search space curado, determinista) ──────────────────────────────
#
# IMPORTANTE: cada lista de ``param_space`` se mantiene PEQUEÑA a propósito. El
# producto cartesiano de todas las familias es el coste máximo del discovery; el
# presupuesto (``DiscoveryBudget``) lo recorta además. Añadir un indicador aquí
# implica asumir el coste de multiple testing (mitigado por PBO/DSR en el LAB).

DISCOVERY_FAMILIES: tuple[DiscoveryFamily, ...] = (
    # ── Trend ──
    DiscoveryFamily(
        name="ema_crossover",
        parent=PARENT_TREND,
        description="Cruce de EMA rápida/lenta (seguimiento de tendencia)",
        indicator_ids=("ema",),
        param_space={
            "fastPeriod": (10, 20),
            "slowPeriod": (50, 100),
        },
        template=_tpl_ema_crossover,
        min_bars_hint=110,
        tags=("trend", "crossover"),
    ),
    DiscoveryFamily(
        name="donchian_breakout",
        parent=PARENT_TREND,
        description="Ruptura de canal Donchian (máximo/mínimo de N barras)",
        indicator_ids=("dc",),
        param_space={"period": (20, 40)},
        template=_tpl_donchian_breakout,
        min_bars_hint=50,
        tags=("trend", "breakout"),
    ),
    DiscoveryFamily(
        name="supertrend_follow",
        parent=PARENT_TREND,
        description="Precio vs SuperTrend (ATR x multiplicador)",
        indicator_ids=("st", "atr"),
        param_space={
            "atrPeriod": (10, 14),
            "multiplier": (2.0, 3.0),
        },
        template=_tpl_supertrend_follow,
        min_bars_hint=40,
        tags=("trend", "atr"),
    ),
    DiscoveryFamily(
        name="adx_di_trend",
        parent=PARENT_TREND,
        description="Tendencia confirmada por ADX con DI+ > DI-",
        indicator_ids=("adx",),
        param_space={
            "period": (14,),
            "threshold": (20.0, 25.0),
        },
        template=_tpl_adx_di_trend,
        min_bars_hint=40,
        tags=("trend", "strength"),
    ),
    DiscoveryFamily(
        name="sar_flip",
        parent=PARENT_TREND,
        description="Precio vs Parabolic SAR (giro de tendencia)",
        indicator_ids=("sar",),
        param_space={
            "step": (0.02,),
            "maxStep": (0.2,),
        },
        template=_tpl_sar_flip,
        min_bars_hint=40,
        tags=("trend", "flip"),
    ),
    DiscoveryFamily(
        name="ichimoku_tk_cross",
        parent=PARENT_TREND,
        description="Cruce Tenkan/Kijun de Ichimoku",
        indicator_ids=("ich",),
        param_space={
            "tenkanPeriod": (9,),
            "kijunPeriod": (26,),
        },
        template=_tpl_ichimoku_tk_cross,
        min_bars_hint=40,
        tags=("trend", "crossover"),
    ),
    # ── Momentum ──
    DiscoveryFamily(
        name="rsi_mean_reversion",
        parent=PARENT_MOMENTUM,
        description="RSI sobrevendido/sobrecomprado (reversión a la media)",
        indicator_ids=("rsi",),
        param_space={
            "period": (14, 21),
            "oversold": (30.0,),
            "overbought": (70.0,),
        },
        template=_tpl_rsi_reversion,
        min_bars_hint=40,
        tags=("momentum", "mean-reversion"),
    ),
    DiscoveryFamily(
        name="macd_signal_cross",
        parent=PARENT_MOMENTUM,
        description="Cruce MACD línea/señal",
        indicator_ids=("macd",),
        param_space={
            "fastPeriod": (12,),
            "slowPeriod": (26,),
            "signalPeriod": (9,),
        },
        template=_tpl_macd_signal_cross,
        min_bars_hint=40,
        tags=("momentum", "crossover"),
    ),
    DiscoveryFamily(
        name="stoch_oversold",
        parent=PARENT_MOMENTUM,
        description="Estocástico %K sobrevendido/sobrecomprado",
        indicator_ids=("stoch",),
        param_space={
            "period": (14, 21),
            "oversold": (20.0,),
            "overbought": (80.0,),
        },
        template=_tpl_stoch_oversold,
        min_bars_hint=40,
        tags=("momentum", "mean-reversion"),
    ),
    DiscoveryFamily(
        name="stoch_rsi_reversion",
        parent=PARENT_MOMENTUM,
        description="StochRSI sobrevendido/sobrecomprado",
        indicator_ids=("srsi", "rsi"),
        param_space={
            "period": (14,),
            "oversold": (20.0,),
            "overbought": (80.0,),
        },
        template=_tpl_stoch_rsi_reversion,
        min_bars_hint=40,
        tags=("momentum", "mean-reversion"),
    ),
    DiscoveryFamily(
        name="williams_r_reversion",
        parent=PARENT_MOMENTUM,
        description="Williams %R sobrevendido/sobrecomprado",
        indicator_ids=("willr",),
        param_space={
            "period": (14,),
            "oversold": (-80.0,),
            "overbought": (-20.0,),
        },
        template=_tpl_williams_r_reversion,
        min_bars_hint=40,
        tags=("momentum", "mean-reversion"),
    ),
    DiscoveryFamily(
        name="roc_momentum",
        parent=PARENT_MOMENTUM,
        description="Rate of Change: momentum positivo/negativo",
        indicator_ids=("roc",),
        param_space={
            "period": (10, 20),
            "threshold": (0.0,),
        },
        template=_tpl_roc_momentum,
        min_bars_hint=40,
        tags=("momentum", "rate-of-change"),
    ),
    # ── Volatility ──
    DiscoveryFamily(
        name="bb_reversion",
        parent=PARENT_VOLATILITY,
        description="Reversión desde banda inferior de Bollinger hacia la media",
        indicator_ids=("bb",),
        param_space={
            "period": (20,),
            "stdDev": (2.0, 2.5),
        },
        template=_tpl_bb_reversion,
        min_bars_hint=40,
        tags=("volatility", "mean-reversion"),
    ),
    DiscoveryFamily(
        name="bb_breakout",
        parent=PARENT_VOLATILITY,
        description="Ruptura de banda superior de Bollinger",
        indicator_ids=("bb",),
        param_space={
            "period": (20,),
            "stdDev": (2.0, 2.5),
        },
        template=_tpl_bb_breakout,
        min_bars_hint=40,
        tags=("volatility", "breakout"),
    ),
)


@dataclass(frozen=True, slots=True)
class DiscoveryBudget:
    """Presupuesto global del discovery por ciclo (anti-explosión combinatoria).

    ``max_trials_total`` se reparte entre las familias en orden del catálogo; una
    familia nunca aporta más de ``max_per_family`` puntos. ``max_candidates`` acota
    el total de candidatas emitidas (el resto se descarta de forma determinista).
    """

    max_trials_total: int = 48
    max_per_family: int = 8
    max_candidates: int = 24
    min_bars: int = 60

    def normalized(self) -> DiscoveryBudget:
        return DiscoveryBudget(
            max_trials_total=max(1, int(self.max_trials_total)),
            max_per_family=max(1, int(self.max_per_family)),
            max_candidates=max(1, int(self.max_candidates)),
            min_bars=max(1, int(self.min_bars)),
        )


# ── V2.36/A16 (auditoría P2-03): allocator explícito de presupuesto ────────────
#
# ANTES (A14): el presupuesto global se repartía por RESERVA SECUENCIAL — primero el
# catálogo consumía hasta agotar ``max_candidates`` y solo después se descontaba una
# reserva para la gramática. El ORDEN del search space decidía quién recibía cupo.
#
# AHORA: un allocator explícito con CUOTAS POR CARRIL. Cada carril declara un peso
# (``weight``) y un mínimo garantizado (``min_floor``); ``allocate()`` normaliza los
# pesos de forma determinista y reparte el presupuesto global por partes, sin que
# ningún carril pueda comerse a otro. La suma de techos nunca excede el presupuesto.
#
# ``adaptive`` queda declarado como carril de peso 0 (placeholder de la futura
# búsqueda adaptativa): NO implementa aprendizaje, solo reserva el hueco semántico.


class GrammarLane:
    """Carriles de la gramática a los que el allocator asigna cupo (namespace estable).

    Se usa ``str`` para el tipo de los campos del allocator; la clase solo centraliza
    los nombres para evitar literales dispersos (mismo patrón que los ``str`` ya
    existentes en el resto del catálogo).
    """

    SIMPLE = "grammar_simple"
    COMPOSITE = "grammar_composite"


class CatalogLane:
    """Carril del catálogo curado de familias técnicas."""

    NAME = "catalog"


@dataclass(frozen=True, slots=True)
class LaneAllocation:
    """Cupo asignado a un carril: techo de candidatas + techo de trials.

    Es un dato derivado (inmutable) del allocator + presupuesto. ``candidates`` es el
    máximo de candidatas que el carril puede emitir en el ciclo; ``trials`` el máximo
    de evaluaciones (puntos materializados) que puede consumir. Ambos se calculan a
    partir de pesos explícitos, nunca del consumo previo de otro carril.
    """

    candidates: int = 0
    trials: int = 0


@dataclass(frozen=True, slots=True)
class DiscoveryBudgetAllocator:
    """Reparto explícito y determinista del presupuesto global por carril (P2-03).

    Decisiones de diseño:

    * **Cuotas explícitas, no consumo secuencial.** Los pesos (``catalog_weight``,
      ``grammar_simple_weight``, ``grammar_composite_weight``, ``adaptive_weight``) y
      los mínimos (``*_min``) son la única fuente de verdad. ``allocate(budget)``
      normaliza los pesos y reparte ``max_candidates``/``max_trials_total`` por partes.
    * **Total y exhaustivo.** ``allocate`` no modifica estado ni depende del orden de
      llamadas: mismo ``(allocator, budget)`` ⇒ mismo reparto. Puede llamarse varias
      veces con el MISMO resultado (idempotente de facto).
    * **Nunca se sobrepasa el global.** La suma de ``candidates`` de TODOS los carriles
      es ``<= budget.max_candidates`` y la suma de ``trials`` ``<= max_trials_total``
      (garantizado por el método de reparto por quedas mayores).
    * **Ningún carril hambriento si se le concede suelo.** Un carril con
      ``weight > 0`` o ``min_floor > 0`` recibe al menos 1 candidata cuando el
      presupuesto lo permite (queda mayor con prioridad a los pisos), de modo que el
      bug A14 (el catálogo se comía todo y la gramática nunca corría) no puede repetirse.
    * **``adaptive``** se declara con peso 0 por defecto: es un placeholder para la
      futura búsqueda adaptativa; NO hay aprendizaje ni realimentación en el motor.

    Reparto (determinista):
      1. ``effective`` = budget.normalized().
      2. Si todos los pesos + pisos son 0 ⇒ todo al catálogo (compatibilidad).
      3. Cuota por peso mayorista (``floor(global * w / W)``) para candidatas y trials.
      4. Las quedas se reparten de mayor a menor (desempate por clase: catálogo primero,
         luego gramática simple, compuesta y adaptive; y enfin por orden alfabético).
      5. Se aplican los pisos: cada carril con derecho recibe al menos su piso y, si el
         presupuesto lo permite, al menos 1 candidata (suelo natural para pesos > 0).
      6. Se repara el total hacia abajo si la suma excediera el global.
    """

    catalog_weight: float = 2.0
    grammar_simple_weight: float = 1.0
    grammar_composite_weight: float = 1.0
    # Placeholder de la búsqueda adaptativa futura: peso 0 (no aprende, no emite).
    adaptive_weight: float = 0.0
    # Pisos garantizados por carril (siempre que el presupuesto global lo permita).
    catalog_min: int = 1
    grammar_simple_min: int = 1
    grammar_composite_min: int = 0
    adaptive_min: int = 0
    # V2.37/P2-02 — suelo de EXPLORACIÓN (anti auto-refuerzo del champion).
    #
    # Política formal exploración/explotación: el carril adaptativo (explotación) NUNCA
    # puede absorber el presupuesto de exploración. ``exploration_floor_ratio`` es la
    # fracción MÍNIMA del presupuesto global de candidatas que se reserva a los carriles
    # exploratorios (catálogo + gramática) antes de que el adaptive pueda tomar su parte.
    #
    # Esto convierte la cota de peso existente (``max_adaptive_weight``) en una política
    # explícita: aunque el prior adaptativo sea muy alto, siempre queda espacio de
    # exploración. Sin él, una familia con suerte recibiría más presupuesto, generaría más
    # evidencia sobre sí misma y se auto-reforzaría ("champion cannot teach itself").
    #
    # ``0.0`` = política desactivada (comportamiento histórico v2.36).
    exploration_floor_ratio: float = 0.5

    def normalized(self) -> DiscoveryBudgetAllocator:
        """Clamp defensivo: pesos/pisos no negativos (sin NaN/negativos)."""

        def _w(value: float) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return 0.0
            if number != number or number < 0:  # NaN o negativo ⇒ 0 (fail-safe)
                return 0.0
            return number

        def _m(value: int) -> int:
            try:
                number = int(value)
            except (TypeError, ValueError):
                return 0
            return max(0, number)

        def _r(value: float) -> float:
            try:
                number = float(value)
            except (TypeError, ValueError):
                return 0.0
            if number != number or number < 0:  # NaN o negativo ⇒ 0 (fail-safe)
                return 0.0
            return min(1.0, number)

        return DiscoveryBudgetAllocator(
            catalog_weight=_w(self.catalog_weight),
            grammar_simple_weight=_w(self.grammar_simple_weight),
            grammar_composite_weight=_w(self.grammar_composite_weight),
            adaptive_weight=_w(self.adaptive_weight),
            catalog_min=_m(self.catalog_min),
            grammar_simple_min=_m(self.grammar_simple_min),
            grammar_composite_min=_m(self.grammar_composite_min),
            adaptive_min=_m(self.adaptive_min),
            exploration_floor_ratio=_r(self.exploration_floor_ratio),
        )

    # Orden canónico de desempate (no alfabético): catálogo, gramática simple,
    # gramática compuesta, adaptive. Determinista y ajeno a la iteración de dicts.
    _TIE_ORDER: tuple[str, ...] = (
        CatalogLane.NAME,
        GrammarLane.SIMPLE,
        GrammarLane.COMPOSITE,
        "adaptive",
    )

    def allocate(self, budget: DiscoveryBudget) -> dict[str, LaneAllocation]:
        """Reparte ``budget`` entre los carriles de forma determinista y total.

        Devuelve un mapping carril → ``LaneAllocation``. El mapping contiene SIEMPRE
        los cuatro carriles declarados (aunque su cupo sea 0), de modo que el llamante
        no dependa de la presencia/ausencia de claves.
        """
        effective = budget.normalized()
        self_norm = self.normalized()

        weights: dict[str, float] = {
            CatalogLane.NAME: self_norm.catalog_weight,
            GrammarLane.SIMPLE: self_norm.grammar_simple_weight,
            GrammarLane.COMPOSITE: self_norm.grammar_composite_weight,
            "adaptive": self_norm.adaptive_weight,
        }
        floors: dict[str, int] = {
            CatalogLane.NAME: self_norm.catalog_min,
            GrammarLane.SIMPLE: self_norm.grammar_simple_min,
            GrammarLane.COMPOSITE: self_norm.grammar_composite_min,
            "adaptive": self_norm.adaptive_min,
        }
        lanes = self._TIE_ORDER

        total_candidates = int(effective.max_candidates)
        total_trials = int(effective.max_trials_total)

        # Caso degenerado: sin pesos ni pisos ⇒ todo al catálogo (compatibilidad con
        # el reparto histórico, que también daba todo al catálogo cuando no había
        # gramática). No se reparte nada a un carril sin derecho.
        if all(weights[lane] <= 0 and floors[lane] <= 0 for lane in lanes):
            return {
                lane: LaneAllocation(
                    candidates=total_candidates if lane == CatalogLane.NAME else 0,
                    trials=total_trials if lane == CatalogLane.NAME else 0,
                )
                for lane in lanes
            }

        weight_sum = sum(weights[lane] for lane in lanes)

        def _apportion(total: int, minimums: dict[str, int], tie: tuple[str, ...]) -> dict[str, int]:
            """Reparto mayorista con pisos y desempate determinista (largest remainder)."""
            if total <= 0:
                return {lane: 0 for lane in lanes}
            # 1) Cuota proporcional al peso.
            quotas: dict[str, float] = {
                lane: (total * weights[lane] / weight_sum) if weight_sum > 0 else 0.0
                for lane in lanes
            }
            base: dict[str, int] = {lane: int(quotas[lane]) for lane in lanes}
            assigned = sum(base.values())
            # 2) Orden de prioridad de las quedas: quedas mayores primero; empate por
            #    orden canónico de carril. Estable y ajeno al orden de iteración.
            order = sorted(
                lanes,
                key=lambda lane: (
                    -round(quotas[lane] - base[lane], 12),
                    tie.index(lane),
                ),
            )
            idx = 0
            while assigned < total and order:
                lane = order[idx % len(order)]
                base[lane] += 1
                assigned += 1
                idx += 1
            # 3) Pisos: un carril con derecho recibe al menos su piso (si cabe).
            for lane in lanes:
                if assigned >= total:
                    break
                floor = minimums[lane]
                if floor > base[lane]:
                    delta = min(floor - base[lane], total - assigned)
                    base[lane] += delta
                    assigned += delta
            return base

        candidates = _apportion(total_candidates, floors, lanes)
        trials = _apportion(total_trials, floors, lanes)

        # Suelo natural: un carril con peso > 0 o piso recibe al menos 1 candidata si
        # el presupuesto global lo permite. Esto es lo que garantiza que ni la
        # gramática ni el catálogo queden a 0 por culpa del otro — el bug A14. Si el
        # presupuesto ya está repartido, se toma una candidata del carril más dotado
        # (que conserve al menos 1) para donarla al carril hambriento.
        for lane in lanes:
            if candidates[lane] > 0:
                continue
            if weights[lane] <= 0 and floors[lane] <= 0:
                continue
            if total_candidates < 1:
                break
            if sum(candidates.values()) < total_candidates:
                candidates[lane] = 1
                continue
            donor_candidates = [
                other
                for other in lanes
                if other != lane and candidates[other] > 1
            ]
            if not donor_candidates:
                continue
            donor = max(
                donor_candidates,
                key=lambda other: (candidates[other], -self._TIE_ORDER.index(other)),
            )
            candidates[donor] -= 1
            candidates[lane] = 1

        # V2.37/P2-02 — suelo de EXPLORACIÓN (política formal anti auto-refuerzo).
        # El carril adaptativo (explotación) no puede comerse la exploración: se reserva
        # ``exploration_floor_ratio`` del presupuesto global de candidatas a los carriles
        # exploratorios (catálogo + gramática). Si el adaptive quedó por encima de su techo
        # permitido, la diferencia se devuelve a exploración (determinista, por orden de
        # carril). Con ``exploration_floor_ratio == 0`` la política está desactivada y el
        # reparto es el histórico.
        floor_ratio = float(self_norm.exploration_floor_ratio)
        if floor_ratio > 0 and total_candidates > 0:
            exploration_lanes = (
                CatalogLane.NAME,
                GrammarLane.SIMPLE,
                GrammarLane.COMPOSITE,
            )
            floor = int(math.ceil(total_candidates * floor_ratio))
            exploration_total = sum(candidates[lane] for lane in exploration_lanes)
            shortfall = max(0, floor - exploration_total)
            adaptive_excess = max(0, candidates["adaptive"] - (total_candidates - floor))
            for _ in range(min(shortfall, adaptive_excess)):
                if candidates["adaptive"] <= 0:
                    break
                candidates["adaptive"] -= 1
                # Devuelve la candidata al carril exploratorio con más peso (y, en
                # empate, al primero del orden canónico): determinista.
                donor = max(
                    exploration_lanes,
                    key=lambda lane: (weights[lane], -self._TIE_ORDER.index(lane)),
                )
                candidates[donor] += 1

        return {
            lane: LaneAllocation(candidates=int(candidates[lane]), trials=int(trials[lane]))
            for lane in lanes
        }

    def exploration_floor_candidates(self, budget: DiscoveryBudget) -> int:
        """Candidatas mínimas reservadas a exploración (catálogo + gramática).

        Política formal V2.37/P2-02: ``ceil(max_candidates * exploration_floor_ratio)``.
        Con la política desactivada (ratio 0) devuelve 0. Determinista.
        """
        effective = budget.normalized()
        ratio = self.normalized().exploration_floor_ratio
        if ratio <= 0:
            return 0
        return int(math.ceil(int(effective.max_candidates) * ratio))

    def normalized_weights(self) -> dict[str, float]:
        """Pesos normalizados (suman 1.0) para observabilidad/auditoría; no reparte.

        Determinista. Si todos los pesos son 0 devuelve el reparto degenerado (todo al
        catálogo) como pesos, coherente con ``allocate``.
        """
        self_norm = self.normalized()
        weights: dict[str, float] = {
            CatalogLane.NAME: self_norm.catalog_weight,
            GrammarLane.SIMPLE: self_norm.grammar_simple_weight,
            GrammarLane.COMPOSITE: self_norm.grammar_composite_weight,
            "adaptive": self_norm.adaptive_weight,
        }
        total = sum(weights.values())
        if total <= 0:
            return {
                lane: (1.0 if lane == CatalogLane.NAME else 0.0) for lane in self._TIE_ORDER
            }
        return {lane: weights[lane] / total for lane in self._TIE_ORDER}

    def lane_for_grammar(self, *, composite: bool = False) -> str:
        """Carril de gramática al que pertenece un plan (simple vs compuesto).

        ``composite`` = True cuando el plan combina más de un bloque opcional; en otro
        caso es ``grammar_simple``. La distinción es semántica (observabilidad y
        reparto), no un segundo motor.
        """
        return GrammarLane.COMPOSITE if composite else GrammarLane.SIMPLE

    @property
    def grammar_candidates(self) -> int:
        """Peso de gramática simple + compuesta (para el cupo agregado de la gramática)."""
        self_norm = self.normalized()
        return int(
            round(self_norm.grammar_simple_weight + self_norm.grammar_composite_weight)
        )


DEFAULT_DISCOVERY_ALLOCATOR = DiscoveryBudgetAllocator()


def family_by_name(name: str) -> DiscoveryFamily | None:
    """Busca una familia por nombre (estable, sin lanzar)."""
    target = str(name or "").strip().lower()
    return next((f for f in DISCOVERY_FAMILIES if f.name == target), None)


def families_by_parent(parent: str | None = None) -> tuple[DiscoveryFamily, ...]:
    """Familias filtradas por rama (``trend``/``momentum``/``volatility``)."""
    if parent is None:
        return DISCOVERY_FAMILIES
    target = str(parent).strip().lower()
    return tuple(f for f in DISCOVERY_FAMILIES if f.parent == target)
