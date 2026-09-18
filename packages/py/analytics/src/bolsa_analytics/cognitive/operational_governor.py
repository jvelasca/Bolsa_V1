"""OperationalGovernor — gobernador de riesgo y mercado (AUTO-3 · V2.43).

Separa tres hechos que hasta ahora vivían mezclados en el eje de régimen:

* **Mercado** (``MarketRegime``): qué está haciendo el mercado. Es un HECHO derivable
  as-of de las barras (``trend_up``/``trend_down``/``range``/``high_vol``/``low_vol``).
* **Riesgo de cartera** (``RiskRegime``): en qué estado de riesgo está la cuenta
  (drawdown medido + estado de medición del dinero).
* **Permiso operativo** (``OperationalState``): qué le está permitido hacer a AUTO.

Invariante que instala: *"el mercado está bajista" y "AUTO tiene prohibido abrir" son
hechos distintos, y ambos son explícitos, auditables y con fuente.*

Cómo se compone la tabla (``MarketRegime × RiskRegime × DD × Vol × Liquidez``):

1. Cada eje tiene un **techo declarado** (``*_cap``): el estado MÁS permisivo que ese eje
   autoriza por sí solo. Los mapas viven en este módulo, a la vista, y son la política.
2. El estado final es el **techo más estricto** de todos los ejes (``_STATE_SEVERITY``).
3. ``halted`` (kill switch) fuerza ``HALTED``: es la única entrada que no viene de un eje.

Propiedades que el gate exige y que este diseño garantiza por construcción:

* **Total**: cualquier combinación de ejes produce un estado; no hay default implícito.
* **Monótona**: cada ``*_cap`` es monótono por eje y el máximo de funciones monótonas es
  monótono, así que *más riesgo nunca produce un estado más permisivo*.
* **Fail-closed**: un eje ``UNKNOWN`` nunca es "libre" — tiene techo declarado
  (``EXIT_ONLY`` o ``ENTRY_RESTRICTED``), jamás ``ENTRY_ALLOWED``. Un valor no reconocido
  se normaliza a ``UNKNOWN`` (no se confía en lo que no se entiende).

El tamaño (``risk_scale``) se DERIVA del estado resuelto y no de cada eje: la composición
es por "el más estricto gana", no por producto de factores. Es una simplificación
declarada (dos ejes al 75 % no dan 56 %), y el motivo es que la severidad es el contrato
auditable y un producto de factores no sería reconstruible desde el journal.

Módulo **puro y determinista** (sin I/O, sin reloj, sin red): la lectura de barras,
drawdown y liquidez ocurre fuera, y aquí solo se decide. Nada de esto se activa por sí
solo: el llamante lo consulta solo con el governor habilitado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, cast

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MeasurementStatus,
    coerce_measurement,
)

# Bump cuando cambie la tabla / los techos / la semántica de escalado (auditabilidad).
GOVERNOR_VERSION = "auto_governor_v1"

# --- Ejes canónicos ----------------------------------------------------------------

# Hecho de mercado (agregado del universo, as-of). ``UNKNOWN`` ⇒ fail-closed.
MarketRegime = Literal[
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "HIGH_VOL",
    "LOW_VOL",
    "UNKNOWN",
]

# Estado de riesgo de la CARTERA (no del mercado): drawdown medido + medición del dinero.
RiskRegime = Literal["RISK_ON", "RISK_REDUCING", "RISK_OFF", "UNKNOWN"]

# Permiso operativo: la ÚNICA cosa que el motor de decisión debe leer.
OperationalState = Literal[
    "ENTRY_ALLOWED",
    "ENTRY_REDUCED",
    "ENTRY_RESTRICTED",
    "EXIT_ONLY",
    "HALTED",
]

# Bandas de entrada por dimensión. ``UNKNOWN`` está en cada una a propósito: "sin dato"
# es un valor de primera clase, nunca un hueco que se rellene con el tramo más benigno.
DrawdownBand = Literal["FULL", "REDUCED", "HALF", "NO_ENTRY", "EXIT_ONLY", "UNKNOWN"]
VolatilityBand = Literal["LOW", "NORMAL", "HIGH", "UNKNOWN"]
LiquidityBand = Literal["OK", "THIN", "UNKNOWN"]

ENCODED_OPERATIONAL_STATES: tuple[OperationalState, ...] = (
    "ENTRY_ALLOWED",
    "ENTRY_REDUCED",
    "ENTRY_RESTRICTED",
    "EXIT_ONLY",
    "HALTED",
)

ENCODED_MARKET_REGIMES: tuple[MarketRegime, ...] = (
    "TREND_UP",
    "TREND_DOWN",
    "RANGE",
    "HIGH_VOL",
    "LOW_VOL",
    "UNKNOWN",
)

ENCODED_DRAWDOWN_BANDS: tuple[DrawdownBand, ...] = (
    "FULL",
    "REDUCED",
    "HALF",
    "NO_ENTRY",
    "EXIT_ONLY",
    "UNKNOWN",
)

ENCODED_VOLATILITY_BANDS: tuple[VolatilityBand, ...] = ("LOW", "NORMAL", "HIGH", "UNKNOWN")

ENCODED_LIQUIDITY_BANDS: tuple[LiquidityBand, ...] = ("OK", "THIN", "UNKNOWN")

ENCODED_RISK_REGIMES: tuple[RiskRegime, ...] = ("RISK_ON", "RISK_REDUCING", "RISK_OFF", "UNKNOWN")

# Severidad creciente. ``HALTED`` es el techo absoluto (kill switch).
_STATE_SEVERITY: dict[str, int] = {
    "ENTRY_ALLOWED": 0,
    "ENTRY_REDUCED": 1,
    "ENTRY_RESTRICTED": 2,
    "EXIT_ONLY": 3,
    "HALTED": 4,
}

# Escala de riesgo declarada por estado resuelto. ``0.0`` en los dos estados sin entrada:
# el 0 es informativo (el veto es el hecho), no una invitación a dimensionar en cero.
RISK_SCALE_BY_STATE: dict[str, float] = {
    "ENTRY_ALLOWED": 1.0,
    "ENTRY_REDUCED": 0.75,
    "ENTRY_RESTRICTED": 0.5,
    "EXIT_ONLY": 0.0,
    "HALTED": 0.0,
}

# --- Techos declarados por eje (LA política, a la vista) ---------------------------

# Mercado. Un ``TREND_DOWN`` no fuerza deshacer riesgo por sí solo (para eso está el eje
# de riesgo y la política de salida, diferida): RESTRICTED reduce tamaño y sube el listón
# de edge, que es lo que evita comprar contra la tendencia confirmada de forma agresiva.
# ``UNKNOWN`` sí es EXIT_ONLY (fail-closed, coherente con ``regime_is_exit_only``).
_MARKET_CAP: dict[str, OperationalState] = {
    "TREND_UP": "ENTRY_ALLOWED",
    "RANGE": "ENTRY_ALLOWED",
    "LOW_VOL": "ENTRY_ALLOWED",
    "HIGH_VOL": "ENTRY_REDUCED",
    "TREND_DOWN": "ENTRY_RESTRICTED",
    "UNKNOWN": "EXIT_ONLY",
}

# Riesgo de cartera. ``UNKNOWN`` (medición incompleta) ⇒ EXIT_ONLY: no se abre riesgo
# nuevo contra un estado de riesgo que no se puede afirmar.
_RISK_CAP: dict[str, OperationalState] = {
    "RISK_ON": "ENTRY_ALLOWED",
    "RISK_REDUCING": "ENTRY_REDUCED",
    "RISK_OFF": "EXIT_ONLY",
    "UNKNOWN": "EXIT_ONLY",
}

# Drawdown: 100 % → 75 % → 50 % → NO ENTRY → EXIT_ONLY (roadmap AUTO-3). Es un mapeo
# 1:1 sobre los cinco estados, para no perder información entre tramos.
_DRAWDOWN_CAP: dict[str, OperationalState] = {
    "FULL": "ENTRY_ALLOWED",
    "REDUCED": "ENTRY_REDUCED",
    "HALF": "ENTRY_RESTRICTED",
    "NO_ENTRY": "EXIT_ONLY",
    "EXIT_ONLY": "HALTED",
    "UNKNOWN": "EXIT_ONLY",
}

# Volatilidad / liquidez: "sin dato ⇒ UNKNOWN ⇒ reduce o veta, nunca libre".
_VOLATILITY_CAP: dict[str, OperationalState] = {
    "LOW": "ENTRY_ALLOWED",
    "NORMAL": "ENTRY_ALLOWED",
    "HIGH": "ENTRY_REDUCED",
    "UNKNOWN": "ENTRY_RESTRICTED",
}

_LIQUIDITY_CAP: dict[str, OperationalState] = {
    "OK": "ENTRY_ALLOWED",
    "THIN": "ENTRY_RESTRICTED",
    "UNKNOWN": "ENTRY_RESTRICTED",
}

# Orden de ejes para declarar el eje que FIJA el techo (determinista en empates).
_AXIS_ORDER: tuple[str, ...] = (
    "halted",
    "drawdown",
    "risk",
    "market",
    "liquidity",
    "volatility",
)


def _coerce(value: Any, *, allowed: tuple[str, ...], unknown: str) -> str:
    """Normaliza una etiqueta de eje: un valor no reconocido es ``unknown`` (fail-closed).

    No se aceptan sinónimos ni minúsculas "casi": la etiqueta es el contrato con el
    journal, así que o es canónica o el eje se declara desconocido.
    """
    text = value.strip() if isinstance(value, str) else ""
    if text in allowed:
        return text
    return unknown


def coerce_market_regime(value: Any) -> MarketRegime:
    """Eje de mercado canónico (no reconocido ⇒ ``UNKNOWN``)."""
    return cast(
        MarketRegime,
        _coerce(value, allowed=ENCODED_MARKET_REGIMES, unknown="UNKNOWN"),
    )


def coerce_risk_regime(value: Any) -> RiskRegime:
    """Eje de riesgo canónico (no reconocido ⇒ ``UNKNOWN``)."""
    return cast(
        RiskRegime,
        _coerce(value, allowed=ENCODED_RISK_REGIMES, unknown="UNKNOWN"),
    )


def coerce_drawdown_band(value: Any) -> DrawdownBand:
    """Banda de drawdown canónica (no reconocida ⇒ ``UNKNOWN``)."""
    return cast(
        DrawdownBand,
        _coerce(value, allowed=ENCODED_DRAWDOWN_BANDS, unknown="UNKNOWN"),
    )


def coerce_volatility_band(value: Any) -> VolatilityBand:
    """Banda de volatilidad canónica (no reconocida ⇒ ``UNKNOWN``)."""
    return cast(
        VolatilityBand,
        _coerce(value, allowed=ENCODED_VOLATILITY_BANDS, unknown="UNKNOWN"),
    )


def coerce_liquidity_band(value: Any) -> LiquidityBand:
    """Banda de liquidez canónica (no reconocida ⇒ ``UNKNOWN``)."""
    return cast(
        LiquidityBand,
        _coerce(value, allowed=ENCODED_LIQUIDITY_BANDS, unknown="UNKNOWN"),
    )


def coerce_operational_state(value: Any) -> OperationalState | None:
    """Estado operativo canónico, o ``None`` si no lo es (para no inventar severidad)."""
    text = value.strip().upper() if isinstance(value, str) else ""
    if text in _STATE_SEVERITY:
        return cast(OperationalState, text)
    return None


def state_severity(state: Any) -> int:
    """Severidad declarada del estado; un estado no canónico es ``HALTED`` (fail-closed)."""
    coerced = coerce_operational_state(state)
    return _STATE_SEVERITY[coerced] if coerced is not None else _STATE_SEVERITY["HALTED"]


def market_cap(regime: MarketRegime | str | None) -> OperationalState:
    """Techo que impone por sí solo el hecho de mercado."""
    return _MARKET_CAP[coerce_market_regime(regime)]


def risk_cap(regime: RiskRegime | str | None) -> OperationalState:
    """Techo que impone por sí solo el estado de riesgo de cartera."""
    return _RISK_CAP[coerce_risk_regime(regime)]


def drawdown_cap(band: DrawdownBand | str | None) -> OperationalState:
    """Techo del tramo de drawdown."""
    return _DRAWDOWN_CAP[coerce_drawdown_band(band)]


def volatility_cap(band: VolatilityBand | str | None) -> OperationalState:
    """Techo de la banda de volatilidad."""
    return _VOLATILITY_CAP[coerce_volatility_band(band)]


def liquidity_cap(band: LiquidityBand | str | None) -> OperationalState:
    """Techo de la banda de liquidez."""
    return _LIQUIDITY_CAP[coerce_liquidity_band(band)]


def risk_scale_for_state(state: OperationalState | str | None) -> float:
    """Escala de riesgo declarada del estado (nunca > 1; fail-closed si no es canónico)."""
    coerced = coerce_operational_state(state)
    if coerced is None:
        return 0.0
    return RISK_SCALE_BY_STATE[coerced]


def strictest_state(*states: OperationalState | str | None) -> OperationalState:
    """Estado MÁS estricto de los aportados (monotonía: el máximo no se relaja nunca)."""
    worst: OperationalState = "ENTRY_ALLOWED"
    worst_severity = -1
    for state in states:
        coerced = coerce_operational_state(state)
        if coerced is None:
            return "HALTED"
        severity = _STATE_SEVERITY[coerced]
        if severity > worst_severity:
            worst = coerced
            worst_severity = severity
    return worst


def resolve_operational_state(
    *,
    market_regime: MarketRegime | str | None = None,
    risk_regime: RiskRegime | str | None = None,
    drawdown_band: DrawdownBand | str | None = None,
    volatility_band: VolatilityBand | str | None = None,
    liquidity_band: LiquidityBand | str | None = None,
    halted: bool = False,
) -> OperationalState:
    """Tabla de decisión: el techo más estricto de los ejes (kill switch incluido).

    Todos los ejes tienen default ``None`` ⇒ ``UNKNOWN`` ⇒ techo fail-closed, así que
    omitir un eje NUNCA es permisivo. Una combinación de ejes produce siempre un estado.
    """
    if halted:
        return "HALTED"
    return strictest_state(
        market_cap(market_regime),
        risk_cap(risk_regime),
        drawdown_cap(drawdown_band),
        volatility_cap(volatility_band),
        liquidity_cap(liquidity_band),
    )


@dataclass(frozen=True, slots=True)
class OperationalAssessment:
    """Lectura completa del gobernador: las tres dimensiones + el permiso + el porqué.

    Es lo que viaja al journal en cada decisión no-trade: ``market_regime`` y
    ``risk_regime`` son HECHOS con fuente, ``state`` es el PERMISO derivado y
    ``binding_axis`` dice qué eje fijó el techo (sin eso, un ``EXIT_ONLY`` no sería
    reconstruible desde el journal).
    """

    market_regime: MarketRegime
    risk_regime: RiskRegime
    drawdown_band: DrawdownBand
    volatility_band: VolatilityBand
    liquidity_band: LiquidityBand
    state: OperationalState
    risk_scale: float
    binding_axis: str

    @property
    def allows_new_entry(self) -> bool:
        """True si el estado autoriza alguna entrada nueva (con el tamaño que sea)."""
        return self.state in ("ENTRY_ALLOWED", "ENTRY_REDUCED", "ENTRY_RESTRICTED")

    @property
    def blocks_new_entry(self) -> bool:
        """True si el estado veta CUALQUIER entrada nueva."""
        return not self.allows_new_entry

    def to_dict(self) -> dict[str, Any]:
        return {
            "governorVersion": GOVERNOR_VERSION,
            "marketRegime": self.market_regime,
            "riskRegime": self.risk_regime,
            "drawdownBand": self.drawdown_band,
            "volatilityBand": self.volatility_band,
            "liquidityBand": self.liquidity_band,
            "operationalState": self.state,
            "riskScale": self.risk_scale,
            "bindingAxis": self.binding_axis,
        }


def _binding_axis(
    *,
    market_regime: MarketRegime | str | None,
    risk_regime: RiskRegime | str | None,
    drawdown_band: DrawdownBand | str | None,
    volatility_band: VolatilityBand | str | None,
    liquidity_band: LiquidityBand | str | None,
    halted: bool,
) -> str:
    """Eje que FIJA el techo final (el primero, en orden declarado, con esa severidad).

    Si ningún eje restringe (el permiso es ``ENTRY_ALLOWED``) devuelve ``"none"``: decir
    que el eje "halted" fijó el techo cuando no bloqueó nada sería un dato falso en el
    journal.
    """
    caps = {
        "halted": "HALTED" if halted else "ENTRY_ALLOWED",
        "drawdown": drawdown_cap(drawdown_band),
        "risk": risk_cap(risk_regime),
        "market": market_cap(market_regime),
        "liquidity": liquidity_cap(liquidity_band),
        "volatility": volatility_cap(volatility_band),
    }
    target = strictest_state(*caps.values())
    if target == "ENTRY_ALLOWED":
        return "none"
    for axis in _AXIS_ORDER:
        if caps[axis] == target:
            return axis
    return "none"


def assess_operational_state(
    *,
    market_regime: MarketRegime | str | None = None,
    risk_regime: RiskRegime | str | None = None,
    drawdown_band: DrawdownBand | str | None = None,
    volatility_band: VolatilityBand | str | None = None,
    liquidity_band: LiquidityBand | str | None = None,
    halted: bool = False,
) -> OperationalAssessment:
    """Resuelve el estado y devuelve la lectura completa (hechos + permiso + eje)."""
    state = resolve_operational_state(
        market_regime=market_regime,
        risk_regime=risk_regime,
        drawdown_band=drawdown_band,
        volatility_band=volatility_band,
        liquidity_band=liquidity_band,
        halted=halted,
    )
    return OperationalAssessment(
        market_regime=coerce_market_regime(market_regime),
        risk_regime=coerce_risk_regime(risk_regime),
        drawdown_band=coerce_drawdown_band(drawdown_band),
        volatility_band=coerce_volatility_band(volatility_band),
        liquidity_band=coerce_liquidity_band(liquidity_band),
        state=state,
        risk_scale=risk_scale_for_state(state),
        binding_axis=_binding_axis(
            market_regime=market_regime,
            risk_regime=risk_regime,
            drawdown_band=drawdown_band,
            volatility_band=volatility_band,
            liquidity_band=liquidity_band,
            halted=halted,
        ),
    )


# --- Derivación de bandas desde medidas (entradas del gobernador) ------------------


@dataclass(frozen=True, slots=True)
class DrawdownPolicy:
    """Política explícita de riesgo por tramo de drawdown (calibrable, SIEMPRE presente).

    Los umbrales son **porcentaje de caída** desde la marca de referencia del día
    (``EquityMarkBook``), no euros: así la política no depende del tamaño de la cuenta.
    Cuatro cortes declarados producen los cinco tramos del roadmap
    (100 % → 75 % → 50 % → NO ENTRY → EXIT_ONLY).

    Fail-closed: sin medición ``COMPLETE`` o sin número, la banda es ``UNKNOWN`` (que
    tiene techo ``EXIT_ONLY``), nunca ``FULL``.
    """

    reduced_pct: float = 5.0
    half_pct: float = 10.0
    no_entry_pct: float = 15.0
    exit_only_pct: float = 20.0

    def __post_init__(self) -> None:
        cuts = (self.reduced_pct, self.half_pct, self.no_entry_pct, self.exit_only_pct)
        if any(a >= b for a, b in zip(cuts, cuts[1:], strict=False)):
            raise ValueError("drawdown cuts must be strictly increasing")

    def band(
        self,
        drawdown_pct: float | None,
        *,
        measurement: MeasurementStatus | str | None = MEASUREMENT_COMPLETE,
    ) -> DrawdownBand:
        """Tramo de drawdown de la caída medida (``None``/no medible ⇒ ``UNKNOWN``)."""
        if coerce_measurement(measurement) != MEASUREMENT_COMPLETE:
            return "UNKNOWN"
        if drawdown_pct is None or not _is_finite(drawdown_pct):
            return "UNKNOWN"
        value = max(0.0, float(drawdown_pct))
        if value >= self.exit_only_pct:
            return "EXIT_ONLY"
        if value >= self.no_entry_pct:
            return "NO_ENTRY"
        if value >= self.half_pct:
            return "HALF"
        if value >= self.reduced_pct:
            return "REDUCED"
        return "FULL"


def risk_regime_from(
    *,
    drawdown_band: DrawdownBand | str | None,
    measurement: MeasurementStatus | str | None = MEASUREMENT_COMPLETE,
) -> RiskRegime:
    """``RiskRegime`` desde el tramo de drawdown y el estado de medición del dinero.

    Una medición que no es ``COMPLETE`` ⇒ ``UNKNOWN`` aunque la banda diga ``FULL``: el
    número existe pero es un SUELO, y un estado de riesgo no verificable no autoriza.
    """
    if coerce_measurement(measurement) != MEASUREMENT_COMPLETE:
        return "UNKNOWN"
    band = coerce_drawdown_band(drawdown_band)
    if band == "UNKNOWN":
        return "UNKNOWN"
    if band == "FULL":
        return "RISK_ON"
    if band in ("REDUCED", "HALF"):
        return "RISK_REDUCING"
    # NO_ENTRY / EXIT_ONLY: el drawdown ya manda deshacer riesgo.
    return "RISK_OFF"


def volatility_band_for(
    *,
    market_regime: MarketRegime | str | None,
    atr_known: bool,
) -> VolatilityBand:
    """Banda de volatilidad desde el hecho de mercado y la disponibilidad de geometría.

    ``HIGH_VOL``/``LOW_VOL`` son medidas del clasificador de barras y mandan sobre la
    disponibilidad del ATR. Sin régimen, o sin geometría de riesgo verificable, la banda
    es ``UNKNOWN`` (techo ``ENTRY_RESTRICTED``): nunca "libre" por ausencia de dato.
    """
    regime = coerce_market_regime(market_regime)
    if regime == "HIGH_VOL":
        return "HIGH"
    if regime == "LOW_VOL":
        return "LOW"
    if regime == "UNKNOWN" or not atr_known:
        return "UNKNOWN"
    return "NORMAL"


def liquidity_band_for(
    *,
    known: bool,
    notional: float | None,
    min_notional: float = 0.0,
) -> LiquidityBand:
    """Banda de liquidez desde la medición y el umbral declarado.

    Sin dato o con un valor no finito ⇒ ``UNKNOWN``. Con dato, por debajo del umbral
    (estricto: ``notional > min_notional`` para estar ``OK``) ⇒ ``THIN``.
    """
    if not known or notional is None or not _is_finite(notional):
        return "UNKNOWN"
    return "OK" if float(notional) > float(min_notional) else "THIN"


# Traducción del eje operativo existente (``market_regime_gate``) al eje de mercado.
# ``RISK_OFF`` (macro) NO se traduce a un régimen de mercado: es un hecho de RIESGO, y
# quien lo captura es ``RiskRegime``. Aquí ⇒ ``UNKNOWN`` (fail-closed).
_MARKET_FROM_OPERATIONAL: dict[str, MarketRegime] = {
    "BULL_TREND": "TREND_UP",
    "BEAR_TREND": "TREND_DOWN",
    "SIDEWAYS": "RANGE",
    "HIGH_VOLATILITY": "HIGH_VOL",
    "LOW_VOLATILITY": "LOW_VOL",
    "RISK_OFF": "UNKNOWN",
    "UNKNOWN": "UNKNOWN",
}


def to_market_regime(operational_regime: Any) -> MarketRegime:
    """Traduce el eje operativo existente (``market_regime_gate``) al eje de mercado.

    ``RISK_OFF`` (macro) no se traduce a un régimen de mercado: es un hecho de RIESGO, y
    quien lo captura es el eje ``RiskRegime``. Aquí ⇒ ``UNKNOWN`` (fail-closed).
    """
    text = str(operational_regime or "").strip().upper()
    return _MARKET_FROM_OPERATIONAL.get(text, "UNKNOWN")


@dataclass(frozen=True, slots=True)
class GovernorPolicy:
    """Política del gobernador (umbrales calibrables; el mecanismo siempre presente)."""

    drawdown: DrawdownPolicy = field(default_factory=DrawdownPolicy)
    # Notional mínimo para considerar la liquidez suficiente (estricto: > umbral).
    min_liquidity_notional: float = 0.0
    # Factor sobre ``min_edge`` en ``ENTRY_RESTRICTED``: el listón de edge sube, no solo
    # baja el tamaño. Un factor < 1 relajaría el listón y está prohibido por monotonía.
    restricted_edge_factor: float = 2.0

    def __post_init__(self) -> None:
        if self.restricted_edge_factor < 1.0:
            raise ValueError("restricted_edge_factor must be >= 1.0 (never relax)")
        if self.min_liquidity_notional < 0:
            raise ValueError("min_liquidity_notional must be >= 0")


def assess_from_measurements(
    *,
    operational_regime: Any,
    drawdown_pct: float | None,
    drawdown_measurement: MeasurementStatus | str | None,
    atr_known: bool,
    liquidity_known: bool,
    liquidity_notional: float | None,
    policy: GovernorPolicy | None = None,
    halted: bool = False,
) -> OperationalAssessment:
    """Camino corto medida → bandas → estado (una sola llamada para el hot path).

    Es el seam que usa el motor: recibe MEDIDAS (no juicios) y devuelve la lectura
    completa. Toda la política de umbrales vive en ``policy``, así que dos llamantes con
    la misma política y las mismas medidas obtienen el mismo estado.
    """
    resolved = policy if policy is not None else GovernorPolicy()
    market_regime = to_market_regime(operational_regime)
    drawdown_band = resolved.drawdown.band(
        drawdown_pct, measurement=drawdown_measurement
    )
    return assess_operational_state(
        market_regime=market_regime,
        risk_regime=risk_regime_from(
            drawdown_band=drawdown_band, measurement=drawdown_measurement
        ),
        drawdown_band=drawdown_band,
        volatility_band=volatility_band_for(market_regime=market_regime, atr_known=atr_known),
        liquidity_band=liquidity_band_for(
            known=liquidity_known,
            notional=liquidity_notional,
            min_notional=resolved.min_liquidity_notional,
        ),
        halted=halted,
    )


def _is_finite(value: Any) -> bool:
    """True si ``value`` es un número finito (``bool`` excluido: no es una medida)."""
    if value is None or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


__all__ = [
    "ENCODED_DRAWDOWN_BANDS",
    "ENCODED_LIQUIDITY_BANDS",
    "ENCODED_MARKET_REGIMES",
    "ENCODED_OPERATIONAL_STATES",
    "ENCODED_RISK_REGIMES",
    "ENCODED_VOLATILITY_BANDS",
    "GOVERNOR_VERSION",
    "RISK_SCALE_BY_STATE",
    "DrawdownBand",
    "DrawdownPolicy",
    "GovernorPolicy",
    "LiquidityBand",
    "MarketRegime",
    "OperationalAssessment",
    "OperationalState",
    "RiskRegime",
    "VolatilityBand",
    "assess_from_measurements",
    "assess_operational_state",
    "coerce_drawdown_band",
    "coerce_liquidity_band",
    "coerce_market_regime",
    "coerce_operational_state",
    "coerce_risk_regime",
    "coerce_volatility_band",
    "drawdown_cap",
    "liquidity_band_for",
    "liquidity_cap",
    "market_cap",
    "resolve_operational_state",
    "risk_cap",
    "risk_regime_from",
    "risk_scale_for_state",
    "state_severity",
    "strictest_state",
    "to_market_regime",
    "volatility_band_for",
    "volatility_cap",
]
