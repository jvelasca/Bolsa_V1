"""AUTO-20B — huella del MATERIAL de una corrida de calibración (PURA y determinista).

Qué resuelve: poder responder "¿de qué ciclos salió este resultado?" sin guardar todos los
``cycleId`` dentro del informe durable. El instrumento mide el mismo material que el informe;
cuando se comparan dos corridas (``v2.62`` frente a ``v2.63``) hay que poder afirmar que el
universo medido es el MISMO, o declarar que cambió. Esta pieza produce ese sello.

Tres reglas duras, declaradas en vez de asumidas:

* **Determinista y estable entre procesos.** La huella se calcula con una serialización
  canónica (claves ordenadas, sin espacios de relleno, ``Decimal``/``float`` normalizados a su
  valor numérico) y se ordenan las filas: **el orden de entrada no cambia la huella** —el
  mismo universo es la misma huella—. ``ensure_ascii=False`` para que un ``é`` no dependa del
  escape.
* **Nada de reloj.** El instante de exportación NO entra a la huella: dos exportaciones del
  mismo material deben dar el mismo sello aunque se hagan en días distintos.
* **El método se declara.** ``MATERIAL_FINGERPRINT_METHOD`` viaja junto al número; ampliar los
  campos que entran a la huella sube el sello (dos huellas distintas con el mismo aspecto no
  pueden venir de instrumentos distintos).

Read-only: no escribe nada, no toca la base de datos ni el journal.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "FINGERPRINT_FIELDS",
    "MATERIAL_FINGERPRINT_METHOD",
    "material_fingerprint",
]

#: Método declarado de la huella. Cambiar los campos que entran obliga a subir este sello.
MATERIAL_FINGERPRINT_METHOD = "material_fingerprint_v1"

#: Campos de UNA fila de ciclo que entran a la huella, en orden. Son la identidad
#: (``cycleId``/``strategyVersion``) más lo medido que un cambio de universo alteraría
#: (``pnl``/``closedAt``/``riskAmount``/``costApplied``/``regime``). Si un campo no está, se
#: huella ``None`` (el hueco también es parte del material).
FINGERPRINT_FIELDS: tuple[str, ...] = (
    "cycleId",
    "strategyVersion",
    "pnl",
    "closedAt",
    "riskAmount",
    "costApplied",
    "regime",
)

#: Claves cuyo VALOR es un número (no un identificador). Solo estas se normalizan cuando llegan
#: como cadena desde el JSON (``"50.000000"`` → ``"50"``). Un ``cycleId``/``strategyVersion``
#: NUNCA se toca: un identificador no es un número aunque lo parezca.
_NUMERIC_KEYS: frozenset[str] = frozenset(
    {"pnl", "riskAmount", "risk_amount", "friction", "total"}
)


def _snake(name: str) -> str:
    """``riskAmount`` → ``risk_amount`` (tolerancia de grafía del resto del instrumento)."""
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out)


def _read(row: Any, name: str) -> Any:
    """Campo ``name`` (camelCase o snake_case) de la fila, o ``None`` si no lo declara."""
    names = (name, _snake(name))
    if isinstance(row, Mapping):
        for candidate in names:
            if candidate in row:
                return row[candidate]
        return None
    for candidate in names:
        if hasattr(row, candidate):
            return getattr(row, candidate)
    return None


def _number_text(value: Any) -> Any:
    """Número → su texto canónico (``"100.000000"`` ≡ ``100`` ≡ ``Decimal("100")`` → ``"100"``).

    Un valor que no es un número legible se devuelve TAL CUAL: el hueco o la cadena rara se
    declaran, no se reinterpretan (inventar un número que no está sería peor que declararlo).
    """
    if isinstance(value, Decimal):
        return str(value) if not value.is_finite() else format(value.normalize(), "f")
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return format(Decimal(value).normalize(), "f")
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return str(value)
        return format(Decimal(str(value)).normalize(), "f")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            parsed = Decimal(text)
        except (InvalidOperation, ValueError, TypeError):
            return value
        return str(parsed) if not parsed.is_finite() else format(parsed.normalize(), "f")
    return value


def _canonical(value: Any, key: str | None = None) -> Any:
    """Valor → primitivo canónico (dicts ordenados; números por VALOR, ids por TEXTO).

    Un ``Decimal('100.000000')``, un ``100`` y la cadena ``"100.000000"`` que trae el JSON son
    el MISMO hecho medido: se normalizan al mismo texto **solo** cuando la clave lo declara
    numérico (``_NUMERIC_KEYS``). Un identificador (``cycleId``/``strategyVersion``/``regime``)
    se conserva byte a byte aunque parezca un número, porque no lo es. Un objeto con ``to_dict``
    (p. ej. ``TradingCost``) se aplana por su propia representación.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (Decimal, int, float)):
        return _number_text(value)
    if isinstance(value, str):
        return _number_text(value) if key in _NUMERIC_KEYS else value
    if isinstance(value, Mapping):
        return {
            str(item_key): _canonical(item, str(item_key))
            for item_key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _canonical(to_dict())
    return str(value)


def _canonical_cycle(row: Any) -> str:
    """(PURA) una fila de ciclo reducida a su línea canónica, con las claves ordenadas."""
    payload = {name: _canonical(_read(row, name), name) for name in FINGERPRINT_FIELDS}
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def material_fingerprint(cycles: Iterable[Any] | None) -> str:
    """(PURA) huella estable del material: ``sha256:<hex>`` sobre las filas ordenadas.

    Ordenar las líneas antes de hashear hace que el MISMO universo dé la MISMA huella
    independientemente del orden en que se leyó (el material no tiene orden propio). Sin
    ciclos la huella del vacío es un valor declarado, no un error: "no hay material" es un
    hecho que también conviene poder comparar.
    """
    lines = sorted(_canonical_cycle(row) for row in (cycles or ()))
    digest = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
