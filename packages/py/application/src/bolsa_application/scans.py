from dataclasses import dataclass
from typing import Any, Literal

from bolsa_analytics.research.manifest import strategy_definition_from_preset
from bolsa_analytics.research.scan_manifest import (
    build_instrument_snapshot_meta,
    hash_fundamentals_batch,
    hash_gate_config,
)
from bolsa_analytics.signals.fundamental_gate import (
    definition_has_fundamental_gate,
    fundamental_gate_max_age_days,
    passes_fundamental_gate,
)
from bolsa_analytics.features.online_adapter import OnlineFeatureAdapter
from bolsa_analytics.features.compute_bridge import materialize_feature_snapshot
from bolsa_analytics.signals.feature_cache import (
    FeatureCache,
    FeatureCacheKey,
    get_or_build_preset_features,
    hash_indicator_specs,
)
from bolsa_analytics.signals.preset_rules import definition_has_rules, enrich_definition_with_preset_rules
from bolsa_analytics.signals.hybrid_scan import (
    DataQualityScanContext,
    build_indicator_context_for_definition,
    evaluate_hybrid_candidate,
    hybrid_scorer_version,
    is_hybrid_definition,
)
from bolsa_analytics.signals.preset_catalog import is_valid_preset_key
from bolsa_analytics.signals.rules_engine import build_indicator_context
from bolsa_analytics.indicators.compute import OhlcvBar
from bolsa_analytics.signals.strategy import SignalEventV1, StrategyBarInput, evaluate_strategy_last_bar
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.ohlcv_repository import OhlcvRepository
from bolsa_domain.repositories.strategy_definition_repository import StrategyDefinitionRepository
from bolsa_domain.value_objects.timeframe import TimeFrame
from bolsa_infrastructure.database.repositories.list_repository import SqlAlchemyListRepository
from bolsa_infrastructure.ids import new_id

from bolsa_application.scan_universe import resolve_scan_universe_instrument_ids
from bolsa_application.refresh_instrument_fundamentals import RefreshFundamentalsBatch
from bolsa_application.events.platform_event_bus import PlatformEventBus
from bolsa_application.events.payloads import scan_completed_payload
from bolsa_domain.platform_kernel import MIN_SCAN_BARS, validate_kernel_timeframe
from bolsa_market.market_calendar import expected_last_daily_bar


@dataclass(frozen=True, slots=True)
class ScanSkippedInstrument:
    instrument_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class ScanHit:
    instrument_id: str
    symbol: str
    name: str
    signal: SignalEventV1
    ai_score: float | None = None
    rating_breakdown: dict[str, Any] | None = None
    data_quality_score: float | None = None
    data_quality_breakdown: dict[str, Any] | None = None
    global_score: float | None = None


@dataclass(frozen=True, slots=True)
class ScanRunResult:
    scan_id: str
    scanned_count: int
    hit_count: int
    hits: list[ScanHit]
    skipped: list[ScanSkippedInstrument]
    strategy_definition_id: str | None
    list_id: str | None
    timeframe: str
    instrument_snapshots: list[dict[str, Any]]
    strategy_version: int
    scan_mode: str = "classic"
    scorer_version: str | None = None
    scorer_id: str | None = None
    gate_rule_hash: str | None = None
    fundamentals_version: str | None = None
    fundamentals_refreshed_count: int | None = None


def scan_run_result_to_dict(result: ScanRunResult) -> dict[str, Any]:
    def signal_to_dict(signal: SignalEventV1) -> dict[str, Any]:
        return {
            "id": signal.id,
            "instrumentId": signal.instrument_id,
            "timestamp": signal.timestamp,
            "kind": signal.kind,
            "strategyDefinitionId": signal.strategy_definition_id,
            "strategyVersion": signal.strategy_version,
            "barIndex": signal.bar_index,
            "price": signal.price,
            "dataVersion": signal.data_version,
            "indicatorSnapshotHash": signal.indicator_snapshot_hash,
            "presetKey": signal.preset_key,
        }

    def hit_to_dict(hit: ScanHit) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "instrumentId": hit.instrument_id,
            "symbol": hit.symbol,
            "name": hit.name,
            "signal": signal_to_dict(hit.signal),
        }
        if hit.ai_score is not None:
            payload["aiScore"] = hit.ai_score
        if hit.rating_breakdown is not None:
            payload["ratingBreakdown"] = hit.rating_breakdown
        if hit.data_quality_score is not None:
            payload["dataQualityScore"] = hit.data_quality_score
        if hit.data_quality_breakdown is not None:
            payload["dataQualityBreakdown"] = hit.data_quality_breakdown
        if hit.global_score is not None:
            payload["globalScore"] = hit.global_score
        return payload

    response: dict[str, Any] = {
        "scanId": result.scan_id,
        "scannedCount": result.scanned_count,
        "hitCount": result.hit_count,
        "hits": [hit_to_dict(hit) for hit in result.hits],
        "skipped": [
            {"instrumentId": item.instrument_id, "reason": item.reason}
            for item in result.skipped
        ],
        "strategyDefinitionId": result.strategy_definition_id,
        "listId": result.list_id,
        "timeframe": result.timeframe,
        "instrumentSnapshots": result.instrument_snapshots,
        "strategyVersion": result.strategy_version,
        "scanMode": result.scan_mode,
    }
    if result.scorer_version is not None:
        response["scorerVersion"] = result.scorer_version
    if result.scorer_id is not None:
        response["scorerId"] = result.scorer_id
    if result.gate_rule_hash is not None:
        response["gateRuleHash"] = result.gate_rule_hash
    if result.fundamentals_version is not None:
        response["fundamentalsVersion"] = result.fundamentals_version
    if result.fundamentals_refreshed_count is not None:
        response["fundamentalsRefreshedCount"] = result.fundamentals_refreshed_count
    return response


class RunScan:
    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        ohlcv_repository: OhlcvRepository,
        strategy_repository: StrategyDefinitionRepository,
        list_repository: SqlAlchemyListRepository,
        feature_cache: FeatureCache | None = None,
        feature_port: OnlineFeatureAdapter | None = None,
        event_bus: PlatformEventBus | None = None,
        fundamentals_batch_refresher: RefreshFundamentalsBatch | None = None,
    ) -> None:
        self._instruments = instrument_repository
        self._ohlcv = ohlcv_repository
        self._strategies = strategy_repository
        self._lists = list_repository
        self._feature_cache = feature_cache
        self._feature_port = feature_port
        self._event_bus = event_bus
        self._fundamentals_batch_refresher = fundamentals_batch_refresher

    async def execute(
        self,
        *,
        universe_list_id: str | None = None,
        universe_instrument_ids: list[str] | None = None,
        strategy_definition_id: str | None = None,
        definition: dict[str, Any] | None = None,
        preset_key: str | None = None,
        timeframe: str = "1d",
        bar_limit: int = 500,
        max_results: int = 100,
        async_job: bool = False,
    ) -> ScanRunResult:
        timeframe = validate_kernel_timeframe(timeframe)
        resolved_definition, resolved_strategy_id = await self._resolve_definition(
            strategy_definition_id=strategy_definition_id,
            definition=definition,
            preset_key=preset_key,
            timeframe=timeframe,
        )
        instrument_ids = await self._resolve_universe(
            list_id=universe_list_id,
            instrument_ids=universe_instrument_ids,
            async_job=async_job,
        )

        tf = TimeFrame(timeframe) if timeframe in {t.value for t in TimeFrame} else TimeFrame.D1
        hits: list[ScanHit] = []
        skipped: list[ScanSkippedInstrument] = []
        instrument_snapshots: list[dict[str, Any]] = []

        enriched_definition = enrich_definition_with_preset_rules(resolved_definition)
        hybrid_mode = is_hybrid_definition(enriched_definition)
        hybrid_candidates: list[ScanHit] = []
        fundamentals_by_instrument: dict[str, dict[str, Any] | None] = {}
        fundamentals_refreshed_count: int | None = None

        if (
            hybrid_mode
            and definition_has_fundamental_gate(enriched_definition)
            and self._fundamentals_batch_refresher is not None
        ):
            max_age_days = fundamental_gate_max_age_days(enriched_definition)
            refresh_result = await self._fundamentals_batch_refresher.execute(
                instrument_ids,
                max_age_days=max_age_days,
                only_stale=True,
            )
            fundamentals_refreshed_count = refresh_result.refreshed_count

        expected_last_bar_iso: str | None = None
        if hybrid_mode and tf == TimeFrame.D1:
            expected_last_bar_iso = expected_last_daily_bar().isoformat()

        for instrument_id in instrument_ids:
            instrument = await self._instruments.get_by_id(instrument_id)
            if instrument is None:
                skipped.append(ScanSkippedInstrument(instrument_id, "Instrumento no encontrado"))
                continue

            bars = await self._ohlcv.get_bars(instrument_id, timeframe=tf, limit=bar_limit)
            if len(bars) < MIN_SCAN_BARS:
                skipped.append(
                    ScanSkippedInstrument(
                        instrument_id,
                        f"Menos de {MIN_SCAN_BARS} barras — sincroniza el instrumento",
                    )
                )
                continue

            strategy_bars = [
                StrategyBarInput(timestamp=bar.timestamp, close=bar.close) for bar in bars
            ]
            timestamps = [bar.timestamp for bar in bars]
            closes = [bar.close for bar in bars]
            instrument_snapshots.append(
                build_instrument_snapshot_meta(
                    instrument_id=instrument_id,
                    timeframe=tf.value,
                    timestamps=timestamps,
                    closes=closes,
                )
            )
            ohlcv_bars = [
                OhlcvBar(
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume or 0),
                )
                for bar in bars
            ]

            if self._feature_port is not None and ohlcv_bars:
                # Consumidor IFeaturePort (RFC-005): snapshot latest vía registry.
                materialize_feature_snapshot(
                    self._feature_port,
                    instrument_id=instrument_id,
                    bars=ohlcv_bars,
                )

            features = None
            indicator_context = None
            indicator_specs = list(enriched_definition.get("indicatorSpecs") or [])
            specs_hash = hash_indicator_specs(indicator_specs)

            if self._feature_cache is not None and bars:
                cache_key = FeatureCacheKey.make(
                    instrument_id,
                    tf.value,
                    bar_limit,
                    len(bars),
                    bars[-1].timestamp,
                    bars[-1].close,
                    specs_hash,
                )
                if hybrid_mode or definition_has_rules(enriched_definition):
                    def build_context() -> dict[str, list[float | None]]:
                        return build_indicator_context(ohlcv_bars, indicator_specs)

                    indicator_context = self._feature_cache.get_or_build(cache_key, build_context)
                else:
                    features = get_or_build_preset_features(
                        self._feature_cache,
                        cache_key,
                        timestamps,
                        closes,
                    )
            elif hybrid_mode or definition_has_rules(enriched_definition):
                indicator_context = build_indicator_context(ohlcv_bars, indicator_specs)

            per_instrument_definition = {
                **enriched_definition,
                "universe": {"instrumentIds": [instrument_id]},
            }
            strategy_definition_id = str(
                resolved_strategy_id or per_instrument_definition.get("id") or "hybrid-scan"
            )
            strategy_version = int(per_instrument_definition.get("version") or 1)

            try:
                if hybrid_mode:
                    fundamentals = await self._instruments.get_fundamentals(instrument_id)
                    fundamentals_by_instrument[instrument_id] = fundamentals
                    passed_fundamental, fundamental_reason = passes_fundamental_gate(
                        per_instrument_definition,
                        fundamentals,
                    )
                    if not passed_fundamental:
                        skipped.append(
                            ScanSkippedInstrument(
                                instrument_id,
                                fundamental_reason or "No cumple filtro fundamental",
                            )
                        )
                        continue
                    if indicator_context is None:
                        indicator_context = build_indicator_context_for_definition(
                            ohlcv_bars,
                            per_instrument_definition,
                        )
                    last_sync = await self._instruments.get_last_sync_detail(instrument_id)
                    data_quality_context = DataQualityScanContext(
                        bar_count=len(bars),
                        last_bar_timestamp=bars[-1].timestamp,
                        expected_last_bar_date=expected_last_bar_iso,
                        last_sync_status=last_sync.status if last_sync else None,
                        last_sync_error=last_sync.error if last_sync else None,
                        recent_timestamps=timestamps,
                        has_fundamental_gate=definition_has_fundamental_gate(
                            per_instrument_definition
                        ),
                        fundamentals_ok=True,
                    )
                    candidate = evaluate_hybrid_candidate(
                        per_instrument_definition,
                        instrument_id=instrument_id,
                        symbol=instrument.symbol,
                        name=instrument.name,
                        ohlcv_bars=ohlcv_bars,
                        strategy_bars=strategy_bars,
                        indicator_context=indicator_context,
                        strategy_definition_id=strategy_definition_id,
                        strategy_version=strategy_version,
                        fundamentals=fundamentals,
                        data_quality_context=data_quality_context,
                    )
                    if candidate is not None:
                        hybrid_candidates.append(
                            ScanHit(
                                instrument_id=candidate.instrument_id,
                                symbol=candidate.symbol,
                                name=candidate.name,
                                signal=candidate.signal,
                                ai_score=candidate.ai_score,
                                rating_breakdown=candidate.rating_breakdown.to_dict(),
                                data_quality_score=candidate.data_quality_score,
                                data_quality_breakdown=candidate.data_quality_breakdown.to_dict(),
                                global_score=candidate.global_score,
                            )
                        )
                    continue

                last_bar_events = evaluate_strategy_last_bar(
                    per_instrument_definition,
                    strategy_bars,
                    instrument_id=instrument_id,
                    mode="raw",
                    features=features,
                    indicator_context=indicator_context,
                )
            except ValueError as exc:
                skipped.append(ScanSkippedInstrument(instrument_id, str(exc)))
                continue

            for signal in last_bar_events:
                hits.append(
                    ScanHit(
                        instrument_id=instrument_id,
                        symbol=instrument.symbol,
                        name=instrument.name,
                        signal=signal,
                    )
                )
                if len(hits) >= max_results:
                    break

            if not hybrid_mode and len(hits) >= max_results:
                break

        if hybrid_mode:
            hybrid_candidates.sort(
                key=lambda hit: (
                    hit.global_score
                    if hit.global_score is not None
                    else (hit.ai_score if hit.ai_score is not None else 0.0)
                ),
                reverse=True,
            )
            hits = hybrid_candidates[:max_results]

        strategy_version = int(resolved_definition.get("version") or 1)
        gate_hash = hash_gate_config(enriched_definition) if hybrid_mode else None
        fundamentals_version = (
            hash_fundamentals_batch(fundamentals_by_instrument)
            if fundamentals_by_instrument
            else None
        )

        result = ScanRunResult(
            scan_id=new_id(),
            scanned_count=len(instrument_ids),
            hit_count=len(hits),
            hits=hits,
            skipped=skipped,
            strategy_definition_id=resolved_strategy_id,
            list_id=universe_list_id,
            timeframe=tf.value,
            instrument_snapshots=instrument_snapshots,
            strategy_version=strategy_version,
            scan_mode="hybrid" if hybrid_mode else "classic",
            scorer_version=hybrid_scorer_version(enriched_definition) if hybrid_mode else None,
            scorer_id="technical_rating_v1" if hybrid_mode else None,
            gate_rule_hash=gate_hash,
            fundamentals_version=fundamentals_version,
            fundamentals_refreshed_count=fundamentals_refreshed_count,
        )

        if self._event_bus is not None:
            await self._event_bus.publish(
                "scan.completed",
                scan_completed_payload(result),
                correlation_id=result.scan_id,
            )

        return result

    async def _resolve_definition(
        self,
        *,
        strategy_definition_id: str | None,
        definition: dict[str, Any] | None,
        preset_key: Literal["sma_crossover", "rsi_mean_reversion"] | None,
        timeframe: str,
    ) -> tuple[dict[str, Any], str | None]:
        if strategy_definition_id:
            saved = await self._strategies.get_definition(strategy_definition_id)
            if saved is None:
                raise ValueError("Estrategia no encontrada")
            resolved = {**saved.definition, "id": saved.id}
            return resolved, saved.id

        if definition is not None:
            return definition, str(definition.get("id")) if definition.get("id") else None

        if preset_key is not None and not is_valid_preset_key(preset_key):
            raise ValueError("presetKey inválido")
        if preset_key is not None:
            return strategy_definition_from_preset(preset_key, instrument_ids=[], timeframe=timeframe), None

        raise ValueError("Indica strategyDefinitionId, definition o presetKey")

    async def _resolve_universe(
        self,
        *,
        list_id: str | None,
        instrument_ids: list[str] | None,
        async_job: bool = False,
    ) -> list[str]:
        return await resolve_scan_universe_instrument_ids(
            self._lists,
            list_id=list_id,
            instrument_ids=instrument_ids,
            async_job=async_job,
        )
