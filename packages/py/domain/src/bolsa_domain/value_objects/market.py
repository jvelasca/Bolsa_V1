"""Value object de dominio de resumen de mercado y resultados de sincronización."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SyncResult:
    bars_added: int
    status: Literal["success", "partial", "failed"]
    error: str | None = None
    bars_inserted: int = 0
    bars_updated: int = 0
    bars_skipped: int = 0
    consolidation_notes: tuple[str, ...] = ()
    # Si False, la condición es permanente (p. ej. Yahoo no encuentra histórico
    # para el símbolo) y la cola de sync NO debe reintentarla con backoff.
    retryable: bool = True


@dataclass(frozen=True, slots=True)
class LiveQuoteReference:
    price: float
    timestamp: str
    source: Literal["db"]


@dataclass(frozen=True, slots=True)
class XtbQuote:
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: str


@dataclass(frozen=True, slots=True)
class InstrumentLiveQuote:
    instrument_id: str
    symbol: str
    reference: LiveQuoteReference | None
    xtb: XtbQuote | None
    spread_pct: float | None
    xtb_available: bool


@dataclass(frozen=True, slots=True)
class MarketProviderStatus:
    id: str
    label: str
    enabled: bool
    healthy: bool
    message: str
