"""DailyOpinionService — dictamen on-demand + caché por cuenta (O3-C / ADR-022).

La postura la decide el SERVIDOR: ``position_open`` sale de las posiciones de la cuenta y
los scores de los chips composite/fundamentales. Los ``hints`` que llegan del navegador ya
no se aceptan (la ruta los ignora); los hints internos (parte diario ESTUDIO, ``eod_batch``)
siguen siendo la vía de los jobs de servidor que ya midieron.

La caché es por ``(instrumento, día, fuente, cuenta)``: dos cuentas no comparten postura. Un
dictamen calculado con la cartera NO medida (``position_open is None``) no se persiste: se
devuelve transitorio y se reintenta en la siguiente llamada.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from bolsa_application.daily_opinion_hints import (
    OpenPositionMeasurement,
    OpinionHint,
    measure_open_positions,
    measure_opinion_hints,
)
from bolsa_application.daily_opinion_stance import (
    ENGINE_VERSION,
    StanceInput,
    compute_stance,
)
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    InstrumentDailyOpinionRecord,
    SqlAlchemyInstrumentDailyOpinionRepository,
    account_scope_for,
    make_idempotency_key,
)
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.database.repositories.instrument_strategy_top_repository import (
    SqlAlchemyInstrumentStrategyTopRepository,
)
from bolsa_infrastructure.database.repositories.ohlcv_repository import (
    SqlAlchemyOhlcvRepository,
)

__all__ = ["DailyOpinionService", "OpinionHint"]

logger = logging.getLogger(__name__)

SOURCE_ON_DEMAND = "on_demand"
SOURCE_EOD_BATCH = "eod_batch"
EOD_STALE_MAX_DAYS = 5


def _parse_bar_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    # YYYY-MM-DD or ISO datetime
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _top_slot1_stars(slots: list[dict[str, Any]]) -> float | None:
    if not slots:
        return None
    ranked = sorted(
        slots,
        key=lambda s: int(s.get("rank") or 99),
    )
    stars = ranked[0].get("stars")
    if stars is None:
        return None
    try:
        return float(stars)
    except (TypeError, ValueError):
        return None


class DailyOpinionService:
    def __init__(
        self,
        opinion_repo: SqlAlchemyInstrumentDailyOpinionRepository,
        top_repo: SqlAlchemyInstrumentStrategyTopRepository,
        ohlcv_repo: SqlAlchemyOhlcvRepository,
        instrument_repo: SqlAlchemyInstrumentRepository | None = None,
        *,
        composite: Any | None = None,
        fundamentals: Any | None = None,
        positions: Any | None = None,
    ) -> None:
        self._opinions = opinion_repo
        self._tops = top_repo
        self._ohlcv = ohlcv_repo
        self._instruments = instrument_repo
        # Puertos de MEDICIÓN server-side (dictamen on-demand). Sin ellos no hay postura
        # medible: el dictamen sale ``position_unmeasured`` y no se cachea.
        self._composite = composite
        self._fundamentals = fundamentals
        self._positions = positions

    async def _resolve_miss_hints(
        self,
        instrument_ids: list[str],
        *,
        account_id: str | None,
        position_measurement: OpenPositionMeasurement,
        as_of: date,
    ) -> dict[str, OpinionHint]:
        """Mide los chips (composite/FA) SOLO de los ids que no se sirven de caché.

        La cartera ya se midió una vez fuera de aquí: no se vuelve a leer. Los hints
        internos (jobs de servidor) no pasan por esta función.
        """
        if not instrument_ids:
            return {}
        measurement = await measure_opinion_hints(
            instrument_ids,
            account_id=account_id,
            composite=self._composite,
            fundamentals=self._fundamentals,
            position_measurement=position_measurement,
            as_of=as_of.isoformat(),
        )
        if measurement.notes:
            logger.info(
                "daily_opinion_service: hints account=%s notes=%s",
                account_id,
                measurement.notes,
            )
        return measurement.by_id

    async def query(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force_refresh: bool = False,
        hints: list[OpinionHint] | None = None,
        timeframe: str = "1d",
        now: datetime | None = None,
        source: str = SOURCE_ON_DEMAND,
    ) -> list[InstrumentDailyOpinionRecord]:
        as_of = as_of_bar_date or datetime.now(UTC).date()
        ids = list(dict.fromkeys(i for i in instrument_ids if i))
        if not ids:
            return []
        # Robustez FK: descartar ids que no existen en el catálogo para que un único
        # instrumento huérfano no derribe todo el batch con un 500 (FK de
        # instrument_daily_opinions.instrument_id). Sin repo (p.ej. tests que no lo
        # inyectan) se preserva el comportamiento anterior.
        if self._instruments is not None:
            existing = await self._instruments.list_existing_ids(ids)
            known = [i for i in ids if i in existing]
        else:
            known = list(ids)
        if not known:
            return []
        ids = known
        src = source if source in (SOURCE_ON_DEMAND, SOURCE_EOD_BATCH, "manual") else SOURCE_ON_DEMAND
        scope = account_scope_for(account_id)

        # Hints internos (jobs de servidor): ya midieron posición y chips.
        internal_by_id = {
            h.instrument_id: h
            for h in (hints or [])
            if str(h.instrument_id or "").strip()
        }

        cached: dict[str, InstrumentDailyOpinionRecord] = {}
        if not force_refresh:
            for row in await self._opinions.list_for_instruments(
                ids, as_of, src, account_scope=scope
            ):
                cached[row.instrument_id] = row

        # H-2: la cartera se mide UNA vez y ANTES de los chips. Es lo que decide qué
        # filas de la caché siguen siendo verificables. Los ids con hint interno no la
        # necesitan: su posición ya viene medida por el job.
        needs_position = [i for i in ids if i not in internal_by_id]
        position_measurement = (
            await measure_open_positions(self._positions, account_id)
            if needs_position
            else OpenPositionMeasurement()
        )

        # La caché solo se sirve si la posición sigue siendo la MISMA medición. Con la
        # cartera no medida no se sirve: la postura guardada no es verificable.
        served: dict[str, InstrumentDailyOpinionRecord] = {}
        pending: list[str] = []
        for instrument_id in ids:
            row_cached = cached.get(instrument_id)
            if force_refresh or row_cached is None:
                pending.append(instrument_id)
                continue
            internal = internal_by_id.get(instrument_id)
            current = (
                internal.position_open
                if internal is not None
                else position_measurement.position_open(instrument_id)
            )
            if current is not None and row_cached.position_open == current:
                served[instrument_id] = row_cached
            else:
                pending.append(instrument_id)

        # Chips SOLO para los ids que no se sirven de caché ni traen hint interno.
        miss_ids = [i for i in pending if i not in internal_by_id]
        miss_hints = await self._resolve_miss_hints(
            miss_ids,
            account_id=account_id,
            position_measurement=position_measurement,
            as_of=as_of,
        )

        out: list[InstrumentDailyOpinionRecord] = []
        for instrument_id in ids:
            row_cached = served.get(instrument_id)
            if row_cached is not None:
                out.append(row_cached)
                continue
            hint = internal_by_id.get(instrument_id) or miss_hints.get(instrument_id)
            if hint is None:
                hint = OpinionHint(
                    instrument_id=instrument_id,
                    position_open=position_measurement.position_open(instrument_id),
                )
            row = await self._compute_and_upsert(
                instrument_id=instrument_id,
                as_of=as_of,
                account_id=account_id,
                hint=hint,
                timeframe=timeframe,
                now=now,
                source=src,
                persist=hint.position_open is not None,
            )
            out.append(row)
        return out

    async def run_eod_batch(
        self,
        *,
        instrument_ids: list[str],
        as_of_bar_date: date | None = None,
        account_id: str | None = None,
        force: bool = True,
        hints: list[OpinionHint] | None = None,
    ) -> list[InstrumentDailyOpinionRecord]:
        """Batch post-cierre (source=eod_batch). Siempre force_refresh salvo force=False.

        ``hints`` permite que el job de servidor aporte los chips (IO/FA/TA) y las
        posiciones de la cuenta ya resueltos; si se omiten, el servicio los mide con sus
        propios puertos (nunca se fabrica ``hasEodBar``: se valida barra a barra).
        """
        return await self.query(
            instrument_ids=instrument_ids,
            as_of_bar_date=as_of_bar_date,
            account_id=account_id,
            force_refresh=force,
            hints=hints,
            source=SOURCE_EOD_BATCH,
        )

    async def history(
        self,
        instrument_id: str,
        *,
        days: int = 30,
        ensure_days: int = 0,
        account_id: str | None = None,
        hint: OpinionHint | None = None,
        timeframe: str = "1d",
    ) -> list[InstrumentDailyOpinionRecord]:
        """Historial de dictámenes; opcionalmente rellena días laborables faltantes."""
        days = max(1, min(int(days), 90))
        ensure_days = max(0, min(int(ensure_days), 21))
        as_of_end = datetime.now(UTC).date()
        date_from = as_of_end - timedelta(days=days - 1)
        scope = account_scope_for(account_id)

        if ensure_days > 0:
            base_hint = hint
            if base_hint is None:
                measurement = await measure_opinion_hints(
                    [instrument_id],
                    account_id=account_id,
                    composite=self._composite,
                    fundamentals=self._fundamentals,
                    positions=self._positions,
                    as_of=as_of_end.isoformat(),
                )
                base_hint = measurement.hint_for(instrument_id)
            # No forzar has_eod del cliente: cada día se valida por barra ≤ asOf.
            day_hint = OpinionHint(
                instrument_id=instrument_id,
                io_score=base_hint.io_score,
                fa_score=base_hint.fa_score,
                ta_score=base_hint.ta_score,
                distress=base_hint.distress,
                position_open=base_hint.position_open,
                allow_trading=base_hint.allow_trading,
                has_eod_bar=None,
            )
            # Sin cartera medida no se inventa historial: no se persiste el día.
            if day_hint.position_open is not None:
                ensure_from = as_of_end - timedelta(days=ensure_days - 1)
                existing = {
                    r.as_of_bar_date
                    for r in await self._opinions.list_history(
                        instrument_id,
                        date_from=ensure_from,
                        date_to=as_of_end,
                        source=SOURCE_ON_DEMAND,
                        account_scope=scope,
                    )
                }
                cursor = ensure_from
                while cursor <= as_of_end:
                    if cursor.weekday() < 5 and cursor not in existing:
                        stance_now = datetime(
                            cursor.year, cursor.month, cursor.day, 18, 0, tzinfo=UTC
                        )
                        await self._compute_and_upsert(
                            instrument_id=instrument_id,
                            as_of=cursor,
                            account_id=account_id,
                            hint=day_hint,
                            timeframe=timeframe,
                            now=stance_now,
                            source=SOURCE_ON_DEMAND,
                            persist=True,
                        )
                    cursor += timedelta(days=1)

        return await self._opinions.list_history(
            instrument_id,
            date_from=date_from,
            date_to=as_of_end,
            source=SOURCE_ON_DEMAND,
            account_scope=scope,
        )

    async def _resolve_has_eod(
        self,
        instrument_id: str,
        as_of: date,
        hint: OpinionHint,
    ) -> bool:
        if hint.has_eod_bar is not None:
            return bool(hint.has_eod_bar)
        bars = await self._ohlcv.get_bars(
            instrument_id,
            timeframe=TimeFrame.D1,
            limit=1,
            date_to=as_of.isoformat(),
        )
        if not bars:
            return False
        bar_date = _parse_bar_date(bars[-1].timestamp)
        if bar_date is None:
            return False
        return (as_of - bar_date) <= timedelta(days=EOD_STALE_MAX_DAYS)

    async def _compute_and_upsert(
        self,
        *,
        instrument_id: str,
        as_of: date,
        account_id: str | None,
        hint: OpinionHint,
        timeframe: str,
        now: datetime | None,
        source: str = SOURCE_ON_DEMAND,
        persist: bool = True,
    ) -> InstrumentDailyOpinionRecord:
        computed_at = datetime.now(UTC)
        stance_now = now or computed_at
        src = source if source in (SOURCE_ON_DEMAND, SOURCE_EOD_BATCH, "manual") else SOURCE_ON_DEMAND
        has_eod = await self._resolve_has_eod(instrument_id, as_of, hint)
        top = await self._tops.get(instrument_id, timeframe)
        has_top = top is not None and bool(top.slots)
        top_stars = _top_slot1_stars(top.slots) if top else None
        strategy_stars_int = int(round(top_stars)) if top_stars is not None else None

        result = compute_stance(
            StanceInput(
                has_eod_bar=has_eod,
                allow_trading=bool(hint.allow_trading),
                has_top=has_top,
                top_updated_at=top.updated_at if top else None,
                top_stars=top_stars,
                io_score=hint.io_score,
                fa_distress=bool(hint.distress),
                # H-145-1: el tri-estado viaja TAL CUAL. Convertirlo con ``bool()`` aquí
                # reintroducía el defecto («no medido» → «sin posición») justo antes del motor.
                position_open=hint.position_open,
            ),
            now=stance_now,
        )

        # Invariante: sell/reduce solo con largo MEDIDO (defensa en profundidad)
        stance = result.stance
        if stance in ("sell_exit", "reduce") and hint.position_open is not True:
            stance = "no_trade"
            reasons = list(result.reasons) + ["position_closed"]
            gate = result.gate_status
            stars = result.dictamen_stars
        else:
            reasons = list(result.reasons)
            gate = result.gate_status
            stars = result.dictamen_stars

        # FA distress: techo ★ ≤3 y nunca buy (engine ya cubre; refuerzo)
        if hint.distress:
            stars = min(stars, 3)
            if stance == "buy":
                stance = (
                    "no_trade" if hint.position_open is not True else "reduce"
                )
                if "fa_distress" not in reasons:
                    reasons.append("fa_distress")

        scope = account_scope_for(account_id)
        payload = {
            "instrument_id": instrument_id,
            "account_id": account_id,
            "account_scope": scope,
            "as_of_bar_date": as_of,
            "stance": stance,
            "dictamen_stars": stars,
            "strategy_stars": strategy_stars_int,
            "io_score": hint.io_score,
            "fa_score": hint.fa_score,
            "ta_score": hint.ta_score,
            "distress": bool(hint.distress),
            "position_open": hint.position_open,
            "reasons": reasons,
            "gate_status": gate,
            "top_id": top.id if top else None,
            "top_version": top.version if top else None,
            "source": src,
            "engine_version": ENGINE_VERSION,
            "idempotency_key": make_idempotency_key(instrument_id, as_of, src, scope),
            "computed_at": computed_at,
        }
        if persist:
            return await self._opinions.upsert(payload)
        # Dictamen NO verificable (cartera no medida): se devuelve sin escribir la caché.
        return InstrumentDailyOpinionRecord(
            id=f"ido_tmp_{uuid4().hex}",
            instrument_id=instrument_id,
            account_id=account_id,
            as_of_bar_date=as_of,
            stance=stance,
            dictamen_stars=int(stars),
            strategy_stars=strategy_stars_int,
            io_score=hint.io_score,
            fa_score=hint.fa_score,
            ta_score=hint.ta_score,
            distress=bool(hint.distress),
            reasons=list(reasons),
            gate_status=gate,
            top_id=top.id if top else None,
            top_version=top.version if top else None,
            source=src,
            engine_version=ENGINE_VERSION,
            idempotency_key=str(payload["idempotency_key"]),
            computed_at=computed_at,
            created_at=computed_at,
            updated_at=computed_at,
            position_open=hint.position_open,
        )
