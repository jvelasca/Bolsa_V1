"""Capa B — resolución de constitutivos (plugin async)."""



from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from bolsa_market.indices.curated_ibex35 import IBEX35_CURATED
from bolsa_market.indices.registry import get_known_index
from bolsa_market.indices.remote_market_constituents import (
    YFIUA_CSV_BY_CODE,
    fetch_stoxx50e_members,
    fetch_yfiua_members,
)
from bolsa_market.indices.wikipedia_constituents import fetch_sp100_members, fetch_sp500_members


@dataclass(frozen=True, slots=True)

class ConstituentMember:

    symbol: str

    yahoo_symbol: str

    name: str | None = None





@dataclass(frozen=True, slots=True)

class ConstituentSet:

    index_code: str

    yahoo_index_symbol: str

    members: tuple[ConstituentMember, ...]

    provider: str

    as_of: str

    content_hash: str



    @property

    def yahoo_symbols(self) -> list[str]:

        return [m.yahoo_symbol for m in self.members]





class ConstituentProvider(Protocol):

    async def resolve(self, index_code_or_yahoo: str) -> ConstituentSet | None:

        """None si el índice no tiene provider listo."""





def _hash_members(members: tuple[ConstituentMember, ...]) -> str:

    payload = "|".join(sorted(m.yahoo_symbol.upper() for m in members))

    return f"c{len(members)}:{hash(payload) & 0xFFFFFFFF:08x}"





def _bundle(

    *,

    code: str,

    yahoo_index: str,

    members: tuple[ConstituentMember, ...],

    provider: str,

) -> ConstituentSet:

    return ConstituentSet(

        index_code=code,

        yahoo_index_symbol=yahoo_index,

        members=members,

        provider=provider,

        as_of=datetime.now(UTC).date().isoformat(),

        content_hash=_hash_members(members),

    )





def _from_remote(

    remote: tuple,

    *,

    code: str,

    yahoo_index: str,

    provider: str,

) -> ConstituentSet:

    members = tuple(

        ConstituentMember(symbol=m.symbol, yahoo_symbol=m.yahoo_symbol, name=m.name)

        for m in remote

    )

    return _bundle(code=code, yahoo_index=yahoo_index, members=members, provider=provider)





class CuratedConstituentProvider:

    """IBEX35 curado en repo."""



    async def resolve(self, index_code_or_yahoo: str) -> ConstituentSet | None:

        known = get_known_index(index_code_or_yahoo)

        if known is None or known.code != "IBEX35":

            return None

        members = tuple(

            ConstituentMember(symbol=sym, yahoo_symbol=yahoo, name=name)

            for sym, yahoo, name in IBEX35_CURATED

        )

        return _bundle(

            code=known.code,

            yahoo_index=known.yahoo_symbol,

            members=members,

            provider="curated_v1",

        )





class RemoteUsConstituentProvider:

    """S&P 500 (CSV) + S&P 100 (Wikipedia/mirror)."""



    async def resolve(self, index_code_or_yahoo: str) -> ConstituentSet | None:

        known = get_known_index(index_code_or_yahoo)

        if known is None:

            return None

        try:

            if known.code == "SPX":

                return _from_remote(

                    await fetch_sp500_members(),

                    code="SPX",

                    yahoo_index=known.yahoo_symbol,

                    provider="sp500_csv_v1",

                )

            if known.code == "OEX":

                return _from_remote(

                    await fetch_sp100_members(),

                    code="OEX",

                    yahoo_index=known.yahoo_symbol,

                    provider="sp100_wiki_v1",

                )

        except Exception:

            return None

        return None





class RemoteIntlConstituentProvider:

    """Índices intl vía CSV Yahoo-aligned (yfiua) + Euro Stoxx 50 (wiki/mirror)."""



    async def resolve(self, index_code_or_yahoo: str) -> ConstituentSet | None:

        known = get_known_index(index_code_or_yahoo)

        if known is None:

            return None

        try:

            if known.code in YFIUA_CSV_BY_CODE:

                return _from_remote(

                    await fetch_yfiua_members(known.code),

                    code=known.code,

                    yahoo_index=known.yahoo_symbol,

                    provider=f"{known.code.lower()}_csv_v1",

                )

            if known.code == "STOXX50E":

                return _from_remote(

                    await fetch_stoxx50e_members(),

                    code="STOXX50E",

                    yahoo_index=known.yahoo_symbol,

                    provider="stoxx50e_wiki_v1",

                )

        except Exception:

            return None

        return None





class CompositeConstituentProvider:

    def __init__(self, *providers: ConstituentProvider) -> None:

        self._providers = providers



    async def resolve(self, index_code_or_yahoo: str) -> ConstituentSet | None:

        for provider in self._providers:

            resolved = await provider.resolve(index_code_or_yahoo)

            if resolved is not None:

                return resolved

        return None





_READY_PROVIDERS = frozenset({"curated", "remote_us", "remote_intl"})





def index_constituents_ready(code_or_yahoo: str) -> bool:

    known = get_known_index(code_or_yahoo)

    if known is None:

        return False

    return known.constituent_provider in _READY_PROVIDERS





def default_constituent_provider() -> CompositeConstituentProvider:

    return CompositeConstituentProvider(

        CuratedConstituentProvider(),

        RemoteUsConstituentProvider(),

        RemoteIntlConstituentProvider(),

    )


