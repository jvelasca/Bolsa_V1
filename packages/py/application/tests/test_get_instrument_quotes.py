"""GetInstrumentQuotes must batch by IDs (no per-id N+1)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bolsa_domain.repositories.instrument_repository import InstrumentWithMeta, SyncLogSnapshot

from bolsa_application.get_instrument_quotes import GetInstrumentQuotes


def _meta(instrument_id: str) -> InstrumentWithMeta:
    return InstrumentWithMeta(
        id=instrument_id,
        symbol=instrument_id.upper(),
        yahoo_symbol=f"{instrument_id.upper()}.MC",
        name=instrument_id,
        exchange="BME",
        country="ES",
        currency="EUR",
        sector=None,
        isin=None,
        is_active=True,
        bar_count=10,
        last_sync=SyncLogSnapshot(status="ok", synced_at="2026-01-01T00:00:00+00:00", error=None),
        last_close=10.0,
        change_pct=1.0,
        last_bar_date="2026-01-01",
        freshness_status="current",
        expected_last_bar_date="2026-01-01",
    )


@dataclass
class _FakeRepo:
    calls: list[list[str]]

    async def get_quotes_by_ids(self, instrument_ids: list[str]) -> list[InstrumentWithMeta]:
        self.calls.append(list(instrument_ids))
        # Mimic production: dedupe + preserve order + skip missing.
        seen: set[str] = set()
        ordered: list[str] = []
        for iid in instrument_ids:
            if not iid or iid in seen:
                continue
            seen.add(iid)
            ordered.append(iid)
        return [_meta(iid) for iid in ordered if iid != "missing"]

    async def get_with_meta_by_id(self, instrument_id: str) -> InstrumentWithMeta | None:
        raise AssertionError("N+1 path must not be used")


def test_get_instrument_quotes_batches_once() -> None:
    repo = _FakeRepo(calls=[])
    use_case = GetInstrumentQuotes(repo)  # type: ignore[arg-type]
    items = asyncio.run(use_case.execute(["a", "b", "a", "", "missing", "c"]))
    assert len(repo.calls) == 1
    assert repo.calls[0] == ["a", "b", "a", "", "missing", "c"]
    assert [item.id for item in items] == ["a", "b", "c"]
