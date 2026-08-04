"""A0 — telemetría de acierto del dictamen diario (proxy 5d).

Mide precisión BUY-alarma vs retorno forward D1 (+5 barras), reutilizando
criterio Outcomes (banda neutra 0.5%). No flip Camino D.

@see docs/engineering/camino-d-auto-thaw-checklist-2026-08-04.md P1–P4
@see docs/engineering/audit-ext-institutional-pre-auto-triage-2026-08-04.md §9
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from bolsa_analytics.cognitive.decision_outcome import (
    NEUTRAL_BAND_PCT,
    OUTCOME_CRITERIA_VERSION,
    verdict_from_return,
)
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.alerts.estudio_opinion_email import map_opinion_to_channel

TELEMETRY_SCHEMA = "opinion_telemetry_v0"
FORWARD_BARS = 5
# Move “relevante” para recall proxy: |return| ≥ este umbral en 5d.
RECALL_MOVE_PCT = 2.0


class _OpinionLike(Protocol):
    instrument_id: str
    as_of_bar_date: date
    stance: str
    dictamen_stars: int


@dataclass(frozen=True, slots=True)
class OpinionTelemetryV0:
    schema_version: str
    as_of: str
    lookback_days: int
    days_with_opinions: int
    opinion_rows: int
    alarma_count: int
    alarma_buy_count: int
    mature_buy_sample: int
    buy_precision_5d: float | None
    buy_hits: int
    buy_misses: int
    buy_neutrals: int
    buy_recall_5d: float | None
    recall_move_sample: int
    recall_caught: int
    criteria_version: str
    forward_bars: int
    neutral_band_pct: float
    caveats: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "asOf": self.as_of,
            "lookbackDays": self.lookback_days,
            "daysWithOpinions": self.days_with_opinions,
            "opinionRows": self.opinion_rows,
            "alarmaCount": self.alarma_count,
            "alarmaBuyCount": self.alarma_buy_count,
            "matureBuySample": self.mature_buy_sample,
            "buyPrecision5d": self.buy_precision_5d,
            "buyHits": self.buy_hits,
            "buyMisses": self.buy_misses,
            "buyNeutrals": self.buy_neutrals,
            "buyRecall5d": self.buy_recall_5d,
            "recallMoveSample": self.recall_move_sample,
            "recallCaught": self.recall_caught,
            "criteriaVersion": self.criteria_version,
            "forwardBars": self.forward_bars,
            "neutralBandPct": self.neutral_band_pct,
            "caveats": list(self.caveats),
        }


def _bar_date(ts: str) -> date:
    return date.fromisoformat(ts[:10])


def forward_return_pct(
    closes_by_date: dict[date, float],
    as_of: date,
    *,
    forward_bars: int = FORWARD_BARS,
) -> float | None:
    """Retorno % desde cierre asOf hasta la N-ésima barra D1 posterior disponible."""
    if as_of not in closes_by_date:
        return None
    later = sorted(d for d in closes_by_date if d > as_of)
    if len(later) < forward_bars:
        return None
    px0 = closes_by_date[as_of]
    px1 = closes_by_date[later[forward_bars - 1]]
    if px0 == 0:
        return None
    return ((px1 - px0) / px0) * 100.0


def score_buy_alarma(
    return_pct: float | None,
) -> tuple[str, bool | None]:
    """verdict / direction_hit usando mismo criterio Outcomes."""
    return verdict_from_return(action="buy", return_pct=return_pct)


@dataclass
class DailyOpinionTelemetryService:
    opinions: Any
    ohlcv: Any

    async def compute(
        self,
        *,
        lookback_days: int = 90,
        instrument_ids: list[str] | None = None,
        as_of: date | None = None,
    ) -> OpinionTelemetryV0:
        lookback_days = max(7, min(int(lookback_days), 366))
        end = as_of or datetime.now(UTC).date()
        start = end - timedelta(days=lookback_days - 1)
        rows: list[Any] = await self.opinions.list_range(
            date_from=start,
            date_to=end,
            instrument_ids=instrument_ids,
            source=None,
            limit=10_000,
        )

        days = {r.as_of_bar_date for r in rows}
        alarma_rows = [
            r
            for r in rows
            if map_opinion_to_channel(
                stance=str(r.stance),
                dictamen_stars=int(r.dictamen_stars),
            )
            == "alarma"
        ]
        alarma_buy = [r for r in alarma_rows if str(r.stance) == "buy"]

        # Cache closes por instrumento (ventana lookback + forward slack).
        close_cache: dict[str, dict[date, float]] = {}
        hits = misses = neutrals = 0
        mature = 0
        for r in alarma_buy:
            closes = await self._closes(r.instrument_id, start, end, close_cache)
            ret = forward_return_pct(closes, r.as_of_bar_date)
            if ret is None:
                continue
            mature += 1
            verdict, _ = score_buy_alarma(ret)
            if verdict == "hit":
                hits += 1
            elif verdict == "miss":
                misses += 1
            elif verdict == "neutral":
                neutrals += 1

        decided = hits + misses
        precision = (hits / decided) if decided > 0 else None

        # Recall proxy: días/instrumentos con move alcista ≥ RECALL_MOVE_PCT
        # cubiertos por alarma buy ese asOf (misma muestra madura).
        recall_move = 0
        recall_caught = 0
        # Solo instrumentos en filas (o filtro).
        instruments = sorted({r.instrument_id for r in rows})
        alarma_buy_keys = {(r.instrument_id, r.as_of_bar_date) for r in alarma_buy}
        for iid in instruments:
            closes = await self._closes(iid, start, end, close_cache)
            for d in sorted(closes):
                if d < start or d > end:
                    continue
                ret = forward_return_pct(closes, d)
                if ret is None or ret < RECALL_MOVE_PCT:
                    continue
                recall_move += 1
                if (iid, d) in alarma_buy_keys:
                    recall_caught += 1
        recall = (recall_caught / recall_move) if recall_move > 0 else None

        caveats = [
            f"Precisión BUY-alarma: hit si return_5d > +{NEUTRAL_BAND_PCT}% "
            f"(criterio Outcomes {OUTCOME_CRITERIA_VERSION}).",
            f"Recall proxy: fracción de moves ≥+{RECALL_MOVE_PCT}%/5d con alarma buy ese día.",
            "Muestra madura requiere ≥5 barras D1 posteriores al asOf.",
            "No es luz verde Camino D; umbrales thaw P3/P4 aparte.",
        ]
        if mature < 10:
            caveats.append("Muestra madura <10: precisión orientativa.")
        if not rows:
            caveats.append("Sin dictámenes en el lookback.")

        return OpinionTelemetryV0(
            schema_version=TELEMETRY_SCHEMA,
            as_of=end.isoformat(),
            lookback_days=lookback_days,
            days_with_opinions=len(days),
            opinion_rows=len(rows),
            alarma_count=len(alarma_rows),
            alarma_buy_count=len(alarma_buy),
            mature_buy_sample=mature,
            buy_precision_5d=round(precision, 4) if precision is not None else None,
            buy_hits=hits,
            buy_misses=misses,
            buy_neutrals=neutrals,
            buy_recall_5d=round(recall, 4) if recall is not None else None,
            recall_move_sample=recall_move,
            recall_caught=recall_caught,
            criteria_version=OUTCOME_CRITERIA_VERSION,
            forward_bars=FORWARD_BARS,
            neutral_band_pct=NEUTRAL_BAND_PCT,
            caveats=caveats,
        )

    async def _closes(
        self,
        instrument_id: str,
        start: date,
        end: date,
        cache: dict[str, dict[date, float]],
    ) -> dict[date, float]:
        if instrument_id in cache:
            return cache[instrument_id]
        # Slack calendario para acumular 5 barras trading tras el fin de lookback.
        date_to = (end + timedelta(days=21)).isoformat()
        bars = await self.ohlcv.get_bars(
            instrument_id,
            timeframe=TimeFrame.D1,
            limit=None,
            date_from=start.isoformat(),
            date_to=date_to,
        )
        mapped = {_bar_date(b.timestamp): float(b.close) for b in bars}
        cache[instrument_id] = mapped
        return mapped
