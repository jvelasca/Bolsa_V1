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

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DISCOVERY_FAMILIES",
    "DiscoveryBudget",
    "DiscoveryFamily",
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
