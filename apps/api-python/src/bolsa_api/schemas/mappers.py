"""Mappers principales dominio ↔ DTO HTTP."""

from bolsa_analytics.indicators import IndicatorPoint, IndicatorSignals
from bolsa_api.schemas.instruments import (
    IndicatorPointDto,
    IndicatorSignalsDto,
    IndicatorsMetaDto,
    IndicatorsResponseDto,
    InstrumentDataStatusDto,
    InstrumentDbInventoryDto,
    InstrumentDetailMetaDto,
    InstrumentDetailResponseDto,
    InstrumentDto,
    InstrumentListMetaDto,
    InstrumentWithMetaDto,
    InstrumentXtbValidationDto,
    OhlcvBarDto,
    OhlcvMetaDto,
    OhlcvResponseDto,
    PriceSummaryDto,
    SyncDetailDto,
    SyncMetaDto,
)
from bolsa_application.get_instrument_data_status import InstrumentDataStatus
from bolsa_application.get_instrument_db_inventory import InstrumentDbInventory
from bolsa_application.get_instrument_detail import InstrumentDetail
from bolsa_application.validate_instrument_xtb import InstrumentXtbValidation
from bolsa_domain.entities.instrument import Instrument
from bolsa_domain.entities.ohlcv_bar import OhlcvBar
from bolsa_domain.repositories.instrument_repository import (
    InstrumentWithMeta,
    SyncLogDetail,
)
from bolsa_domain.value_objects.price_summary import PriceSummary


def to_instrument_dto(item: InstrumentWithMeta) -> InstrumentWithMetaDto:
    return InstrumentWithMetaDto(
        id=item.id,
        symbol=item.symbol,
        yahoo_symbol=item.yahoo_symbol,
        name=item.name,
        exchange=item.exchange,
        country=item.country,
        currency=item.currency,
        sector=item.sector,
        isin=item.isin,
        is_active=item.is_active,
        meta=InstrumentListMetaDto(
            bar_count=item.bar_count,
            last_sync=(
                SyncMetaDto(
                    status=item.last_sync.status,
                    synced_at=item.last_sync.synced_at,
                    error=item.last_sync.error,
                )
                if item.last_sync
                else None
            ),
            last_close=item.last_close,
            change_pct=item.change_pct,
            last_bar_date=item.last_bar_date,
            freshness_status=item.freshness_status,
            expected_last_bar_date=item.expected_last_bar_date,
        ),
    )


def _to_base_instrument_dto(instrument: Instrument) -> InstrumentDto:
    return InstrumentDto(
        id=instrument.id,
        symbol=instrument.symbol,
        yahoo_symbol=instrument.yahoo_symbol,
        name=instrument.name,
        exchange=instrument.exchange,
        country=instrument.country,
        currency=instrument.currency,
        sector=instrument.sector,
        isin=instrument.isin,
        is_active=instrument.is_active,
    )


def _to_price_summary_dto(summary: PriceSummary) -> PriceSummaryDto:
    return PriceSummaryDto(
        last_close=summary.last_close,
        previous_close=summary.previous_close,
        change_abs=summary.change_abs,
        change_pct=summary.change_pct,
        period_low=summary.period_low,
        period_high=summary.period_high,
        bar_count=summary.bar_count,
        first_date=summary.first_date,
        last_date=summary.last_date,
    )


def _to_sync_detail_dto(sync: SyncLogDetail) -> SyncDetailDto:
    return SyncDetailDto(
        status=sync.status,
        bars_added=sync.bars_added,
        synced_at=sync.synced_at,
        error=sync.error,
    )


def to_instrument_detail_dto(detail: InstrumentDetail) -> InstrumentDetailResponseDto:
    return InstrumentDetailResponseDto(
        data=_to_base_instrument_dto(detail.instrument),
        meta=InstrumentDetailMetaDto(
            last_sync=_to_sync_detail_dto(detail.last_sync) if detail.last_sync else None,
            price_summary=(
                _to_price_summary_dto(detail.price_summary) if detail.price_summary else None
            ),
        ),
    )


def to_ohlcv_dto(bars: list[OhlcvBar], *, timeframe: str = "1d") -> OhlcvResponseDto:
    return OhlcvResponseDto(
        data=[
            OhlcvBarDto(
                timestamp=bar.timestamp,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                adj_close=bar.adj_close,
                source=bar.source,
            )
            for bar in bars
        ],
        meta=OhlcvMetaDto(timeframe=timeframe, count=len(bars)),
    )


def to_indicators_dto(
    points: list[IndicatorPoint],
    signals: IndicatorSignals,
) -> IndicatorsResponseDto:
    return IndicatorsResponseDto(
        data=[
            IndicatorPointDto(
                timestamp=point.timestamp,
                sma20=point.sma20,
                sma50=point.sma50,
                ema20=point.ema20,
                rsi14=point.rsi14,
            )
            for point in points
        ],
        meta=IndicatorsMetaDto(
            signals=IndicatorSignalsDto(
                rsi_zone=signals.rsi_zone,
                sma_cross=signals.sma_cross,
            ),
        ),
    )


def to_data_status_dto(status: InstrumentDataStatus) -> InstrumentDataStatusDto:
    return InstrumentDataStatusDto(
        timeframe=status.timeframe,
        last_bar_date=status.last_bar_date,
        expected_last_bar_date=status.expected_last_bar_date,
        freshness_status=status.freshness_status,
        bar_count=status.bar_count,
        last_sync_status=status.last_sync_status,
        last_sync_at=status.last_sync_at,
        last_sync_error=status.last_sync_error,
        sanity_warnings=list(status.sanity_warnings),
        gap_count=status.gap_count,
        xtb_vs_close_deviation_pct=status.xtb_vs_close_deviation_pct,
        last_xtb_quote_at=status.last_xtb_quote_at,
    )


def to_db_inventory_dto(inventory: InstrumentDbInventory) -> InstrumentDbInventoryDto:
    from bolsa_api.schemas.instruments import (
        InstrumentAppDataCountsDto,
        InstrumentOhlcvLayerDto,
        InstrumentRecordDto,
        InstrumentSyncLogEntryDto,
    )

    inst = inventory.instrument
    return InstrumentDbInventoryDto(
        instrument=InstrumentRecordDto(
            id=inst.id,
            symbol=inst.symbol,
            yahoo_symbol=inst.yahoo_symbol,
            name=inst.name,
            exchange=inst.exchange,
            country=inst.country,
            currency=inst.currency,
            sector=inst.sector,
            isin=inst.isin,
            is_active=inst.is_active,
            created_at=inst.created_at,
            updated_at=inst.updated_at,
            profile_fetched_at=inst.profile_fetched_at,
            last_xtb_validation=inst.last_xtb_validation,
        ),
        ohlcv_layers=[
            InstrumentOhlcvLayerDto(
                timeframe=layer.timeframe,
                source=layer.source,
                bar_count=layer.bar_count,
                first_date=layer.first_date,
                last_date=layer.last_date,
            )
            for layer in inventory.ohlcv_layers
        ],
        recent_sync_logs=[
            InstrumentSyncLogEntryDto(
                provider=log.provider,
                status=log.status,
                bars_added=log.bars_added,
                synced_at=log.synced_at,
                error=log.error,
            )
            for log in inventory.recent_sync_logs
        ],
        app_data=InstrumentAppDataCountsDto(
            positions=inventory.app_data.positions,
            transactions=inventory.app_data.transactions,
            backtest_runs=inventory.app_data.backtest_runs,
            list_memberships=inventory.app_data.list_memberships,
            price_alerts=inventory.app_data.price_alerts,
            pending_orders=inventory.app_data.pending_orders,
            ledger_entries=inventory.app_data.ledger_entries,
        ),
        derived_data_notes=list(inventory.derived_data_notes),
    )


def to_xtb_validation_dto(validation: InstrumentXtbValidation) -> InstrumentXtbValidationDto:
    return InstrumentXtbValidationDto(
        available=validation.available,
        message=validation.message,
        db_last_close=validation.db_last_close,
        db_last_date=validation.db_last_date,
        xtb_last=validation.xtb_last,
        xtb_bid=validation.xtb_bid,
        xtb_ask=validation.xtb_ask,
        xtb_timestamp=validation.xtb_timestamp,
        deviation_pct=validation.deviation_pct,
        recommendation=validation.recommendation,
        validated_at=validation.validated_at,
        wrote_to_db=validation.wrote_to_db,
    )
