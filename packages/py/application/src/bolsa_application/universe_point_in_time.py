"""Contrato ``Universe(D)`` — universo point-in-time para estudios históricos (sin implementar).

Qué es
------
Cuando un replay histórico no recibe ``--watch``, el watch se deriva del CATÁLOGO ACTUAL
(instrumentos activos, con sector, con historia). Eso puede introducir **survivorship bias**:
un activo que existía en ``D`` pero ya no está activo desaparece del universo simulado
(hallazgo D34-05). Un universo point-in-time responde a "qué instrumentos eran elegibles en
``D``", no a "qué instrumentos existen hoy".

Este módulo SOLO declara el contrato (tipo + protocolo + helper puro). NO implementa la
consulta ni cambia el watch por defecto: preparar el contrato no autoriza a inventar la
fuente de verdad de ``active_at``/``sector_at``. Mientras no exista una implementación, el
sesgo se DECLARA en el artefacto (``meta.survivorBiasRisk``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class UniverseMember:
    """Un instrumento elegible con su estado tal y como era en el punto de decisión.

    ``sector_at`` es ``None`` cuando el sector NO se puede reconstruir en el punto ``D``: es un
    hueco declarado (nunca se inventa un sector actual).
    """

    instrument_id: str
    #: ``YYYY-MM-DD``: fecha desde la que el instrumento es elegible en el punto de decisión.
    active_at: str
    #: Sector conocido ENTONCES; ``None`` = no medido en el punto ``D``.
    sector_at: str | None
    #: ``YYYY-MM-DD``: primera fecha con historia/barra disponible hasta ``D``.
    availability_at: str


@runtime_checkable
class PointInTimeUniverse(Protocol):
    """Fuente de universo point-in-time: devuelve los miembros elegibles en ``day``."""

    def members(self, day: str) -> Sequence[UniverseMember]:
        """Miembros elegibles en ``day`` (``YYYY-MM-DD``); secuencia vacía si no hay ninguno."""
        ...


def universe_ids(universe: PointInTimeUniverse, day: str) -> list[str]:
    """Ids de los miembros elegibles en ``day``, deterministas y sin duplicados.

    Helper puro: normaliza orden y deduplica para que dos corridas midan el MISMO universo.
    Un ``instrument_id`` vacío se descarta (no se inventa un instrumento).
    """
    ids = {str(member.instrument_id).strip() for member in universe.members(day)}
    return sorted(value for value in ids if value)


__all__ = [
    "PointInTimeUniverse",
    "UniverseMember",
    "universe_ids",
]
