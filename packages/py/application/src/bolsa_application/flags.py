"""Lectura de configuración por entorno con **lista blanca** (fail-closed).

Origen: auditoría de TRADING/AUTO de `v2.88.183-beta`, hallazgo **P1**. El patrón que
había repartido por los workers

    (os.getenv(NOMBRE) or "").strip().lower() not in {"", "0", "false", "no", "off"}

es **fail-open**: cualquier valor que no esté en la lista de apagado ENCIENDE el
interruptor. Un ``disabled``, una ``n`` o una errata ``onn`` activaban AUTO o el precio
real. La regla de esta casa es la contraria: solo una familia corta y explícita de
valores ENCIENDE; todo lo demás (vacío incluido) cae al default declarado por el
llamante.

Este módulo es el ÚNICO sitio donde vive esa decisión. Un cambio aquí cambia todos los
interruptores a la vez, que es justo lo que se quiere: que no puedan divergir.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Final

logger = logging.getLogger(__name__)

#: Valores que ENCIENDEN. Nada fuera de este conjunto enciende.
TRUTHY: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})

#: Valores que APAGAN (``none`` incluido: hay despliegues que lo usan así).
FALSY: Final[frozenset[str]] = frozenset({"0", "false", "no", "off", "none"})


def env_flag(name: str, *, default: bool = False) -> bool:
    """Lee un interruptor booleano de entorno con lista blanca.

    - Vacío o ausente ⇒ ``default`` (nunca enciende por accidente).
    - Familia "on" (``1/true/yes/on``) ⇒ ``True``.
    - Familia "off" (``0/false/no/off/none``) ⇒ ``False``.
    - Cualquier otra cosa (``disabled``, ``n``, ``of``, ``2``, ``onn``) ⇒ ``default``
      y un ``warning`` con el valor crudo, para que el despliegue roto se vea en el log
      en vez de decidir en silencio.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    token = raw.lower()
    if token in TRUTHY:
        return True
    if token in FALSY:
        return False
    logger.warning(
        "env %s=%r no es un booleano reconocido; se usa el default %s "
        "(lista blanca: 1/true/yes/on)",
        name,
        raw,
        default,
    )
    return default


def env_finite_float(
    name: str,
    *,
    default: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    """Lee un float de entorno que debe ser **finito** y estar en rango.

    ``nan`` e ``inf`` no son configuración válida: se tratan como valor inválido y se
    devuelve ``default`` con un ``warning`` (auditoría P9). Sin esto, un
    ``AUTO_ENGINE_SIM_INTERVAL_SECONDS=Infinity`` suspendía el worker para siempre y un
    ``NaN`` atravesaba comparaciones ``> 0``.
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        logger.warning("env %s=%r no es numerico; se usa el default %r", name, raw, default)
        return default
    if not math.isfinite(value):
        logger.warning("env %s=%r no es finito; se usa el default %r", name, raw, default)
        return default
    if minimum is not None and value < minimum:
        logger.warning(
            "env %s=%r queda por debajo del minimo %r; se usa el default %r",
            name,
            raw,
            minimum,
            default,
        )
        return default
    if maximum is not None and value > maximum:
        logger.warning(
            "env %s=%r queda por encima del maximo %r; se usa el default %r",
            name,
            raw,
            maximum,
            default,
        )
        return default
    return value


def env_positive_int(name: str, *, default: int) -> int:
    """Lee un entero de entorno estrictamente positivo; cualquier otra cosa ⇒ ``default``."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        logger.warning("env %s=%r no es entero; se usa el default %r", name, raw, default)
        return default
    if value <= 0:
        logger.warning("env %s=%r no es positivo; se usa el default %r", name, raw, default)
        return default
    return value


__all__ = ["FALSY", "TRUTHY", "env_finite_float", "env_flag", "env_positive_int"]
