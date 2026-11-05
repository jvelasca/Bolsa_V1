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

S10 (auditoría .183) — ``build_signal_identity`` devolvía ``Optional``, y un ``None`` se
puede ignorar: el llamador seguía adelante sin deduplicar, sin auditar y sin poder reproducir
la señal, y el silencio del ``None`` lo hacía indistinguible de "señal nueva". ``SignalClaim``
(con ``claim_signal_id``/``claim_signal_for_bar``) cierra ese hueco: o hay identidad
reclamada, o hay un motivo del vocabulario. No existe el valor neutro que se pueda dejar
pasar de largo.

Este módulo es puro: no toca DB ni reloj salvo por el ``now`` que le pase el llamante.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

__all__ = [
    "SIGNAL_DUPLICATE",
    "SIGNAL_IDENTITY_MISSING",
    "SIGNAL_STALE",
    "SignalClaim",
    "SignalIdentity",
    "bar_window",
    "build_signal_identity",
    "claim_signal_for_bar",
    "claim_signal_id",
    "compute_signal_hash",
    "timeframe_seconds",
]

# Delimitador canónico para componer la identidad de señal (evita colisiones entre
# campos concatenados, p.ej. ("a", "bc") vs ("ab", "c")).
_FIELD_SEP = "\x1f"

# Unidades de timeframe soportadas por ``bar_window`` (minuto/hora/día).
_TIMEFRAME_UNITS: dict[str, int] = {"m": 60, "h": 3600, "d": 86400}

#: Motivos del CLAIM (S10, auditoría .183). Son también los literales que el journal de AUTO
#: publica como ``reason`` de una señal descartada, así que su dueño es este módulo y
#: ``bolsa_application.auto_v2_entry`` los re-exporta en vez de reescribirlos.
#:
#: ``signal_identity_missing``: no hay identidad verificable (timeframe ilegible, reloj sin
#: zona, instrumento/acción vacíos) ⇒ no se puede deduplicar, ni auditar, ni reproducir.
SIGNAL_IDENTITY_MISSING = "signal_identity_missing"
#: La MISMA señal sobre la MISMA barra ya se consumió (worker de 60s sobre señal D1).
SIGNAL_DUPLICATE = "signal_duplicate"
#: La señal caducó: decidir con ella sería decidir sobre una barra que ya no rige.
SIGNAL_STALE = "signal_stale"


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


@dataclass(frozen=True, slots=True)
class SignalClaim:
    """Resultado de RECLAMAR una señal: identidad + por qué no se pudo (S10).

    El defecto que cierra: ``build_signal_identity`` devuelve ``Optional``, y un llamador
    podía ignorar el ``None`` y continuar. Ahí la señal no se deduplicaba (se re-emitía en
    cada turno sobre la misma barra), no se podía auditar y no se podía reproducir — y el
    silencio del ``None`` lo hacía indistinguible de "la señal es nueva".

    Un ``SignalClaim`` **nunca** es ``None`` y nunca está a medias: o trae ``signal_id`` y
    ``is_claimed`` es ``True``, o trae un ``reason`` del vocabulario. Leerlo obliga a decidir,
    porque no hay valor "neutro" que se pueda dejar pasar.
    """

    signal_id: str = ""
    identity: SignalIdentity | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        claimed = bool(self.signal_id)
        refused = bool(self.reason)
        if claimed == refused:
            # Un estado intermedio (id con motivo, o ni id ni motivo) sería ambiguo justo
            # donde el llamador decide si opera: se prohíbe en el constructor.
            raise ValueError("SignalClaim exige exactamente uno de signal_id o reason")

    @property
    def is_claimed(self) -> bool:
        """True solo si hay identidad y NO hay motivo de rechazo."""
        return bool(self.signal_id) and not self.reason


def claim_signal_id(
    signal_id: str | None,
    *,
    valid_until: str = "",
    as_of: str = "",
    consumed: Collection[str] = (),
) -> SignalClaim:
    """Reclama una identidad YA construida (``signal_duplicate``/``signal_stale``).

    El orden de las reglas es el mismo del journal de AUTO y no es casual: sin identidad no
    hay nada que comparar (``signal_identity_missing``); una identidad ya consumida es la
    misma señal repitiéndose (``signal_duplicate``); y una señal caducada alimentaría una
    decisión con una barra que ya no rige (``signal_stale``), aunque no se hubiera consumido.
    """
    identifier = str(signal_id or "").strip()
    if not identifier:
        return SignalClaim(reason=SIGNAL_IDENTITY_MISSING)
    if identifier in {str(item).strip() for item in consumed}:
        return SignalClaim(reason=SIGNAL_DUPLICATE)
    expiry = str(valid_until or "").strip()
    moment = str(as_of or "").strip()
    if expiry and moment and moment > expiry:
        return SignalClaim(reason=SIGNAL_STALE)
    return SignalClaim(signal_id=identifier)


def claim_signal_for_bar(
    *,
    instrument_id: str,
    action: str,
    strategy_version: str | None,
    timeframe: str,
    moment: datetime | None,
    extra: tuple[Any, ...] = (),
    valid_until: str = "",
    as_of: str = "",
    consumed: Collection[str] = (),
) -> SignalClaim:
    """Construye la identidad de la barra que contiene ``moment`` y la reclama.

    ``moment is None`` o sin zona ⇒ ``signal_identity_missing``: no se inventa una ventana
    para poder deduplicar (una barra mal calculada haría que dos señales distintas se leyeran
    como la misma, o al revés).
    """
    if moment is None:
        return SignalClaim(reason=SIGNAL_IDENTITY_MISSING)
    window = bar_window(moment, timeframe)
    if window is None:
        return SignalClaim(reason=SIGNAL_IDENTITY_MISSING)
    bar_start, bar_close = window
    identity = build_signal_identity(
        instrument_id=instrument_id,
        strategy_version=strategy_version or "",
        timeframe=timeframe,
        bar_timestamp=bar_start,
        action=action,
        generated_at=moment.isoformat(),
        valid_until=valid_until or bar_close,
        extra=extra,
    )
    if identity is None:
        return SignalClaim(reason=SIGNAL_IDENTITY_MISSING)
    claim = claim_signal_id(
        identity.signal_id,
        valid_until=identity.valid_until,
        as_of=as_of,
        consumed=consumed,
    )
    if not claim.is_claimed:
        return SignalClaim(identity=identity, reason=claim.reason)
    return SignalClaim(signal_id=claim.signal_id, identity=identity)
