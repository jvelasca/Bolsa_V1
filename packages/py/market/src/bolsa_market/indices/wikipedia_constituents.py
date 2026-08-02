"""Constituents remotos alineados a Yahoo (S&P 500 / S&P 100).



Fuentes:

- SPX: CSV publico datasets/s-and-p-500-companies (simbolos Yahoo US).

- OEX: Wikipedia (HTML directo; si 403, mirror markdown via r.jina.ai).



Cache en memoria por proceso (TTL).

"""



from __future__ import annotations

import csv
import io
import re
import time
from dataclasses import dataclass

import httpx

SP500_CSV_URL = (

    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"

    "main/data/constituents.csv"

)

SP100_WIKI_URL = "https://en.wikipedia.org/wiki/S%26P_100"

# Mirror legible cuando Wikimedia bloquea bots (403 robot policy).

SP100_WIKI_MIRROR_URL = "https://r.jina.ai/http://en.wikipedia.org/wiki/S%26P_100"



_USER_AGENT = "BolsaV1/0.1 (research; local bolsa app; +https://localhost)"



_CACHE_TTL_SEC = 6 * 60 * 60





@dataclass(frozen=True, slots=True)

class RemoteMember:

    symbol: str

    yahoo_symbol: str

    name: str | None = None





@dataclass

class _CacheEntry:

    members: tuple[RemoteMember, ...]

    fetched_at: float





_cache: dict[str, _CacheEntry] = {}





def _cache_get(key: str) -> tuple[RemoteMember, ...] | None:

    entry = _cache.get(key)

    if entry is None:

        return None

    if time.monotonic() - entry.fetched_at > _CACHE_TTL_SEC:

        return None

    return entry.members





def _cache_set(key: str, members: tuple[RemoteMember, ...]) -> None:

    _cache[key] = _CacheEntry(members=members, fetched_at=time.monotonic())





def clear_remote_constituents_cache() -> None:

    _cache.clear()





def _yahoo_us_symbol(raw: str) -> str:

    """BRK.B -> BRK-B (Yahoo)."""

    return raw.strip().upper().replace(".", "-")





def _clean_name(raw: str) -> str:

    # Markdown links: [Apple Inc.](url "title") → Apple Inc.

    m = re.match(r"\[([^\]]+)\]", raw.strip())

    if m:

        return m.group(1).strip()

    return raw.strip()





async def fetch_sp500_members(

    client: httpx.AsyncClient | None = None,

) -> tuple[RemoteMember, ...]:

    cached = _cache_get("SPX")

    if cached is not None:

        return cached



    owns = client is None

    cli = client or httpx.AsyncClient(

        timeout=30.0,

        headers={"User-Agent": _USER_AGENT},

        follow_redirects=True,

    )

    try:

        response = await cli.get(SP500_CSV_URL)

        response.raise_for_status()

        text = response.text

    finally:

        if owns:

            await cli.aclose()



    reader = csv.DictReader(io.StringIO(text))

    members: list[RemoteMember] = []

    seen: set[str] = set()

    for row in reader:

        raw = (row.get("Symbol") or row.get("symbol") or "").strip()

        if not raw:

            continue

        yahoo = _yahoo_us_symbol(raw)

        if yahoo in seen:

            continue

        seen.add(yahoo)

        name = (row.get("Security") or row.get("Name") or row.get("name") or yahoo).strip()

        members.append(RemoteMember(symbol=yahoo, yahoo_symbol=yahoo, name=name))



    if len(members) < 400:

        raise RuntimeError(f"SP500 CSV incompleto ({len(members)} filas)")



    out = tuple(members)

    _cache_set("SPX", out)

    return out





_SP100_HTML_ROW_RE = re.compile(

    r"<tr[^>]*>\s*<td[^>]*>\s*(?:<a[^>]*>)?([A-Z]{1,5}(?:\.[A-Z])?)"

    r"(?:</a>)?\s*</td>\s*<td[^>]*>\s*(?:<a[^>]*>)?([^<]+)",

    re.IGNORECASE,

)

# Markdown table (jina): | AAPL | Apple Inc. | ...

_SP100_MD_ROW_RE = re.compile(

    r"\|\s*([A-Z]{1,5}(?:\.[A-Z])?)\s*\|\s*([^|\n]+)\|",

)





def _parse_sp100_html(html: str) -> list[RemoteMember]:

    lower = html.lower()

    start = lower.find('id="components"')

    if start < 0:

        start = lower.find("components")

    chunk = html[start : start + 80_000] if start >= 0 else html



    members: list[RemoteMember] = []

    seen: set[str] = set()

    for match in _SP100_HTML_ROW_RE.finditer(chunk):

        raw = match.group(1).upper()

        yahoo = _yahoo_us_symbol(raw)

        if yahoo in seen or len(yahoo) > 6:

            continue

        seen.add(yahoo)

        name = (match.group(2) or yahoo).strip() or yahoo

        members.append(RemoteMember(symbol=yahoo, yahoo_symbol=yahoo, name=name))

        if len(members) >= 120:

            break

    return members





def _parse_sp100_markdown(text: str) -> list[RemoteMember]:

    members: list[RemoteMember] = []

    seen: set[str] = set()

    skip = {"SYMBOL", "TICKER", "COMPANY", "SECTOR", "GICS"}

    for match in _SP100_MD_ROW_RE.finditer(text):

        raw = match.group(1).upper()

        if raw in skip:

            continue

        yahoo = _yahoo_us_symbol(raw)

        if yahoo in seen or len(yahoo) > 6:

            continue

        name = _clean_name(match.group(2)) or yahoo

        # Filtrar filas basura del infobox (OEX, SP100 como "trading symbol")

        if yahoo in {"OEX", "SP100"}:

            continue

        seen.add(yahoo)

        members.append(RemoteMember(symbol=yahoo, yahoo_symbol=yahoo, name=name))

        if len(members) >= 120:

            break

    return members





async def fetch_sp100_members(

    client: httpx.AsyncClient | None = None,

) -> tuple[RemoteMember, ...]:

    cached = _cache_get("OEX")

    if cached is not None:

        return cached



    owns = client is None

    cli = client or httpx.AsyncClient(

        timeout=45.0,

        headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},

        follow_redirects=True,

    )

    members: list[RemoteMember] = []

    try:

        # 1) Wikipedia HTML

        try:

            response = await cli.get(SP100_WIKI_URL)

            if response.status_code == 200 and len(response.text) > 5_000:

                members = _parse_sp100_html(response.text)

        except httpx.HTTPError:

            members = []



        # 2) Mirror markdown si HTML bloqueado / incompleto

        if len(members) < 80:

            response = await cli.get(SP100_WIKI_MIRROR_URL)

            response.raise_for_status()

            members = _parse_sp100_markdown(response.text)

    finally:

        if owns:

            await cli.aclose()



    if len(members) < 80:

        raise RuntimeError(f"S&P 100 incompleto ({len(members)} tickers)")



    out = tuple(members)

    _cache_set("OEX", out)

    return out


