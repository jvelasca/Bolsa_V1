"""``PointInTimeUniverseProvider`` real — implementación de ``Universe(D)`` sobre la BD.

Qué es
------
La implementación **operativa** del contrato ``Universe(D)`` de
:mod:`bolsa_application.universe_point_in_time`. Traduce las tablas durables
(``ohlcv_bars`` + ``instruments``) a ``UniverseMember`` y responde "qué instrumentos eran
elegibles en ``D``" con el predicado puro ``eligible_at`` (fail-closed).

Honestidad de la fuente (real vs DECLARADO)
-------------------------------------------
No existe hoy historial de listado/baja ni de sector point-in-time, así que cada campo se
declara por su procedencia y **nunca** se disfraza:

* ``availability_from`` / ``availability_until`` — **REAL**: ``MIN``/``MAX(timestamp)`` de las
  barras D1 durables. Es la única señal histórica demostrable.
* ``active_from`` — **DECLARADO**: alta en el catálogo (``instruments.created_at``). NO es la
  fecha de listado del instrumento; es una cota superior declarada.
* ``active_until`` — **DECLARADO**: ``None`` (abierto) si ``is_active`` es ``True``; si es
  ``False``, la fecha de la última barra como cota declarada de baja (no la fecha real).
* ``sector_at`` — **DECLARADO**: ``instruments.sector`` ACTUAL, no un sector point-in-time.
  Puede ser ``None`` (hueco declarado, no se inventa).

Un instrumento sin barras no tiene ``availability_from`` demostrable ⇒ **inelegible**
(fail-closed), igual que exige el contrato. La cobertura de lo real y de lo aproximado viaja
en :meth:`CatalogPointInTimeUniverse.coverage` para que el artefacto la declare.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_application.universe_point_in_time import (
    UniverseMember,
    eligible_at,
    universe_ids,
)

__all__ = ["CatalogPointInTimeUniverse"]

#: Campos y su procedencia (REAL = demostrable desde barras; DECLARADO = aproximación).
_PROVENANCE: dict[str, str] = {
    "availability_from": "REAL: MIN(timestamp) de barras D1 durables.",
    "availability_until": "REAL: MAX(timestamp) de barras D1 durables.",
    "active_from": "DECLARADO: instruments.created_at (alta en catálogo, no fecha de listado).",
    "active_until": "DECLARADO: None si is_active; última barra si is_active=False.",
    "sector_at": "DECLARADO: instruments.sector actual (no point-in-time).",
}

#: Procedencia declarada de ``active_from`` en MODO HISTÓRICO (``historical=True``): el suelo
#: de elegibilidad pasa a ser la disponibilidad REAL de barras, porque ``created_at`` es el
#: alta en el catálogo (reciente) y NO una fecha de listado: usarlo como suelo haría
#: inaccesible toda la historia anterior a la creación del catálogo.
_HISTORICAL_ACTIVE_FROM = (
    "DECLARADO (modo histórico): availability_from REAL (primera barra D1). El alta en el "
    "catálogo (instruments.created_at) NO es fecha de listado y se declara aparte."
)


def _day(value: Any) -> str | None:
    """Día ``YYYY-MM-DD`` de un ``datetime``/``date``/texto legible, o ``None`` (no se adivina)."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text[:10] if len(text) >= 10 else None
    iso = getattr(value, "isoformat", None)
    if callable(iso):
        text = str(iso())
        return text[:10] if len(text) >= 10 else None
    return None


@dataclass(frozen=True, slots=True)
class CatalogPointInTimeUniverse:
    """Universo point-in-time materializado desde la BD (una lectura determinista).

    Construido con :meth:`load` (BD real) o :meth:`from_members` (puro, para tests). Implementa
    el protocolo :class:`~bolsa_application.universe_point_in_time.PointInTimeUniverse`.
    """

    _members: tuple[UniverseMember, ...] = field(default_factory=tuple, repr=False)
    _excluded_no_bars: int = 0
    _excluded_insufficient_bars: int = 0
    _excluded_no_sector: int = 0
    _instruments_considered: int = 0
    _historical: bool = False

    # ── Construcción ─────────────────────────────────────────────────────────

    @classmethod
    def from_members(
        cls,
        members: Sequence[UniverseMember],
        *,
        excluded_no_bars: int = 0,
        excluded_insufficient_bars: int = 0,
        excluded_no_sector: int = 0,
        instruments_considered: int | None = None,
        historical: bool = False,
    ) -> CatalogPointInTimeUniverse:
        """Construye el universo con miembros ya calculados (sin BD; determinista)."""
        materialized = tuple(members)
        return cls(
            _members=materialized,
            _excluded_no_bars=int(excluded_no_bars),
            _excluded_insufficient_bars=int(excluded_insufficient_bars),
            _excluded_no_sector=int(excluded_no_sector),
            _instruments_considered=(
                len(materialized) if instruments_considered is None else int(instruments_considered)
            ),
            _historical=bool(historical),
        )

    @classmethod
    async def load(
        cls,
        factory: Any,
        *,
        min_bars: int = 60,
        require_sector: bool = False,
        historical: bool = False,
    ) -> CatalogPointInTimeUniverse:
        """Materializa el universo desde ``ohlcv_bars`` + ``instruments`` (read-only).

        ``min_bars`` exige un mínimo de barras D1 para considerar al instrumento medible
        (ATR/régimen); los instrumentos con menos se declaran excluidos, nunca se inventan
        barras. ``require_sector`` descarta además a los que no tienen sector en el catálogo.
        ``historical`` (modo histórico) usa la disponibilidad REAL de barras como suelo de
        elegibilidad en vez de ``created_at`` (ver ``from_catalog_rows``).
        """
        from sqlalchemy import func, select

        from bolsa_infrastructure.database.models.tables import (
            InstrumentRow,
            OhlcvBarRow,
        )

        async with factory() as session:
            bar_rows = (
                await session.execute(
                    select(
                        OhlcvBarRow.instrument_id,
                        func.min(OhlcvBarRow.timestamp),
                        func.max(OhlcvBarRow.timestamp),
                        func.count(),
                    )
                    .where(OhlcvBarRow.timeframe == "1d")
                    .group_by(OhlcvBarRow.instrument_id)
                )
            ).all()
            instrument_rows = (
                await session.execute(
                    select(
                        InstrumentRow.id,
                        InstrumentRow.sector,
                        InstrumentRow.is_active,
                        InstrumentRow.created_at,
                    )
                )
            ).all()

        return cls.from_catalog_rows(
            bar_rows,
            instrument_rows,
            min_bars=min_bars,
            require_sector=require_sector,
            historical=historical,
        )

    @classmethod
    def from_catalog_rows(
        cls,
        bar_rows: Sequence[Sequence[Any]],
        instrument_rows: Sequence[Sequence[Any]],
        *,
        min_bars: int = 60,
        require_sector: bool = False,
        historical: bool = False,
    ) -> CatalogPointInTimeUniverse:
        """Traduce las filas crudas de ``ohlcv_bars``/``instruments`` a ``UniverseMember``.

        Puro y determinista (sin BD): ``bar_rows`` = ``(instrument_id, min_ts, max_ts, count)``;
        ``instrument_rows`` = ``(id, sector, is_active, created_at)``. Aplica la procedencia
        real-vs-declarada descrita en el módulo y el predicado fail-closed del contrato.

        ``historical`` (modo histórico): el suelo de elegibilidad ``active_from`` sale de la
        disponibilidad REAL de barras (``availability_from``), no de ``created_at``. Éste es el
        alta en el catálogo (reciente) y NO una fecha de listado: usarlo como suelo haría
        inaccesible toda la historia anterior a la creación del catálogo. La cota SUPERIOR
        (``active_until``, baja/delistado) NO cambia: es la que corrige el survivorship.
        """
        floor = max(0, int(min_bars))
        instruments = {
            str(row[0]): {
                "sector": row[1],
                "is_active": row[2],
                "created_at": row[3],
            }
            for row in instrument_rows
        }
        bars_by_id: dict[str, tuple[Any, Any, int]] = {
            str(row[0]): (row[1], row[2], int(row[3] or 0)) for row in bar_rows
        }

        members: list[UniverseMember] = []
        excluded_no_bars = 0
        excluded_insufficient = 0
        excluded_no_sector = 0
        for instrument_id, meta in instruments.items():
            bars = bars_by_id.get(instrument_id)
            bar_count = bars[2] if bars is not None else 0
            if bars is None or bar_count < 1:
                excluded_no_bars += 1
                continue
            if bar_count < floor:
                excluded_insufficient += 1
                continue
            sector_at = meta["sector"]
            sector_text = str(sector_at) if sector_at else None
            if require_sector and sector_text is None:
                excluded_no_sector += 1
                continue
            availability_from = _day(bars[0])
            availability_until = _day(bars[1])
            # ``active_until``: abierto si sigue activo; cota declarada (última barra) si no.
            active_until = None if bool(meta["is_active"]) else availability_until
            # Suelo de elegibilidad: REAL (barras) en modo histórico; si no, alta en catálogo.
            active_from = availability_from if historical else _day(meta["created_at"])
            members.append(
                UniverseMember(
                    instrument_id=instrument_id,
                    active_from=active_from,
                    active_until=active_until,
                    availability_from=availability_from,
                    availability_until=availability_until,
                    sector_at=sector_text,
                )
            )

        members.sort(key=lambda member: member.instrument_id)
        return cls(
            _members=tuple(members),
            _excluded_no_bars=excluded_no_bars,
            _excluded_insufficient_bars=excluded_insufficient,
            _excluded_no_sector=excluded_no_sector,
            _instruments_considered=len(instruments),
            _historical=bool(historical),
        )

    # ── Protocolo ``PointInTimeUniverse`` ────────────────────────────────────

    def members(self, day: str) -> list[UniverseMember]:
        """Miembros ELEGIBLES en ``day`` (filtrando por ``eligible_at``, determinista)."""
        return [member for member in self._members if eligible_at(member, day)]

    def ids(self, day: str) -> list[str]:
        """Ids elegibles en ``day`` (deduplicados y ordenados), vía ``universe_ids``."""
        return universe_ids(self, day)

    # ── Declaración de cobertura ─────────────────────────────────────────────

    @property
    def excluded_no_bars(self) -> int:
        """Instrumentos sin ninguna barra D1: disponibilidad NO demostrable (inelegibles)."""
        return self._excluded_no_bars

    def coverage(self) -> dict[str, Any]:
        """Procedencia y cobertura: qué es REAL, qué es DECLARADO y cuánto se excluyó."""
        provenance = dict(_PROVENANCE)
        if self._historical:
            provenance["active_from"] = _HISTORICAL_ACTIVE_FROM
        return {
            "provider": "CatalogPointInTimeUniverse",
            "historicalMode": self._historical,
            "provenance": provenance,
            "instrumentsConsidered": self._instruments_considered,
            "membersMaterialized": len(self._members),
            "excludedNoBars": self._excluded_no_bars,
            "excludedInsufficientBars": self._excluded_insufficient_bars,
            "excludedNoSector": self._excluded_no_sector,
        }
