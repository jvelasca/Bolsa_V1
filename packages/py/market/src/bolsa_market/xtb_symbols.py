def to_xtb_symbol(local_symbol: str, *, yahoo_symbol: str | None = None) -> str:
    yahoo = (yahoo_symbol or "").strip().upper()
    if yahoo and "." in yahoo:
        return yahoo
    symbol = local_symbol.strip().upper()
    if symbol.endswith(".ES"):
        return symbol
    return f"{symbol}.ES"


def from_xtb_symbol(xtb_symbol: str) -> str:
    return xtb_symbol.replace(".ES", "").replace(".es", "").upper()


def is_supported_xtb_symbol(local_symbol: str) -> bool:
    symbol = local_symbol.upper()
    return 1 <= len(symbol) <= 10 and symbol.isalnum()
