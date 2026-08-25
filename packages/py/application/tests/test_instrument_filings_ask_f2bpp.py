"""F2b++ — AskInstrumentFiling con índice local (mock instrument repo)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bolsa_application.instrument_filings import AskInstrumentFiling
from bolsa_market.filing_store import save_filing


class _FakeInstruments:
    def __init__(self, instrument) -> None:
        self._instrument = instrument

    async def get_by_id(self, instrument_id: str):
        if self._instrument and self._instrument.id == instrument_id:
            return self._instrument
        return None


@pytest.mark.asyncio
async def test_ask_filing_heuristic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    instrument = SimpleNamespace(id="inst-1", symbol="ACME", sector="Technology")
    meta = save_filing(
        instrument_id="inst-1",
        kind="10-K",
        original_name="acme.txt",
        content_type="text/plain",
        content=(
            b"ITEM 1A. RISK FACTORS\n"
            b"Customer concentration and supply chain disruption are key risks.\n"
            b"ITEM 7. MD&A\nRevenue increased year over year.\n"
        ),
    )
    import bolsa_ai

    def _no_llm():
        raise RuntimeError("no llm")

    monkeypatch.setattr(bolsa_ai, "get_default_proxy", _no_llm)

    result = await AskInstrumentFiling(_FakeInstruments(instrument)).execute(
        "inst-1",
        meta["id"],
        "customer concentration risks",
    )
    assert result is not None
    assert result["engine"] == "heuristic_rag"
    assert result["payload"]["answer"]
    assert result["hits"]
    assert result["question"] == "customer concentration risks"


@pytest.mark.asyncio
async def test_ask_rejects_empty_question(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    instrument = SimpleNamespace(id="inst-1", symbol="ACME", sector=None)
    meta = save_filing(
        instrument_id="inst-1",
        kind="10-K",
        original_name="acme.txt",
        content_type="text/plain",
        content=b"ITEM 1A RISK\nSomething about debt.\n",
    )
    with pytest.raises(ValueError, match="question"):
        await AskInstrumentFiling(_FakeInstruments(instrument)).execute(
            "inst-1",
            meta["id"],
            "   ",
        )
