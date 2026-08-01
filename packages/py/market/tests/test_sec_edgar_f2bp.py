"""F2b+ — SEC EDGAR client (unit; sin red)."""

from bolsa_market.sec_edgar import (
    SecEdgarClient,
    SecFilingHit,
    document_bytes_to_extractable,
    html_to_text,
    pad_cik,
    us_ticker_from_yahoo_symbol,
)


def test_us_ticker_accepts_plain_and_brk():
    assert us_ticker_from_yahoo_symbol("aapl") == "AAPL"
    assert us_ticker_from_yahoo_symbol("BRK.B") == "BRK.B"


def test_us_ticker_rejects_european_suffix():
    assert us_ticker_from_yahoo_symbol("SAN.MC") is None
    assert us_ticker_from_yahoo_symbol("AIR.PA") is None


def test_pad_cik():
    assert pad_cik(320193) == "0000320193"
    assert pad_cik("789019") == "0000789019"


def test_html_to_text_strips_tags():
    html = "<html><body><h1>ITEM 1A</h1><p>Risk factors here.</p><script>x()</script></body></html>"
    text = html_to_text(html)
    assert "ITEM 1A" in text
    assert "Risk factors" in text
    assert "x()" not in text


def test_document_bytes_html_to_txt():
    html = b"<html><body><p>ITEM 7 MD&amp;A</p></body></html>"
    data, ctype, name = document_bytes_to_extractable(html, "text/html", "aapl-10k.htm")
    assert ctype == "text/plain"
    assert name.endswith(".txt")
    assert b"ITEM 7" in data or b"MD" in data


def test_pick_latest_10k():
    client = SecEdgarClient()
    submissions = {
        "cik": "320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-Q"],
                "accessionNumber": ["0001", "0000320193-23-000106", "0003"],
                "primaryDocument": ["a.htm", "aapl-20230930.htm", "q.htm"],
                "filingDate": ["2024-01-01", "2023-11-03", "2023-08-01"],
            }
        },
    }
    hit = client.pick_latest_filing(submissions, form="10-K")
    assert hit is not None
    assert hit.form == "10-K"
    assert hit.accession_number == "0000320193-23-000106"
    assert "aapl-20230930.htm" in hit.document_url
    assert hit.cik == "0000320193"


def test_pick_missing_form():
    client = SecEdgarClient()
    hit = client.pick_latest_filing(
        {"cik": "1", "filings": {"recent": {"form": ["8-K"], "accessionNumber": ["a"], "primaryDocument": ["x.htm"], "filingDate": ["2020-01-01"]}}},
        form="10-K",
    )
    assert hit is None


def test_sec_filing_hit_accession_nodash():
    hit = SecFilingHit(
        cik="0000320193",
        ticker="AAPL",
        form="10-K",
        accession_number="0000320193-23-000106",
        primary_document="x.htm",
        filing_date="2023-11-03",
        company_name="Apple",
    )
    assert hit.accession_nodash == "000032019323000106"
