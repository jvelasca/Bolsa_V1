"""Handoff durable propuesta ESTUDIO → ciclo AUTO (casos de uso y reglas puras).

Problema que cierra
-------------------
El parte diario ESTUDIO publica por valor una señal (``signalId``) y un plan
(``TradePlan.decisionId``), pero el productor AUTO acuñaba su propia identidad a partir
de la barra (``signal_identity_for_bar``) y **no** consumía el plan del parte. La cadena
``señal → plan → reserva → orden → fill → posición → salida → cierre`` solo podía
"cuadrar" por símbolo, que es una INFERENCIA y no una prueba.

Este módulo define el contrato del puente:

1. :class:`PersistEstudioDailyProposals` — del ``result`` del job diario a filas
   durables (idempotente, sin reescribir identidades ya publicadas).
2. :class:`LoadAdoptableDailyProposals` — qué puede adoptar el productor para SU
   frontera de decisión, con la frescura declarada por la vela (no por el reloj).
3. :class:`RecordDailyProposalOutcomes` — desenlace: consumida con el ``cycle_id`` que
   la adoptó, o rechazada con el motivo. Nunca se sustituye el plan para "cuadrar".

Reglas duras
------------
* Sin ``decision_id`` (identidad del plan) o sin ``signal_id`` NO hay adopción: la
  propuesta queda pendiente y la cadena declarará ``not_attributed``.
* Una propuesta con vela POSTERIOR a la frontera de decisión no se adelanta (lookahead).
* Una propuesta con vela demasiado antigua caduca (``expired``) con su motivo: nunca se
  atribuye un plan de otra semana al ciclo de hoy.
* El productor puede rechazarla (gates del motor). Rechazo ≠ "se busca otra": la
  propuesta se cierra con el motivo y el ciclo, si existe, queda sin atribuir.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

from bolsa_domain.entities.estudio_daily_proposal import (
    PROPOSAL_STATUS_EXPIRED,
    PROPOSAL_STATUS_REJECTED,
    EstudioDailyProposal,
)

__all__ = [
    "ADOPTION_ABSENT_NOT_IN_UNIVERSE",
    "ADOPTION_ABSENT_NOT_PROPOSED",
    "ADOPTION_ABSENT_UNMEASURED",
    "ADOPTION_EXACT",
    "ADOPTION_MISMATCH",
    "ADOPTION_UNWINDOWED",
    "AdoptionResult",
    "HandoffSummary",
    "LoadAdoptableDailyProposals",
    "PersistEstudioDailyProposals",
    "ProposalEvidenceReader",
    "ProposalStore",
    "RecordDailyProposalOutcomes",
    "proposal_candidate_from_value",
    "proposal_identity_matches",
    "proposal_price_conflict",
    "select_adoptable",
]

#: Días de calendario que una propuesta sigue siendo adoptable. Acota la atribución
#: de un plan viejo al ciclo de hoy sin convertir la cadena en una inferencia.
PROPOSAL_MAX_BAR_LAG_DAYS = 5

#: D-1 (auditoría 2) — divergencia máxima tolerada (fracción de la entrada publicada)
#: entre la geometría del parte y el precio VIVO del tick. Por encima, el plan publicado
#: ya no es el que se ejecutaría: el stop y el objetivo se midieron contra OTRO precio,
#: el riesgo real por acción no es el presupuestado y la orden nace con el stop al otro
#: lado del mercado (cierre en el primer tick).
PROPOSAL_MAX_ENTRY_DIVERGENCE_PCT = 0.02

#: Motivos estables del contraste precio vivo ↔ geometría publicada (nunca un booleano).
PROPOSAL_PRICE_MARKET_UNKNOWN = "market_price_unknown"
PROPOSAL_PRICE_ENTRY_ABSENT = "entry_absent"
PROPOSAL_PRICE_GEOMETRY_NOT_FINITE = "geometry_not_finite"
PROPOSAL_PRICE_AT_OR_BELOW_STOP = "at_or_below_stop"
PROPOSAL_PRICE_TARGET_REACHED = "target_reached"
PROPOSAL_PRICE_DIVERGED = "diverged"

#: Tolerancia de la comparación del borde: ``abs(98/100 - 1)`` es ``0.020000000000000018``
#: en coma flotante, así que comparar con ``> 0.02`` convertiría el límite declarado
#: («veto SOLO por encima del 2 %») en un veto en el propio 2 %. El épsilon absorbe el
#: ruido de representación sin ensanchar el contrato (``1e-12`` es ~4e-11 del límite).
_DIVERGENCE_EPSILON = 1e-12

#: D-2 (auditoría 2) — motivos de degradación del parte que IMPIDEN adoptar sus propuestas.
#: Un parte con ``positions_unavailable`` no midió la cartera: la propuesta se sigue
#: persistiendo (el usuario la ve y el hueco queda declarado en ``skipped``), pero AUTO no
#: la adopta, porque el plan pudo dimensionarse contra una cartera que no existe.
PROPOSAL_BLOCKING_DEGRADATIONS: frozenset[str] = frozenset({"positions_unavailable"})
PROPOSAL_DEGRADED = "proposal_degraded"

#: Estados de atribución que la evidencia publica (nunca un booleano ambiguo).
ADOPTION_EXACT = "exact"
ADOPTION_MISMATCH = "mismatch"
ADOPTION_ABSENT_NOT_PROPOSED = "not_proposed"
ADOPTION_ABSENT_NOT_IN_UNIVERSE = "not_in_daily_universe"
ADOPTION_ABSENT_UNMEASURED = "unmeasured"
ADOPTION_UNWINDOWED = "outside_window"


class ProposalStore(Protocol):
    """Puerto mínimo de persistencia (lo implementa el repositorio SQLAlchemy).

    La firma es EXPLÍCITA (no ``**kwargs``): el productor y el job diario deben pasar
    exactamente los mismos campos que la tabla durable, y un ``**kwargs`` habría dejado
    que un typo llegara a producción sin que mypy lo viera.
    """

    async def upsert_pending(
        self,
        *,
        account_id: str,
        day: str,
        instrument_id: str,
        symbol: str | None = None,
        decision_id: str | None = None,
        signal_id: str | None = None,
        strategy_definition_id: str | None = None,
        strategy_version: int | None = None,
        preset_key: str | None = None,
        bar_date: str | None = None,
        plan: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> EstudioDailyProposal: ...

    async def mark_consumed(
        self, proposal_id: str, *, cycle_id: str
    ) -> bool: ...

    async def mark_settled(
        self, proposal_id: str, *, status: str, reason: str | None = None
    ) -> bool: ...


class ProposalEvidenceReader(Protocol):
    """Puerto de lectura para la evidencia (repositorio real o doble de test)."""

    async def pending_for(
        self,
        *,
        account_id: str,
        instruments: Iterable[str],
        max_bar_date: str,
        limit: int = 200,
    ) -> list[EstudioDailyProposal]: ...


@dataclass(frozen=True, slots=True)
class HandoffSummary:
    """Resumen del handoff para el ``result`` del job (y para la evidencia)."""

    proposed: int = 0
    skipped: tuple[dict[str, str], ...] = ()
    proposal_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": "estudio-daily-propuestas-v1",
            "proposed": self.proposed,
            # Un valor sin propuesta se declara con su motivo; nunca se omite en silencio.
            "skipped": [dict(row) for row in self.skipped],
            "proposalIds": list(self.proposal_ids),
        }


@dataclass(frozen=True, slots=True)
class _Adoption:
    proposal: EstudioDailyProposal
    bar_lag_days: int


@dataclass(frozen=True, slots=True)
class AdoptionResult:
    """Resultado puro de la selección: adoptables, caducadas y aplazadas."""

    adoptable: dict[str, _Adoption] = field(default_factory=dict)
    expired: tuple[tuple[str, str], ...] = ()
    skipped: tuple[dict[str, str], ...] = ()

    def by_instrument(self) -> dict[str, dict[str, Any]]:
        """Vista JSON-friendly para el productor (clave: instrumento y símbolo)."""
        out: dict[str, dict[str, Any]] = {}
        for adoption in self.adoptable.values():
            payload = proposal_to_handoff_payload(adoption)
            out[adoption.proposal.instrument_id] = payload
            symbol = (adoption.proposal.symbol or "").strip().upper()
            if symbol:
                out[symbol] = payload
        return out


def proposal_to_handoff_payload(adoption: _Adoption) -> dict[str, Any]:
    """Lo que el productor necesita para adoptar la propuesta, sin inventar nada."""
    proposal = adoption.proposal
    plan = dict(proposal.plan or {})
    return {
        "proposalId": proposal.id,
        "planId": proposal.decision_id,
        "signalId": proposal.signal_id,
        "instrumentId": proposal.instrument_id,
        "symbol": proposal.symbol,
        "barDate": proposal.bar_date,
        "barLagDays": adoption.bar_lag_days,
        "day": proposal.day,
        "strategyDefinitionId": proposal.strategy_definition_id,
        "strategyVersion": proposal.strategy_version,
        "presetKey": proposal.preset_key,
        "entry": plan.get("entry"),
        "structuralStop": plan.get("structuralStop"),
        "target1": plan.get("target1"),
        "target2": plan.get("target2"),
    }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _day(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _lag_days(later: str, earlier: str) -> int | None:
    try:
        return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
    except ValueError:
        return None


def _reason_codes(value: Any) -> tuple[str, ...]:
    """Motivos de degradación LIMPIOS y sin duplicados (orden de aparición)."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    seen: dict[str, None] = {}
    for item in value:
        text = _text(item)
        if text is not None:
            seen.setdefault(text, None)
    return tuple(seen)


def proposal_price_conflict(
    payload: Mapping[str, Any],
    *,
    market_price: float | None,
    direction: str = "long",
    tolerance_pct: float = PROPOSAL_MAX_ENTRY_DIVERGENCE_PCT,
) -> str | None:
    """D-1 — motivo por el que la geometría PUBLICADA no es ejecutable al precio vivo.

    ``select_adoptable`` certifica identidad y frescura, pero no que el plan siga siendo
    ejecutable con el precio de hoy: el parte propone ``entry``/``structuralStop`` y el
    productor ejecuta al precio VIVO. Con el mercado en/por debajo del stop publicado, la
    posición nace con el stop al otro lado y se cierra en el primer tick (el mismo fallo
    que el proyecto midió el 2026-10-21 en adopciones); con el mercado muy por encima de
    la entrada, el riesgo real por acción es mayor que el presupuestado. Sin este
    contraste, dimensionar y ejecutar con precios distintos es una atribución falsa.

    Es una función PURA y falsable: sin I/O, sin reloj, sin estado. Devuelve ``None``
    cuando la geometría es ejecutable (o cuando la propuesta no publica geometría: en ese
    caso el camino histórico decide) y un motivo ESTABLE en caso contrario:

    * ``market_price_unknown`` — no hay precio vivo con el que contrastar (``UNKNOWN != 0``);
    * ``entry_absent`` — publica stop/objetivo sin entrada válida, o la entrada no es finita;
    * ``geometry_not_finite`` — publica un stop/objetivo ``NaN``/``inf``: no hay nivel que
      contrastar, así que la geometría es inutilizable (no «sin dato», que sería adoptable);
    * ``at_or_below_stop`` — el mercado ya está en/por debajo del stop (largo; espejo en corto);
    * ``target_reached`` — el mercado ya alcanzó el objetivo primario;
    * ``diverged:<frac>`` — la divergencia relativa a la entrada supera ``tolerance_pct``.
    """
    entry = _number(payload.get("entry"))
    stop = _number(payload.get("structuralStop"))
    target = _number(payload.get("target1"))
    if entry is None:
        # Sin entrada publicada no hay geometría que contrastar; pero si publica stop u
        # objetivo sin entrada, el plan está incompleto y no se adopta a ciegas.
        return (
            PROPOSAL_PRICE_ENTRY_ABSENT if (stop is not None or target is not None) else None
        )
    if not math.isfinite(entry) or entry <= 0:
        return PROPOSAL_PRICE_ENTRY_ABSENT
    # Un nivel no finito no se puede contrastar: adoptarlo entregaría ``NaN``/``inf`` al
    # dimensionado (``decide_portfolio``) y el stop dejaría de ser un número. No es «sin
    # dato» (que se declara y sigue el camino histórico): es geometría INVÁLIDA.
    for level in (stop, target):
        if level is not None and not math.isfinite(level):
            return PROPOSAL_PRICE_GEOMETRY_NOT_FINITE
    price = _number(market_price)
    if price is None or not math.isfinite(price) or price <= 0:
        # Sin precio vivo no se puede afirmar que la geometría es ejecutable: fail-closed.
        return PROPOSAL_PRICE_MARKET_UNKNOWN
    if stop is not None:
        if (direction == "short" and price >= stop) or (
            direction != "short" and price <= stop
        ):
            return PROPOSAL_PRICE_AT_OR_BELOW_STOP
    if target is not None:
        if (direction == "short" and price <= target) or (
            direction != "short" and price >= target
        ):
            return PROPOSAL_PRICE_TARGET_REACHED
    divergence = abs(price / entry - 1.0)
    tolerance = max(0.0, float(tolerance_pct))
    # Borde INCLUSIVO: exactamente el 2 % no veta (ver ``_DIVERGENCE_EPSILON``).
    if divergence - tolerance > _DIVERGENCE_EPSILON:
        return f"{PROPOSAL_PRICE_DIVERGED}:{divergence:.4f}"
    return None


def proposal_candidate_from_value(
    value: Mapping[str, Any],
    *,
    degraded_reasons: Sequence[str] = (),
) -> tuple[dict[str, Any] | None, str | None]:
    """Extrae la propuesta de UN valor del parte diario.

    Devuelve ``(candidato, motivo_de_omision)``. Solo se propone lo que el parte
    declara como ``ok`` con un plan ``TRIGGERED``: un valor sin señal, sin plan o con
    error NO genera propuesta (el hueco se declara, no se rellena).

    D-2 (auditoría 2): ``degraded_reasons`` son los motivos por los que el PARTE quedó
    ``partial``. Viajan DENTRO del plan persistido (``plan.degradedReasons``) para que la
    propuesta no pierda la marca al cruzar la frontera: con la marca, AUTO puede declarar
    ``proposal_degraded:<motivo>`` en vez de adoptar un plan medido contra una cartera que
    no se pudo leer. La propuesta se sigue persistiendo (el usuario la ve y el hueco no se
    rellena en silencio).
    """
    status = _text(value.get("status"))
    if status != "ok":
        return None, f"value_status:{status or 'unknown'}"
    plan = value.get("plan")
    if not isinstance(plan, Mapping):
        return None, "plan_absent"
    plan_status = _text(plan.get("status"))
    if plan_status != "TRIGGERED":
        return None, f"plan_status:{plan_status or 'unknown'}"
    strategy = value.get("strategy")
    strategy = strategy if isinstance(strategy, Mapping) else {}
    decision_id = _text(plan.get("decisionId")) or _text(strategy.get("planId"))
    if decision_id is None:
        # Sin identidad de plan no hay atribución exacta posible: se declara y se omite.
        return None, "plan_without_identity"
    signal_id = _text(strategy.get("signalId"))
    if signal_id is None:
        return None, "signal_without_identity"
    instrument_id = _text(value.get("instrumentId"))
    if instrument_id is None:
        return None, "instrument_absent"
    version = strategy.get("strategyVersion")
    try:
        version_int = int(version) if version is not None else None
    except (TypeError, ValueError):
        version_int = None
    candidate_plan: dict[str, Any] = {
        key: plan.get(key)
        for key in (
            "decisionId",
            "status",
            "direction",
            "entry",
            "structuralStop",
            "target1",
            "target2",
            "riskAmount",
            "expectedRR",
        )
        if plan.get(key) is not None
    }
    # D-2 — la marca de parte PARCIAL viaja con la propuesta: sin ella la cadena no puede
    # distinguir un plan medido con la cartera completa de uno medido sin cartera.
    degradations = _reason_codes(degraded_reasons)
    if degradations:
        candidate_plan["degradedReasons"] = list(degradations)
    return (
        {
            "instrument_id": instrument_id,
            "symbol": _text(value.get("symbol")),
            "decision_id": decision_id,
            "signal_id": signal_id,
            "strategy_definition_id": _text(strategy.get("strategyDefinitionId")),
            "strategy_version": version_int,
            "preset_key": _text(strategy.get("presetKey")),
            "bar_date": _day(value.get("asOfBarDate")),
            "plan": candidate_plan,
        },
        None,
    )


class PersistEstudioDailyProposals:
    """Persiste las propuestas del parte diario (idempotente, sin backfill)."""

    def __init__(self, store: ProposalStore) -> None:
        self._store = store

    async def execute(
        self, *, account_id: str, report: Mapping[str, Any]
    ) -> HandoffSummary:
        day = _day(report.get("asOf")) or _text(report.get("asOf")) or ""
        if not account_id or not day:
            return HandoffSummary(
                skipped=({"instrumentId": "", "reason": "missing_account_or_day"},)
            )
        values = report.get("values")
        rows = values if isinstance(values, Sequence) else []
        # D-2 — el parte declara POR QUÉ quedó parcial; la marca viaja a cada propuesta.
        degradations = _reason_codes(
            report.get("degradedReasons") or report.get("degraded_reasons")
        )
        proposed = 0
        skipped: list[dict[str, str]] = []
        ids: list[str] = []
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            candidate, reason = proposal_candidate_from_value(
                raw, degraded_reasons=degradations
            )
            instrument = _text(raw.get("instrumentId")) or ""
            if candidate is None:
                skipped.append(
                    {"instrumentId": instrument, "reason": reason or "unknown"}
                )
                continue
            record = await self._store.upsert_pending(
                account_id=account_id, day=day, **candidate
            )
            proposed += 1
            ids.append(record.id)
        return HandoffSummary(
            proposed=proposed,
            skipped=tuple(skipped),
            proposal_ids=tuple(ids),
        )


def select_adoptable(
    proposals: Sequence[EstudioDailyProposal],
    *,
    instruments: Iterable[str],
    decision_bar_day: str,
    max_lag_days: int = PROPOSAL_MAX_BAR_LAG_DAYS,
) -> AdoptionResult:
    """Selecciona, por instrumento, la propuesta que el productor puede adoptar.

    Reglas (puras y falsables):

    * solo propuestas PENDIENTES con ``decision_id`` y ``signal_id``;
    * una propuesta de un parte DEGRADADO (motivo bloqueante en ``plan.degradedReasons``)
      no se adopta: se declara en ``skipped`` como ``proposal_degraded:<motivo>``;
    * la vela de la propuesta no puede ser POSTERIOR a la frontera de decisión (lookahead);
    * el retraso de vela se declara (``barLagDays``) y por encima de ``max_lag_days``
      la propuesta CADUCA con motivo (no se atribuye un plan viejo a un ciclo nuevo);
    * se elige la vela más reciente por instrumento (el repositorio ya ordena).
    """
    wanted: set[str] = set()
    for item in instruments:
        text = _text(item)
        if text is not None:
            wanted.add(text.upper())
    limit = date.fromisoformat(decision_bar_day) if _valid_day(decision_bar_day) else None

    chosen: dict[str, _Adoption] = {}
    expired: list[tuple[str, str]] = []
    skipped: list[dict[str, str]] = []
    for proposal in proposals:
        keys = {
            key
            for key in (
                (proposal.instrument_id or "").strip().upper(),
                (proposal.symbol or "").strip().upper(),
            )
            if key
        }
        if not keys or not (keys & wanted):
            continue
        if not proposal.is_pending:
            continue
        if proposal.decision_id is None or proposal.signal_id is None:
            skipped.append(
                {
                    "instrumentId": proposal.instrument_id,
                    "reason": "proposal_without_identity",
                }
            )
            continue
        # D-2 — un parte degradado no midió lo que dice medir: la propuesta se declara con
        # su motivo (``proposal_degraded:<motivo>``) y NO se adopta. Sin este contraste,
        # AUTO adoptaba tal cual un plan dimensionado contra una cartera ilegible.
        blocking = sorted(
            PROPOSAL_BLOCKING_DEGRADATIONS.intersection(proposal.degraded_reasons)
        )
        if blocking:
            skipped.append(
                {
                    "instrumentId": proposal.instrument_id,
                    "reason": f"{PROPOSAL_DEGRADED}:{blocking[0]}",
                }
            )
            continue
        bar_date = proposal.bar_date
        if bar_date is None or not _valid_day(bar_date):
            skipped.append(
                {
                    "instrumentId": proposal.instrument_id,
                    "reason": "proposal_without_bar_date",
                }
            )
            continue
        lag = _lag_days(decision_bar_day, bar_date) if limit is not None else None
        if lag is None:
            skipped.append(
                {
                    "instrumentId": proposal.instrument_id,
                    "reason": "decision_bar_day_unknown",
                }
            )
            continue
        if lag < 0:
            # La vela de la propuesta es posterior a la frontera: no se adelanta.
            skipped.append(
                {
                    "instrumentId": proposal.instrument_id,
                    "reason": f"proposal_bar_in_future:{bar_date}",
                }
            )
            continue
        if lag > max(0, int(max_lag_days)):
            expired.append(
                (
                    proposal.id,
                    f"proposal_stale:{bar_date} ({lag}d > {int(max_lag_days)}d)",
                )
            )
            continue
        # Un instrumento solo adopta UNA propuesta: la primera (más reciente) manda y
        # las claves alternativas (id/símbolo) apuntan a la misma.
        already = any(
            existing.proposal.id == proposal.id for existing in chosen.values()
        )
        if already:
            continue
        for key in keys:
            if key in wanted and key not in chosen:
                chosen[key] = _Adoption(proposal=proposal, bar_lag_days=lag)
    return AdoptionResult(
        adoptable=chosen, expired=tuple(expired), skipped=tuple(skipped)
    )


def _valid_day(value: str) -> bool:
    try:
        date.fromisoformat(value[:10])
    except (TypeError, ValueError):
        return False
    return True


class LoadAdoptableDailyProposals:
    """Caso de uso del productor: props adoptables para su frontera de decisión."""

    def __init__(self, reader: ProposalEvidenceReader) -> None:
        self._reader = reader

    async def execute(
        self,
        *,
        account_id: str,
        instruments: Iterable[str],
        decision_bar_day: str,
        max_lag_days: int = PROPOSAL_MAX_BAR_LAG_DAYS,
    ) -> AdoptionResult:
        if not account_id or not decision_bar_day:
            return AdoptionResult()
        proposals = await self._reader.pending_for(
            account_id=account_id,
            instruments=instruments,
            max_bar_date=decision_bar_day,
        )
        return select_adoptable(
            proposals,
            instruments=instruments,
            decision_bar_day=decision_bar_day,
            max_lag_days=max_lag_days,
        )


class RecordDailyProposalOutcomes:
    """Cierra el desenlace de las propuestas que el productor evaluó.

    ``approved`` con ciclo ⇒ ``consumed`` + ``consumed_cycle_id``. Sin aprobación ⇒
    ``rejected`` con el motivo del motor. Una propuesta que el motor no evaluó no se
    toca (sigue pendiente y la cadena la declara).
    """

    def __init__(self, store: ProposalStore) -> None:
        self._store = store

    async def execute(
        self, outcomes: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        consumed = 0
        rejected = 0
        expired = 0
        now = datetime.now(UTC)
        for row in outcomes:
            proposal_id = _text(row.get("proposalId"))
            if proposal_id is None:
                continue
            status = _text(row.get("status")) or PROPOSAL_STATUS_REJECTED
            if status == "consumed":
                cycle_id = _text(row.get("cycleId"))
                if cycle_id is None:
                    # Sin ciclo durable no hay consumo: se declara el motivo.
                    await self._store.mark_settled(
                        proposal_id,
                        status=PROPOSAL_STATUS_REJECTED,
                        reason="consumed_without_cycle",
                    )
                    rejected += 1
                    continue
                if await self._store.mark_consumed(proposal_id, cycle_id=cycle_id):
                    consumed += 1
                continue
            if status == PROPOSAL_STATUS_EXPIRED:
                if await self._store.mark_settled(
                    proposal_id,
                    status=PROPOSAL_STATUS_EXPIRED,
                    reason=_text(row.get("reason")),
                ):
                    expired += 1
                continue
            reason = _text(row.get("reason")) or "engine_rejected"
            if await self._store.mark_settled(
                proposal_id, status=PROPOSAL_STATUS_REJECTED, reason=reason
            ):
                rejected += 1
        return {
            "consumed": consumed,
            "rejected": rejected,
            "expired": expired,
            "at": now.isoformat(),
        }


def proposal_identity_matches(
    *,
    proposal_plan_id: str | None,
    proposal_signal_id: str | None,
    cycle_plan_id: str | None,
    cycle_signal_id: str | None,
) -> str:
    """Estado de atribución por IGUALDAD de identidades durables.

    No compara el símbolo ni el ranking: eso es una inferencia. Si a alguna de las dos
    partes le falta identidad, el estado es ``unmeasured`` (hueco declarado), nunca
    ``exact`` ni ``mismatch``.
    """
    if not _text(proposal_plan_id) or not _text(cycle_plan_id):
        return ADOPTION_ABSENT_UNMEASURED
    if not _text(proposal_signal_id) or not _text(cycle_signal_id):
        return ADOPTION_ABSENT_UNMEASURED
    if (
        _text(proposal_plan_id) == _text(cycle_plan_id)
        and _text(proposal_signal_id) == _text(cycle_signal_id)
    ):
        return ADOPTION_EXACT
    return ADOPTION_MISMATCH
