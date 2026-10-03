"""Contrato ``Universe(D)`` — universo point-in-time para estudios históricos (sin implementar).

Qué es
------
Cuando un replay histórico no recibe ``--watch``, el watch se deriva del CATÁLOGO ACTUAL
(instrumentos activos, con sector, con historia). Eso puede introducir **survivorship bias**:
un activo que existía en ``D`` pero ya no está activo desaparece del universo simulado
(hallazgo D34-05). Un universo point-in-time responde a "qué instrumentos eran elegibles en
``D``", no a "qué instrumentos existen hoy".

Este módulo SOLO declara el contrato (tipo + protocolo + helpers puros). NO implementa la
consulta ni cambia el watch por defecto: preparar el contrato no autoriza a inventar la
fuente de verdad de las fechas de alta/baja/sector. Mientras no exista una implementación, el
sesgo se DECLARA en el artefacto (``meta.survivorBiasRisk``).

Contrato demostrable (D35-01)
-----------------------------
Un miembro NO declara solo desde cuándo existía (``active_from``): declara también **hasta
cuándo** (``active_until``), de modo que ser elegible en ``D`` es una propiedad **demostrable**
(``eligible_at``), no una suposición. Un intervalo de fin ``None`` se interpreta como
**abierto** (sin fin registrado): es una suposición declarada, no una certeza. Un inicio
desconocido NO se puede demostrar y por tanto el miembro queda **inelegible** (fail-closed).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


def _clean_id(value: Any) -> str | None:
    """Id no vacío o ``None``: ``None``/``""``/solo espacios NO son un instrumento."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_day(value: Any) -> str | None:
    """Día ``YYYY-MM-DD`` legible o ``None`` (no se adivina una fecha malformada)."""
    text = str(value or "").strip()
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-" and text[7] == "-":
        return text[:10]
    return None


@dataclass(frozen=True, slots=True)
class UniverseMember:
    """Un instrumento elegible con su estado tal y como era en el punto de decisión.

    ``sector_at`` es ``None`` cuando el sector NO se puede reconstruir en el punto ``D``: es un
    hueco declarado (nunca se inventa un sector actual). Los intervalos con fin ``None`` se
    interpretan como **abiertos** (sin fin registrado).
    """

    instrument_id: str
    #: ``YYYY-MM-DD``: fecha desde la que el instrumento es elegible. ``None`` = no demostrable.
    active_from: str | None
    #: ``YYYY-MM-DD``: fecha hasta la que es elegible (delistado). ``None`` = sin fin registrado.
    active_until: str | None
    #: ``YYYY-MM-DD``: primera fecha con historia/barra disponible. ``None`` = no demostrable.
    availability_from: str | None
    #: ``YYYY-MM-DD``: última fecha con historia/barra disponible. ``None`` = sin fin registrado.
    availability_until: str | None
    #: Sector conocido ENTONCES; ``None`` = no medido en el punto ``D``.
    sector_at: str | None


@runtime_checkable
class PointInTimeUniverse(Protocol):
    """Fuente de universo point-in-time: devuelve los miembros elegibles en ``day``."""

    def members(self, day: str) -> Sequence[UniverseMember]:
        """Miembros elegibles en ``day`` (``YYYY-MM-DD``); secuencia vacía si no hay ninguno."""
        ...


def _within(day: str, start: str | None, end: str | None) -> bool:
    """``day`` dentro de ``[start, end]`` con ``start`` DEMOSTRABLE y ``end`` abierto si ``None``.

    Un ``start`` ausente NO se puede demostrar (fail-closed): la pertenencia es ``False``.
    """
    if start is None or day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def eligible_at(member: UniverseMember, day: Any) -> bool:
    """¿Es DEMOSTRABLE que ``member`` era elegible en ``day``? (fail-closed).

    Se exige: id presente, ``day`` legible, inicio de actividad y de disponibilidad
    declarados, y ``day`` dentro de ambos intervalos (fin ``None`` = abierto). Cualquier hueco
    de los necesarios para demostrarlo devuelve ``False``: no se afirma elegibilidad que no se
    pueda probar.
    """
    if _clean_id(member.instrument_id) is None:
        return False
    target = _opt_day(day)
    if target is None:
        return False
    active_from = _opt_day(member.active_from)
    availability_from = _opt_day(member.availability_from)
    if active_from is None or availability_from is None:
        return False
    return _within(target, active_from, _opt_day(member.active_until)) and _within(
        target, availability_from, _opt_day(member.availability_until)
    )


def universe_ids(universe: PointInTimeUniverse, day: str) -> list[str]:
    """Ids de los miembros ELEGIBLES en ``day``, deterministas y sin duplicados.

    Helper puro: filtra por ``eligible_at`` (no basta con que la fuente los liste), normaliza
    orden y deduplica para que dos corridas midan el MISMO universo. Un ``instrument_id``
    vacío/nulo se descarta (no se inventa un instrumento).
    """
    return sorted(
        {
            member_id
            for member in universe.members(day)
            if (member_id := _clean_id(member.instrument_id)) is not None
            and eligible_at(member, day)
        }
    )


__all__ = [
    "PointInTimeUniverse",
    "UniverseMember",
    "eligible_at",
    "universe_ids",
]
