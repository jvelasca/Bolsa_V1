"""AUTO-9 — evidencia de RIESGO por ciclo financiero (READ-ONLY, PURA en el ensamblado).

Qué resuelve, exactamente: el **denominador** de R (``pnl / reserved_risk``) y el coste
**estimado** de cada ciclo, atados por ``cycle_id``. Son los dos datos que el informe
AUTO-7 no podía medir y que convertían ``expectancy_r`` en un ``None`` permanente.

Tres reglas duras, declaradas en vez de asumidas:

* **Denominador único.** Un ciclo puede tener varias reservas (la de ENTRADA y las de
  SALIDA). El denominador es la reserva de entrada (``side='buy'``) **más antigua** con
  ``reserved_risk > 0``. Con varias candidatas se elige la más antigua y se **declaran**
  (``entry_reservations``): se prohíbe repartir el riesgo entre varias, porque R es una
  razón contra UN denominador, no una media de denominadores. La antigüedad se compara como
  **instante**, no como texto, y una candidata sin instante legible se declara
  (``cycle_with_undated_reservation``) en vez de dejar que el desempate lo decida una
  comparación de cadenas: esa comparación solo coincide con el orden cronológico mientras
  TODOS los orígenes serialicen ``created_at`` con el mismo ancho fijo, que es una propiedad
  del repositorio y no del contrato de este módulo.
* **Ausencia declarada.** Un ciclo sin reserva de entrada —o con ``reserved_risk <= 0``,
  que es lo que declara una reserva de venta— queda con ``risk_amount = None`` y su motivo.
  Nunca un ``0``: el R de un riesgo cero es ``inf``, no ``0``.
* **Régimen: medido o declarado, con el motivo exacto.** El mapa ``regime_by_cycle`` viene de
  fuera (``AUTO-10`` lo lee del journal durable por ``decision_id`` derivado + confirmación de
  ``payload['cycleId']``). Si el llamante **no** consultó ninguna fuente durable, el hueco se
  declara ``regime_not_durable``; si la consultó y ese ciclo no trae régimen confirmado, se
  declara ``regime_not_found`` — dos hechos distintos que no se colapsan. Nunca un ``UNKNOWN``
  inventado.

**Las reservas LIBERADAS cuentan.** Cuando un ciclo se cierra, su reserva de entrada ya no
está viva: filtrar por ``is_live`` dejaría el denominador en ``None`` justo en los ciclos
que SÍ tienen resultado. El llamante usa ``list_by_cycle_ids`` (vivas y liberadas).

Read-only: este módulo no escribe nada; solo lee y agrega.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
)
from bolsa_analytics.cognitive.portfolio_reservation import (
    PortfolioReservation,
    TradingCost,
)

__all__ = [
    "CYCLE_RISK_MULTIPLE_RESERVATIONS",
    "CYCLE_RISK_REGIME_NOT_DURABLE",
    "CYCLE_RISK_REGIME_NOT_FOUND",
    "CYCLE_RISK_UNDATED_RESERVATION",
    "CYCLE_RISK_WITHOUT_RISK",
    "CycleRisk",
    "apply_cycle_risk",
    "cycle_risk_from_reservations",
]

#: El ciclo no tiene reserva de entrada identificable ⇒ denominador ausente.
CYCLE_RISK_WITHOUT_RISK = "cycle_without_risk"
#: El ciclo tiene varias reservas de entrada: se usa la más antigua y se declara el resto.
CYCLE_RISK_MULTIPLE_RESERVATIONS = "cycle_with_multiple_reservations"
#: El régimen por ciclo no es legible de ninguna fuente durable (ningún lector consultado).
CYCLE_RISK_REGIME_NOT_DURABLE = "regime_not_durable"
#: Se SÍ consultó la fuente durable y ese ciclo no trae régimen confirmado (hueco distinto).
CYCLE_RISK_REGIME_NOT_FOUND = "regime_not_found"
#: El ciclo tiene varias candidatas y al menos una no declara un instante legible: el desempate
#: por antigüedad no está probado para esas filas (se coloca al final, nunca se le supone fecha).
CYCLE_RISK_UNDATED_RESERVATION = "cycle_with_undated_reservation"


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _dec(value: Any) -> Decimal | None:
    """Decimal del valor, o ``None`` si no es cuantificable (nunca un cero de relleno)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return result if result.is_finite() else None


@dataclass(frozen=True, slots=True)
class CycleRisk:
    """El material de riesgo de UN ciclo, con el estado de medición de cada dimensión.

    Los tres estados son independientes a propósito: un ciclo puede tener denominador
    medido y coste sin medir (``risk_measurement = COMPLETE``, ``cost_measurement =
    UNKNOWN``) y el R neto de ese ciclo no es decisorio aunque el bruto sí. Colapsarlos en
    un único estado obligaría a elegir cuál se pierde.
    """

    cycle_id: str
    risk_amount: Decimal | None = None
    cost: TradingCost | None = None
    regime: str | None = None
    #: Reserva que aportó el denominador (la de entrada más antigua), o ``None``.
    reservation_id: str | None = None
    #: Cuántas reservas de entrada candidatas había (``> 1`` ⇒ se declaró el resto).
    entry_reservations: int = 0
    risk_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    cost_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    regime_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    notes: tuple[str, ...] = ()

    def to_cycle_fields(self) -> dict[str, Any]:
        """(PURA) los campos que el informe puro LEE de una fila de ciclo.

        Solo se emiten las dimensiones MEDIDAS: dejar una clave con ``None`` sería
        indistinguible de "no la aporto", y el informe tiene que poder declarar el hueco.
        """
        fields: dict[str, Any] = {}
        if self.risk_amount is not None:
            fields["riskAmount"] = self.risk_amount
        if self.cost is not None:
            fields["cost"] = self.cost
        if self.regime is not None:
            fields["regime"] = self.regime
        return fields

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycleId": self.cycle_id,
            "riskAmount": None if self.risk_amount is None else str(self.risk_amount),
            "costEstimate": None if self.cost is None else self.cost.to_dict(),
            "regime": self.regime,
            "reservationId": self.reservation_id,
            "entryReservations": self.entry_reservations,
            "riskMeasurement": self.risk_measurement,
            "costMeasurement": self.cost_measurement,
            "regimeMeasurement": self.regime_measurement,
            "notes": list(self.notes),
        }


def _instant(value: Any) -> datetime | None:
    """Instante de un ``created_at`` ISO-8601, o ``None`` si no es legible (nunca se supone)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _antiquity_key(row: PortfolioReservation) -> tuple[int, float, str]:
    """Clave de antigüedad: instante legible primero (cronológico), sin fecha al FINAL.

    El primer componente separa las filas con instante de las que no lo tienen, y el
    desempate por ``reservation_id`` mantiene el resultado determinista e independiente del
    orden de entrada. Antes se comparaba el texto de ``created_at``: correcto solo mientras
    TODO origen use el mismo ancho fijo (lo garantiza el repositorio, no este contrato).
    """
    instant = _instant(row.created_at)
    return (
        0 if instant is not None else 1,
        instant.timestamp() if instant else 0.0,
        _clean(row.reservation_id),
    )


def _entry_candidates(
    rows: Iterable[PortfolioReservation],
) -> tuple[list[PortfolioReservation], bool]:
    """Reservas de ENTRADA con riesgo positivo, de la más antigua a la más nueva.

    Devuelve además si alguna candidata **no** declara un instante legible: ese hecho solo
    importa cuando hay varias candidatas (es el desempate el que queda sin probar).
    """
    candidates = [
        row
        for row in rows
        if row.is_buy and (risk := _dec(row.reserved_risk)) is not None and risk > 0
    ]
    undated = any(_instant(row.created_at) is None for row in candidates)
    return sorted(candidates, key=_antiquity_key), undated


def _cycle_risk(
    cycle_id: str,
    rows: Sequence[PortfolioReservation],
    regimes: Mapping[str, str],
    *,
    regime_source_durable: bool,
) -> CycleRisk:
    candidates, undated = _entry_candidates(rows)
    entry = candidates[0] if candidates else None
    notes: list[str] = []
    if entry is None:
        notes.append(CYCLE_RISK_WITHOUT_RISK)
    elif len(candidates) > 1:
        notes.append(CYCLE_RISK_MULTIPLE_RESERVATIONS)
        if undated:
            # Solo se declara cuando hubo que DESEMPATAR: con una sola candidata la fecha de
            # la otra no cambia nada, y una nota que no cambia nada es ruido en la evidencia.
            notes.append(CYCLE_RISK_UNDATED_RESERVATION)
    regime = _clean(regimes.get(cycle_id))
    if not regime:
        notes.append(
            CYCLE_RISK_REGIME_NOT_FOUND if regime_source_durable else CYCLE_RISK_REGIME_NOT_DURABLE
        )
    risk = _dec(entry.reserved_risk) if entry is not None else None
    cost = (entry.cost or None) if entry is not None else None
    return CycleRisk(
        cycle_id=cycle_id,
        risk_amount=risk,
        cost=cost,
        regime=regime or None,
        reservation_id=_clean(entry.reservation_id) if entry is not None else None,
        entry_reservations=len(candidates),
        risk_measurement=MEASUREMENT_COMPLETE if risk is not None else MEASUREMENT_UNKNOWN,
        cost_measurement=MEASUREMENT_COMPLETE if cost is not None else MEASUREMENT_UNKNOWN,
        regime_measurement=MEASUREMENT_COMPLETE if regime else MEASUREMENT_UNKNOWN,
        notes=tuple(notes),
    )


def cycle_risk_from_reservations(
    cycle_ids: Iterable[str],
    reservations: Iterable[PortfolioReservation],
    *,
    regime_by_cycle: Mapping[str, str] | None = None,
    regime_source_durable: bool = False,
) -> dict[str, CycleRisk]:
    """(PURA) evidencia de riesgo por ciclo, a partir de las reservas de esos ciclos.

    Devuelve una entrada por CADA ciclo pedido, incluidas las que declaran su hueco: una
    ausencia silenciosa en el mapa sería "no lo miré", no "no lo hay". El orden de salida
    sigue el de ``cycle_ids`` (estable, sin depender del orden de las reservas).

    ``regime_source_durable`` declara si el llamante **sí** consultó una fuente durable de
    régimen (el journal de ``AUTO-10``): un ciclo ausente del mapa pasa entonces de
    ``regime_not_durable`` ("no hay fuente") a ``regime_not_found`` ("la fuente se leyó y no
    lo tiene"). Sin el flag, el comportamiento de ``AUTO-9`` queda intacto.
    """
    keys: list[str] = []
    seen: set[str] = set()
    for raw in cycle_ids:
        key = _clean(raw)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    grouped: dict[str, list[PortfolioReservation]] = {}
    for row in reservations:
        key = _clean(row.cycle_id)
        if key and key in seen:
            grouped.setdefault(key, []).append(row)
    regimes = regime_by_cycle or {}
    return {
        key: _cycle_risk(
            key,
            grouped.get(key, ()),
            regimes,
            regime_source_durable=regime_source_durable,
        )
        for key in keys
    }


def apply_cycle_risk(
    cycles: Iterable[Mapping[str, Any]],
    cycle_risk: Mapping[str, CycleRisk] | None,
) -> tuple[Mapping[str, Any], ...]:
    """(PURA) enriquece las filas de ciclo con la evidencia medida.

    Sin evidencia (``None`` o mapa vacío) devuelve las filas **tal cual**, de modo que la
    ruta que no tiene productor siga siendo byte-idéntica a la de ``AUTO-7``. Un ciclo que
    exista en las filas pero no en el mapa se deja intacto: su hueco lo declara el informe.
    """
    rows = tuple(cycles)
    if not cycle_risk:
        return rows
    enriched: list[dict[str, Any]] = []
    for cycle in rows:
        row = dict(cycle)
        evidence = cycle_risk.get(_clean(row.get("cycleId")))
        if evidence is not None:
            row.update(evidence.to_cycle_fields())
        enriched.append(row)
    return tuple(enriched)
