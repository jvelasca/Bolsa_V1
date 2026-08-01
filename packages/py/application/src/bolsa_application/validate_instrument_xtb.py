"""Contraste read-only entre cierre en BD y cotización XTB en vivo."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Literal

from bolsa_application.get_instrument_detail import GetInstrumentDetail
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_domain.repositories.sync_log_repository import SyncLogRepository
from bolsa_market.providers import XtbBridgeClient, format_xtb_bridge_connect_error
from bolsa_market.xtb_symbols import to_xtb_symbol
from bolsa_infrastructure.database.repositories.instrument_repository import SqlAlchemyInstrumentRepository

Recommendation = Literal["aligned", "review", "unavailable", "no_db_reference"]


@dataclass(frozen=True, slots=True)
class InstrumentXtbValidation:
    available: bool
    message: str
    db_last_close: float | None
    db_last_date: str | None
    xtb_last: float | None
    xtb_bid: float | None
    xtb_ask: float | None
    xtb_timestamp: str | None
    deviation_pct: float | None
    recommendation: Recommendation
    validated_at: str
    wrote_to_db: bool = False


class ValidateInstrumentWithXtb:
    """Obtiene cotización XTB, contrasta con BD y guarda el informe (no toca OHLCV)."""

    def __init__(
        self,
        instrument_repository: InstrumentRepository,
        detail_use_case: GetInstrumentDetail,
        sync_log_repository: SyncLogRepository,
        xtb_bridge_url: str | None,
    ) -> None:
        self._instruments = instrument_repository
        self._detail = detail_use_case
        self._sync_logs = sync_log_repository
        self._xtb_bridge_url = xtb_bridge_url

    async def execute(self, instrument_id: str) -> InstrumentXtbValidation | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None

        validated_at = datetime.now(timezone.utc).isoformat()
        detail = await self._detail.execute(instrument_id)
        db_close: float | None = None
        db_date: str | None = None
        if detail and detail.price_summary:
            db_close = detail.price_summary.last_close
            db_date = detail.price_summary.last_date

        result = await self._fetch_validation(
            instrument.symbol,
            yahoo_symbol=instrument.yahoo_symbol,
            db_close=db_close,
            db_date=db_date,
            validated_at=validated_at,
        )

        await self._persist(instrument_id, result)
        return result

    async def _fetch_validation(
        self,
        symbol: str,
        *,
        yahoo_symbol: str,
        db_close: float | None,
        db_date: str | None,
        validated_at: str,
    ) -> InstrumentXtbValidation:
        if not self._xtb_bridge_url or not self._xtb_bridge_url.strip():
            return InstrumentXtbValidation(
                available=False,
                message="XTB_BRIDGE_URL no configurada.",
                db_last_close=db_close,
                db_last_date=db_date,
                xtb_last=None,
                xtb_bid=None,
                xtb_ask=None,
                xtb_timestamp=None,
                deviation_pct=None,
                recommendation="unavailable",
                validated_at=validated_at,
            )

        client = XtbBridgeClient(self._xtb_bridge_url.strip())
        try:
            health = await client.check_health()
            if health.status != "ok":
                return InstrumentXtbValidation(
                    available=False,
                    message=health.message or "Bridge XTB no responde correctamente.",
                    db_last_close=db_close,
                    db_last_date=db_date,
                    xtb_last=None,
                    xtb_bid=None,
                    xtb_ask=None,
                    xtb_timestamp=None,
                    deviation_pct=None,
                    recommendation="unavailable",
                    validated_at=validated_at,
                )

            quote = await client.fetch_quote(
                to_xtb_symbol(symbol, yahoo_symbol=yahoo_symbol),
                reference_close=db_close,
            )
        except Exception as exc:
            message = (
                format_xtb_bridge_connect_error(self._xtb_bridge_url.strip(), exc)
                if self._xtb_bridge_url
                else str(exc)
            )
            return InstrumentXtbValidation(
                available=False,
                message=message,
                db_last_close=db_close,
                db_last_date=db_date,
                xtb_last=None,
                xtb_bid=None,
                xtb_ask=None,
                xtb_timestamp=None,
                deviation_pct=None,
                recommendation="unavailable",
                validated_at=validated_at,
            )

        deviation: float | None = None
        recommendation: Recommendation = "no_db_reference"
        if db_close is not None and db_close != 0:
            deviation = ((quote.last - db_close) / db_close) * 100
            recommendation = "aligned" if abs(deviation) < 2.0 else "review"

        summary = (
            f"XTB {quote.last:.4f} vs cierre BD {db_close:.4f} ({db_date})"
            if db_close is not None and db_date
            else f"XTB {quote.last:.4f} (sin cierre de referencia en BD)"
        )
        if deviation is not None:
            summary += f" · Δ {deviation:+.2f}%"
        if health.mode == "mock":
            summary += " · Bridge mock (precio simulado cerca del cierre BD)"

        return InstrumentXtbValidation(
            available=True,
            message=summary,
            db_last_close=db_close,
            db_last_date=db_date,
            xtb_last=quote.last,
            xtb_bid=quote.bid,
            xtb_ask=quote.ask,
            xtb_timestamp=quote.timestamp,
            deviation_pct=deviation,
            recommendation=recommendation,
            validated_at=validated_at,
        )

    async def _persist(self, instrument_id: str, result: InstrumentXtbValidation) -> None:
        payload = {
            key: value
            for key, value in asdict(result).items()
            if key != "wrote_to_db"
        }
        payload["wroteToDb"] = False

        if isinstance(self._instruments, SqlAlchemyInstrumentRepository):
            await self._instruments.update_last_xtb_validation(instrument_id, payload)

        log_status: Literal["success", "partial", "failed"] = "success" if result.available else "partial"
        if result.recommendation == "review":
            log_status = "partial"
        await self._sync_logs.create_log(
            instrument_id,
            provider="xtb",
            status=log_status,
            bars_added=0,
            error=result.message if not result.available else None,
        )
