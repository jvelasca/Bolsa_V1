"""V2.34 / A14 — gramática controlada de Discovery (Strategy Intelligence).

Amplía el catálogo curado de ``discovery_catalog`` (familias técnicas fijas) con una
**gramática de composición**: una estrategia se describe como la conjunción de bloques
funcionales

    REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT

donde ``ENTRY_TRIGGER`` y ``EXIT`` son obligatorios y los otros tres son opcionales,
con un techo duro de **hasta 3 componentes** opcionales. La combinatoria nunca «explota»:
se acota con ``GrammarBudget`` (que envuelve ``DiscoveryBudget``) y con un orden de
enumeración total y determinista.

Decisiones de diseño (auditoría A14):

* **No hay segundo motor ni segundo FSM.** Cada plan materializa una
  ``StrategyDefinitionV1`` con los MISMOS helpers y el MISMO esquema que el catálogo
  (``entries``/``exits`` como ``RuleGroupV1`` planos con ``operator="all"``), que es lo
  que consume ``_simulate_rules_strategy`` / ``evaluate_rules_signals``.
* **No hay nesting.** ``RuleGroupV1`` es plano; la composición se logra eligiendo *qué*
  bloques entran en la conjunción, no añadiendo sintaxis al motor.
* **Determinismo total.** Mismo input ⇒ mismos planes, en el mismo orden e ids
  reproducibles. Cero aleatoriedad, cero IA, cero red/DB.
* **Fail-closed.** Un plan cuyos bloques no materializan no existe; un veto de
  compatibilidad descarta la combinación; sin trigger/exit no hay plan.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from bolsa_application.discovery_catalog import (
    DiscoveryBudget,
    _compare,
    _cross,
    _definition,
    _price_vs,
    _spec,
)

__all__ = [
    "COMPONENT_EXIT",
    "COMPONENT_MOMENTUM",
    "COMPONENT_REGIME",
    "COMPONENT_TREND_FILTER",
    "COMPONENT_TRIGGER",
    "GRAMMAR_COMPONENT_ORDER",
    "GrammarBudget",
    "GrammarComponent",
    "GrammarPlan",
    "enumerate_grammar_plans",
    "grammar_variants_for_plan",
]

# ── Vocabulario de bloques funcionales ────────────────────────────────────────

COMPONENT_REGIME = "regime"
COMPONENT_TREND_FILTER = "trend_filter"
COMPONENT_MOMENTUM = "momentum"
COMPONENT_TRIGGER = "entry_trigger"
COMPONENT_EXIT = "exit"

# Orden total y estable de enumeración (por posición de bloque). Los opcionales se
# combinan en este orden; trigger/exit son obligatorios y van al final del cálculo.
GRAMMAR_COMPONENT_ORDER: tuple[str, ...] = (
    COMPONENT_REGIME,
    COMPONENT_TREND_FILTER,
    COMPONENT_MOMENTUM,
)

# Bloques obligatorios: sin ellos el plan no se materializa (fail-closed).
_REQUIRED_COMPONENTS: tuple[str, ...] = (COMPONENT_TRIGGER, COMPONENT_EXIT)

# Techo duro de componentes OPCIONALES por combinación (no negociable: anti-explosión).
MAX_OPTIONAL_COMPONENTS = 3


# ── Piezas de la gramática ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GrammarComponent:
    """Una variante concreta de un bloque funcional.

    ``name`` es el identificador estable de la variante (trazabilidad / id de
    candidata). ``build_specs()`` devuelve los ``indicatorSpecs`` que necesita y
    ``build_rules()`` las reglas (todas con el ``signalKind`` del bloque) que se
    añaden a la conjunción. Ambas son puras y deterministas.

    La separación specs/reglas permite deduplicar specs entre bloques (p. ej. dos
    bloques que usan ``ema(20)`` no duplican el indicador).
    """

    name: str
    kind: str
    build_specs: Callable[[], list[dict[str, Any]]]
    build_rules: Callable[[], list[dict[str, Any]]]
    tags: tuple[str, ...] = field(default_factory=tuple)


# ── Catálogo de variantes por bloque (declarativo, acotado) ───────────────────
#
# Cada lista es PEQUEÑA a propósito. El producto de variantes es el coste teórico
# máximo; ``GrammarBudget`` y el techo de componentes lo recortan de forma
# determinista. Añadir una variante aquí implica asumir su coste de multiple testing
# (mitigado después por CPCV/PBO/DSR en el LAB).


def _regime_variants() -> tuple[GrammarComponent, ...]:
    """REGIME — habilitador contextual (veto si no se cumple)."""

    def _price_above_sma(period: int) -> GrammarComponent:
        spec = _spec("sma", period=period)

        def _specs() -> list[dict[str, Any]]:
            return [spec]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(spec, operator="gt", signal_kind="entry_long")]

        return GrammarComponent(
            name=f"regime_price_above_sma{period}",
            kind=COMPONENT_REGIME,
            build_specs=_specs,
            build_rules=_rules,
            tags=("regime", "trend"),
        )

    def _adx_above(threshold: float) -> GrammarComponent:
        adx = _spec("adx", period=14, line="main")

        def _specs() -> list[dict[str, Any]]:
            return [adx]

        def _rules() -> list[dict[str, Any]]:
            return [_compare(adx, operator="gt", right_value=threshold, signal_kind="entry_long")]

        return GrammarComponent(
            name=f"regime_adx_gt{int(threshold)}",
            kind=COMPONENT_REGIME,
            build_specs=_specs,
            build_rules=_rules,
            tags=("regime", "strength"),
        )

    return (
        _price_above_sma(200),
        _price_above_sma(100),
        _adx_above(20.0),
        _adx_above(25.0),
    )


def _trend_variants() -> tuple[GrammarComponent, ...]:
    """TREND FILTER — dirección de fondo."""

    def _ema_stack(fast: int, slow: int) -> GrammarComponent:
        fast_spec = _spec("ema", period=fast)
        slow_spec = _spec("ema", period=slow)

        def _specs() -> list[dict[str, Any]]:
            return [fast_spec, slow_spec]

        def _rules() -> list[dict[str, Any]]:
            return [
                {
                    "type": "indicator_vs_indicator",
                    "leftSpec": fast_spec,
                    "rightSpec": slow_spec,
                    "operator": "gt",
                    "signalKind": "entry_long",
                }
            ]

        return GrammarComponent(
            name=f"trend_ema{fast}_gt_ema{slow}",
            kind=COMPONENT_TREND_FILTER,
            build_specs=_specs,
            build_rules=_rules,
            tags=("trend",),
        )

    def _donchian_upper(period: int) -> GrammarComponent:
        # Mismo defecto y misma corrección que en ``_donchian_break`` del trigger: la
        # banda superior incluye la barra actual, así que ``close > upper`` es imposible
        # y el filtro de tendencia nunca deja pasar ninguna entrada. Se usa la banda
        # MEDIA (``close`` sobre el punto medio del canal = fondo alcista).
        mid = _spec("dc", period=period, line="mid")

        def _specs() -> list[dict[str, Any]]:
            return [mid]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(mid, operator="gt", signal_kind="entry_long")]

        return GrammarComponent(
            name=f"trend_dc{period}_breakout",
            kind=COMPONENT_TREND_FILTER,
            build_specs=_specs,
            build_rules=_rules,
            tags=("trend", "breakout"),
        )

    return (
        _ema_stack(20, 50),
        _ema_stack(10, 50),
        _donchian_upper(20),
        _donchian_upper(40),
    )


def _momentum_variants() -> tuple[GrammarComponent, ...]:
    """MOMENTUM — confirmación de impulso (nunca contradice al trigger de continuación)."""

    def _rsi_above(level: float) -> GrammarComponent:
        rsi = _spec("rsi", period=14)

        def _specs() -> list[dict[str, Any]]:
            return [rsi]

        def _rules() -> list[dict[str, Any]]:
            return [_compare(rsi, operator="gt", right_value=level, signal_kind="entry_long")]

        return GrammarComponent(
            name=f"momentum_rsi_gt{int(level)}",
            kind=COMPONENT_MOMENTUM,
            build_specs=_specs,
            build_rules=_rules,
            tags=("momentum",),
        )

    def _roc_above(threshold: float) -> GrammarComponent:
        roc = _spec("roc", period=12)

        def _specs() -> list[dict[str, Any]]:
            return [roc]

        def _rules() -> list[dict[str, Any]]:
            return [_compare(roc, operator="gt", right_value=threshold, signal_kind="entry_long")]

        return GrammarComponent(
            name=f"momentum_roc_gt{int(threshold)}",
            kind=COMPONENT_MOMENTUM,
            build_specs=_specs,
            build_rules=_rules,
            tags=("momentum", "rate-of-change"),
        )

    def _macd_bullish() -> GrammarComponent:
        main = _spec("macd", fastPeriod=12, slowPeriod=26, signalPeriod=9, line="main")
        signal = _spec("macd", fastPeriod=12, slowPeriod=26, signalPeriod=9, line="signal")

        def _specs() -> list[dict[str, Any]]:
            return [main, signal]

        def _rules() -> list[dict[str, Any]]:
            return [
                {
                    "type": "indicator_vs_indicator",
                    "leftSpec": main,
                    "rightSpec": signal,
                    "operator": "gt",
                    "signalKind": "entry_long",
                }
            ]

        return GrammarComponent(
            name="momentum_macd_gt_signal",
            kind=COMPONENT_MOMENTUM,
            build_specs=_specs,
            build_rules=_rules,
            tags=("momentum", "crossover"),
        )

    return (
        _rsi_above(50.0),
        _rsi_above(55.0),
        _roc_above(0.0),
        _macd_bullish(),
    )


def _trigger_variants() -> tuple[GrammarComponent, ...]:
    """ENTRY TRIGGER — disparador obligatorio (1 por plan)."""

    def _ema_cross(fast: int, slow: int) -> GrammarComponent:
        fast_spec = _spec("ema", period=fast)
        slow_spec = _spec("ema", period=slow)

        def _specs() -> list[dict[str, Any]]:
            return [fast_spec, slow_spec]

        def _rules() -> list[dict[str, Any]]:
            return [
                _cross(
                    fast_spec,
                    slow_spec,
                    direction="bullish",
                    signal_kind="entry_long",
                )
            ]

        return GrammarComponent(
            name=f"trigger_ema{fast}_cross_ema{slow}",
            kind=COMPONENT_TRIGGER,
            build_specs=_specs,
            build_rules=_rules,
            tags=("trigger", "crossover"),
        )

    def _donchian_break(period: int) -> GrammarComponent:
        # La banda ``upper`` del Donchian incluye la barra actual (``max(high)`` de la
        # ventana), así que ``close > upper`` es matemáticamente imposible: el máximo de
        # la ventana es siempre ≥ ``high[i]`` ≥ ``close[i]``. Un trigger así nunca
        # dispara (0 operaciones, 0 trials, sin evidencia posible). Se usa la banda
        # MEDIA como disparador de ruptura, igual que el preset ``donchian_breakout``
        # de producción: ``close`` por encima del punto medio del canal = tendencia.
        mid = _spec("dc", period=period, line="mid")

        def _specs() -> list[dict[str, Any]]:
            return [mid]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(mid, operator="gt", signal_kind="entry_long")]

        return GrammarComponent(
            name=f"trigger_dc{period}_break",
            kind=COMPONENT_TRIGGER,
            build_specs=_specs,
            build_rules=_rules,
            tags=("trigger", "breakout"),
        )

    def _bb_break(period: int, std_dev: float) -> GrammarComponent:
        upper = _spec("bb", period=period, stdDev=std_dev, line="upper")

        def _specs() -> list[dict[str, Any]]:
            return [upper]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(upper, operator="gt", signal_kind="entry_long")]

        return GrammarComponent(
            name=f"trigger_bb{period}_{std_dev}_break",
            kind=COMPONENT_TRIGGER,
            build_specs=_specs,
            build_rules=_rules,
            tags=("trigger", "volatility", "breakout"),
        )

    return (
        _ema_cross(10, 50),
        _ema_cross(20, 100),
        _donchian_break(20),
        _donchian_break(40),
        _bb_break(20, 2.0),
    )


def _exit_variants() -> tuple[GrammarComponent, ...]:
    """EXIT — salida obligatoria (1 por plan).

    Nota (P2-02, no-bug): ``exit_ema10_cross_ema50`` / ``exit_ema20_cross_ema100``
    comparten operandos con los triggers ``trigger_ema{10,20}_cross_ema{50,100}``, pero
    son reglas DISTINTAS (dirección bajista vs alcista y ``signalKind="exit"`` vs
    ``"entry_long"``). El veto ``_trend_regime_conflicts`` las acepta correctamente:
    reutilizar specs es legítimo y se deduplica al materializar.
    """

    def _ema_cross_down(fast: int, slow: int) -> GrammarComponent:
        fast_spec = _spec("ema", period=fast)
        slow_spec = _spec("ema", period=slow)

        def _specs() -> list[dict[str, Any]]:
            return [fast_spec, slow_spec]

        def _rules() -> list[dict[str, Any]]:
            return [
                _cross(
                    fast_spec,
                    slow_spec,
                    direction="bearish",
                    signal_kind="exit",
                )
            ]

        return GrammarComponent(
            name=f"exit_ema{fast}_cross_ema{slow}",
            kind=COMPONENT_EXIT,
            build_specs=_specs,
            build_rules=_rules,
            tags=("exit", "crossover"),
        )

    def _price_below_sma(period: int) -> GrammarComponent:
        sma = _spec("sma", period=period)

        def _specs() -> list[dict[str, Any]]:
            return [sma]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(sma, operator="lt", signal_kind="exit")]

        return GrammarComponent(
            name=f"exit_price_below_sma{period}",
            kind=COMPONENT_EXIT,
            build_specs=_specs,
            build_rules=_rules,
            tags=("exit",),
        )

    def _dc_lower(period: int) -> GrammarComponent:
        lower = _spec("dc", period=period, line="lower")

        def _specs() -> list[dict[str, Any]]:
            return [lower]

        def _rules() -> list[dict[str, Any]]:
            return [_price_vs(lower, operator="lt", signal_kind="exit")]

        return GrammarComponent(
            name=f"exit_dc{period}_lower",
            kind=COMPONENT_EXIT,
            build_specs=_specs,
            build_rules=_rules,
            tags=("exit", "breakout"),
        )

    return (
        _ema_cross_down(10, 50),
        _ema_cross_down(20, 100),
        _price_below_sma(50),
        _dc_lower(20),
    )


GRAMMAR_VARIANTS: dict[str, tuple[GrammarComponent, ...]] = {
    COMPONENT_REGIME: _regime_variants(),
    COMPONENT_TREND_FILTER: _trend_variants(),
    COMPONENT_MOMENTUM: _momentum_variants(),
    COMPONENT_TRIGGER: _trigger_variants(),
    COMPONENT_EXIT: _exit_variants(),
}
"""Variantes declaradas por bloque. Orden de tupla = orden de enumeración."""


# Pares axiales acoplados: permutar el TRIGGER de un plan cuyo EXIT es el homónimo
# bajista deja el exit mirando las MISMAS series que el trigger recién cambiado. Un
# cruce alcista y otro bajista de las mismas EMAs no pueden dispararse el mismo día, así
# que el trigger queda inalcanzable, la simulación no genera operaciones y el punto se
# descarta como trial. El resultado es un grid degenerado (menos de 2 columnas) y el PBO
# CSCV no puede calcularse: el LAB se queda sin evidencia real sobre candidatas
# gramaticales. Para evitar eso, cuando se permuta el trigger se arrastra el exit
# homónimo al par correspondiente (10/50 ↔ 10/50, 20/100 ↔ 20/100).
_AXIAL_TRIGGER_EXIT_PAIRS: tuple[tuple[str, str], ...] = (
    ("trigger_ema10_cross_ema50", "exit_ema10_cross_ema50"),
    ("trigger_ema20_cross_ema100", "exit_ema20_cross_ema100"),
)
"""Pares trigger↔exit homónimos que deben permutarse juntos (orden de tupla estable)."""

_TRIGGER_AXIS_KINDS: frozenset[str] = frozenset({COMPONENT_TRIGGER, COMPONENT_EXIT})
"""Bloques axiales: son la columna vertebral del plan (entrada/salida obligatorias)."""


# ── Vetos de compatibilidad (deterministas, sin IA) ───────────────────────────


def _rule_fingerprint(rule: Mapping[str, Any]) -> tuple[Any, ...]:
    """Huella estable de una regla (para detectar duplicados reales)."""

    def _spec_key(spec: Any) -> Any:
        if not isinstance(spec, Mapping):
            return None
        return (
            spec.get("definitionId"),
            tuple(sorted((spec.get("parameters") or {}).items())),
        )

    return (
        rule.get("type"),
        rule.get("signalKind"),
        rule.get("direction"),
        rule.get("operator"),
        rule.get("rightValue"),
        rule.get("value"),
        _spec_key(rule.get("leftSpec")),
        _spec_key(rule.get("rightSpec")),
        _spec_key(rule.get("indicatorSpec")),
    )


def _trend_regime_conflicts(components: Sequence[GrammarComponent]) -> bool:
    """Veto de redundancia: rechaza combinaciones con reglas duplicadas.

    Dos bloques pueden compartir specs (p. ej. trigger y exit sobre el mismo par de
    EMAs, con direcciones contrarias): eso es legítimo y los specs se deduplican al
    materializar. Lo que NO es admisible es repetir la MISMA regla (mismo tipo,
    operandos, dirección y ``signalKind``) en dos bloques, porque añade una condición
    redundante sin información.
    """
    seen: set[tuple[Any, ...]] = set()
    for component in components:
        for rule in component.build_rules():
            key = _rule_fingerprint(rule)
            if key in seen:
                return True
            seen.add(key)
    return False


def _mutually_unreachable_trigger_exit(components: Sequence[GrammarComponent]) -> bool:
    """Veto de inanición: trigger y exit que no pueden dispararse nunca.

    Un trigger de rango roto ``price_vs(dc:upper, gt)`` con un exit de canal
    ``price_vs(dc:lower, lt)`` es una estrategia vacía: para entrar el precio debe estar
    por encima de la banda superior y para salir por debajo de la inferior, así que el
    exit no puede cumplirse mientras la posición está abierta. No es un error de datos:
    la combinación es estructuralmente inoperable y el LAB solo puede registrar 0 trials.
    Se descarta el plan para no emitir candidatas que jamás producirán evidencia.

    El caso "comparten series" (p. ej. trigger EMA alcista vs exit EMA bajista del mismo
    par) NO entra aquí: es legítimo a nivel de reglas y no siempre es inoperable; el
    acoplamiento de ``_AXIAL_TRIGGER_EXIT_PAIRS`` ya lo resuelve al permutar.
    """
    by_kind = {component.kind: component for component in components}
    trigger = by_kind.get(COMPONENT_TRIGGER)
    exit_component = by_kind.get(COMPONENT_EXIT)
    if trigger is None or exit_component is None:
        return False

    trigger_rules = trigger.build_rules()
    exit_rules = exit_component.build_rules()
    if len(trigger_rules) != 1 or len(exit_rules) != 1:
        return False

    trigger_rule = trigger_rules[0]
    exit_rule = exit_rules[0]
    if trigger_rule.get("type") != "price_vs_indicator":
        return False
    if exit_rule.get("type") != "price_vs_indicator":
        return False
    if trigger_rule.get("operator") != "gt" or exit_rule.get("operator") != "lt":
        return False

    trigger_spec = trigger_rule.get("indicatorSpec") or {}
    exit_spec = exit_rule.get("indicatorSpec") or {}
    trigger_params = dict(trigger_spec.get("parameters") or {})
    exit_params = dict(exit_spec.get("parameters") or {})
    # Mismo indicador y mismo periodo, pero bandas opuestas (upper/lower): rango que
    # nunca se cumple de entrada a salida.
    return (
        trigger_spec.get("definitionId") == exit_spec.get("definitionId")
        and trigger_params.get("period") == exit_params.get("period")
        and trigger_params.get("line") == "upper"
        and exit_params.get("line") == "lower"
    )


def _conjunctive_ema_starvation(components: Sequence[GrammarComponent]) -> bool:
    """Veto de inanición: trigger EMA y filtro de tendencia EMA que se excluyen.

    El trigger ``trigger_ema10_cross_ema50`` sólo puede dispararse en un cruce al alza de
    EMA10 sobre EMA50, y los gates conjuntivos del plan (régimen de tendencia y filtro
    ``trend_ema20_gt_ema50``) deben cumplirse SIMULTÁNEAMENTE. Pero un cruce de EMA10
    sobre EMA50 ocurre necesariamente antes de que EMA20 confirme por encima de EMA50,
    así que ``EMA10 > EMA50`` y ``EMA20 > EMA50`` no son ciertos en ningún cruce. Medido
    sobre una serie de ciclos: 210 barras cumplen ambas condiciones, 0 cruces.

    El resultado es un plan estructuralmente inoperable (0 trials, sin evidencia). Se
    veta para no emitir candidatas que jamás podrán promocionar. Un filtro de tendencia
    más lento (EMA10 sobre EMA50) sí es compatible con el trigger y se acepta.
    """
    by_kind = {component.kind: component for component in components}
    trigger = by_kind.get(COMPONENT_TRIGGER)
    trend = by_kind.get(COMPONENT_TREND_FILTER)
    if trigger is None or trend is None:
        return False

    trigger_rules = trigger.build_rules()
    if len(trigger_rules) != 1 or trigger_rules[0].get("type") != "indicator_cross":
        return False
    if trigger_rules[0].get("direction") != "bullish":
        return False

    left = trigger_rules[0].get("leftSpec") or {}
    right = trigger_rules[0].get("rightSpec") or {}
    if left.get("definitionId") != "ema" or right.get("definitionId") != "ema":
        return False
    trigger_fast = (left.get("parameters") or {}).get("period")
    trigger_slow = (right.get("parameters") or {}).get("period")

    # El filtro de tendencia debe ser un EMA-stack con el MISMO par lento/corto que el
    # trigger pero confirmando desde la pata lenta (p. ej. trigger 10/50 + trend 20/50).
    trend_rules = trend.build_rules()
    if len(trend_rules) != 1 or trend_rules[0].get("type") != "indicator_vs_indicator":
        return False
    t_left = trend_rules[0].get("leftSpec") or {}
    t_right = trend_rules[0].get("rightSpec") or {}
    if t_left.get("definitionId") != "ema" or t_right.get("definitionId") != "ema":
        return False
    trend_fast = (t_left.get("parameters") or {}).get("period")
    trend_slow = (t_right.get("parameters") or {}).get("period")

    # Misma pata lenta y pata rápida MÁS LENTA que la del trigger ⇒ el filtro confirma
    # después de que el trigger haya cruzado ⇒ el trigger es inalcanzable.
    return trend_slow == trigger_slow and isinstance(trend_fast, int) and isinstance(
        trigger_fast, int
    ) and trend_fast > trigger_fast


def _plan_is_coherent(components: Sequence[GrammarComponent]) -> bool:
    """True si la combinación de bloques es admisible (pasa todos los vetos)."""
    return (
        not _trend_regime_conflicts(components)
        and not _mutually_unreachable_trigger_exit(components)
        and not _conjunctive_ema_starvation(components)
    )


# ── Plan gramatical ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GrammarPlan:
    """Una combinación concreta de bloques, materializable a ``StrategyDefinitionV1``.

    ``name`` es estable y determinista (deriva de los nombres de las variantes en el
    orden canónico de bloques), de modo que el mismo plan produce siempre el mismo
    ``presetKey`` y el mismo id de candidata.
    """

    name: str
    components: tuple[GrammarComponent, ...]

    @property
    def preset_key(self) -> str:
        return f"grammar_{self.name}"

    def materialize(self) -> dict[str, Any] | None:
        """Construye la ``StrategyDefinitionV1`` ejecutable (fail-closed).

        Une las reglas de todos los bloques en ``entries`` (conjunción ``all``) y las
        del bloque EXIT en ``exits``. Deduplica ``indicatorSpecs`` por clave
        ``definitionId::parameters`` para no recalcular el mismo indicador. Devuelve
        ``None`` si falta algún bloque obligatorio o no hay reglas (no se inventa una
        definición).
        """
        by_kind: dict[str, list[GrammarComponent]] = {}
        for component in self.components:
            by_kind.setdefault(component.kind, []).append(component)

        for required in _REQUIRED_COMPONENTS:
            if required not in by_kind:
                return None

        entries: list[dict[str, Any]] = []
        exits: list[dict[str, Any]] = []
        specs: list[dict[str, Any]] = []
        seen_specs: set[str] = set()

        # Orden determinista de emisión: obligatorios primero en orden canónico, luego
        # los opcionales en el orden de ``GRAMMAR_COMPONENT_ORDER``.
        ordered_kinds = (*_REQUIRED_COMPONENTS, *GRAMMAR_COMPONENT_ORDER)
        emitted_kinds: set[str] = set()
        for kind in ordered_kinds:
            if kind in emitted_kinds:
                continue
            emitted_kinds.add(kind)
            for component in by_kind.get(kind, ()):
                for spec in component.build_specs():
                    key = f"{spec.get('definitionId')}::{sorted((spec.get('parameters') or {}).items())}"
                    if key not in seen_specs:
                        seen_specs.add(key)
                        specs.append(spec)
                if kind == COMPONENT_EXIT:
                    exits.extend(component.build_rules())
                else:
                    entries.extend(component.build_rules())

        if not entries or not exits:
            return None

        return _definition(
            self.preset_key,
            specs,
            entries=entries,
            exits=exits,
        )


# ── Presupuesto y enumeración determinista ────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GrammarBudget:
    """Presupuesto de la gramática: envuelve ``DiscoveryBudget`` con techo de bloques.

    El presupuesto GLOBAL de discovery sigue siendo uno solo (``base``): la gramática
    consume su remanente, nunca un presupuesto paralelo. ``max_components`` acota los
    bloques OPCIONALES por combinación (1..``MAX_OPTIONAL_COMPONENTS``);
    ``max_per_component_variant`` acota cuántas variantes de cada bloque entran en la
    enumeración (anti-explosión determinista).
    """

    base: DiscoveryBudget = field(default_factory=DiscoveryBudget)
    max_components: int = MAX_OPTIONAL_COMPONENTS
    max_per_component_variant: int = 4
    min_bars: int = 120

    def normalized(self) -> GrammarBudget:
        return GrammarBudget(
            base=self.base.normalized(),
            max_components=max(1, min(int(self.max_components), MAX_OPTIONAL_COMPONENTS)),
            max_per_component_variant=max(1, int(self.max_per_component_variant)),
            min_bars=max(1, int(self.min_bars)),
        )


def _ordered_variants() -> dict[str, tuple[GrammarComponent, ...]]:
    """Variantes en orden de tupla (estable)."""
    return GRAMMAR_VARIANTS


def enumerate_grammar_plans(
    budget: GrammarBudget | None = None,
) -> tuple[GrammarPlan, ...]:
    """Enumera los planes gramaticales de forma determinista y acotada.

    Orden total: por nº de componentes opcionales (1, 2, 3), luego por la combinación
    de bloques en el orden de ``GRAMMAR_COMPONENT_ORDER`` (``combinations`` ya es
    lexicográfico y estable), luego por el producto de variantes en orden de tupla con
    un índice mixto que recorre la ÚLTIMA dimensión más rápido (producto cartesiano
    estable). El corte se aplica por presupuesto ANTES de materializar.

    Nunca hay aleatoriedad: el mismo presupuesto produce siempre la misma tupla de
    planes, en el mismo orden.
    """
    effective = (budget or GrammarBudget()).normalized()
    variants = _ordered_variants()
    cap = effective.max_per_component_variant

    # Variantes recortadas por bloque, en orden estable.
    pool: dict[str, tuple[GrammarComponent, ...]] = {
        kind: tuple(variants.get(kind, ()))[:cap] for kind in variants
    }

    optional_kinds = tuple(
        kind for kind in GRAMMAR_COMPONENT_ORDER if pool.get(kind)
    )
    triggers = pool.get(COMPONENT_TRIGGER, ())
    exits = pool.get(COMPONENT_EXIT, ())
    if not triggers or not exits:
        return ()

    plans: list[GrammarPlan] = []

    for count in range(1, effective.max_components + 1):
        for combo in combinations(optional_kinds, count):
            # Producto cartesiano estable de las variantes de los opcionales.
            optionals: list[list[GrammarComponent]] = [
                list(pool[kind]) for kind in combo
            ]
            for chosen in _cartesian(optionals):
                # Orden de anidamiento: ``exit`` es el bucle EXTERNO y ``trigger`` el
                # INTERNO, de modo que el trigger varía más rápido que el exit y ambos más
                # rápido que la combinación de opcionales. Así un corte por cupo (el
                # allocator concede pocas candidatas) cubre varios triggers en lugar de
                # agotar todas las variantes de exit bajo un solo trigger (P2-01). Medido:
                # con cap=4 antes salía 1 trigger × 4 exits; ahora 4 triggers × 1 exit.
                for exit_component in exits:
                    for trigger in triggers:
                        components = (
                            *chosen,
                            trigger,
                            exit_component,
                        )
                        if not _plan_is_coherent(components):
                            continue
                        name = "__".join(
                            component.name for component in _canonical_order(components)
                        )
                        plans.append(GrammarPlan(name=name, components=tuple(components)))

    # Deduplicación estable (un plan puede repetirse si dos bloques comparten variante
    # que colisiona en nombre) preservando el primer orden de aparición.
    seen: set[str] = set()
    unique: list[GrammarPlan] = []
    for plan in plans:
        if plan.name in seen:
            continue
        seen.add(plan.name)
        unique.append(plan)
    return tuple(unique)


def _cartesian(pools: Sequence[Sequence[GrammarComponent]]) -> list[tuple[GrammarComponent, ...]]:
    """Producto cartesiano estable (la última dimensión varía más rápido)."""
    result: list[tuple[GrammarComponent, ...]] = [()]
    for pool in pools:
        result = [(*prefix, item) for prefix in result for item in pool]
    return result


def _canonical_order(
    components: Sequence[GrammarComponent],
) -> tuple[GrammarComponent, ...]:
    """Reordena los bloques en el orden canónico (obligatorios + opcionales)."""
    order_index = {kind: i for i, kind in enumerate((*_REQUIRED_COMPONENTS, *GRAMMAR_COMPONENT_ORDER))}
    return tuple(sorted(components, key=lambda c: (order_index.get(c.kind, 99), c.name)))


def grammar_variants_for_plan(
    plan: GrammarPlan,
    *,
    max_variants: int = 4,
    axis_index: int = 0,
) -> list[dict[str, Any]]:
    """Grid de variantes hermanas del plan para el LAB (A14).

    Un plan gramatical es UNA definición concreta, sin grid propio. Para que el LAB
    re-optimice de verdad y el PBO CSCV tenga múltiples columnas que rankear, se
    devuelven variantes hermanas: el mismo plan del que se permuta UNA variante de UN
    bloque (uno de los bloques presentes: los OPCIONALES si los hay, y solo si no hay
    ninguno, el trigger), manteniendo el resto fijo. El primer elemento es SIEMPRE el
    propio plan (la candidata que trajo el Discovery), de modo que el campeón pueda ser
    la original.

    ``axis_index`` selecciona de forma DETERMINISTA qué bloque se permuta, rotando
    sobre los bloques permutables del plan (``axis_index % len(permutables)``). El eje
    son preferentemente los OPCIONALES presentes (regime/trend/momentum) y nunca el
    último opcional a secas: rotar sobre el conjunto completo evita que dos planes
    vecinos compartan siempre el mismo eje, de modo que el LAB rankea columnas que
    varían de verdad (P2-01). Los bloques axiales (trigger/exit) solo entran como eje
    cuando el plan no tiene ningún opcional. El llamante pasa un índice estable (p. ej.
    el orden de emisión); el valor por defecto 0 conserva el comportamiento histórico de
    un único eje.

    Cuando el eje cae sobre el trigger, el exit homónimo se permuta CON ÉL por par
    (``_AXIAL_TRIGGER_EXIT_PAIRS``). Sin ese arrastre, el exit seguiría mirando las
    series del trigger anterior y la señal de entrada quedaría inalcanzable, dejando el
    plan con <2 trials y sin PBO (grid degenerado).

    Determinista y acotado a ``max_variants``. Fail-closed: las variantes que no
    materializan se descartan (no se inventan puntos).
    """
    variants: list[dict[str, Any]] = []
    own = plan.materialize()
    if own is None:
        return []
    variants.append({"label": plan.name, "definition": own})

    current = {c.kind: c for c in plan.components}
    optional_kinds = [
        kind for kind in GRAMMAR_COMPONENT_ORDER if kind in current and kind in GRAMMAR_VARIANTS
    ]

    # Preferencia de eje (V2.39.2): los bloques OPCIONALES primero, y los axiales
    # (trigger/exit) solo como último recurso. Motivo: permutar un bloque axial sin tocar
    # el resto puede inutilizar el trigger (ver ``_AXIAL_TRIGGER_EXIT_PAIRS``), y en el
    # mejor caso el grid degenera a 1 columna. Rotar sobre los opcionales mantiene el
    # grid con ≥2 columnas operables en la inmensa mayoría de los planes.
    permutable_kinds = [
        *optional_kinds,
        *(kind for kind in current if kind in _TRIGGER_AXIS_KINDS and kind in GRAMMAR_VARIANTS),
    ]
    if not permutable_kinds:
        return variants
    swap_kind = permutable_kinds[int(axis_index) % len(permutable_kinds)]
    pool = GRAMMAR_VARIANTS.get(swap_kind, ())

    # Si el eje es el trigger y su exit homónimo está presente, se permutan AMBOS: el
    # exit acompaña al trigger por PAR (no por nombre), de modo que la señal de salida
    # sigue siendo alcanzable sobre las nuevas series. Sin esto, las variantes del eje
    # trigger nunca operan y el plan se queda sin PBO.
    paired_exit_kind: str | None = None
    if swap_kind == COMPONENT_TRIGGER and COMPONENT_EXIT in current:
        current_trigger_name = current[COMPONENT_TRIGGER].name
        current_exit_name = current[COMPONENT_EXIT].name
        for trigger_name, exit_name in _AXIAL_TRIGGER_EXIT_PAIRS:
            if current_trigger_name == trigger_name and current_exit_name == exit_name:
                paired_exit_kind = COMPONENT_EXIT
                break

    for alternative in pool:
        if len(variants) >= max_variants:
            break
        if alternative.name == current.get(swap_kind, alternative).name:
            continue
        replacements = {swap_kind: alternative}
        if paired_exit_kind is not None:
            # El índice del par se deriva de la posición del trigger en la tabla, no del
            # nombre del exit (fail-closed: si no se encuentra el par, no se arrastra).
            pair_index = next(
                (
                    index
                    for index, (trigger_name, _) in enumerate(_AXIAL_TRIGGER_EXIT_PAIRS)
                    if trigger_name == current[COMPONENT_TRIGGER].name
                ),
                None,
            )
            if pair_index is None:
                continue
            pool_exits = GRAMMAR_VARIANTS.get(COMPONENT_EXIT, ())
            exit_index = next(
                (
                    index
                    for index, component in enumerate(pool_exits)
                    if component.name == _AXIAL_TRIGGER_EXIT_PAIRS[pair_index][1]
                ),
                None,
            )
            if exit_index is None:
                continue
            replacements[COMPONENT_EXIT] = pool_exits[exit_index]
        swapped = tuple(
            replacements.get(c.kind, c) for c in plan.components
        )
        if not _plan_is_coherent(swapped):
            continue
        candidate_plan = GrammarPlan(
            name="__".join(c.name for c in _canonical_order(swapped)),
            components=swapped,
        )
        materialized = candidate_plan.materialize()
        if materialized is None:
            continue
        if any(v["definition"] == materialized for v in variants):
            continue
        variants.append({"label": candidate_plan.name, "definition": materialized})

    return variants
