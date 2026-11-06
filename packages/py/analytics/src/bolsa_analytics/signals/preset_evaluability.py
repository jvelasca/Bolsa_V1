"""Evaluabilidad de la ventana: ¿puede el preset decidir sus reglas con estas barras?

**B-1 / B-6** de la auditoría de detección (2026-10-26). El scan comparaba contra
``MIN_SCAN_BARS = 50`` fijo. Con un ``bar_limit`` por debajo del warmup real del
preset, las series del contexto quedaban en ``None``, la regla no disparaba y el
scan publicaba **«sin señal»** cuando lo correcto era **«no evaluable»**. El
silencio se leía como ausencia de mercado.

**Por qué esto no es aritmética de periodos.** Un ``required_bars`` calculado como
``period + 1`` se desincroniza en cuanto cambia un indicador: Ichimoku desplaza 26
barras (``senkouBPeriod = 52`` + ``displacement = 26`` ⇒ 79, no 53), MACD necesita
``slow + signal``, y un cruce necesita además la barra **anterior** (``-2``), no
solo la última. Aquí la pregunta se responde sobre la serie que el motor
realmente lee: una regla es decidible si **cada serie que referencia está definida
en el índice que la regla consulta**.

Consecuencia deliberada: este módulo no promete un número «de catálogo», sino el
que sale de la evidencia. Si mañana un indicador cambia su warmup, la respuesta
cambia con él y ninguna tabla queda mintiendo.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from bolsa_analytics.indicators.compute import OhlcvBar, instance_spec_key

#: Prefijo estable del motivo. La API y los tests no deben depender del texto libre.
WARMUP_INSUFFICIENT = "warmup_insufficient"

#: Sonda por defecto con la que se mide el warmup de un preset **antes** de pedir barras.
#: Es la ventana máxima que el catálogo necesita (201) con holgura: la medición se hace
#: sobre la serie, no sobre una aritmética de periodos que se desincronice.
PROBE_BARS = 500

_CROSS_RULE = "indicator_cross"

#: Campos de cada tipo de regla que contienen una spec de indicador, y en qué índice
#: se consulta la serie: las comparaciones miran la última barra; un cruce compara la
#: última con la anterior y por eso exige **dos** valores definidos.
_SPEC_FIELDS: dict[str, tuple[tuple[str, ...], int]] = {
    "indicator_cross": (("leftSpec", "rightSpec"), 2),
    "indicator_compare": (("leftSpec",), 1),
    "price_vs_indicator": (("indicatorSpec",), 1),
    "indicator_vs_indicator": (("leftSpec", "rightSpec"), 1),
}


def iter_rules(definition: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Recorre las reglas de ``entries`` y ``exits`` (las que el motor evalúa)."""
    for side in ("entries", "exits"):
        group = definition.get(side)
        if not isinstance(group, dict):
            continue
        rules = group.get("rules")
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if isinstance(rule, dict):
                yield rule


def spec_key_of(raw: Any) -> str | None:
    """Clave de instancia (``sma::period=200``) de una spec de regla, o ``None``."""
    if not isinstance(raw, dict) or not raw.get("definitionId"):
        return None
    parameters = raw.get("parameters")
    return instance_spec_key(str(raw["definitionId"]), dict(parameters or {}))


def required_spec_depth(definition: dict[str, Any]) -> dict[str, int]:
    """``spec_key`` → barras finales que la serie debe tener definidas.

    ``1`` para comparaciones (solo ``-1``) y ``2`` para cruces (``-1`` y ``-2``).
    Si una spec aparece en ambos tipos de regla, gana el requisito más exigente.
    """
    depth: dict[str, int] = {}
    for rule in iter_rules(definition):
        entry = _SPEC_FIELDS.get(str(rule.get("type") or ""))
        if entry is None:
            continue
        fields, needed = entry
        for field in fields:
            key = spec_key_of(rule.get(field))
            if key is not None:
                depth[key] = max(depth.get(key, 0), needed)
    return depth


def _first_defined(series: Sequence[float | None]) -> int | None:
    for index, value in enumerate(series):
        if value is not None:
            return index
    return None


def required_bars_for(series: Sequence[float | None], depth: int) -> int | None:
    """Barras mínimas para que la serie cubra sus ``depth`` últimas posiciones.

    ``None`` si la serie no se define en ninguna barra de la ventana (ese caso no es
    «faltan barras», es «no hay serie», y se declara como tal).
    """
    first = _first_defined(series)
    if first is None:
        return None
    return first + depth


def unevaluable_specs(
    indicator_context: dict[str, list[float | None]],
    definition: dict[str, Any],
) -> list[tuple[str, int | None]]:
    """Pares ``(spec_key, barras_requeridas | None)`` que la ventana no cubre.

    Una serie **ausente** del contexto no se atribuye al warmup: es otro defecto
    (la definición referencia una spec que no declaró) y se deja fuera para no
    disfrazarlo de «faltan barras».
    """
    problems: list[tuple[str, int | None]] = []
    for key, depth in required_spec_depth(definition).items():
        series = indicator_context.get(key)
        if series is None:
            continue
        if len(series) < depth or any(value is None for value in series[-depth:]):
            problems.append((key, required_bars_for(series, depth)))
    return problems


def _probe_bars(count: int) -> list[OhlcvBar]:
    """Serie OHLCV determinista para medir el warmup sin tocar BD ni ficheros.

    Sólo importa el ORDEN y que la geometría sea coherente (``high >= close >= low``,
    ``volume > 0``): los indicadores se calculan sobre la serie, no sobre las fechas.
    """
    return [
        OhlcvBar(
            timestamp=f"2000-01-{1 + index % 28:02d}",
            open=100.0 + 0.1 * index - 0.2,
            high=100.0 + 0.1 * index + 0.5,
            low=100.0 + 0.1 * index - 0.5,
            close=100.0 + 0.1 * index,
            volume=1000.0,
        )
        for index in range(count)
    ]


def measured_warmup_bars(
    definition: dict[str, Any],
    *,
    probe_bars: int = PROBE_BARS,
) -> int | None:
    """Barras que el preset necesita para que **todas** sus series estén definidas.

    Esta es la función que **dimensiona la ventana antes de pedir barras**. Hasta ahora el
    warmup sólo se diagnosticaba *después* (``evaluability_reason``): el worker pedía
    ``AUTO_ENGINE_SIM_SIGNAL_BARS`` barras y, con un preset de SMA200, publicaba un HOLD
    declarado pero inevitable. Aquí la misma medición se usa para pedir lo que hace falta.

    Devuelve ``0`` si el preset no referencia ninguna serie (no paga warmup), el número
    exacto de barras si la sonda la define, y ``None`` cuando **no se puede medir**: o la
    serie no se define ni con ``probe_bars``, o la definición referencia una spec que no
    declaró. ``None`` no es «0 barras»: el llamante debe fallar cerrado y declararlo
    (``warmup_unmeasurable``), nunca asumir una ventana.

    La definición se enriquece con las reglas del preset cuando sólo trae ``presetKey``:
    medir sobre una definición sin reglas daría «no paga warmup» y es justo el silencio
    que este módulo existe para evitar.
    """
    from bolsa_analytics.signals.preset_catalog import enrich_definition_with_preset_rules
    from bolsa_analytics.signals.rules_engine import build_indicator_context

    resolved = enrich_definition_with_preset_rules(definition)
    depth = required_spec_depth(resolved)
    if not depth:
        return 0
    specs = list(resolved.get("indicatorSpecs") or [])
    if not specs:
        return None
    context = build_indicator_context(_probe_bars(probe_bars), specs)
    required = 0
    for key, needed in depth.items():
        series = context.get(key)
        if series is None:
            # La definición referencia una spec que no declaró: no es «faltan barras»,
            # es una definición incompleta. No se puede dimensionar y se declara.
            return None
        bars = required_bars_for(series, needed)
        if bars is None:
            return None
        required = max(required, bars)
    return required


def evaluability_reason(
    definition: dict[str, Any],
    indicator_context: dict[str, list[float | None]] | None,
    *,
    bar_count: int,
) -> str | None:
    """``None`` si el preset es evaluable con esta ventana; si no, el motivo explícito.

    El motivo empieza por :data:`WARMUP_INSUFFICIENT` y nombra cada serie que no
    alcanza, con las barras que necesitaría. Sirve para el ``ScanSkippedInstrument``:
    el instrumento deja de contarse como «sin señal» y pasa a contarse como
    «no evaluable», que es lo que de verdad ocurrió.
    """
    if not indicator_context:
        return None

    problems = unevaluable_specs(indicator_context, definition)
    if not problems:
        return None

    parts: list[str] = []
    for key, required in problems:
        label = key.replace("::", " ")
        if required is None:
            # La serie no se define en NINGUNA barra de la ventana: no se puede
            # afirmar un número exacto sin recurrir a aritmética de periodos, que
            # es justo lo que este módulo evita. Lo verdadero es «hace falta más».
            parts.append(f"{label} requiere más de {bar_count} barras")
        else:
            parts.append(f"{label} requiere >= {required} barras")

    detail = "; ".join(parts)
    return f"{WARMUP_INSUFFICIENT}: {detail} (ventana: {bar_count} barras)"
