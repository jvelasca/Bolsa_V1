"""Alias de búsqueda humano → código / símbolo Yahoo de índice."""

from __future__ import annotations

# query normalizada (lower, sin espacios extremos) → código canónico
INDEX_ALIASES: dict[str, str] = {
    "ibex": "IBEX35",
    "ibex35": "IBEX35",
    "ibex 35": "IBEX35",
    "^ibex": "IBEX35",
    "sp500": "SPX",
    "spx": "SPX",
    "s&p500": "SPX",
    "s&p 500": "SPX",
    "standard and poors 500": "SPX",
    "^gspc": "SPX",
    "gspc": "SPX",
    "sp100": "OEX",
    "s&p100": "OEX",
    "s&p 100": "OEX",
    "oex": "OEX",
    "^oex": "OEX",
    "dax": "DAX",
    "dax40": "DAX",
    "^gdaxi": "DAX",
    "gdaxi": "DAX",
    "ndx": "NDX",
    "nasdaq100": "NDX",
    "nasdaq 100": "NDX",
    "^ndx": "NDX",
    "eurostoxx50": "STOXX50E",
    "euro stoxx 50": "STOXX50E",
    "stoxx50": "STOXX50E",
    "^stoxx50e": "STOXX50E",
    "dow": "DJI",
    "dowjones": "DJI",
    "dow jones": "DJI",
    "djia": "DJI",
    "^dji": "DJI",
    "dji": "DJI",
    "ftse": "FTSE100",
    "ftse100": "FTSE100",
    "ftse 100": "FTSE100",
    "^ftse": "FTSE100",
    "ftsemib": "FTSEMIB",
    "ftse mib": "FTSEMIB",
    "mib": "FTSEMIB",
    "hang seng": "HSI",
    "hangseng": "HSI",
    "hsi": "HSI",
    "^hsi": "HSI",
}


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def canonical_index_code(query: str) -> str | None:
    """Si el query es un alias conocido, devuelve el código canónico."""
    return INDEX_ALIASES.get(_normalize_query(query))


def expand_index_query_aliases(query: str) -> list[str]:
    """Queries a probar en Yahoo (original + alias canónico + símbolo ^)."""
    q = query.strip()
    if not q:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        key = value.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append(value.strip())

    add(q)
    code = canonical_index_code(q)
    if code:
        add(code)
        from bolsa_market.indices.registry import get_known_index

        known = get_known_index(code)
        if known:
            add(known.yahoo_symbol)
            add(known.display_name)
    return out
