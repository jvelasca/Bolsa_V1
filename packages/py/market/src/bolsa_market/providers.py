from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from bolsa_market.yahoo_chart import YahooMarketDataProvider


def format_xtb_bridge_connect_error(base_url: str, exc: Exception) -> str:
    message = str(exc).strip()
    if isinstance(exc, httpx.ConnectError) or "connection attempts failed" in message.lower():
        return (
            f"No se pudo conectar al bridge XTB en {base_url}. "
            "En desarrollo, arranca el mock con: node scripts/xtb-bridge-mock.mjs "
            "(o reinicia pnpm dev, que lo levanta automáticamente)."
        )
    if isinstance(exc, httpx.TimeoutException):
        return f"El bridge XTB en {base_url} no respondió a tiempo."
    return message or f"Error al contactar el bridge XTB en {base_url}."

@dataclass(frozen=True, slots=True)
class XtbBridgeHealth:
    status: str
    mode: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class XtbBridgeQuote:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: str


class XtbBridgeClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def check_health(self) -> XtbBridgeHealth:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self._base_url}/health")
        except Exception as exc:
            return XtbBridgeHealth(
                status="error",
                message=format_xtb_bridge_connect_error(self._base_url, exc),
            )
        if not response.is_success:
            return XtbBridgeHealth(status="error", message=f"Bridge respondió {response.status_code}")
        body = response.json()
        if body.get("status") == "ok":
            return XtbBridgeHealth(
                status="ok",
                mode=body.get("mode"),
                message=body.get("message"),
            )
        return XtbBridgeHealth(status="error", message=body.get("message", "Bridge no disponible"))

    async def fetch_quote(
        self,
        xtb_symbol: str,
        *,
        reference_close: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> XtbBridgeQuote:
        from urllib.parse import quote

        params: dict[str, str] = {}
        if reference_close is not None and reference_close > 0:
            params["reference"] = str(reference_close)

        async def _get(http: httpx.AsyncClient) -> XtbBridgeQuote:
            try:
                response = await http.get(
                    f"{self._base_url}/symbols/{quote(xtb_symbol, safe='')}/quote",
                    params=params or None,
                )
            except Exception as exc:
                raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc
            if not response.is_success:
                body = response.json() if response.content else {}
                raise RuntimeError(
                    body.get("error", f"XTB bridge quote error ({response.status_code})")
                )
            data = response.json()
            return XtbBridgeQuote(
                symbol=data["symbol"],
                bid=float(data["bid"]),
                ask=float(data["ask"]),
                last=float(data["last"]),
                timestamp=data["timestamp"],
            )

        if client is not None:
            return await _get(client)
        try:
            async with httpx.AsyncClient(timeout=5.0) as owned:
                return await _get(owned)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc

    async def fetch_quotes(
        self,
        xtb_symbols: list[str],
        *,
        references: dict[str, float | None] | None = None,
        concurrency: int = 8,
    ) -> dict[str, XtbBridgeQuote]:
        """Fetch many quotes with one HTTP client and bounded concurrency.

        Failures for individual symbols are skipped (partial map).
        """
        ordered: list[str] = []
        seen: set[str] = set()
        for symbol in xtb_symbols:
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            ordered.append(symbol)
        if not ordered:
            return {}

        refs = references or {}
        sem = asyncio.Semaphore(max(1, concurrency))
        out: dict[str, XtbBridgeQuote] = {}

        async with httpx.AsyncClient(timeout=5.0) as client:

            async def _one(symbol: str) -> None:
                async with sem:
                    try:
                        quote = await self.fetch_quote(
                            symbol,
                            reference_close=refs.get(symbol),
                            client=client,
                        )
                    except Exception:
                        return
                    out[symbol] = quote

            await asyncio.gather(*[_one(symbol) for symbol in ordered])
        return out


__all__ = [
    "XtbBridgeClient",
    "XtbBridgeHealth",
    "XtbBridgeQuote",
    "YahooMarketDataProvider",
    "format_xtb_bridge_connect_error",
]
