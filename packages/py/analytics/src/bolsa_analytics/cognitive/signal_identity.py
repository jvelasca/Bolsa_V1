"""SignalIdentity — identidad y frescura de señal (AUTO 2.0 · P1).

Elimina el comportamiento errático de re-evaluar la misma última barra en cada turno:
si el worker corre cada 60s pero la señal es D1, una misma barra genera la MISMA señal
una y otra vez (BUY 09:00, BUY 10:00, BUY 11:00...). La identidad de señal permite
detectar "misma barra + misma estrategia ⇒ misma señal" y NO re-emitir la oportunidad.

Identidad canónica::

    instrument + strategy_version + timeframe + bar_timestamp + signal_hash

``signal_hash`` es un hash estable de la ACCIÓN dominante de la señal (o del contenido
de la señal), de modo que dos señales sobre la misma barra y la misma versión de
estrategia, con el mismo resultado, colisionan.

Además porta ``generated_at`` y ``valid_until``: una señal expira, y una señal expirada
no debe alimentar una nueva decisión (fail-closed).

Este módulo es puro: no toca DB ni reloj salvo por el ``now`` que le pase el llamante.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Delimitador canónico para componer la identidad de señal (evita colisiones entre
# campos concatenados, p.ej. ("a", "bc") vs ("ab", "c")).
_FIELD_SEP = "\x1f"

# Unidades de timeframe soportadas por ``bar_window`` (minuto/hora/día).
_TIMEFRAME_UNITS: dict[str, int] = {"m": 60, "h": 3600, "d": 86400}


@dataclass(frozen=True, slots=True)
class SignalIdentity:
    """Identidad inmutable de una señal generada sobre una barra concreta."""

    instrument_id: str
    strategy_version: str
    timeframe: str
    bar_timestamp: str
    signal_hash: str
    generated_at: str = ""
    valid_until: str = ""

    @property
    def signal_id(self) -> str:
        """Id canónico estable: ``instrument|version|timeframe|bar|hash``."""
        return _FIELD_SEP.join(
            (
                self.instrument_id,
                self.strategy_version,
                self.timeframe,
                self.bar_timestamp,
                self.signal_hash,
            )
        )

    def same_signal_as(self, other: SignalIdentity) -> bool:
        """True si ambos apuntan a la MISMA barra y el MISMO resultado de señal."""
        return self.signal_id == other.signal_id

    def is_fresh(self, now: str) -> bool:
        """True si ``now <= valid_until``. Sin ``valid_until`` ⇒ False (fail-closed)."""
        if not self.valid_until:
            return False
        return now <= self.valid_until

    def to_dict(self) -> dict[str, Any]:
        return {
            "signalId": self.signal_id,
            "instrumentId": self.instrument_id,
            "strategyVersion": self.strategy_version,
            "timeframe": self.timeframe,
            "barTimestamp": self.bar_timestamp,
            "signalHash": self.signal_hash,
            "generatedAt": self.generated_at,
            "validUntil": self.valid_until,
        }


def compute_signal_hash(action: str, *extra: Any) -> str:
    """Hash estable (SHA-256 truncado) de la acción + contexto de la señal.

    ``extra`` son campos adicionales que distinguen señales del mismo ``action``
    (p.ej. parámetros que cambian la decisión). El resultado es determinista y corto.
    """
    payload = _FIELD_SEP.join(str(x) for x in (action, *extra))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:16]


def timeframe_seconds(timeframe: str) -> int | None:
    """Duración de la barra en segundos (``1m``/``15m``/``4h``/``1d``).

    ``None`` si el timeframe no se entiende: no se adivina una duración, porque una
    barra mal calculada rompería la deduplicación (dos barras distintas leyéndose como
    la misma, o al revés).
    """
    raw = str(timeframe or "").strip().lower()
    if len(raw) < 2:
        return None
    unit = _TIMEFRAME_UNITS.get(raw[-1])
    if unit is None:
        return None
    digits = raw[:-1]
    if not digits.isdigit():
        return None
    size = int(digits)
    if size <= 0:
        return None
    return size * unit


def bar_window(moment: datetime, timeframe: str) -> tuple[str, str] | None:
    """Ventana ``(inicio, cierre)`` ISO-UTC de la barra que contiene ``moment``.

    Anclada a medianoche UTC (misma convención para todos los timeframes), de modo que
    dos ``moment`` dentro de la misma barra producen el mismo ``inicio`` y por tanto la
    MISMA identidad de señal.

    Fail-closed: timeframe ilegible o ``moment`` sin zona ⇒ ``None``. Sin barra no hay
    identidad, y sin identidad no se deduplica (nunca se inventa la ventana).
    """
    seconds = timeframe_seconds(timeframe)
    if seconds is None or moment.tzinfo is None:
        return None
    epoch = int(moment.astimezone(UTC).timestamp())
    start_epoch = (epoch // seconds) * seconds
    start = datetime.fromtimestamp(start_epoch, tz=UTC)
    closing = datetime.fromtimestamp(start_epoch + seconds, tz=UTC)
    return start.isoformat(), closing.isoformat()


def build_signal_identity(
    *,
    instrument_id: str,
    strategy_version: str,
    timeframe: str,
    bar_timestamp: str,
    action: str,
    generated_at: str = "",
    valid_until: str = "",
    extra: tuple[Any, ...] = (),
) -> SignalIdentity | None:
    """Construye una identidad de señal; ``None`` si faltan campos obligatorios.

    Fail-closed: sin instrumento, versión, timeframe, barra o acción no hay identidad
    (no se puede deduplicar ⇒ no se re-emite).
    """
    if not all(
        (
            str(instrument_id).strip(),
            str(strategy_version).strip(),
            str(timeframe).strip(),
            str(bar_timestamp).strip(),
            str(action).strip(),
        )
    ):
        return None
    return SignalIdentity(
        instrument_id=str(instrument_id).strip(),
        strategy_version=str(strategy_version).strip(),
        timeframe=str(timeframe).strip(),
        bar_timestamp=str(bar_timestamp).strip(),
        signal_hash=compute_signal_hash(str(action), *extra),
        generated_at=str(generated_at),
        valid_until=str(valid_until),
    )
