import pytest

from bolsa_application.refresh_instrument_fundamentals import RefreshFundamentalsBatch


class _FakeInstrumentRepository:
    def __init__(self, fundamentals_by_id: dict[str, dict | None]) -> None:
        self._fundamentals = fundamentals_by_id

    async def get_fundamentals(self, instrument_id: str) -> dict | None:
        return self._fundamentals.get(instrument_id)


@pytest.mark.asyncio
async def test_batch_skips_fresh_fundamentals() -> None:
    fresh = {"fetchedAt": "2099-01-01T00:00:00+00:00"}
    repo = _FakeInstrumentRepository({"a": fresh, "b": fresh})
    refresher = RefreshFundamentalsBatch(repo)

    result = await refresher.execute(["a", "b"], max_age_days=30, only_stale=True)

    assert result.refreshed_count == 0
    assert result.skipped_count == 2
    assert result.failed_count == 0


@pytest.mark.asyncio
async def test_batch_noop_without_sqlalchemy_repo() -> None:
    repo = _FakeInstrumentRepository({"a": None})
    refresher = RefreshFundamentalsBatch(repo)

    result = await refresher.execute(["a"], max_age_days=30, only_stale=True)

    assert result.refreshed_count == 0
    assert result.skipped_count == 1
    assert result.failed_count == 0
