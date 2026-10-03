"""DÍA-D AUTO (sandbox) — contrato PURO del artefacto y comparador declarado vs ejecutado.

Qué es
------
El "DÍA-D AUTO" es un **sandbox read-only**: sitúa el motor AUTO real en una fecha pasada
``D`` con reloj/precio inyectados (el mismo harness hermético de ``v2.86``/``v2.87``), recoge
lo que el motor **DECLARÓ** que haría ese día, lo confronta con lo que la ventana PAPER
**EJECUTÓ** de verdad (los hechos durables de ``D``, si existen) y con lo que el mercado hizo
**después** de ``D`` (OOS real). Ni escribe en la base durable ni sustituye la ventana PAPER.

Este módulo es **PURO y determinista**: no hace I/O, no lee el reloj y no inventa ceros. Solo
construye el payload canónico del artefacto y decide, paso a paso de la cadena AUTO, si lo
declarado y lo ejecutado **coinciden** (``MATCH``), **divergen** (``DIVERGENT``) o **no se
pueden medir** (``NOT_MEASURED``).

Regla dura (heredada del monitor AUTO): una magnitud que no se pudo medir viaja ``None`` con
medición ``UNKNOWN``; NUNCA un ``0`` de relleno. Un ``0`` es una MEDICIÓN ("no pasó nada") y
un hueco es la AUSENCIA de medición ("no lo sé"); confundirlos es exactamente el defecto que
este instrumento existe para no repetir.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)

#: Versión del esquema del artefacto. Un cambio de forma la sube.
SCHEMA_VERSION = "dia-d-auto-v1"

#: Cadena canónica de la operativa AUTO, en orden. La comparación respeta este orden y la UI
#: pinta una fila por paso: un paso ausente en ambos lados se declara ``NOT_MEASURED``.
CHAIN_STEPS: tuple[str, ...] = (
    "SIGNAL",
    "TOP_N",
    "RISK",
    "RESERVATION",
    "ORDER",
    "FILL",
    "PROTECTION",
    "SETTLEMENT",
    "CYCLE_CLOSED",
)

#: Veredicto por paso: lo declarado y lo ejecutado coinciden / divergen / no se pudo medir.
VERDICT_MATCH = "MATCH"
VERDICT_DIVERGENT = "DIVERGENT"
VERDICT_NOT_MEASURED = "NOT_MEASURED"

#: Veredicto GLOBAL adicional: hay pasos medidos y pasos sin medir (ni todo ni nada).
VERDICT_PARTIAL = "PARTIAL"

_ALL_VERDICTS: frozenset[str] = frozenset(
    {VERDICT_MATCH, VERDICT_DIVERGENT, VERDICT_NOT_MEASURED, VERDICT_PARTIAL}
)

#: Tolerancia de comparación de magnitudes continuas (precios, cantidades, R). Es una
#: tolerancia de IGUALDAD de contrato, no un margen de negocio: ``1e-9`` separa el redondeo
#: binario del desvío real sin admitir una diferencia con significado.
_VALUE_TOLERANCE = 1e-9

#: Límites que SIEMPRE viajan con el artefacto (se declaran, no se disfrazan).
DEFAULT_LIMITS: tuple[str, ...] = (
    "Sandbox read-only: no escribe en la BD durable ni sustituye la ventana PAPER.",
    "El cubo de calendario sale del reloj de pared: un replay no fabrica cubos durables.",
    "Aproximacion D1: un dia = un tick.",
    "Un paso sin traza durable se declara NOT_MEASURED; nunca se rellena con 0.",
    "AUTO_ENGINE_SIM_REAL_PRICE no se fuerza: el precio del replay es el price_script inyectado.",
    "CYCLE_CLOSED usa una identidad unica: D-cycle = ciclo cuya APERTURA ocurre en D; el "
    "cycle_id del replay vive en memoria y el durable en la ventana PAPER, asi que se "
    "compara la REGLA (1/0/None), no una union literal de ids.",
)


def normalize_day(value: Any) -> str:
    """Normaliza un día a ``YYYY-MM-DD``; ``""`` si no es una fecha legible.

    No se adivina: un día malformado se declara vacío en vez de recortarse a ciegas.
    """
    text = str(value or "").strip()
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""


def finite_number(value: Any) -> float | None:
    """``float`` FINITO de un valor cuantificable; ``None`` si no lo es (nunca ``0``).

    Un ``NaN`` **y** un ``+inf``/``-inf`` se declaran huecos: no son mediciones. Dejar pasar
    un infinito contaminaría la esperanza, el hit-rate y el total de R y, además, produciría
    JSON no estándar (``Infinity``) que rompe consumidores JavaScript.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _comparable(value: Any) -> Any:
    """Proyección de un valor a su forma comparable (o ``None`` si no es medible).

    Un número es comparable como número; cualquier otra cosa se compara como texto no vacío.
    Un ``""``/``None`` NO es una medición: se devuelve ``None`` para que el paso se declare
    ``NOT_MEASURED`` en vez de "coincidir con cadena vacía".
    """
    number = finite_number(value)
    if number is not None:
        return number
    if value is None or isinstance(value, bool):
        return value if isinstance(value, bool) else None
    text = str(value).strip()
    return text or None


def values_equal(left: Any, right: Any) -> bool:
    """Igualdad de contrato entre dos magnitudes comparables (``False`` si falta alguna).

    Dos huecos NO son "iguales": no se puede afirmar que coinciden. Por eso un ``None`` en
    cualquier lado devuelve ``False`` (y el llamante lo traduce a ``NOT_MEASURED``).
    """
    if left is None or right is None:
        return False
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(left, right, rel_tol=_VALUE_TOLERANCE, abs_tol=_VALUE_TOLERANCE)
    return bool(left == right)


def compare_step(declared: Any, executed: Any) -> dict[str, Any]:
    """Compara UN paso de la cadena y devuelve su veredicto con la medición declarada.

    * ambos medibles e iguales → ``MATCH`` / ``COMPLETE``;
    * ambos medibles y distintos → ``DIVERGENT`` / ``COMPLETE``;
    * alguno no medible → ``NOT_MEASURED`` / ``UNKNOWN``.
    """
    left = _comparable(declared)
    right = _comparable(executed)
    if left is None or right is None:
        verdict, measurement = VERDICT_NOT_MEASURED, MEASUREMENT_UNKNOWN
    elif values_equal(left, right):
        verdict, measurement = VERDICT_MATCH, MEASUREMENT_COMPLETE
    else:
        verdict, measurement = VERDICT_DIVERGENT, MEASUREMENT_COMPLETE
    return {
        "declared": left,
        "executed": right,
        "verdict": verdict,
        "measurement": measurement,
    }


def compare_declared_vs_executed(
    declared: Mapping[str, Any] | None,
    executed: Mapping[str, Any] | None,
    *,
    chain: Sequence[str] = CHAIN_STEPS,
) -> list[dict[str, Any]]:
    """Compara la cadena completa paso a paso, en el ORDEN canónico. Nunca rellena con ``0``.

    Un paso ausente en cualquiera de los dos lados es un hueco declarado (``NOT_MEASURED``),
    no una coincidencia ni un cero.
    """
    declared_map = declared or {}
    executed_map = executed or {}
    rows: list[dict[str, Any]] = []
    for step in chain:
        row = compare_step(declared_map.get(step), executed_map.get(step))
        rows.append({"step": step, **row})
    return rows


def summarize_comparison(comparison: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Resumen determinista: conteos por veredicto y veredicto global.

    Global: todo sin medir → ``NOT_MEASURED``; algo diverge → ``DIVERGENT``; hay medidas y
    huecos → ``PARTIAL``; todo coincide → ``MATCH``. El orden de precedencia hace que una
    divergencia REAL nunca quede escondida detrás de un hueco.
    """
    match = sum(1 for row in comparison if row.get("verdict") == VERDICT_MATCH)
    divergent = sum(1 for row in comparison if row.get("verdict") == VERDICT_DIVERGENT)
    not_measured = sum(1 for row in comparison if row.get("verdict") == VERDICT_NOT_MEASURED)
    steps = len(comparison)
    if steps == 0 or not_measured == steps:
        verdict = VERDICT_NOT_MEASURED
    elif divergent > 0:
        verdict = VERDICT_DIVERGENT
    elif not_measured > 0:
        verdict = VERDICT_PARTIAL
    else:
        verdict = VERDICT_MATCH
    return {
        "verdict": verdict,
        "match": match,
        "divergent": divergent,
        "notMeasured": not_measured,
        "steps": steps,
    }


def _cycle_id(value: Any) -> str | None:
    """Identidad de ciclo normalizada o ``None``: ``None``/``""``/espacios NO son un id.

    Fail-closed: un hueco no puede convertirse en el id literal ``"None"`` (hallazgo D35-02).
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def cycle_closure_summary(
    opened_ids: Sequence[Any],
    closed_ids: Sequence[Any],
) -> dict[str, Any]:
    """Identidad ÚNICA del ciclo para el paso ``CYCLE_CLOSED`` (declarado y ejecutado).

    Un **D-cycle** es un ciclo cuya **apertura** (buy) ocurre en ``D``. Este helper traduce
    "qué ciclos nacieron en D" y "qué ciclos cerraron después" al MISMO valor comparable
    ``1`` / ``0`` / ``None`` (antes, el lado declarado emitía ``1/0/None`` y el ejecutado una
    CUENTA: no eran comparables y la identidad del ciclo difería — hallazgo D34-01).

    * ``1`` si al menos un D-cycle tiene un cierre posterior;
    * ``0`` si hay D-cycles y ninguno cerró (sigue vivo);
    * ``None`` (UNKNOWN) si no hay ninguna apertura reconstruible: no se puede afirmar ni
      cierre ni vida. Los conjuntos ``opened``/``closed``/``open`` acompañan al veredicto para
      que el detalle durable explique la decisión.

    Un identificador ``None``/vacío se descarta (nunca se normaliza a ``"None"``): si todas
    las aperturas se descartan, el paso es ``None``/UNKNOWN (fail-closed, D35-02).
    """
    opened = sorted({cid for value in opened_ids if (cid := _cycle_id(value)) is not None})
    closed = {cid for value in closed_ids if (cid := _cycle_id(value)) is not None}
    if not opened:
        return {"step": None, "opened": [], "closed": [], "open": [], "unmeasured": True}
    closed_in = [cycle_id for cycle_id in opened if cycle_id in closed]
    still_open = [cycle_id for cycle_id in opened if cycle_id not in closed]
    return {
        "step": 1 if closed_in else 0,
        "opened": opened,
        "closed": closed_in,
        "open": still_open,
        "unmeasured": False,
    }


def build_dia_d_auto_artifact(
    *,
    day: Any,
    declared: Mapping[str, Any] | None,
    executed: Mapping[str, Any] | None = None,
    oos: Mapping[str, Any] | None = None,
    declared_detail: Mapping[str, Any] | None = None,
    executed_detail: Mapping[str, Any] | None = None,
    meta: Mapping[str, Any] | None = None,
    chain: Sequence[str] = CHAIN_STEPS,
    limits: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Construye el payload canónico del artefacto DÍA-D AUTO (puro y determinista).

    ``declared``/``executed`` son mapas ``paso → magnitud`` (escalares medibles o ``None``).
    El detalle rico de cada lado viaja aparte (``declared_detail``/``executed_detail``) para
    no ensuciar la comparación. Sin sellos de tiempo ni identificadores aleatorios: el mismo
    estado produce el mismo payload byte a byte.
    """
    declared_map = {str(k): _json_safe(v) for k, v in (declared or {}).items()}
    executed_map = {str(k): _json_safe(v) for k, v in (executed or {}).items()}
    comparison = compare_declared_vs_executed(declared_map, executed_map, chain=chain)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "DIA_D_AUTO",
        "readOnly": True,
        "day": normalize_day(day),
        "meta": {str(k): _json_safe(v) for k, v in (meta or {}).items()},
        "declared": declared_map,
        "executed": executed_map,
        "declaredDetail": {str(k): _json_safe(v) for k, v in (declared_detail or {}).items()},
        "executedDetail": {str(k): _json_safe(v) for k, v in (executed_detail or {}).items()},
        "oos": {str(k): _json_safe(v) for k, v in (oos or {}).items()},
        "comparison": comparison,
        "summary": summarize_comparison(comparison),
        "limits": [str(item) for item in (limits if limits is not None else DEFAULT_LIMITS)],
    }


def _json_safe(value: Any) -> Any:
    """Convierte un valor a una forma JSON determinista (``Decimal``/dataclass→primitivos)."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    number = finite_number(value)
    if number is not None:
        return number
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    return str(value)


__all__ = [
    "CHAIN_STEPS",
    "DEFAULT_LIMITS",
    "SCHEMA_VERSION",
    "VERDICT_DIVERGENT",
    "VERDICT_MATCH",
    "VERDICT_NOT_MEASURED",
    "VERDICT_PARTIAL",
    "build_dia_d_auto_artifact",
    "compare_declared_vs_executed",
    "compare_step",
    "cycle_closure_summary",
    "finite_number",
    "normalize_day",
    "summarize_comparison",
    "values_equal",
]
