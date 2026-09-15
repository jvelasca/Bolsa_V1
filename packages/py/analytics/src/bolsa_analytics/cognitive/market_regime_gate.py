"""MarketRegimeGate — régimen operativo y gating de entrada (AUTO 2.0 · P1).

Distingue el régimen de **Research** (ligado a la evidencia adaptativa del trial) del
régimen **operativo** que AUTO necesita ANTES de operar. El clasificador de barras
``discovery_market_regime_v0`` emite ``trend_up/trend_down/range/high_vol`` (o vacío);
el régimen macro cognitivo emite ``risk_on/risk_off/crisis/neutral/uncertain``. Este
módulo mapea ambos a un eje operativo único y decide si una entrada nueva está
permitida.

Eje operativo canónico::

    BULL_TREND / BEAR_TREND / SIDEWAYS / HIGH_VOLATILITY / LOW_VOLATILITY
    / RISK_OFF / UNKNOWN

Regla dura (fail-closed): ``UNKNOWN`` ⇒ **NO NEW ENTRY**. ``RISK_OFF`` ⇒ **NO NEW
LONG** (exit-only). El resto permite entrada, sujeta al resto de gates.

No es un motor de decisión: solo da un veredicto de régimen. El ``PortfolioDecisionEngine``
lo consulta como una de sus barreras.
"""

from __future__ import annotations

from typing import Literal

OperationalRegime = Literal[
    "BULL_TREND",
    "BEAR_TREND",
    "SIDEWAYS",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "RISK_OFF",
    "UNKNOWN",
]

# Etiquetas del clasificador de barras (discovery_market_regime_v0).
_TRIAL_TREND_UP = "trend_up"
_TRIAL_TREND_DOWN = "trend_down"
_TRIAL_RANGE = "range"
_TRIAL_HIGH_VOL = "high_vol"
_NO_REGIME = ""

# Etiquetas del régimen macro cognitivo (market_state.classify_regime).
_MACRO_RISK_ON = "risk_on"
_MACRO_RISK_OFF = "risk_off"
_MACRO_CRISIS = "crisis"
_MACRO_NEUTRAL = "neutral"
_MACRO_UNCERTAIN = "uncertain"

# Regímenes que bloquean una ENTRADA nueva (fail-closed).
_BLOCKED_ENTRY: frozenset[str] = frozenset({"UNKNOWN", "RISK_OFF"})


def map_trial_regime(trial_regime: str | None) -> OperationalRegime:
    """Mapea el régimen de barras (v0) al eje operativo. Vacío/desconocido ⇒ UNKNOWN."""
    value = str(trial_regime or "").strip()
    if value == _TRIAL_TREND_UP:
        return "BULL_TREND"
    if value == _TRIAL_TREND_DOWN:
        return "BEAR_TREND"
    if value == _TRIAL_RANGE:
        return "SIDEWAYS"
    if value == _TRIAL_HIGH_VOL:
        return "HIGH_VOLATILITY"
    return "UNKNOWN"


def map_macro_regime(macro_regime: str | None) -> OperationalRegime:
    """Mapea el régimen macro cognitivo al eje operativo. Desconocido ⇒ UNKNOWN."""
    value = str(macro_regime or "").strip().lower()
    if value in (_MACRO_CRISIS, _MACRO_RISK_OFF):
        return "RISK_OFF"
    if value == _MACRO_UNCERTAIN:
        return "UNKNOWN"
    if value == _MACRO_RISK_ON:
        return "BULL_TREND"
    if value == _MACRO_NEUTRAL:
        return "SIDEWAYS"
    return "UNKNOWN"


def resolve_operational_regime(
    *,
    trial_regime: str | None = None,
    macro_regime: str | None = None,
) -> OperationalRegime:
    """Resuelve el régimen operativo: prefiere el de barras (as-of), cae al macro.

    El régimen de barras es derivable as-of y determinista; el macro puede no estar
    disponible (dato live). Si el de barras es UNKNOWN y hay macro, se usa el macro.
    """
    trial = map_trial_regime(trial_regime)
    if trial != "UNKNOWN":
        return trial
    return map_macro_regime(macro_regime)


def regime_allows_new_entry(regime: OperationalRegime | str | None) -> bool:
    """True solo si el régimen permite UNA entrada nueva (fail-closed).

    ``UNKNOWN`` y ``RISK_OFF`` bloquean. El resto permite (sujeto a otros gates).
    """
    value = str(regime or "UNKNOWN").strip().upper()
    return value not in _BLOCKED_ENTRY


def regime_blocks_new_long(regime: OperationalRegime | str | None) -> bool:
    """True si el régimen veta un LONG nuevo (RISK_OFF/UNKNOWN/BEAR_TREND)."""
    value = str(regime or "UNKNOWN").strip().upper()
    return value in {"UNKNOWN", "RISK_OFF", "BEAR_TREND"}


def regime_blocks_new_short(regime: OperationalRegime | str | None) -> bool:
    """True si el régimen veta un SHORT nuevo (RISK_OFF/UNKNOWN/BULL_TREND).

    Simétrico de ``regime_blocks_new_long``: no se abre contra la tendencia confirmada.
    """
    value = str(regime or "UNKNOWN").strip().upper()
    return value in {"UNKNOWN", "RISK_OFF", "BULL_TREND"}


def regime_allows_entry_for(
    regime: OperationalRegime | str | None,
    direction: str | None = "long",
) -> bool:
    """Gate DIRECCIONAL de entrada (fail-closed): el que debe consultar el hot path.

    Combina el gate general (``UNKNOWN``/``RISK_OFF`` bloquean cualquier entrada) con el
    eje de dirección: un LONG no se abre en ``BEAR_TREND`` ni un SHORT en ``BULL_TREND``.
    Sin esta capa, ``regime_blocks_new_long`` quedaría sin uso y un motor long-only
    abriría en tendencia bajista confirmada.
    """
    if not regime_allows_new_entry(regime):
        return False
    if str(direction or "").strip().lower() == "short":
        return not regime_blocks_new_short(regime)
    return not regime_blocks_new_long(regime)


def regime_is_exit_only(regime: OperationalRegime | str | None) -> bool:
    """True si el régimen fuerza modo exit-only (no entradas, solo gestionar salidas)."""
    return not regime_allows_new_entry(regime)
