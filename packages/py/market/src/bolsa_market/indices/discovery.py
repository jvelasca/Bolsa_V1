"""Capa A — discovery de índices vía Yahoo search + aliases locales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from bolsa_market.indices.aliases import canonical_index_code, expand_index_query_aliases
from bolsa_market.indices.registry import KNOWN_INDICES, KnownIndex, get_known_index

try:
    from bolsa_market.indices.constituents import index_constituents_ready
except Exception:  # pragma: no cover
    def index_constituents_ready(code_or_yahoo: str) -> bool:
        known = get_known_index(code_or_yahoo)
        return bool(known and known.constituent_provider == "curated")

YahooSearchFn = Callable[..., Awaitable[list[dict[str, Any]]]]


@dataclass(frozen=True, slots=True)
class IndexHit:
    code: str | None
    display_name: str
    yahoo_symbol: str
    region: str | None
    currency: str | None
    quote_type: str
    source: str  # alias | yahoo | known
    constituent_ready: bool
    score: float


def _hit_from_known(known: KnownIndex, *, source: str, score: float) -> IndexHit:
    return IndexHit(
        code=known.code,
        display_name=known.display_name,
        yahoo_symbol=known.yahoo_symbol,
        region=known.region,
        currency=known.currency,
        quote_type="INDEX",
        source=source,
        constituent_ready=index_constituents_ready(known.code),
        score=score,
    )


def _hit_from_yahoo_quote(quote: dict[str, Any]) -> IndexHit | None:
    quote_type = str(quote.get("quoteType") or "").upper()
    if quote_type != "INDEX":
        return None
    symbol = str(quote.get("symbol") or "").strip()
    if not symbol:
        return None
    name = str(
        quote.get("longname")
        or quote.get("shortname")
        or quote.get("longName")
        or quote.get("shortName")
        or symbol,
    )
    known = get_known_index(symbol)
    if known:
        return _hit_from_known(known, source="yahoo", score=float(quote.get("score") or 50) + 20)
    return IndexHit(
        code=None,
        display_name=name,
        yahoo_symbol=symbol,
        region=None,
        currency=None,
        quote_type="INDEX",
        source="yahoo",
        constituent_ready=False,
        score=float(quote.get("score") or 10),
    )


async def discover_market_indices(
    query: str,
    *,
    search_fn: YahooSearchFn | None = None,
    limit: int = 12,
) -> list[IndexHit]:
    """Busca índices: aliases/known primero, luego Yahoo INDEX."""
    q = query.strip()
    if not q:
        return []

    hits: list[IndexHit] = []
    seen_symbols: set[str] = set()

    def push(hit: IndexHit) -> None:
        key = hit.yahoo_symbol.upper()
        if key in seen_symbols:
            return
        seen_symbols.add(key)
        hits.append(hit)

    code = canonical_index_code(q)
    if code and code in KNOWN_INDICES:
        push(_hit_from_known(KNOWN_INDICES[code], source="alias", score=1000))

    # Coincidencia parcial en catálogo known (sin red)
    qn = q.lower()
    for known in KNOWN_INDICES.values():
        if (
            qn in known.code.lower()
            or qn in known.display_name.lower()
            or qn in known.yahoo_symbol.lower()
        ):
            push(_hit_from_known(known, source="known", score=800))

    if search_fn is not None:
        for sub_q in expand_index_query_aliases(q)[:3]:
            try:
                quotes = await search_fn(sub_q, quotes_count=limit)
            except Exception:
                continue
            for quote in quotes:
                hit = _hit_from_yahoo_quote(quote)
                if hit:
                    push(hit)
            if len(hits) >= limit:
                break

    hits.sort(key=lambda h: (-h.score, h.display_name))
    return hits[:limit]
