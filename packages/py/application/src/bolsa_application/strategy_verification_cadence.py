"""Cadencia de verificación — épocas **no solapadas** y ventana móvil declarada.

Por qué existe este módulo
--------------------------
Una cohorte que cuenta 12 replays diarios con ``D = ayer`` no tiene 12 muestras: tiene una
sola operación mirada 12 veces. Ese defecto (pseudorreplicación) no lo detecta
``certify_cohort``, porque su contrato es verificar el método de cada artefacto, no la
independencia entre artefactos.

Aquí se separan DOS relojes y no se mezclan:

* **Épocas** (el que decide): ``D_k`` anclado y paso ``everyDays``; la época ``k`` cubre
  ``(D_k, D_{k+1}]``. Cerrada aporta **una** muestra. Las ventanas no se solapan por
  construcción, y ``assert_non_overlapping`` lo comprueba en lugar de suponerlo.
* **Ventana móvil** (el que se ve): ``(hoy - lookback, hoy]``. Se marca ``overlapping=True``
  y **nunca** entra al veredicto.

Reglas duras:

* Un solape detectado ⇒ ``insufficient_independent_sample``, jamás PASS.
* Una época sin cerrar (la última) se declara ``open`` y no cuenta como muestra.
* Módulo puro: sin reloj, sin I/O. El ``today`` lo inyecta el llamante.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from bolsa_application.strategy_verification_profile import (
    StrategyVerificationProfileV1,
    VerificationProfileError,
    is_iso_day,
)

__all__ = [
    "SAMPLE_KIND_EPOCH",
    "SAMPLE_KIND_ROLLING",
    "STATUS_CLOSED",
    "STATUS_OPEN",
    "VERDICT_INSUFFICIENT_INDEPENDENT",
    "VerificationEpoch",
    "assert_non_overlapping",
    "build_epochs",
    "build_rolling_window",
    "independent_sample_gate",
    "independent_samples",
    "overlaps",
]

SAMPLE_KIND_EPOCH = "epoch"
SAMPLE_KIND_ROLLING = "rolling"

STATUS_CLOSED = "closed"
STATUS_OPEN = "open"

#: Motivo de gate: la cohorte tiene ventanas que se pisan.
VERDICT_INSUFFICIENT_INDEPENDENT = "insufficient_independent_sample"


def _day(value: str | None, *, label: str) -> date:
    if not is_iso_day(value):
        raise VerificationProfileError(f"{label} debe ser una fecha YYYY-MM-DD")
    return date.fromisoformat(str(value)[:10])


@dataclass(frozen=True, slots=True)
class VerificationEpoch:
    """Ventana ``(day, to_day]`` con su estado y su independencia declarada.

    ``overlapping`` no es un cálculo vago: si es ``True`` la época NO es una muestra
    independiente y el veredicto lo rechaza.
    """

    epoch_id: str
    index: int
    day: str
    to_day: str
    status: str
    kind: str = SAMPLE_KIND_EPOCH
    overlapping: bool = False

    def __post_init__(self) -> None:
        _day(self.day, label="epoch.day")
        _day(self.to_day, label="epoch.toDay")
        if self.to_day < self.day:
            raise VerificationProfileError("epoch.toDay es anterior a epoch.day")
        if self.status not in (STATUS_CLOSED, STATUS_OPEN):
            raise VerificationProfileError(f"estado de época no soportado: {self.status}")

    @property
    def is_sample(self) -> bool:
        """Solo una época **cerrada y no solapada** cuenta como muestra independiente."""
        return self.status == STATUS_CLOSED and not self.overlapping

    def to_dict(self) -> dict[str, object]:
        return {
            "epochId": self.epoch_id,
            "index": self.index,
            "day": self.day,
            "toDay": self.to_day,
            "status": self.status,
            "kind": self.kind,
            "overlapping": self.overlapping,
            "isSample": self.is_sample,
        }


def overlaps(a: VerificationEpoch, b: VerificationEpoch) -> bool:
    """¿Comparten algún día las ventanas ``(day, to_day]``?

    Los extremos son excluyentes por la izquierda y excluyentes por la derecha: dos épocas
    contiguas ``(D0, D1]`` y ``(D1, D2]`` **no** se solapan (comparten el instante ``D1``,
    que no es un día de mercado de ninguna de las dos).
    """
    return a.day < b.to_day and b.day < a.to_day


def assert_non_overlapping(epochs: Sequence[VerificationEpoch]) -> None:
    """Falla si dos épocas muestreadas se pisan (no se asume, se comprueba)."""
    samples = [epoch for epoch in epochs if epoch.is_sample]
    ordered = sorted(samples, key=lambda epoch: (epoch.day, epoch.to_day))
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if overlaps(previous, current):
            raise VerificationProfileError(
                "épocas solapadas: "
                f"({previous.day}, {previous.to_day}] y ({current.day}, {current.to_day}]"
            )


def build_epochs(
    profile: StrategyVerificationProfileV1,
    *,
    first_day: str,
    today: str,
) -> tuple[VerificationEpoch, ...]:
    """Épocas ancladas desde ``first_day`` hasta ``today`` (la última puede quedar abierta).

    ``anchorDay`` del perfil manda si está declarado y es anterior a ``today``. El ancla se
    desplaza al pasado por múltiplos de ``everyDays`` para que la rejilla sea estable: añadir
    un día a la ventana no mueve las épocas anteriores.
    """
    start = _day(first_day, label="firstDay")
    end = _day(today, label="today")
    if start >= end:
        return ()
    anchor = (
        _day(profile.cadence.anchor_day, label="anchorDay")
        if profile.cadence.anchor_day
        else start
    )
    if anchor > start:
        anchor = start
    step = max(1, int(profile.cadence.every_days))

    # Rejilla estable: se avanza desde el ancla sin recolocar épocas ya emitidas.
    boundaries: list[date] = [anchor]
    cursor = anchor
    while cursor < end:
        cursor = cursor + timedelta(days=step)
        boundaries.append(cursor)

    epochs: list[VerificationEpoch] = []
    for index in range(len(boundaries) - 1):
        day = boundaries[index]
        frontier = boundaries[index + 1]
        # Una frontera que cae hoy (o después) deja la época ABIERTA: la barra de hoy aún no
        # está completa y contarla sería medir con datos parciales.
        status = STATUS_CLOSED if frontier < end else STATUS_OPEN
        to_day = min(frontier, end)
        if to_day <= day:
            continue
        epochs.append(
            VerificationEpoch(
                epoch_id=f"epoch:{day.isoformat()}",
                index=index,
                day=day.isoformat(),
                to_day=to_day.isoformat(),
                status=status,
            )
        )
    return tuple(epochs)


def build_rolling_window(
    profile: StrategyVerificationProfileV1,
    *,
    today: str,
) -> VerificationEpoch:
    """Ventana móvil del día: se publica para el historial y **no** es muestra."""
    end = _day(today, label="today")
    lookback = max(1, int(profile.cadence.rolling_lookback_days))
    start = end - timedelta(days=lookback)
    return VerificationEpoch(
        epoch_id=f"rolling:{end.isoformat()}",
        index=-1,
        day=start.isoformat(),
        to_day=end.isoformat(),
        status=STATUS_OPEN,
        kind=SAMPLE_KIND_ROLLING,
        overlapping=True,
    )


def independent_samples(
    epochs: Iterable[VerificationEpoch],
) -> tuple[VerificationEpoch, ...]:
    """Solo las épocas cerradas y no solapadas, en orden temporal."""
    return tuple(
        sorted(
            (epoch for epoch in epochs if epoch.is_sample),
            key=lambda epoch: (epoch.day, epoch.to_day),
        )
    )


def independent_sample_gate(
    epochs: Sequence[VerificationEpoch],
    *,
    required: int,
) -> dict[str, object]:
    """Gate de independencia y tamaño: sin las dos cosas no hay veredicto estadístico."""
    samples = independent_samples(epochs)
    overlapping = [epoch.epoch_id for epoch in epochs if epoch.overlapping]
    reason: str | None = None
    if overlapping or not _non_overlapping(samples):
        reason = VERDICT_INSUFFICIENT_INDEPENDENT
    elif len(samples) < max(1, int(required)):
        reason = f"insufficient_sample:{len(samples)}/{max(1, int(required))}"
    return {
        "passed": reason is None,
        "samples": len(samples),
        "required": max(1, int(required)),
        "overlapping": overlapping,
        "reason": reason,
    }


def _non_overlapping(samples: Sequence[VerificationEpoch]) -> bool:
    ordered = sorted(samples, key=lambda epoch: (epoch.day, epoch.to_day))
    return not any(
        overlaps(previous, current)
        for previous, current in zip(ordered, ordered[1:], strict=False)
    )
