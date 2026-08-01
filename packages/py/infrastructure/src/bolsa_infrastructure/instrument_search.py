import re

_ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


def normalize_isin(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def looks_like_isin_query(query: str) -> bool:
    normalized = normalize_isin(query)
    return len(normalized) >= 10 and bool(_ISIN_RE.match(normalized))
