from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx

from bolsa_market.yahoo_chart import YahooMarketDataProvider

XtbBridgeOrderStatus = Literal["submitted", "rejected", "filled"]


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


@dataclass(frozen=True, slots=True)
class XtbBridgeOrderResult:
    """Respuesta bridge POST /orders. submitted ≠ fill; filled→ledger (XL-2)."""

    status: XtbBridgeOrderStatus
    reason: str | None = None
    venue_order_id: str | None = None


XtbBridgeOrderQueryState = Literal[
    "working",
    "partial",
    "filled",
    "rejected",
    "cancelled",
]


@dataclass(frozen=True, slots=True)
class XtbBridgeOrderState:
    """Respuesta bridge GET /orders/{id} (broker-truth life-cycle de la orden).

    filled/remaining son cantidades del venue (sin aritmética financiera aquí).
    """

    venue_order_id: str
    state: XtbBridgeOrderQueryState
    filled_quantity: float
    remaining_quantity: float
    reason: str | None = None
    instrument_id: str | None = None
    side: str | None = None


@dataclass(frozen=True, slots=True)
class XtbBridgeAccountCash:
    """Respuesta bridge GET /account/cash (LR-1 read-only)."""

    cash: float
    currency: str = "EUR"


@dataclass(frozen=True, slots=True)
class XtbBridgePosition:
    """Posición live desde bridge GET /account/positions."""

    instrument_id: str
    quantity: float


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

    async def fetch_cash(self) -> XtbBridgeAccountCash:
        """GET /account/cash — read-only (LR-1). No trade."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/account/cash")
        except Exception as exc:
            raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc
        if not response.is_success:
            body = response.json() if response.content else {}
            raise RuntimeError(
                body.get("error", f"XTB bridge cash error ({response.status_code})")
            )
        data = response.json()
        return XtbBridgeAccountCash(
            cash=float(data.get("cash", 0)),
            currency=str(data.get("currency") or "EUR"),
        )

    async def fetch_positions(self) -> list[XtbBridgePosition]:
        """GET /account/positions — read-only (LR-1). No trade."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/account/positions")
        except Exception as exc:
            raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc
        if not response.is_success:
            body = response.json() if response.content else {}
            raise RuntimeError(
                body.get("error", f"XTB bridge positions error ({response.status_code})")
            )
        data = response.json()
        raw_positions = data.get("positions") if isinstance(data, dict) else None
        if not isinstance(raw_positions, list):
            return []
        out: list[XtbBridgePosition] = []
        for row in raw_positions:
            if not isinstance(row, dict):
                continue
            iid = row.get("instrumentId") or row.get("instrument_id")
            if not isinstance(iid, str) or not iid.strip():
                continue
            try:
                qty = float(row.get("quantity", 0))
            except (TypeError, ValueError):
                continue
            out.append(XtbBridgePosition(instrument_id=iid.strip(), quantity=qty))
        return out

    async def submit_order(
        self,
        *,
        instrument_id: str,
        side: str,
        quantity: float,
        price: float,
        account_id: str,
        idempotency_key: str,
        order_id: str | None = None,
        intent_id: str | None = None,
    ) -> XtbBridgeOrderResult:
        """POST /orders al bridge. Fail-closed: rejected si el mock no permite órdenes."""
        payload = {
            "instrumentId": instrument_id,
            "side": side,
            "quantity": quantity,
            "price": price,
            "accountId": account_id,
            "idempotencyKey": idempotency_key,
            "orderId": order_id,
            "intentId": intent_id,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(f"{self._base_url}/orders", json=payload)
        except Exception as exc:
            raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc
        body = response.json() if response.content else {}
        if not response.is_success:
            return XtbBridgeOrderResult(
                status="rejected",
                reason=str(body.get("reason") or body.get("error") or f"http_{response.status_code}"),
            )
        status_raw = str(body.get("status") or "rejected").lower()
        venue_order_id = body.get("venueOrderId") or body.get("orderId")
        if status_raw == "submitted":
            return XtbBridgeOrderResult(
                status="submitted",
                reason=body.get("reason"),
                venue_order_id=venue_order_id,
            )
        if status_raw == "filled":
            return XtbBridgeOrderResult(
                status="filled",
                reason=body.get("reason"),
                venue_order_id=venue_order_id,
            )
        return XtbBridgeOrderResult(
            status="rejected",
            reason=str(body.get("reason") or "live_rejected"),
            venue_order_id=venue_order_id,
        )

    async def query_order(
        self,
        venue_order_id: str,
    ) -> XtbBridgeOrderState:
        """GET /orders/{venue_order_id} — broker-truth del estado de una orden.

        Fail-closed: solo ``working|partial|filled|rejected|cancelled`` se
        consideran respuestas válidas de life-cycle; 404/timeout/HTTP-error
        lanzan ``RuntimeError`` (el recovery lo trata como ``unavailable`` y la
        máquina permanece UNKNOWN — no se fabrica cierre).
        """
        vid = (venue_order_id or "").strip()
        if not vid:
            raise RuntimeError("query_order requires venue_order_id")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/orders/{vid}")
        except Exception as exc:
            raise RuntimeError(format_xtb_bridge_connect_error(self._base_url, exc)) from exc
        if not response.is_success:
            body = response.json() if response.content else {}
            raise RuntimeError(
                body.get("reason") or body.get("error")
                or f"XTB bridge order query error ({response.status_code})"
            )
        body = response.json()
        state_raw = str(body.get("state") or "unavailable").lower()
        valid = {"working", "partial", "filled", "rejected", "cancelled"}
        if state_raw not in valid:
            # No es un life-cycle reconocible → no cierre (fail-closed).
            raise RuntimeError(f"XTB bridge order state inesperado: {state_raw!r}")
        def _qty(value: str | float | int | None) -> float:
            try:
                return max(0.0, float(value))
            except (TypeError, ValueError):
                return 0.0

        body_vid = body.get("venueOrderId") or body.get("orderId") or vid
        return XtbBridgeOrderState(
            venue_order_id=str(body_vid),
            state=state_raw,
            filled_quantity=_qty(body.get("filledQty")),
            remaining_quantity=_qty(body.get("remainingQty")),
            reason=(body.get("reason") or body.get("error") or None),
            instrument_id=body.get("instrumentId") if isinstance(body.get("instrumentId"), str) else None,
            side=body.get("side") if isinstance(body.get("side"), str) else None,
        )


__all__ = [
    "XtbBridgeAccountCash",
    "XtbBridgeClient",
    "XtbBridgeHealth",
    "XtbBridgeOrderQueryState",
    "XtbBridgeOrderResult",
    "XtbBridgeOrderState",
    "XtbBridgePosition",
    "XtbBridgeQuote",
    "YahooMarketDataProvider",
    "format_xtb_bridge_connect_error",
]
