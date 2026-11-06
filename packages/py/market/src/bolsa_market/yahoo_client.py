from __future__ import annotations

import asyncio
import math
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from bolsa_market.yahoo_circuit_breaker import (
    YahooCircuitBreaker,
    YahooCircuitOpenError,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

QUERY_HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class YahooRateLimitError(RuntimeError):
    """Yahoo Finance devolvió 429 tras agotar reintentos."""


class YahooSymbolNotFoundError(RuntimeError):
    """Yahoo no reconoce el símbolo (404): condición permanente, no reintentar."""


class YahooProviderDisabledError(RuntimeError):
    """El proveedor Yahoo está DESHABILITADO en Configuración: no se lanza la petición.

    N-1 — el interruptor de Configuración se aplicaba solo al histórico (``CAPABILITY_OHLCV``)
    mientras fundamentales, FX, índices, búsqueda, macro y noticias seguían pidiendo a Yahoo
    con el proveedor «deshabilitado» en pantalla. Este error cierra el hueco en el único
    punto por el que pasan TODAS las peticiones (``_ensure_traffic_allowed``), para que la
    configuración signifique lo mismo para todo el mundo y no dependa de que cada ruta se
    acuerde de consultarla.
    """


#: N-1 — estado de tráfico del proveedor Yahoo para ESTE proceso. Arranca habilitado (el
#: defecto de la configuración es ``enabled=True``) para que un proceso que todavía no ha
#: leído la tabla no cambie de comportamiento. Lo refresca el resolver de proveedores en
#: cada lectura de configuración (``MarketProviderConfigResolver.list_configs``).
_YAHOO_TRAFFIC: dict[str, Any] = {"enabled": True, "reason": None}


def set_yahoo_traffic_enabled(enabled: bool, *, reason: str | None = None) -> None:
    """Declara si el proceso puede hablar con Yahoo (lo aplica el resolver).

    No es un secreto ni un caché de configuración: es el semáforo que consulta el cliente
    antes de cada petición. ``reason`` viaja en el error para que el operador no vea «Yahoo
    sin respuesta» cuando la causa es que él mismo lo apagó.
    """
    _YAHOO_TRAFFIC["enabled"] = bool(enabled)
    _YAHOO_TRAFFIC["reason"] = reason


def yahoo_traffic_enabled() -> bool:
    """``True`` si este proceso puede pedir a Yahoo."""
    return bool(_YAHOO_TRAFFIC["enabled"])


def _ensure_traffic_allowed() -> None:
    """Fail-closed por configuración: con el proveedor apagado NO se sale a la red."""
    if yahoo_traffic_enabled():
        return
    reason = _YAHOO_TRAFFIC["reason"] or "provider_disabled:yahoo"
    raise YahooProviderDisabledError(
        f"Yahoo Finance está deshabilitado en Configuración ({reason}): "
        "no se lanza la petición"
    )


def normalize_yahoo_error(exc: Exception) -> str:
    raw = str(exc)
    if isinstance(exc, YahooProviderDisabledError):
        return str(exc)
    if isinstance(exc, YahooSymbolNotFoundError):
        return "Yahoo no encontró histórico para este símbolo. Revisa el ticker (ej. AENA.MC)."
    if isinstance(exc, YahooCircuitOpenError) or "circuit OPEN" in raw:
        return (
            "Yahoo Finance en cooldown (circuit breaker). "
            "Espera un minuto e inténtalo de nuevo."
        )
    if "429" in raw or "too many requests" in raw.lower():
        return (
            "Yahoo Finance limitó las peticiones (429). "
            "Espera 1–2 minutos e inténtalo de nuevo. "
            "Evita sincronizar muchos tickers seguidos."
        )
    if "timeout" in raw.lower() or "timed out" in raw.lower():
        return "Yahoo Finance no respondió a tiempo. Comprueba tu conexión e inténtalo de nuevo."
    if "404" in raw or "not found" in raw.lower():
        return "Yahoo no encontró histórico para este símbolo. Revisa el ticker (ej. AENA.MC)."
    if len(raw) > 200:
        return f"{raw[:200]}…"
    return raw


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(float(retry_after), 1.0)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(retry_after)
                if parsed is not None:
                    return max(parsed.timestamp() - time.time(), 1.0)
            except (TypeError, ValueError, OSError):
                pass
    return min(90.0, 5.0 * float(2**attempt))


@dataclass
class YahooFinanceClient:
    """Cliente HTTP Yahoo: throttle, reintentos con backoff y circuit breaker."""

    min_interval_sec: float = field(
        default_factory=lambda: float(os.environ.get("YAHOO_MIN_INTERVAL_SEC", "2.0")),
    )
    max_retries: int = field(
        default_factory=lambda: int(os.environ.get("YAHOO_MAX_RETRIES", "4")),
    )
    circuit: YahooCircuitBreaker = field(default_factory=YahooCircuitBreaker)

    def __post_init__(self) -> None:
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._crumb: str | None = None
        self._host_index = 0
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        # N-1 — el semáforo se consulta aquí: todo ``fetch_*`` pasa por este punto antes de
        # tocar la red (y antes de ``_ensure_crumb``/``_throttle``), así que una ruta nueva
        # queda cubierta sin acordarse de la configuración.
        _ensure_traffic_allowed()
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                },
                follow_redirects=True,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        self._crumb = None

    async def _reset_session(self) -> None:
        await self.aclose()

    async def _throttle(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self.min_interval_sec - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = time.monotonic()

    async def _ensure_crumb(self, client: httpx.AsyncClient) -> None:
        if self._crumb:
            return
        # fc.yahoo.com fija cookie A3; sin ella getcrumb → 401 Invalid Crumb.
        try:
            await client.get("https://fc.yahoo.com")
        except httpx.HTTPError:
            pass
        try:
            await client.get("https://finance.yahoo.com/")
        except httpx.HTTPError:
            pass
        for host in QUERY_HOSTS:
            try:
                crumb_response = await client.get(f"https://{host}/v1/test/getcrumb")
            except httpx.HTTPError:
                continue
            if crumb_response.is_success and crumb_response.text.strip():
                text = crumb_response.text.strip()
                # JSON de error no es crumb válido
                if text.startswith("{") or "Unauthorized" in text:
                    continue
                self._crumb = text
                return

    async def _request_with_crumb(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str | int],
    ) -> httpx.Response | None:
        """GET con crumb; en 401 renueva sesión y reintenta una vez."""
        await self._throttle()
        try:
            response = await client.get(url, params=params)
        except httpx.HTTPError:
            return None
        if response.status_code != 401:
            return response
        self._crumb = None
        await self._reset_session()
        client = await self._get_client()
        await self._ensure_crumb(client)
        if self._crumb:
            params = {**params, "crumb": self._crumb}
        await self._throttle()
        try:
            return await client.get(url, params=params)
        except httpx.HTTPError:
            return None

    def _next_host(self) -> str:
        host = QUERY_HOSTS[self._host_index % len(QUERY_HOSTS)]
        self._host_index += 1
        return host

    async def fetch_chart_payload(
        self,
        yahoo_symbol: str,
        *,
        period1: int,
        period2: int,
        interval: str = "1d",
    ) -> dict[str, Any]:
        try:
            self.circuit.before_call()
        except YahooCircuitOpenError as exc:
            raise RuntimeError(normalize_yahoo_error(exc)) from exc

        client = await self._get_client()
        await self._ensure_crumb(client)

        params: dict[str, str | int] = {
            "period1": period1,
            "period2": period2,
            "interval": interval,
        }
        if self._crumb:
            params["crumb"] = self._crumb

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            await self._throttle()
            host = self._next_host()
            url = f"https://{host}/v8/finance/chart/{yahoo_symbol}"

            try:
                response = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == self.max_retries - 1:
                    self.circuit.record_failure()
                    raise RuntimeError(normalize_yahoo_error(exc)) from exc
                await asyncio.sleep(min(90.0, 5.0 * (2**attempt)))
                continue

            if response.status_code == 401 and self._crumb:
                self._crumb = None
                await self._ensure_crumb(client)
                if self._crumb:
                    params["crumb"] = self._crumb
                continue

            if response.status_code == 404:
                # Símbolo no reconocido por Yahoo: condición permanente, no reintentar
                # ni contar como fallo transitorio del provider (circuit breaker).
                raise YahooSymbolNotFoundError(
                    f"Yahoo no encontró histórico para el símbolo '{yahoo_symbol}' (404)"
                )

            if response.status_code in RETRYABLE_STATUS:
                last_error = YahooRateLimitError(
                    f"Client error '{response.status_code} {response.reason_phrase}' "
                    f"for url '{response.url}'",
                )
                if response.status_code == 429:
                    await self._reset_session()
                if attempt == self.max_retries - 1:
                    self.circuit.record_failure()
                    raise RuntimeError(normalize_yahoo_error(last_error)) from last_error
                await asyncio.sleep(_retry_delay_seconds(response, attempt))
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                self.circuit.record_failure()
                raise RuntimeError(normalize_yahoo_error(exc)) from exc

            payload: dict[str, Any] = response.json()
            chart_error = payload.get("chart", {}).get("error")
            if chart_error:
                description = chart_error.get("description", str(chart_error))
                self.circuit.record_failure()
                raise RuntimeError(normalize_yahoo_error(RuntimeError(description)))

            result = payload.get("chart", {}).get("result")
            if not result:
                self.circuit.record_failure()
                raise RuntimeError(f"Yahoo no devolvió barras diarias para {yahoo_symbol}")

            self.circuit.record_success()
            return payload

        self.circuit.record_failure()
        if last_error:
            raise RuntimeError(normalize_yahoo_error(last_error)) from last_error
        raise RuntimeError(f"Yahoo no devolvió barras diarias para {yahoo_symbol}")

    async def search_quotes(self, query: str, *, quotes_count: int = 10) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            return []

        client = await self._get_client()
        await self._ensure_crumb(client)
        params: dict[str, str | int] = {
            "q": normalized,
            "quotesCount": quotes_count,
            "newsCount": 0,
        }
        if self._crumb:
            params["crumb"] = self._crumb

        await self._throttle()
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        quotes = payload.get("quotes") or []
        return [q for q in quotes if isinstance(q, dict)]

    async def fetch_news(self, query: str, *, news_count: int = 8) -> list[dict[str, Any]]:
        """Noticias Yahoo vía /v1/finance/search (newsCount)."""
        normalized = query.strip()
        if not normalized:
            return []

        client = await self._get_client()
        await self._ensure_crumb(client)
        params: dict[str, str | int] = {
            "q": normalized,
            "quotesCount": 0,
            "newsCount": max(1, min(int(news_count), 20)),
            "lang": "en-US",
            "region": "US",
        }
        if self._crumb:
            params["crumb"] = self._crumb

        await self._throttle()
        url = "https://query2.finance.yahoo.com/v1/finance/search"
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        news = payload.get("news") or []
        return [n for n in news if isinstance(n, dict)]

    async def fetch_isin(self, yahoo_symbol: str) -> str | None:
        normalized = yahoo_symbol.strip()
        if not normalized:
            return None

        client = await self._get_client()
        await self._ensure_crumb(client)
        params: dict[str, str | int] = {"modules": "summaryProfile"}
        if self._crumb:
            params["crumb"] = self._crumb

        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{normalized}"
        response = await self._request_with_crumb(client, url, params)
        if response is None:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        payload = response.json()
        results = payload.get("quoteSummary", {}).get("result") or []
        if not results:
            return None
        profile = results[0].get("summaryProfile") or {}
        isin = profile.get("isin")
        if isinstance(isin, str) and isin.strip():
            return isin.strip().upper()
        return None

    async def fetch_quote_summary(
        self,
        yahoo_symbol: str,
        *,
        modules: str = (
            "summaryProfile,summaryDetail,financialData,defaultKeyStatistics,"
            "calendarEvents,balanceSheetHistory,incomeStatementHistory,"
            "cashflowStatementHistory"
        ),
    ) -> dict[str, Any] | None:
        normalized = yahoo_symbol.strip()
        if not normalized:
            return None

        client = await self._get_client()
        await self._ensure_crumb(client)
        params: dict[str, str | int] = {"modules": modules}
        if self._crumb:
            params["crumb"] = self._crumb

        url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{normalized}"
        response = await self._request_with_crumb(client, url, params)
        if response is None:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        payload = response.json()
        results = payload.get("quoteSummary", {}).get("result") or []
        if not results:
            return None
        modules_out: dict[str, Any] = results[0]
        try:
            from bolsa_market.yahoo_fundamentals_timeseries import (
                ALL_TIMESERIES_TYPES,
                enrich_modules_from_timeseries,
            )

            ts_payload = await self.fetch_fundamentals_timeseries(
                normalized,
                types=ALL_TIMESERIES_TYPES,
            )
            modules_out = enrich_modules_from_timeseries(modules_out, ts_payload)
        except Exception:
            # quoteSummary parcial sigue siendo útil
            pass
        return modules_out

    async def fetch_fundamentals_timeseries(
        self,
        yahoo_symbol: str,
        *,
        types: tuple[str, ...] | list[str],
        years: int = 5,
    ) -> dict[str, Any] | None:
        """WS fundamentals-timeseries (annual* fields)."""
        import time as _time

        normalized = yahoo_symbol.strip()
        if not normalized or not types:
            return None

        client = await self._get_client()
        await self._ensure_crumb(client)
        now = int(_time.time())
        params: dict[str, str | int] = {
            "type": ",".join(types),
            "period1": now - max(1, years) * 365 * 24 * 3600,
            "period2": now,
        }
        if self._crumb:
            params["crumb"] = self._crumb

        url = (
            "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/"
            f"v1/finance/timeseries/{normalized}"
        )
        response = await self._request_with_crumb(client, url, params)
        if response is None:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            return None
        return payload

    async def fetch_dividend_history(self, yahoo_symbol: str, *, years: int = 5) -> list[dict[str, Any]]:
        normalized = yahoo_symbol.strip()
        if not normalized:
            return []

        client = await self._get_client()
        await self._ensure_crumb(client)
        params: dict[str, str | int] = {
            "range": f"{years}y",
            "interval": "1d",
            "events": "div",
        }
        if self._crumb:
            params["crumb"] = self._crumb

        await self._throttle()
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{normalized}"
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        payload = response.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return []

        dividends = (result[0].get("events") or {}).get("dividends") or {}
        history: list[dict[str, Any]] = []
        for timestamp, event in dividends.items():
            if not isinstance(event, dict):
                continue
            amount = event.get("amount")
            if amount is None:
                continue
            try:
                date = datetime.fromtimestamp(int(timestamp), tz=UTC).date().isoformat()
            except (TypeError, ValueError, OSError):
                date = str(timestamp)
            history.append({"date": date, "amount": float(amount)})

        history.sort(key=lambda item: item["date"], reverse=True)
        return history[:24]

    async def fetch_spot_price(self, yahoo_symbol: str) -> tuple[float, str]:
        """Precio spot del símbolo.

        N-2 — un precio no finito o ``<= 0`` NO es un precio: se rechaza en el origen (con
        el valor crudo en el mensaje) en lugar de propagarse como si fuera una cotización.
        Antes, un ``regularMarketPrice`` a 0 o ``NaN`` llegaba intacto a la sonda del
        proveedor (que lo daba por bueno, verde) y a FX (que solo filtraba ``== 0`` en la
        cotización inversa).
        """
        import time

        now = int(time.time())
        payload = await self.fetch_chart_payload(
            yahoo_symbol,
            period1=now - 86400 * 5,
            period2=now,
            interval="1d",
        )
        result = payload["chart"]["result"][0]
        meta = result.get("meta") or {}
        regular_price = meta.get("regularMarketPrice")
        if regular_price is not None:
            timestamp = meta.get("regularMarketTime") or now
            return _validated_spot_price(regular_price, yahoo_symbol), str(timestamp)

        quotes = result.get("indicators", {}).get("quote") or [{}]
        closes = quotes[0].get("close") or []
        timestamps = result.get("timestamp") or []
        for index in range(len(closes) - 1, -1, -1):
            close = closes[index]
            if close is not None:
                ts = timestamps[index] if index < len(timestamps) else now
                return _validated_spot_price(close, yahoo_symbol), str(ts)

        raise RuntimeError(f"Yahoo no devolvió precio spot para {yahoo_symbol}")


def _validated_spot_price(raw: Any, yahoo_symbol: str) -> float:
    """``float(raw)`` si es un precio utilizable; ``RuntimeError`` con el valor crudo si no."""
    try:
        price = float(raw)
    except (TypeError, ValueError):
        raise RuntimeError(
            f"Yahoo devolvió un precio spot no numérico para {yahoo_symbol}: {raw!r}"
        ) from None
    if not math.isfinite(price) or price <= 0:
        raise RuntimeError(
            f"Yahoo devolvió un precio spot no válido para {yahoo_symbol}: {raw!r}"
        )
    return price


_shared_client: YahooFinanceClient | None = None


def get_yahoo_finance_client() -> YahooFinanceClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = YahooFinanceClient()
    return _shared_client
