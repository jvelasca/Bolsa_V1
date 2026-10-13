"""V2.98 · PAPER WINDOW CERTIFICATION — certificador puro de la ventana longitudinal PAPER.

Qué resuelve: el contrato PAPER exige una ventana **real** de ``≥4 días`` de calendario, ``≥2``
episodios de régimen y ``≥32`` ciclos medibles (``P3-2``/``P3-3``, ADR-046). Esos tres números
``window_gate`` ya los calcula del material durable (``operability_window``), pero su salida es un
``dict`` sin tipar y —sobre todo— **colapsa el hueco a cero**: sin filas devuelve ``days=0``,
``episodes=0``, ``cycles=0``. Ese cero es peligroso: «no lo he mirado» y «lo miré y no hay nada»
no son el mismo hecho.

Esta pieza es la capa tipada que cierra el matiz: dada la MISMA serie diaria durable (las filas que
``build_window_row`` produce), delega el cómputo en ``window_gate`` (no abre un segundo camino que
pudiera divergir) y publica cada criterio con su **eje**, su **umbral exigido** y su **hueco
declarado**.

Reglas duras:

* **``UNKNOWN ≠ 0``.** Si el material NO se midió (fuente no leída), los tres conteos viajan ``None``
  y el veredicto es ``INCONCLUSIVE`` —jamás un ``READY`` fabricado ni un ``0`` de relleno—. Un cero
  sólo es legítimo cuando el material SÍ se leyó y estaba vacío.
* **Importa los umbrales de su fuente única.** ``MARKET_WINDOW_MIN_DAYS``/``_EPISODES``/``_CYCLES``
  y el veredicto viven en ``operability_window``: aquí NO se re-declaran.
* **Cómputo único.** ``días`` = cubos de CALENDARIO distintos, ``episodios`` = regímenes distintos y
  ``ciclos`` = ciclos MEDIBLES (con R): exactamente lo que cuenta ``window_gate``.
* **No decide.** No toca el motor, el gobernador ni ``TOP_N``; sólo LEE y declara.

Puro y determinista: sin I/O, sin red, sin reloj. La lectura del material durable es del llamante.

@see packages/py/application/src/bolsa_application/operability_window.py (``window_gate``)
@see docs/adr/046-protocolo-longitudinal-paper.md
@see docs/PROJECT_PREMISES.md §5.1.2
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from bolsa_application.operability_window import (
    MARKET_WINDOW_INCONCLUSIVE,
    MARKET_WINDOW_MIN_CYCLES,
    MARKET_WINDOW_MIN_DAYS,
    MARKET_WINDOW_MIN_EPISODES,
    MARKET_WINDOW_READY,
    window_gate,
)

__all__ = [
    "CERTIFICATION_AXIS",
    "CRITERION_CYCLES",
    "CRITERION_DAYS",
    "CRITERION_EPISODES",
    "PAPER_WINDOW_CERTIFICATION_SCHEMA",
    "PaperWindowCertification",
    "PaperWindowCriterion",
    "PaperWindowMaterial",
    "certify_paper_window",
]

#: Sello del certificador. Si cambia un criterio o su eje, el sello lo declara.
PAPER_WINDOW_CERTIFICATION_SCHEMA = "paper_window_certification_v1"

#: EJE declarado del certificado: la ventana de ``window_gate`` (no la del contrato PAPER, que
#: cuenta ``closed_operations``/``fills``). Se publica para que nadie confunda los dos ejes.
CERTIFICATION_AXIS = (
    "market_window: dias de CALENDARIO (cubos distintos) / regimenes DISTINTOS / ciclos MEDIBLES (R)"
)

#: Identificadores estables de cada criterio del certificado.
CRITERION_DAYS = "days"
CRITERION_EPISODES = "episodes"
CRITERION_CYCLES = "measurable_cycles"


@dataclass(frozen=True, slots=True)
class PaperWindowMaterial:
    """El material durable ya LEÍDO que se certifica (aquí no hay I/O).

    ``measured`` declara si la fuente se pudo leer: ``False`` ⇒ los tres conteos son huecos
    (``None``), NUNCA ceros. ``rows`` son las filas de la serie diaria (``build_window_row``);
    con ``measured=True`` y sin filas el material es un cero **medido** («la leí y está vacía»).
    """

    measured: bool
    rows: Sequence[Mapping[str, Any]] = ()
    account_id: str | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class PaperWindowCriterion:
    """Un criterio del certificado: qué exige, cuánto se midió y si se cumple."""

    id: str
    measured: bool
    actual: int | None
    required: int
    met: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "measured": self.measured,
            "actual": self.actual,
            "required": self.required,
            "met": self.met,
        }


@dataclass(frozen=True, slots=True)
class PaperWindowCertification:
    """El certificado tipado de la ventana: veredicto, conteos medidos/huecos y criterios faltantes."""

    schema_version: str
    axis: str
    verdict: str
    ready: bool
    measured: bool
    days: int | None
    episodes: int | None
    measurable_cycles: int | None
    min_days: int
    min_episodes: int
    min_cycles: int
    criteria: tuple[PaperWindowCriterion, ...]
    missing: tuple[str, ...]
    day_list: tuple[str, ...]
    regimes: tuple[str, ...]
    account_id: str | None = None
    source: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "axis": self.axis,
            "verdict": self.verdict,
            "ready": self.ready,
            "measured": self.measured,
            "days": self.days,
            "episodes": self.episodes,
            "measurableCycles": self.measurable_cycles,
            "thresholds": {
                "days": self.min_days,
                "episodes": self.min_episodes,
                "measurableCycles": self.min_cycles,
            },
            "criteria": [criterion.as_dict() for criterion in self.criteria],
            "missingCriterionIds": list(self.missing),
            "dayList": list(self.day_list),
            "regimes": list(self.regimes),
            "accountId": self.account_id,
            "source": self.source,
        }


def _criterion(criterion_id: str, actual: int | None, required: int) -> PaperWindowCriterion:
    """Criterio tipado: ``met`` sólo con un conteo MEDIDO que alcanza el umbral (``None`` no cumple)."""
    if actual is None:
        return PaperWindowCriterion(
            id=criterion_id, measured=False, actual=None, required=required, met=False
        )
    return PaperWindowCriterion(
        id=criterion_id, measured=True, actual=actual, required=required, met=actual >= required
    )


def certify_paper_window(material: PaperWindowMaterial) -> PaperWindowCertification:
    """(PURA) certifica la ventana PAPER a partir del material durable ya leído.

    Delega el cómputo en ``window_gate`` (una sola noción de días/episodios/ciclos) y traduce su
    salida al contrato tipado. Si el material NO se midió (``measured=False``), los tres conteos se
    declaran ``None`` aunque ``window_gate`` devuelva ceros: un hueco nunca se colapsa a cero.
    """
    gate = window_gate(list(material.rows))
    measured = bool(material.measured)
    # Un material no medido NO puede certificar nada: los conteos son huecos, no ceros.
    days = int(gate["days"]) if measured else None
    episodes = int(gate["episodes"]) if measured else None
    cycles = int(gate["cycles"]) if measured else None

    criteria = (
        _criterion(CRITERION_DAYS, days, MARKET_WINDOW_MIN_DAYS),
        _criterion(CRITERION_EPISODES, episodes, MARKET_WINDOW_MIN_EPISODES),
        _criterion(CRITERION_CYCLES, cycles, MARKET_WINDOW_MIN_CYCLES),
    )
    missing = tuple(criterion.id for criterion in criteria if not criterion.met)
    # READY sólo con el material MEDIDO y los tres criterios cumplidos: sin medición, INCONCLUSIVE.
    ready = measured and not missing
    return PaperWindowCertification(
        schema_version=PAPER_WINDOW_CERTIFICATION_SCHEMA,
        axis=CERTIFICATION_AXIS,
        verdict=MARKET_WINDOW_READY if ready else MARKET_WINDOW_INCONCLUSIVE,
        ready=ready,
        measured=measured,
        days=days,
        episodes=episodes,
        measurable_cycles=cycles,
        min_days=MARKET_WINDOW_MIN_DAYS,
        min_episodes=MARKET_WINDOW_MIN_EPISODES,
        min_cycles=MARKET_WINDOW_MIN_CYCLES,
        criteria=criteria,
        missing=missing,
        day_list=tuple(gate["dayList"]) if measured else (),
        regimes=tuple(gate["regimes"]) if measured else (),
        account_id=material.account_id,
        source=material.source,
    )
