"""Constituents remotos alineados a Yahoo (familia remote_intl).

Fuentes:
- CSV yfiua/index-constituents (simbolos Yahoo): DAX, NDX, DJI, FTSE100, FTSEMIB, HSI.
- STOXX50E: Wikipedia via mirror markdown si Wikimedia bloquea bots.

Cache en memoria por proceso (TTL).
"""

from __future__ import annotations

import csv
import io
import re
import time
from dataclasses import dataclass

import httpx

YFIUA_BASE = "https://yfiua.github.io/index-constituents"

# code canónico → (csv slug, min_count)
YFIUA_CSV_BY_CODE: dict[str, tuple[str, int]] = {
    "DAX": ("dax", 35),
    "NDX": ("nasdaq100", 90),
    "DJI": ("dowjones", 28),
    "FTSE100": ("ftse100", 90),
    "FTSEMIB": ("ftsemib", 35),
    "HSI": ("hsi", 70),
}

STOXX50E_WIKI_URL = "https://en.wikipedia.org/wiki/EURO_STOXX_50"
STOXX50E_MIRROR_URL = "https://r.jina.ai/http://en.wikipedia.org/wiki/EURO_STOXX_50"

_USER_AGENT = "BolsaV1/0.1 (research; local bolsa app; +https://localhost)"
_CACHE_TTL_SEC = 6 * 60 * 60

_STOXX_MD_ROW_RE = re.compile(
    r"\|\s*([A-Z0-9]{1,6}(?:\.[A-Z]{1,3})?)\s*\|[^|\n]*\|[^|\n]*\|",
)


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


def clear_remote_intl_constituents_cache() -> None:
    _cache.clear()


def yfiua_csv_url(slug: str) -> str:
    return f"{YFIUA_BASE}/constituents-{slug}.csv"


# Compat exports usados por tests
DAX_CSV_URL = yfiua_csv_url("dax")
NDX_CSV_URL = yfiua_csv_url("nasdaq100")


def _symbol_parts(yahoo: str) -> tuple[str, str]:
    yahoo = yahoo.strip().upper()
    base = yahoo.split(".", 1)[0]
    return base, yahoo


async def fetch_yfiua_members(
    code: str,
    client: httpx.AsyncClient | None = None,
) -> tuple[RemoteMember, ...]:
    meta = YFIUA_CSV_BY_CODE.get(code.upper())
    if meta is None:
        raise ValueError(f"Sin CSV yfiua para {code}")
    slug, min_count = meta
    cached = _cache_get(code.upper())
    if cached is not None:
        return cached

    owns = client is None
    cli = client or httpx.AsyncClient(
        timeout=30.0,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    )
    try:
        response = await cli.get(yfiua_csv_url(slug))
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
        symbol, yahoo = _symbol_parts(raw)
        if yahoo in seen:
            continue
        seen.add(yahoo)
        name = (row.get("Name") or row.get("name") or symbol).strip()
        members.append(RemoteMember(symbol=symbol, yahoo_symbol=yahoo, name=name))

    if len(members) < min_count:
        raise RuntimeError(f"{code} CSV incompleto ({len(members)} filas)")

    out = tuple(members)
    _cache_set(code.upper(), out)
    return out


async def fetch_dax_members(client: httpx.AsyncClient | None = None) -> tuple[RemoteMember, ...]:
    return await fetch_yfiua_members("DAX", client)


async def fetch_ndx_members(client: httpx.AsyncClient | None = None) -> tuple[RemoteMember, ...]:
    return await fetch_yfiua_members("NDX", client)


def _parse_stoxx_markdown(text: str) -> list[RemoteMember]:
    members: list[RemoteMember] = []
    seen: set[str] = set()
    skip = {"TICKER", "SYMBOL", "NAME", "SECTOR", "MAIN"}
    for match in _STOXX_MD_ROW_RE.finditer(text):
        raw = match.group(1).upper()
        if raw in skip or "." not in raw:
            continue
        symbol, yahoo = _symbol_parts(raw)
        if yahoo in seen:
            continue
        seen.add(yahoo)
        members.append(RemoteMember(symbol=symbol, yahoo_symbol=yahoo, name=symbol))
        if len(members) >= 60:
            break
    return members


async def fetch_stoxx50e_members(
    client: httpx.AsyncClient | None = None,
) -> tuple[RemoteMember, ...]:
    cached = _cache_get("STOXX50E")
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
        try:
            response = await cli.get(STOXX50E_WIKI_URL)
            if response.status_code == 200 and len(response.text) > 5_000:
                for match in re.finditer(
                    r">([A-Z0-9]{1,6}\.(?:DE|PA|AS|MI|MC|HE|BR|LS|VI))<",
                    response.text,
                ):
                    symbol, yahoo = _symbol_parts(match.group(1))
                    if yahoo not in {m.yahoo_symbol for m in members}:
                        members.append(
                            RemoteMember(symbol=symbol, yahoo_symbol=yahoo, name=symbol),
                        )
        except httpx.HTTPError:
            members = []

        if len(members) < 40:
            response = await cli.get(STOXX50E_MIRROR_URL)
            response.raise_for_status()
            members = _parse_stoxx_markdown(response.text)

        if len(members) < 40:
            raise RuntimeError(f"STOXX50E incompleto ({len(members)} filas)")

        out = tuple(members)
        _cache_set("STOXX50E", out)
        return out
    finally:
        if owns:
            await cli.aclose()
