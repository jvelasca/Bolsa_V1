from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bolsa_market.instrument_fundamentals import build_fundamentals_snapshot
from bolsa_market.fundamentals_as_of import extract_statement_pack


def _raw(node: Any) -> Any:
    if isinstance(node, dict):
        if "fmt" in node and node["fmt"] not in (None, ""):
            return node["fmt"]
        if "raw" in node:
            return node["raw"]
    return node


def _field(label: str, value: Any) -> dict[str, Any] | None:
    if value is None or value == "" or value == "—":
        return None
    if isinstance(value, float):
        text = f"{value:.2f}".rstrip("0").rstrip(".")
        return {"label": label, "value": text}
    return {"label": label, "value": str(value)}


def _section(title: str, fields: list[dict[str, Any] | None]) -> dict[str, Any] | None:
    items = [field for field in fields if field is not None]
    if not items:
        return None
    return {"title": title, "fields": items}


def build_profile_snapshot(
    *,
    yahoo_modules: dict[str, Any],
    dividend_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = yahoo_modules.get("summaryProfile") or {}
    detail = yahoo_modules.get("summaryDetail") or {}
    financial = yahoo_modules.get("financialData") or {}
    stats = yahoo_modules.get("defaultKeyStatistics") or {}
    calendar = yahoo_modules.get("calendarEvents") or {}

    about = profile.get("longBusinessSummary")
    market_hours = profile.get("exchangeTimezoneName") or profile.get("exchange")

    basic_sections: list[dict[str, Any]] = []
    if about:
        basic_sections.append({"title": "Acerca de", "text": str(about)})

    essentials = _section(
        "Esenciales",
        [
            _field("Sector", profile.get("sector")),
            _field("Industria", profile.get("industry")),
            _field("País", profile.get("country")),
            _field("Moneda", detail.get("currency") or profile.get("currency")),
            _field("Empleados", _raw(profile.get("fullTimeEmployees"))),
            _field("Web", profile.get("website")),
            _field("Beta", _raw(detail.get("beta"))),
            _field("Capitalización", _raw(detail.get("marketCap"))),
        ],
    )
    if essentials:
        basic_sections.append(essentials)

    profitability = _section(
        "Rentabilidad (mercado)",
        [
            _field("PER (trailing)", _raw(detail.get("trailingPE"))),
            _field("PER (forward)", _raw(detail.get("forwardPE"))),
            _field("EPS (trailing)", _raw(stats.get("trailingEps"))),
            _field("EPS (forward)", _raw(stats.get("forwardEps"))),
            _field("Margen beneficio", _raw(stats.get("profitMargins"))),
            _field("ROE", _raw(financial.get("returnOnEquity"))),
            _field("ROA", _raw(financial.get("returnOnAssets"))),
        ],
    )
    if profitability:
        basic_sections.append(profitability)

    if market_hours:
        basic_sections.append(
            {
                "title": "Horario del mercado",
                "fields": [{"label": "Zona horaria", "value": str(market_hours)}],
            },
        )

    dividend_summary = _section(
        "Resumen",
        [
            _field("Dividendo anual", _raw(detail.get("dividendRate"))),
            _field("Rentabilidad por dividendo", _raw(detail.get("dividendYield"))),
            _field("Ratio de reparto", _raw(detail.get("payoutRatio"))),
            _field("Ex-dividendo", _raw(detail.get("exDividendDate"))),
        ],
    )
    dividend_upcoming = _section(
        "Próximos",
        [
            _field("Fecha dividendo", _raw(calendar.get("dividendDate"))),
            _field("Ex-dividendo", _raw(calendar.get("exDividendDate"))),
        ],
    )
    dividend_sections = [section for section in (dividend_summary, dividend_upcoming) if section]

    fundamentals = build_fundamentals_snapshot(yahoo_modules=yahoo_modules)
    statement_pack = extract_statement_pack(yahoo_modules)

    financial_sections: list[dict[str, Any]] = []
    market_data = _section(
        "Datos de mercado",
        [
            _field("Precio actual", _raw(financial.get("currentPrice") or detail.get("regularMarketPrice"))),
            _field("Apertura", _raw(detail.get("open"))),
            _field("Máximo día", _raw(detail.get("dayHigh"))),
            _field("Mínimo día", _raw(detail.get("dayLow"))),
            _field("Volumen", _raw(detail.get("volume"))),
            _field("Volumen medio", _raw(detail.get("averageVolume"))),
            _field("Máx. 52 sem.", _raw(detail.get("fiftyTwoWeekHigh"))),
            _field("Mín. 52 sem.", _raw(detail.get("fiftyTwoWeekLow"))),
        ],
    )
    valuation = _section(
        "Valoración",
        [
            _field("Capitalización", _raw(detail.get("marketCap"))),
            _field("Valor empresa", _raw(stats.get("enterpriseValue"))),
            _field("PER", _raw(detail.get("trailingPE"))),
            _field("PER forward", _raw(detail.get("forwardPE"))),
            _field("PEG", _raw(stats.get("pegRatio"))),
            _field("Precio/Valor contable", _raw(stats.get("priceToBook"))),
            _field("Objetivo alto", _raw(financial.get("targetHighPrice"))),
            _field("Objetivo bajo", _raw(financial.get("targetLowPrice"))),
            _field("Recomendación", financial.get("recommendationKey")),
        ],
    )
    strength = _section(
        "Solidez financiera",
        [
            _field("Caja total", _raw(financial.get("totalCash"))),
            _field("Deuda total", _raw(financial.get("totalDebt"))),
            _field("Deuda/Equity", _raw(financial.get("debtToEquity"))),
            _field("Current ratio", _raw(financial.get("currentRatio"))),
            _field("Altman Z", fundamentals.get("altmanZ")),
            _field("EBITDA", _raw(financial.get("ebitda"))),
            _field("Flujo caja libre", _raw(financial.get("freeCashflow"))),
            _field("Flujo operativo", _raw(financial.get("operatingCashflow"))),
        ],
    )
    fin_profitability = _section(
        "Rentabilidad",
        [
            _field("Margen bruto", _raw(financial.get("grossMargins"))),
            _field("Margen operativo", _raw(financial.get("operatingMargins"))),
            _field("Margen neto", _raw(financial.get("profitMargins"))),
            _field("Crecimiento ingresos", _raw(financial.get("revenueGrowth"))),
            _field("Crecimiento beneficio", _raw(financial.get("earningsGrowth"))),
            _field("ROE", _raw(financial.get("returnOnEquity"))),
            _field("ROA", _raw(financial.get("returnOnAssets"))),
        ],
    )
    for section in (market_data, valuation, strength, fin_profitability):
        if section:
            financial_sections.append(section)

    history = dividend_history or []

    return {
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "fundamentals": fundamentals,
        "statementPack": statement_pack,
        "basic": {"sections": basic_sections},
        "dividends": {
            "sections": dividend_sections,
            "history": history,
        },
        "financials": {"sections": financial_sections},
    }
