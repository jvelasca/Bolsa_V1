"""Helpers para mapear preview de eliminación de instrumento → DTO."""

from __future__ import annotations

from bolsa_api.schemas.instrument_lifecycle import (
    InstrumentRemovalPreviewDto,
    ListMembershipRefDto,
    NamedRefDto,
    OrphanInstrumentDto,
    OrphanInstrumentsDto,
    PurgeOrphanSkippedDto,
    PurgeOrphansResultDto,
    RemoveInstrumentFromListResultDto,
)
from bolsa_application.instrument_lifecycle import InstrumentRemovalPreview
from bolsa_application.remove_list_instrument import (
    ListOrphanInstrumentsResult,
    RemoveFromListResult,
)


def to_removal_preview_dto(preview: InstrumentRemovalPreview) -> InstrumentRemovalPreviewDto:
    return InstrumentRemovalPreviewDto(
        instrument_id=preview.instrument_id,
        symbol=preview.symbol,
        name=preview.name,
        list_memberships=[
            ListMembershipRefDto(list_id=m.list_id, list_name=m.list_name, source=m.source)
            for m in preview.list_memberships
        ],
        remaining_list_count=preview.remaining_list_count,
        trackers_by_instrument=[
            NamedRefDto(id=t.id, name=t.name, detail=t.detail)
            for t in preview.trackers_by_instrument
        ],
        trackers_by_list=[
            NamedRefDto(id=t.id, name=t.name, detail=t.detail) for t in preview.trackers_by_list
        ],
        price_alerts_active=preview.price_alerts_active,
        price_alerts_total=preview.price_alerts_total,
        signal_alerts_active=preview.signal_alerts_active,
        signal_alerts_total=preview.signal_alerts_total,
        positions=preview.positions,
        pending_orders=preview.pending_orders,
        transactions=preview.transactions,
        backtest_runs=preview.backtest_runs,
        ledger_entries=preview.ledger_entries,
        ohlcv_bar_count=preview.ohlcv_bar_count,
        would_be_orphan=preview.would_be_orphan,
        can_purge=preview.can_purge,
        purge_blocked_reasons=list(preview.purge_blocked_reasons),
        purge_warnings=list(preview.purge_warnings),
    )


def to_remove_from_list_result_dto(
    result: RemoveFromListResult,
) -> RemoveInstrumentFromListResultDto:
    return RemoveInstrumentFromListResultDto(
        list_id=result.list_id,
        instrument_id=result.instrument_id,
        removed_from_list=result.removed_from_list,
        became_orphan=result.became_orphan,
        purged=result.purged,
        purge_skipped_reasons=list(result.purge_skipped_reasons),
        preview=to_removal_preview_dto(result.preview) if result.preview else None,
    )


def to_orphans_dto(result: ListOrphanInstrumentsResult) -> OrphanInstrumentsDto:
    return OrphanInstrumentsDto(
        orphans=[
            OrphanInstrumentDto(
                id=o.id,
                symbol=o.symbol,
                name=o.name,
                ohlcv_bar_count=o.ohlcv_bar_count,
            )
            for o in result.orphans
        ],
        total_ohlcv_bars=result.total_ohlcv_bars,
    )


def to_purge_orphans_result_dto(raw: dict[str, object]) -> PurgeOrphansResultDto:
    skipped_raw = raw.get("skipped") or []
    skipped: list[PurgeOrphanSkippedDto] = []
    if isinstance(skipped_raw, list):
        for item in skipped_raw:
            if not isinstance(item, dict):
                continue
            skipped.append(
                PurgeOrphanSkippedDto(
                    instrument_id=str(item.get("instrumentId", "")),
                    symbol=str(item.get("symbol", "")),
                    reasons=[str(r) for r in (item.get("reasons") or [])],
                )
            )
    purged_ids = raw.get("purgedIds") or []
    return PurgeOrphansResultDto(
        purged_ids=[str(x) for x in purged_ids] if isinstance(purged_ids, list) else [],
        skipped=skipped,
        scanned=int(raw.get("scanned") or 0),
    )
