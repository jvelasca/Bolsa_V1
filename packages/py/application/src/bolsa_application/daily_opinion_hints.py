"""Hints del dictamen diario — mediciones de SERVIDOR (nunca del navegador).

El cliente no puede fijar la postura por posición ni los scores del día: ``position_open``
sale de las posiciones abiertas de la cuenta autenticada, y ``io/fa/ta/distress`` de los
mismos chips que usa el parte diario ESTUDIO. ``has_eod_bar`` viaja siempre ``None`` para
que el servicio valide la barra contra la BD (fail-closed).

TRI-ESTADO (H-145-1/H-156-1): ``position_open=None`` significa «la cartera NO se midió»
(adaptador ausente o lectura caída). Nunca se degrada a ``False``: el motor de dictamen
falla cerrado con ``position_unmeasured``.

Reutilizado por:
- ``DailyOpinionService`` (on-demand, POST /instrument-daily-opinions/query)
- ``RunEstudioDailyOps`` (parte diario, source=eod_batch)
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = [
    "COMPOSITE_CHUNK",
    "FUNDAMENTALS_CHUNK",
    "OpenPositionMeasurement",
    "OpinionHint",
    "ServerHintMeasurement",
    "measure_open_positions",
    "measure_opinion_hints",
]

logger = logging.getLogger(__name__)

COMPOSITE_CHUNK = 40
FUNDAMENTALS_CHUNK = 80


@dataclass(frozen=True, slots=True)
class OpinionHint:
    """Mediciones que alimentan ``compute_stance`` para UN instrumento."""

    instrument_id: str
    io_score: float | None = None
    fa_score: float | None = None
    ta_score: float | None = None
    distress: bool = False
    #: TRI-ESTADO: ``None`` = cartera no medida (NO es «sin posición»).
    position_open: bool | None = None
    #: Advisory: el veto de ejecución no se simula en el dictamen.
    allow_trading: bool = True
    #: ``None`` ⇒ el servicio valida la última barra EOD por su cuenta.
    has_eod_bar: bool | None = None


class _CompositeChipsPort(Protocol):
    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = COMPOSITE_CHUNK,
        horizon: str = "swing",
        regime: str = "neutral",
        as_of: str | None = None,
    ) -> list[dict[str, Any]]: ...


class _FundamentalsChipsPort(Protocol):
    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = FUNDAMENTALS_CHUNK,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]: ...


class _OpenPositionsPort(Protocol):
    async def list_open_for_account(self, account_id: str) -> list[Any]: ...


@dataclass(frozen=True, slots=True)
class ServerHintMeasurement:
    """Resultado de la medición: hints por id + huecos declarados."""

    hints: list[OpinionHint]
    by_id: dict[str, OpinionHint] = field(default_factory=dict)
    composite_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    fundamentals_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    open_position_ids: set[str] = field(default_factory=set)
    positions_measured: bool = False
    composite_measured: bool = False
    fundamentals_measured: bool = False
    composite_failed_ids: int = 0
    fundamentals_failed_ids: int = 0
    notes: list[str] = field(default_factory=list)

    def hint_for(self, instrument_id: str) -> OpinionHint:
        found = self.by_id.get(instrument_id)
        if found is not None:
            return found
        return OpinionHint(instrument_id=instrument_id)


@dataclass(frozen=True, slots=True)
class OpenPositionMeasurement:
    """Lectura BARATA de posiciones: ids abiertos + si la cartera se midió.

    Permite resolver la caché (¿la postura guardada sigue siendo verificable?) sin
    pagar los chips composite/fundamentales. ``measured=False`` ⇒ ``position_open``
    viaja ``None`` y el motor falla cerrado; nunca es «sin posición».
    """

    open_ids: set[str] = field(default_factory=set)
    measured: bool = False

    def position_open(self, instrument_id: str) -> bool | None:
        if not self.measured:
            return None
        return instrument_id in self.open_ids


def _chunks(ids: Sequence[str], size: int) -> Iterable[list[str]]:
    step = max(1, size)
    for start in range(0, len(ids), step):
        yield list(ids[start : start + step])


def _float_or_none(raw: Any) -> float | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    return None


def _chip_map(chips: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for chip in chips or []:
        if not isinstance(chip, dict):
            continue
        iid = str(chip.get("instrumentId") or "").strip()
        if iid:
            out[iid] = chip
    return out


async def _composite_chips(
    port: _CompositeChipsPort | None,
    ids: list[str],
    *,
    as_of: str | None,
) -> tuple[list[dict[str, Any]], int]:
    """Chips composite + nº de ids de chunks que fallaron (≠ ids sin tarjeta)."""
    if port is None:
        return [], 0
    chips: list[dict[str, Any]] = []
    failed_ids = 0
    for chunk in _chunks(ids, COMPOSITE_CHUNK):
        try:
            chips.extend(
                await port.execute_chips(
                    chunk,
                    max_ids=COMPOSITE_CHUNK,
                    horizon="swing",
                    regime="neutral",
                    as_of=as_of,
                )
            )
        except Exception:  # noqa: BLE001 — el hueco se declara, no se inventa un 0
            failed_ids += len(chunk)
            logger.warning(
                "daily_opinion_hints: composite_chips_unavailable ids=%d",
                len(chunk),
                exc_info=True,
            )
    return chips, failed_ids


async def _fundamentals_chips(
    port: _FundamentalsChipsPort | None,
    ids: list[str],
    *,
    as_of: str | None,
) -> tuple[list[dict[str, Any]], int]:
    if port is None:
        return [], 0
    chips: list[dict[str, Any]] = []
    failed_ids = 0
    for chunk in _chunks(ids, FUNDAMENTALS_CHUNK):
        try:
            chips.extend(
                await port.execute_chips(
                    chunk,
                    max_ids=FUNDAMENTALS_CHUNK,
                    as_of=as_of,
                )
            )
        except Exception:  # noqa: BLE001 — el hueco se declara, no se inventa un 0
            failed_ids += len(chunk)
            logger.warning(
                "daily_opinion_hints: fundamentals_chips_unavailable ids=%d",
                len(chunk),
                exc_info=True,
            )
    return chips, failed_ids


async def _open_position_ids(
    port: _OpenPositionsPort | None,
    account_id: str | None,
) -> tuple[set[str], bool]:
    """Ids con posición abierta + si la cartera se MIDIÓ (≠ «no hay posiciones»)."""
    if port is None or not (account_id or "").strip():
        return set(), False
    try:
        rows = await port.list_open_for_account(str(account_id))
    except Exception:  # noqa: BLE001 — lectura caída = no medido, nunca «sin posición»
        logger.warning(
            "daily_opinion_hints: positions_unavailable account_id=%s",
            account_id,
            exc_info=True,
        )
        return set(), False
    open_ids: set[str] = set()
    for row in rows:
        iid = str(getattr(row, "instrument_id", "") or "")
        if iid:
            open_ids.add(iid)
    return open_ids, True


async def measure_open_positions(
    positions: _OpenPositionsPort | None,
    account_id: str | None,
) -> OpenPositionMeasurement:
    """Mide SOLO la cartera (una lectura), sin tocar chips.

    La usa el servicio para decidir qué filas de la caché siguen siendo verificables
    antes de pagar composite/fundamentales.
    """
    open_ids, measured = await _open_position_ids(positions, account_id)
    return OpenPositionMeasurement(open_ids=open_ids, measured=measured)


async def measure_opinion_hints(
    instrument_ids: Sequence[str],
    *,
    account_id: str | None,
    composite: _CompositeChipsPort | None = None,
    fundamentals: _FundamentalsChipsPort | None = None,
    positions: _OpenPositionsPort | None = None,
    position_measurement: OpenPositionMeasurement | None = None,
    as_of: str | None = None,
) -> ServerHintMeasurement:
    """Mide en servidor los hints del dictamen para ``instrument_ids``.

    Un adaptador ausente o una lectura caída NO se convierte en un valor neutro: el hueco
    viaja ``None`` y el motor de dictamen lo declara.

    ``position_measurement`` permite reutilizar una lectura de cartera ya hecha (y evita
    repetirla) cuando el llamante solo necesita los chips de un subconjunto.
    """
    ids = list(
        dict.fromkeys(str(i or "").strip() for i in instrument_ids if str(i or "").strip())
    )
    if not ids:
        return ServerHintMeasurement(hints=[])

    composite_chips, composite_failed = await _composite_chips(composite, ids, as_of=as_of)
    fundamentals_chips, fundamentals_failed = await _fundamentals_chips(
        fundamentals, ids, as_of=as_of
    )
    if position_measurement is None:
        open_ids, positions_measured = await _open_position_ids(positions, account_id)
    else:
        open_ids = set(position_measurement.open_ids)
        positions_measured = position_measurement.measured

    composite_by_id = _chip_map(composite_chips)
    fundamentals_by_id = _chip_map(fundamentals_chips)

    notes: list[str] = []
    if not positions_measured:
        # Sin adaptador tampoco se consultó nada: «no medido» se declara, no se asume
        # «sin posición» (H-156-1).
        notes.append("positions_unavailable")
    if composite_failed:
        notes.append(f"composite_chips_unavailable:{composite_failed}_ids")
    if fundamentals_failed:
        notes.append(f"fundamentals_chips_unavailable:{fundamentals_failed}_ids")

    hints: list[OpinionHint] = []
    for iid in ids:
        chip = composite_by_id.get(iid) or {}
        fund = fundamentals_by_id.get(iid) or {}
        hints.append(
            OpinionHint(
                instrument_id=iid,
                io_score=_float_or_none(chip.get("indiceOperativo")),
                fa_score=_float_or_none(fund.get("scoreDisplay100")),
                ta_score=_float_or_none(chip.get("technicalDisplay100")),
                distress=bool(fund.get("distress")),
                position_open=(iid in open_ids) if positions_measured else None,
                allow_trading=True,
                has_eod_bar=None,
            )
        )
    return ServerHintMeasurement(
        hints=hints,
        by_id={hint.instrument_id: hint for hint in hints},
        composite_by_id=composite_by_id,
        fundamentals_by_id=fundamentals_by_id,
        open_position_ids=open_ids,
        positions_measured=positions_measured,
        composite_measured=composite is not None,
        fundamentals_measured=fundamentals is not None,
        composite_failed_ids=composite_failed,
        fundamentals_failed_ids=fundamentals_failed,
        notes=notes,
    )
