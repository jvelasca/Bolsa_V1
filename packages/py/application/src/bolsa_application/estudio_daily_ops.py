"""Servicio — operativa diaria AUTO del universo ESTUDIO.

Un solo recorrido, resuelto en servidor:

1. Universo canónico ``estudio`` (fail-closed: ``unavailable``/``empty`` ⇒ cero opiniones).
2. Hints por valor construidos en servidor (chips composite + fundamentales + posiciones
   de la cuenta). Nada de ``allowTrading``/``hasEodBar`` inventados: ``has_eod_bar`` queda
   a ``None`` para que el servicio de opiniones lo valide barra a barra.
3. ``DailyOpinionService.run_eod_batch`` (idempotente por ``(instrumento, día, fuente)``).
4. ``ProposeEstudioAutoOpenings`` en **dry-run** con esas mismas opiniones ``eod_batch``.
5. Parte por valor con los cuatro estados que la UI nunca mezcla: ``ok`` (plan disparado),
   ``no_signal`` (sin dictamen de apertura), ``no_plan`` (hay señal, el plan no dispara)
   y ``error`` (el valor falló; el batch continúa).

Un fallo de un valor NO aborta el batch. Un fallo global de ``propose`` degrada a
``error`` solo los valores con señal de apertura, nunca se convierte en un ``ok`` falso.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from math import ceil
from typing import Any, Protocol

from bolsa_application.daily_opinion_service import OpinionHint
from bolsa_application.daily_ops_report import (
    ESTUDIO_STATUS_EMPTY,
    ESTUDIO_STATUS_OK,
)
from bolsa_application.estudio_auto_hits import resolve_estudio_auto_source
from bolsa_application.paper_desk_entry import resolve_estudio_universe
from bolsa_infrastructure.alerts.estudio_opinion_email import map_opinion_to_channel

__all__ = [
    "ESTUDIO_DAILY_OPINION_SOURCE",
    "EstudioDailyReport",
    "EstudioDailyValue",
    "RunEstudioDailyOps",
]

#: Fuente de las opiniones calculadas por este recorrido (idempotencia por esta fuente).
ESTUDIO_DAILY_OPINION_SOURCE = "eod_batch"

STATUS_OK = "ok"
STATUS_NO_SIGNAL = "no_signal"
STATUS_NO_PLAN = "no_plan"
STATUS_ERROR = "error"

_VALUES_STATUSES = (STATUS_OK, STATUS_NO_SIGNAL, STATUS_NO_PLAN, STATUS_ERROR)
_OPINION_CHUNK = 10
_COMPOSITE_CHUNK = 40
_FUNDAMENTALS_CHUNK = 80
_MAX_VALUES = 100

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


class _EstudioListPort(Protocol):
    async def execute(self, list_id: str) -> Any: ...


class _OpinionBatchPort(Protocol):
    async def run_eod_batch(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force: bool = True,
        hints: list[OpinionHint] | None = None,
    ) -> list[Any]: ...


class _CompositeChipsPort(Protocol):
    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 40,
        horizon: str = "swing",
        regime: str = "neutral",
        as_of: str | None = None,
    ) -> list[dict[str, Any]]: ...


class _FundamentalsChipsPort(Protocol):
    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 80,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]: ...


class _OpenPositionsPort(Protocol):
    async def list_open_for_account(self, account_id: str) -> list[Any]: ...


class _ProposePort(Protocol):
    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]: ...


# ── contrato de salida ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EstudioDailyValue:
    """Parte de UN valor: señal, decisión y plan. Un hueco viaja como ``None``."""

    instrument_id: str
    status: str
    symbol: str | None = None
    reason: str | None = None
    as_of_bar_date: str | None = None
    computed_at: str | None = None
    stance: str | None = None
    dictamen_stars: int | None = None
    channel: str | None = None
    auto_source: str | None = None
    opinion_reasons: list[str] = field(default_factory=list)
    gate_status: str | None = None
    engine_version: str | None = None
    top_id: str | None = None
    top_version: int | None = None
    indicators: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] | None = None
    why_not: list[str] = field(default_factory=list)
    strategy: dict[str, Any] | None = None
    #: Tri-estado de posición abierta: ``None`` = no medido (la lectura falló). El motor de
    #: dictamen sigue recibiendo ``False`` (Δ decisión = 0); esta bandera solo declara el hueco.
    position_open: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrument_id,
            "symbol": self.symbol,
            "status": self.status,
            "reason": self.reason,
            "asOfBarDate": self.as_of_bar_date,
            "computedAt": self.computed_at,
            # H-145-1 — ``positionOpen`` es TRI-ESTADO: ``True``/``False`` cuando la lectura de
            # posiciones respondió y ``None`` cuando no se pudo medir (antes un fallo de lectura
            # se publicaba como ``False``: «sin posición» sin evidencia).
            "positionOpen": self.position_open,
            "opinion": {
                "stance": self.stance,
                "dictamenStars": self.dictamen_stars,
                "channel": self.channel,
                "autoSource": self.auto_source,
                "reasons": list(self.opinion_reasons),
                "gateStatus": self.gate_status,
                "engineVersion": self.engine_version,
                # Identidad del TOP que consumió la opinión (evidencia real, no un hueco).
                "topId": self.top_id,
                "topVersion": self.top_version,
            },
            "indicators": dict(self.indicators),
            "plan": self.plan,
            "whyNot": list(self.why_not),
            "strategy": self.strategy,
        }


@dataclass(frozen=True, slots=True)
class EstudioDailyReport:
    """Parte completo del día para una cuenta."""

    as_of: str
    account_id: str
    status: str
    values: list[EstudioDailyValue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    generated_at: str | None = None
    truncated: bool = False
    #: Tamaño del universo ESTUDIO **antes** del recorte (`_MAX_VALUES`). Permite declarar
    #: cobertura («procesados de esperados») sin fabricar un dato: 0 = no medido.
    universe_count: int = 0

    @property
    def counts(self) -> dict[str, int]:
        out = {status: 0 for status in _VALUES_STATUSES}
        for value in self.values:
            out[value.status] = out.get(value.status, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        counts = self.counts
        return {
            "asOf": self.as_of,
            "accountId": self.account_id,
            "status": self.status,
            "scannedCount": len(self.values),
            "counts": counts,
            "values": [value.to_dict() for value in self.values],
            "notes": list(self.notes),
            "generatedAt": self.generated_at,
            "truncated": self.truncated,
            "universeCount": self.universe_count,
            # Los contadores SIEMPRE suman el universo escaneado (criterio falsable).
            "countsConsistent": sum(counts.values()) == len(self.values),
        }


# ── helpers ──────────────────────────────────────────────────────────────────


def _chunks(ids: Sequence[str], size: int) -> Iterable[list[str]]:
    step = max(1, size)
    for start in range(0, len(ids), step):
        yield list(ids[start : start + step])


def _iso_day(raw: Any) -> str:
    if isinstance(raw, date):
        return raw.isoformat()
    return str(raw or "")[:10]


def _iso_dt(raw: Any) -> str | None:
    return raw.isoformat() if isinstance(raw, datetime) else None


def _float_or_none(raw: Any) -> float | None:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    return None


def _int_or_none(raw: Any) -> int | None:
    if isinstance(raw, int) and not isinstance(raw, bool):
        return int(raw)
    return None


def _chip_map(chips: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for chip in chips:
        iid = str(chip.get("instrumentId") or "").strip()
        if iid:
            out[iid] = chip
    return out


def _plan_payload(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    """Solo niveles del ``TradePlan``; un hueco se declara ``None`` (jamás un 0)."""
    if not isinstance(plan, dict):
        return None
    return {
        "status": plan.get("status"),
        "direction": plan.get("direction"),
        "entry": _float_or_none(plan.get("entry")),
        "structuralStop": _float_or_none(plan.get("structuralStop")),
        "target1": _float_or_none(plan.get("target1")),
        "target2": _float_or_none(plan.get("target2")),
        "riskAmount": _float_or_none(plan.get("riskAmount")),
        "expectedRR": _float_or_none(plan.get("expectedRR")),
        "entryCondition": plan.get("entryCondition"),
        "entrySetup": plan.get("entrySetup"),
        "expiresAt": plan.get("expiresAt"),
        "executionAllowed": plan.get("executionAllowed"),
        "whyNot": [str(w) for w in (plan.get("whyNot") or []) if w],
    }


def _auto_source_for(row: Any) -> str | None:
    stance = str(getattr(row, "stance", "") or "")
    stars = _int_or_none(getattr(row, "dictamen_stars", None)) or 0
    return resolve_estudio_auto_source(stance=stance, dictamen_stars=stars)


def _channel_for(row: Any) -> str | None:
    stance = str(getattr(row, "stance", "") or "")
    stars = _int_or_none(getattr(row, "dictamen_stars", None)) or 0
    return map_opinion_to_channel(stance=stance, dictamen_stars=stars)


# ── servicio ─────────────────────────────────────────────────────────────────


class RunEstudioDailyOps:
    """Genera la operativa diaria por valor (idempotente por fuente ``eod_batch``)."""

    def __init__(
        self,
        estudio_list: _EstudioListPort | None,
        opinions: _OpinionBatchPort,
        propose: _ProposePort,
        *,
        composite: _CompositeChipsPort | None = None,
        fundamentals: _FundamentalsChipsPort | None = None,
        positions: _OpenPositionsPort | None = None,
    ) -> None:
        self._estudio = estudio_list
        self._opinions = opinions
        self._propose = propose
        self._composite = composite
        self._fundamentals = fundamentals
        self._positions = positions

    async def execute(
        self,
        *,
        account_id: str,
        as_of: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> EstudioDailyReport:
        day = _iso_day(as_of) or datetime.now(UTC).date().isoformat()
        notes: list[str] = []
        await self._emit(on_progress, phase="universe", done=0, total=0)

        resolution = await resolve_estudio_universe(self._estudio)
        if resolution.status != ESTUDIO_STATUS_OK:
            reason = (
                "Universo ESTUDIO vacío: no hay valores que operar"
                if resolution.status == ESTUDIO_STATUS_EMPTY
                else "Universo ESTUDIO no disponible"
            )
            return EstudioDailyReport(
                as_of=day,
                account_id=account_id,
                status=resolution.status,
                notes=[reason],
                generated_at=datetime.now(UTC).isoformat(),
            )

        ids = list(dict.fromkeys(str(i) for i in resolution.instrument_ids if i))
        universe_count = len(ids)
        truncated = len(ids) > _MAX_VALUES
        if truncated:
            ids = ids[:_MAX_VALUES]
            notes.append(
                f"Universo recortado a {_MAX_VALUES} valores (el ESTUDIO tiene más)"
            )

        await self._emit(on_progress, phase="hints", done=0, total=len(ids))
        hints, chip_by_id, hint_notes, position_open_by_id = await self._build_hints(
            ids, account_id=account_id, day=day
        )
        notes.extend(hint_notes)

        await self._emit(on_progress, phase="opinions", done=0, total=len(ids))
        rows, value_errors = await self._run_opinions(
            ids,
            account_id=account_id,
            day=day,
            hints=hints,
            on_progress=on_progress,
        )

        await self._emit(on_progress, phase="propose", done=0, total=len(ids))
        hits_by_id, skipped_by_id, propose_error = await self._run_propose(
            ids, account_id=account_id, day=day, hints=hints
        )
        if propose_error is not None:
            notes.append(f"propose no disponible: {propose_error}")
        notes.append(
            "allowTrading=true se declara como cálculo advisory; el veto de ejecución "
            "se aplica en el camino de ejecución (PAPER_D_EXECUTE)."
        )

        await self._emit(on_progress, phase="compose", done=0, total=len(ids))
        values = self._compose(
            ids,
            rows={str(r.instrument_id): r for r in rows},
            chip_by_id=chip_by_id,
            hits_by_id=hits_by_id,
            skipped_by_id=skipped_by_id,
            value_errors=value_errors,
            propose_error=propose_error,
            position_open_by_id=position_open_by_id,
        )
        await self._emit(
            on_progress, phase="done", done=len(values), total=len(values)
        )

        return EstudioDailyReport(
            as_of=day,
            account_id=account_id,
            status=ESTUDIO_STATUS_OK,
            values=values,
            notes=notes,
            generated_at=datetime.now(UTC).isoformat(),
            truncated=truncated,
            universe_count=universe_count,
        )

    # ── hints ────────────────────────────────────────────────────────────────

    async def _build_hints(
        self,
        ids: list[str],
        *,
        account_id: str,
        day: str,
    ) -> tuple[list[OpinionHint], dict[str, dict[str, Any]], list[str], dict[str, bool | None]]:
        """Hints por valor + notas de huecos declarados + posición abierta TRI-ESTADO.

        Un fallo de chips se DECLARA en ``notes`` (cuántos ids quedaron sin ese indicador); un
        fallo de la lectura de posiciones deja el valor a ``None`` (no medido) en el mapa de
        posición, en vez de afirmar «sin posición».
        """
        composite_chips: list[dict[str, Any]] = []
        fundamentals_chips: list[dict[str, Any]] = []
        notes: list[str] = []
        if self._composite is not None:
            failed = 0
            for chunk in _chunks(ids, _COMPOSITE_CHUNK):
                try:
                    composite_chips.extend(
                        await self._composite.execute_chips(
                            chunk, horizon="swing", regime="neutral", as_of=day
                        )
                    )
                except Exception:  # noqa: BLE001 — el batch sigue, el hueco se declara.
                    failed += len(chunk)
            if failed:
                notes.append(f"composite_chips_unavailable:{failed}_ids")
        if self._fundamentals is not None:
            failed = 0
            for chunk in _chunks(ids, _FUNDAMENTALS_CHUNK):
                try:
                    fundamentals_chips.extend(
                        await self._fundamentals.execute_chips(chunk, as_of=day)
                    )
                except Exception:  # noqa: BLE001 — el batch sigue, el hueco se declara.
                    failed += len(chunk)
            if failed:
                notes.append(f"fundamentals_chips_unavailable:{failed}_ids")

        chip_by_id = _chip_map(composite_chips)
        fund_by_id = _chip_map(fundamentals_chips)

        open_ids: set[str] = set()
        positions_measured = True
        if self._positions is not None:
            try:
                for position in await self._positions.list_open_for_account(account_id):
                    iid = str(getattr(position, "instrument_id", "") or "")
                    if iid:
                        open_ids.add(iid)
            except Exception:  # noqa: BLE001 — se declara «no medido», no «sin posición».
                open_ids = set()
                positions_measured = False
                notes.append("positions_unavailable")

        hints: list[OpinionHint] = []
        for iid in ids:
            chip = chip_by_id.get(iid) or {}
            fund = fund_by_id.get(iid) or {}
            hints.append(
                OpinionHint(
                    instrument_id=iid,
                    io_score=_float_or_none(chip.get("indiceOperativo")),
                    fa_score=_float_or_none(fund.get("scoreDisplay100")),
                    ta_score=_float_or_none(chip.get("technicalDisplay100")),
                    distress=bool(fund.get("distress")),
                    position_open=iid in open_ids,
                    # Advisory: el veto de ejecución no se simula aquí (se declara en notes).
                    allow_trading=True,
                    has_eod_bar=None,
                )
            )
        return hints, chip_by_id, notes, {
            iid: (iid in open_ids) if positions_measured else None for iid in ids
        }

    # ── opiniones ────────────────────────────────────────────────────────────

    async def _run_opinions(
        self,
        ids: list[str],
        *,
        account_id: str,
        day: str,
        hints: list[OpinionHint],
        on_progress: ProgressCallback | None,
    ) -> tuple[list[Any], dict[str, str]]:
        rows: list[Any] = []
        errors: dict[str, str] = {}
        hint_by_id = {h.instrument_id: h for h in hints}
        done = 0
        total = len(ids)
        bar_date = date.fromisoformat(day)

        async def _run(chunk: list[str]) -> list[Any]:
            return await self._opinions.run_eod_batch(
                instrument_ids=chunk,
                as_of_bar_date=bar_date,
                account_id=account_id,
                force=True,
                hints=[hint_by_id[i] for i in chunk if i in hint_by_id],
            )

        for chunk in _chunks(ids, _OPINION_CHUNK):
            try:
                rows.extend(await _run(chunk))
            except Exception:
                # Aislamiento por valor: se reintenta uno a uno antes de declarar el fallo.
                for iid in chunk:
                    try:
                        rows.extend(await _run([iid]))
                    except Exception as exc:  # noqa: BLE001 — un valor no tumba el batch
                        errors[iid] = f"opinion_error:{exc}"
            done += len(chunk)
            await self._emit(on_progress, phase="opinions", done=done, total=total)
        return rows, errors

    # ── propuesta dry-run ────────────────────────────────────────────────────

    async def _run_propose(
        self,
        ids: list[str],
        *,
        account_id: str,
        day: str,
        hints: list[OpinionHint],
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], str | None]:
        try:
            result = await self._propose.execute(
                {
                    "instrumentIds": ids,
                    "asOfBarDate": day,
                    "accountId": account_id,
                    "maxCandidates": min(len(ids), _MAX_VALUES),
                    "execute": False,
                    # Reutiliza las opiniones `eod_batch` recién escritas y los hints del job.
                    "forceRefresh": False,
                    "hints": hints,
                    "opinionSource": ESTUDIO_DAILY_OPINION_SOURCE,
                }
            )
        except Exception as exc:  # noqa: BLE001 — el parte sigue, con error declarado
            return {}, {}, str(exc)

        hits = {
            str(h.get("instrumentId")): h
            for h in (result.get("hits") or [])
            if isinstance(h, dict) and h.get("instrumentId")
        }
        skipped = {
            str(s.get("instrumentId")): s
            for s in (result.get("skipped") or [])
            if isinstance(s, dict) and s.get("instrumentId")
        }
        return hits, skipped, None

    # ── composición del parte ────────────────────────────────────────────────

    def _compose(
        self,
        ids: list[str],
        *,
        rows: dict[str, Any],
        chip_by_id: dict[str, dict[str, Any]],
        hits_by_id: dict[str, dict[str, Any]],
        skipped_by_id: dict[str, dict[str, Any]],
        value_errors: dict[str, str],
        propose_error: str | None,
        position_open_by_id: dict[str, bool | None],
    ) -> list[EstudioDailyValue]:
        values: list[EstudioDailyValue] = []
        for iid in ids:
            row = rows.get(iid)
            chip = chip_by_id.get(iid) or {}
            payload: dict[str, Any] = {
                "instrument_id": iid,
                "symbol": chip.get("ticker"),
                # H-145-1 — ``None`` cuando la lectura de posiciones falló: el parte declara el
                # hueco en vez de afirmar «sin posición» desde una lectura caída.
                "position_open": position_open_by_id.get(iid),
                "indicators": {
                    "io": _float_or_none(chip.get("indiceOperativo")),
                    "fa": _float_or_none(chip.get("scoreDisplay100")),
                    "ta": _float_or_none(chip.get("technicalDisplay100")),
                    "confidence": chip.get("confidence"),
                    "regime": chip.get("regime"),
                },
            }
            if row is not None:
                payload.update(
                    {
                        "as_of_bar_date": _iso_day(row.as_of_bar_date),
                        "computed_at": _iso_dt(row.computed_at),
                        "stance": getattr(row, "stance", None),
                        "dictamen_stars": _int_or_none(
                            getattr(row, "dictamen_stars", None)
                        ),
                        "channel": _channel_for(row),
                        "auto_source": _auto_source_for(row),
                        "opinion_reasons": list(getattr(row, "reasons", None) or []),
                        "gate_status": getattr(row, "gate_status", None),
                        "engine_version": getattr(row, "engine_version", None),
                        "top_id": getattr(row, "top_id", None),
                        "top_version": _int_or_none(
                            getattr(row, "top_version", None)
                        ),
                    }
                )

            if iid in value_errors:
                values.append(
                    EstudioDailyValue(
                        status=STATUS_ERROR,
                        reason=value_errors[iid],
                        **payload,
                    )
                )
                continue

            if row is None:
                values.append(
                    EstudioDailyValue(
                        status=STATUS_ERROR,
                        reason="opinion_missing",
                        **payload,
                    )
                )
                continue

            hit = hits_by_id.get(iid)
            if hit is not None:
                plan = _plan_payload(hit.get("tradePlan"))
                raw_signal = hit.get("signal")
                signal: dict[str, Any] = (
                    raw_signal if isinstance(raw_signal, dict) else {}
                )
                payload["symbol"] = payload.get("symbol") or hit.get("symbol")
                values.append(
                    EstudioDailyValue(
                        status=STATUS_OK,
                        plan=plan,
                        why_not=list((plan or {}).get("whyNot") or []),
                        strategy={
                            # `presetKey` aquí es el preset de ORIGEN del camino Estudio
                            # (constante `estudio_auto`), no la identidad de la estrategia.
                            "presetKey": signal.get("presetKey"),
                            "strategyDefinitionId": signal.get("strategyDefinitionId"),
                            "strategyVersion": signal.get("strategyVersion"),
                            "planId": hit.get("planId") or hit.get("scanId"),
                            "signalId": signal.get("id"),
                        },
                        **payload,
                    )
                )
                continue

            skipped = skipped_by_id.get(iid)
            if skipped is not None:
                plan = _plan_payload(skipped.get("tradePlan"))
                why_not = [str(w) for w in (skipped.get("whyNot") or []) if w]
                values.append(
                    EstudioDailyValue(
                        status=STATUS_NO_PLAN,
                        reason=str(skipped.get("reason") or "no_tradeplan"),
                        plan=plan,
                        why_not=why_not,
                        **payload,
                    )
                )
                continue

            if _auto_source_for(row) is None:
                stance = str(getattr(row, "stance", "") or "")
                values.append(
                    EstudioDailyValue(
                        status=STATUS_NO_SIGNAL,
                        reason=(
                            "dictamen_insuficiente"
                            if stance == "buy"
                            else f"stance:{stance or 'unknown'}"
                        ),
                        **payload,
                    )
                )
                continue

            # Tenía señal de apertura pero ``propose`` no devolvió nada para el valor.
            values.append(
                EstudioDailyValue(
                    status=STATUS_ERROR if propose_error else STATUS_NO_PLAN,
                    reason=(
                        f"propose_error:{propose_error}"
                        if propose_error
                        else "propose_sin_resultado"
                    ),
                    **payload,
                )
            )
        return values

    # ── progreso ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _emit(
        on_progress: ProgressCallback | None,
        *,
        phase: str,
        done: int,
        total: int,
    ) -> None:
        if on_progress is None:
            return
        await on_progress(
            {
                "phase": phase,
                "done": int(done),
                "total": int(total),
                "percent": (
                    None if total <= 0 else min(100, int(ceil(done * 100 / total)))
                ),
                "updatedAt": datetime.now(UTC).isoformat(),
            }
        )
