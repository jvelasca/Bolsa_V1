"""F2b+ — fetch_from_sec use case con EDGAR mock (sin red)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bolsa_application.instrument_filings import InstrumentFilingsService
from bolsa_market.sec_edgar import SecFilingHit


@dataclass
class _Inst:
    id: str
    symbol: str
    yahoo_symbol: str
    sector: str | None = "Technology"


class _Repo:
    def __init__(self, inst: _Inst | None) -> None:
        self._inst = inst

    async def get_by_id(self, instrument_id: str):
        if self._inst and self._inst.id == instrument_id:
            return self._inst
        return None


class _FakeEdgar:
    def __init__(self, hit: SecFilingHit, content: bytes, ctype: str) -> None:
        self._hit = hit
        self._content = content
        self._ctype = ctype
        self.closed = False

    async def fetch_latest_filing_bytes(self, *, yahoo_symbol: str, form: str = "10-K"):
        assert form == "10-K"
        assert yahoo_symbol
        return self._hit, self._content, self._ctype

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_fetch_from_sec_saves_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    hit = SecFilingHit(
        cik="0000320193",
        ticker="AAPL",
        form="10-K",
        accession_number="0000320193-23-000106",
        primary_document="aapl.htm",
        filing_date="2023-11-03",
        company_name="Apple Inc.",
    )
    html = b"<html><body><p>ITEM 1A. RISK FACTORS</p><p>Supply chain.</p></body></html>"
    edgar = _FakeEdgar(hit, html, "text/html")
    svc = InstrumentFilingsService(_Repo(_Inst("i1", "AAPL", "AAPL")), edgar=edgar)

    first = await svc.fetch_from_sec("i1", kind="10-K")
    assert first is not None
    assert first["deduped"] is False
    assert first["data"]["source"] == "sec_edgar"
    assert first["data"]["accessionNumber"] == hit.accession_number
    assert first["data"]["extractStatus"] == "ok"
    assert first["data"]["charCount"] > 0

    second = await svc.fetch_from_sec("i1", kind="10-K")
    assert second is not None
    assert second["deduped"] is True
    assert second["data"]["id"] == first["data"]["id"]


@pytest.mark.asyncio
async def test_fetch_from_sec_missing_instrument(tmp_path, monkeypatch):
    monkeypatch.setenv("BOLSA_FILINGS_DIR", str(tmp_path))
    svc = InstrumentFilingsService(_Repo(None), edgar=_FakeEdgar(
        SecFilingHit("1", "X", "10-K", "a", "x.htm", "2020-01-01", "X"),
        b"x",
        "text/plain",
    ))
    assert await svc.fetch_from_sec("missing") is None
