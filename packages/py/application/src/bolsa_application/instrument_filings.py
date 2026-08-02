"""Casos de uso F2b/F2b++ — filings locales, resumen y Q&A RAG (sin Score_FUND)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bolsa_analytics.knowledge.filing_ask import (
    build_filing_ask_variables,
    heuristic_filing_answer,
)
from bolsa_analytics.knowledge.filing_summary import (
    build_filing_summary_variables,
    heuristic_filing_summary,
)
from bolsa_domain.repositories.instrument_repository import InstrumentRepository
from bolsa_market.filing_rag import (
    FILING_RAG_VERSION,
    ensure_chunk_index,
    format_context_for_prompt,
    retrieve_chunks,
)
from bolsa_market.filing_store import (
    FILING_STORE_VERSION,
    delete_filing,
    find_filing_by_accession,
    get_filing,
    list_filings,
    prefer_summary_excerpt,
    read_filing_text,
    save_filing,
    update_filing_summary,
)
from bolsa_market.sec_edgar import SecEdgarClient, document_bytes_to_extractable


class InstrumentFilingsService:
    """CRUD metadatos/bytes en disco; exige que el instrumento exista en BD."""

    def __init__(
        self,
        instruments: InstrumentRepository,
        *,
        edgar: SecEdgarClient | None = None,
    ) -> None:
        self._instruments = instruments
        self._edgar = edgar

    async def list(self, instrument_id: str) -> dict[str, Any] | None:
        if await self._instruments.get_by_id(instrument_id) is None:
            return None
        return {
            "data": list_filings(instrument_id),
            "storeVersion": FILING_STORE_VERSION,
        }

    async def upload(
        self,
        instrument_id: str,
        *,
        kind: str,
        original_name: str,
        content_type: str,
        content: bytes,
    ) -> dict[str, Any] | None:
        if await self._instruments.get_by_id(instrument_id) is None:
            return None
        meta = save_filing(
            instrument_id=instrument_id,
            kind=kind,
            original_name=original_name,
            content_type=content_type,
            content=content,
            extra={"source": "upload"},
        )
        return {"data": meta}

    async def fetch_from_sec(
        self,
        instrument_id: str,
        *,
        kind: str = "10-K",
    ) -> dict[str, Any] | None:
        """
        F2b+ — descarga el último filing EDGAR y lo guarda en el almacén local.
        No escribe profile_snapshot.fundamentals ni Score_FUND.
        """
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None
        if kind not in ("10-K", "10-Q"):
            raise ValueError("SEC fetch solo soporta kind 10-K o 10-Q")

        yahoo_symbol = getattr(instrument, "yahoo_symbol", None) or getattr(
            instrument, "symbol", ""
        )
        client = self._edgar or SecEdgarClient()
        owned = self._edgar is None
        try:
            hit, content, ctype = await client.fetch_latest_filing_bytes(
                yahoo_symbol=str(yahoo_symbol),
                form=kind,
            )
        finally:
            if owned:
                await client.aclose()

        existing = find_filing_by_accession(instrument_id, hit.accession_number)
        if existing is not None:
            return {"data": existing, "deduped": True}

        store_bytes, store_ctype, store_name = document_bytes_to_extractable(
            content,
            ctype,
            hit.primary_document,
        )
        meta = save_filing(
            instrument_id=instrument_id,
            kind=kind,
            original_name=store_name[:256],
            content_type=store_ctype,
            content=store_bytes,
            extra={
                "source": "sec_edgar",
                "cik": hit.cik,
                "accessionNumber": hit.accession_number,
                "filingDate": hit.filing_date,
                "documentUrl": hit.document_url,
                "secTicker": hit.ticker,
                "companyName": hit.company_name,
            },
        )
        return {"data": meta, "deduped": False}

    async def delete(self, instrument_id: str, filing_id: str) -> bool | None:
        if await self._instruments.get_by_id(instrument_id) is None:
            return None
        return delete_filing(instrument_id, filing_id)


class SummarizeInstrumentFiling:
    """Resumen narrativo (Ollama o heurística). Persiste lastSummary solo en disco filings."""

    def __init__(self, instruments: InstrumentRepository) -> None:
        self._instruments = instruments

    async def execute(self, instrument_id: str, filing_id: str) -> dict[str, Any] | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None
        filing = get_filing(instrument_id, filing_id)
        if filing is None:
            return None

        text = read_filing_text(instrument_id, filing_id)
        excerpt = prefer_summary_excerpt(text or "")
        ticker = getattr(instrument, "symbol", None) or "—"
        sector = getattr(instrument, "sector", None)

        variables = build_filing_summary_variables(
            ticker=str(ticker),
            sector=str(sector) if sector else None,
            filing=filing,
            excerpt=excerpt,
        )
        heuristic = heuristic_filing_summary(
            ticker=str(ticker),
            filing=filing,
            text=text,
        )

        try:
            from bolsa_ai import get_default_proxy

            proxy = get_default_proxy()
            completion = proxy.complete_structured(
                prompt_template_id="prompt_filing_summary_v1",
                variables=variables,
            )
        except Exception:  # noqa: BLE001
            completion = None

        if completion is None:
            engine = "heuristic"
            payload = heuristic
            provider = None
            model = None
        else:
            payload_raw = completion.payload if isinstance(completion.payload, dict) else None
            paragraphs = payload_raw.get("paragraphs") if payload_raw else None
            if not isinstance(paragraphs, list) or len(paragraphs) < 1:
                payload = heuristic
            else:
                cleaned = [str(p).strip() for p in paragraphs if str(p).strip()][:3]
                while len(cleaned) < 3:
                    cleaned.append(heuristic["paragraphs"][len(cleaned)])
                disclaimer = (
                    str(payload_raw.get("disclaimer")).strip()
                    if payload_raw and payload_raw.get("disclaimer")
                    else heuristic["disclaimer"]
                )
                payload = {"paragraphs": cleaned, "disclaimer": disclaimer}
            engine = f"{completion.provider}_structured_v1"
            provider = completion.provider
            model = completion.model_name

        summary_meta = {
            "engine": engine,
            "paragraphs": payload["paragraphs"],
            "disclaimer": payload["disclaimer"],
            "summarizedAt": datetime.now(UTC).isoformat(),
            "provider": provider,
            "model": model,
        }
        updated = update_filing_summary(instrument_id, filing_id, summary_meta) or filing
        return {
            "engine": engine,
            "payload": payload,
            "provider": provider,
            "model": model,
            "filing": updated,
        }


class AskInstrumentFiling:
    """F2b++ — Q&A con retrieval TF-IDF local sobre el extracto del filing."""

    def __init__(self, instruments: InstrumentRepository) -> None:
        self._instruments = instruments

    async def execute(
        self,
        instrument_id: str,
        filing_id: str,
        question: str,
        *,
        top_k: int = 4,
    ) -> dict[str, Any] | None:
        instrument = await self._instruments.get_by_id(instrument_id)
        if instrument is None:
            return None
        filing = get_filing(instrument_id, filing_id)
        if filing is None:
            return None

        q = (question or "").strip()
        if not q:
            raise ValueError("question vacía")
        if len(q) > 800:
            raise ValueError("question supera 800 caracteres")

        index = ensure_chunk_index(instrument_id, filing_id)
        hits = retrieve_chunks(index or {"chunks": []}, q, top_k=top_k)
        context = format_context_for_prompt(hits)
        ticker = getattr(instrument, "symbol", None) or "—"
        sector = getattr(instrument, "sector", None)

        variables = build_filing_ask_variables(
            ticker=str(ticker),
            sector=str(sector) if sector else None,
            filing=filing,
            question=q,
            context=context,
        )
        heuristic = heuristic_filing_answer(
            ticker=str(ticker),
            question=q,
            hits=hits,
        )

        try:
            from bolsa_ai import get_default_proxy

            proxy = get_default_proxy()
            completion = proxy.complete_structured(
                prompt_template_id="prompt_filing_ask_v1",
                variables=variables,
            )
        except Exception:  # noqa: BLE001
            completion = None

        if completion is None:
            engine = "heuristic_rag"
            payload = heuristic
            provider = None
            model = None
        else:
            payload_raw = completion.payload if isinstance(completion.payload, dict) else None
            answer = str(payload_raw.get("answer") or "").strip() if payload_raw else ""
            if not answer:
                payload = heuristic
            else:
                disclaimer = (
                    str(payload_raw.get("disclaimer")).strip()
                    if payload_raw and payload_raw.get("disclaimer")
                    else heuristic["disclaimer"]
                )
                payload = {"answer": answer, "disclaimer": disclaimer}
            engine = f"{completion.provider}_rag_v1"
            provider = completion.provider
            model = completion.model_name

        return {
            "engine": engine,
            "indexVersion": FILING_RAG_VERSION,
            "payload": payload,
            "provider": provider,
            "model": model,
            "hits": hits,
            "filing": filing,
            "question": q,
        }
