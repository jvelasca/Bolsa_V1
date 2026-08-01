"""FIE F2b+ — cliente SEC EDGAR (submissions + documento primario).

Resuelve ticker → CIK, localiza el último 10-K/10-Q y descarga el primary
document. **Sin RAG / sin indexación vectorial.**

Requisitos SEC: cabecera ``User-Agent`` identificable
(``BOLSA_SEC_USER_AGENT``, p.ej. ``BolsaV1 research you@email.com``).

@see https://www.sec.gov/search-filings/edgar-application-programming-interfaces
@see docs/engineering/fundamental-intelligence-engine-2026-07-30.md
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

import httpx

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_DOC_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{document}"
)

DEFAULT_SEC_USER_AGENT = "BolsaV1 personal-research contact@localhost"
TICKER_CACHE_TTL_SEC = 6 * 3600

# Sufijos Yahoo de mercados no-US (no hay 10-K SEC).
_NON_US_YAHOO_SUFFIXES = frozenset(
    {
        "MC",
        "DE",
        "PA",
        "L",
        "MI",
        "AS",
        "SW",
        "TO",
        "AX",
        "HK",
        "T",
        "SA",
        "MX",
        "BR",
        "SS",
        "ST",
        "HE",
        "CO",
        "OL",
        "VI",
        "LS",
        "WA",
    }
)


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"p", "div", "br", "tr", "li", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", " ".join(self._chunks)).strip()


def html_to_text(html: str) -> str:
    """Extrae texto plano de HTML SEC (stdlib; sin BeautifulSoup)."""
    parser = _HtmlTextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", html)
    return parser.text()


def us_ticker_from_yahoo_symbol(yahoo_symbol: str) -> str | None:
    """
    Devuelve ticker US para EDGAR, o None si parece no-US.

    Acepta ``AAPL``, ``BRK.B``; rechaza ``SAN.MC``, ``AIR.PA``, etc.
    """
    raw = (yahoo_symbol or "").strip().upper()
    if not raw:
        return None
    if "." in raw:
        _base, suffix = raw.rsplit(".", 1)
        if suffix in _NON_US_YAHOO_SUFFIXES:
            return None
    return raw


def pad_cik(cik: int | str) -> str:
    return str(int(str(cik).strip())).zfill(10)


@dataclass(frozen=True, slots=True)
class SecFilingHit:
    """Metadatos del filing EDGAR listo para descargar."""

    cik: str
    ticker: str
    form: str
    accession_number: str
    primary_document: str
    filing_date: str
    company_name: str

    @property
    def accession_nodash(self) -> str:
        return self.accession_number.replace("-", "")

    @property
    def document_url(self) -> str:
        return ARCHIVE_DOC_URL.format(
            cik_int=int(self.cik),
            accession_nodash=self.accession_nodash,
            document=self.primary_document,
        )


class SecEdgarClient:
    """Cliente HTTP EDGAR (tickers + submissions + documento)."""

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._user_agent = (
            (user_agent or os.getenv("BOLSA_SEC_USER_AGENT") or DEFAULT_SEC_USER_AGENT).strip()
        )
        self._owned_client = client is None
        self._client = client
        self._ticker_map: dict[str, str] | None = None
        self._ticker_map_at = 0.0

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json,text/html,text/plain,*/*",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(45.0, connect=15.0),
                headers=self._headers(),
                follow_redirects=True,
            )
            self._owned_client = True
        return self._client

    async def aclose(self) -> None:
        if self._owned_client and self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def _get_json(self, url: str) -> Any:
        client = await self._get_client()
        resp = await client.get(url, headers=self._headers())
        if resp.status_code == 403:
            raise RuntimeError(
                "SEC EDGAR rechazó la petición (403). "
                "Configura BOLSA_SEC_USER_AGENT con un contacto real, "
                "p.ej. 'BolsaV1 research you@email.com'."
            )
        resp.raise_for_status()
        return resp.json()

    async def load_ticker_cik_map(self, *, force: bool = False) -> dict[str, str]:
        """Mapa ticker→CIK (10 dígitos). Cache en memoria."""
        now = time.time()
        if (
            not force
            and self._ticker_map is not None
            and (now - self._ticker_map_at) < TICKER_CACHE_TTL_SEC
        ):
            return self._ticker_map
        data = await self._get_json(COMPANY_TICKERS_URL)
        mapping: dict[str, str] = {}
        if isinstance(data, dict):
            for row in data.values():
                if not isinstance(row, dict):
                    continue
                ticker = str(row.get("ticker") or "").strip().upper()
                cik_raw = row.get("cik_str")
                if not ticker or cik_raw is None:
                    continue
                mapping[ticker] = pad_cik(cik_raw)
        self._ticker_map = mapping
        self._ticker_map_at = now
        return mapping

    async def resolve_cik(self, ticker: str) -> str | None:
        mapping = await self.load_ticker_cik_map()
        return mapping.get(ticker.strip().upper())

    def pick_latest_filing(
        self,
        submissions: dict[str, Any],
        *,
        form: str,
    ) -> SecFilingHit | None:
        """Elige el filing más reciente del form pedido en ``filings.recent``."""
        filings = submissions.get("filings") if isinstance(submissions, dict) else None
        recent = filings.get("recent") if isinstance(filings, dict) else None
        if not isinstance(recent, dict):
            return None
        forms = recent.get("form") or []
        accessions = recent.get("accessionNumber") or []
        documents = recent.get("primaryDocument") or []
        dates = recent.get("filingDate") or []
        if not (
            isinstance(forms, list)
            and isinstance(accessions, list)
            and isinstance(documents, list)
            and isinstance(dates, list)
        ):
            return None
        want = form.upper()
        cik = pad_cik(submissions.get("cik") or "")
        tickers = submissions.get("tickers") or []
        ticker = str(tickers[0]).upper() if isinstance(tickers, list) and tickers else ""
        name = str(submissions.get("name") or "")
        for i, f in enumerate(forms):
            if str(f).upper() != want:
                continue
            if i >= len(accessions) or i >= len(documents) or i >= len(dates):
                continue
            doc = str(documents[i] or "").strip()
            acc = str(accessions[i] or "").strip()
            if not doc or not acc:
                continue
            return SecFilingHit(
                cik=cik,
                ticker=ticker,
                form=want,
                accession_number=acc,
                primary_document=doc,
                filing_date=str(dates[i]),
                company_name=name,
            )
        return None

    async def fetch_submissions(self, cik: str) -> dict[str, Any]:
        url = SUBMISSIONS_URL.format(cik=pad_cik(cik))
        data = await self._get_json(url)
        if not isinstance(data, dict):
            raise RuntimeError("Respuesta submissions SEC inválida")
        return data

    async def download_document(self, hit: SecFilingHit) -> tuple[bytes, str]:
        """Descarga primary document; content-type inferido por extensión."""
        client = await self._get_client()
        resp = await client.get(hit.document_url, headers=self._headers())
        if resp.status_code == 403:
            raise RuntimeError(
                "SEC EDGAR rechazó la descarga del documento (403). "
                "Revisa BOLSA_SEC_USER_AGENT."
            )
        resp.raise_for_status()
        name = hit.primary_document.lower()
        if name.endswith(".htm") or name.endswith(".html"):
            ctype = "text/html"
        elif name.endswith(".txt"):
            ctype = "text/plain"
        elif name.endswith(".pdf"):
            ctype = "application/pdf"
        else:
            ctype = resp.headers.get("content-type") or "application/octet-stream"
        return resp.content, ctype

    async def fetch_latest_filing_bytes(
        self,
        *,
        yahoo_symbol: str,
        form: str = "10-K",
    ) -> tuple[SecFilingHit, bytes, str]:
        """
        Pipeline: ticker US → CIK → submissions → download.

        Raises ValueError for non-US / missing CIK / missing form.
        """
        ticker = us_ticker_from_yahoo_symbol(yahoo_symbol)
        if ticker is None:
            raise ValueError(
                f"El símbolo {yahoo_symbol!r} no parece US (SEC EDGAR). "
                "Usa un ticker USA (p.ej. AAPL) o sube el PDF/TXT manualmente."
            )
        cik = await self.resolve_cik(ticker)
        if not cik:
            raise ValueError(f"SEC no tiene CIK para el ticker {ticker}")
        submissions = await self.fetch_submissions(cik)
        hit = self.pick_latest_filing(submissions, form=form)
        if hit is None:
            raise ValueError(f"No hay filing {form} reciente en EDGAR para {ticker}")
        content, ctype = await self.download_document(hit)
        return hit, content, ctype


def document_bytes_to_extractable(
    content: bytes,
    content_type: str,
    original_name: str,
) -> tuple[bytes, str, str]:
    """
    Normaliza HTML SEC → texto UTF-8 para el filing store.

    Returns ``(bytes_to_store, content_type, store_name)``.
    """
    name_l = original_name.lower()
    ctype = (content_type or "").lower()
    is_html = "html" in ctype or name_l.endswith(".htm") or name_l.endswith(".html")
    if is_html:
        html = content.decode("utf-8", errors="replace")
        text = html_to_text(html)
        if not text:
            text = re.sub(r"<[^>]+>", " ", html)
        text = text.strip()
        return text.encode("utf-8"), "text/plain", f"{original_name}.txt"
    return content, content_type, original_name
