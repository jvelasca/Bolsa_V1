"""Búsqueda / constitutivos / suscripción / sync de índices (capas A–C)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from bolsa_application.import_instrument import ImportInstrument
from bolsa_infrastructure.database.repositories.index_subscribe_job_repository import (
    IndexSubscribeJobRecord,
    SqlAlchemyIndexSubscribeJobRepository,
)
from bolsa_infrastructure.database.repositories.instrument_repository import (
    SqlAlchemyInstrumentRepository,
)
from bolsa_infrastructure.database.repositories.list_repository import (
    InstrumentListDetail,
    InstrumentListSummary,
    SqlAlchemyListRepository,
)
from bolsa_market.indices import (
    ConstituentSet,
    IndexHit,
    catalog_list_id_for_index,
    default_constituent_provider,
    discover_market_indices,
    get_known_index,
    index_code_from_catalog_list_id,
    index_constituents_ready,
)
from bolsa_market.indices.registry import KNOWN_INDICES
from bolsa_market.yahoo_client import get_yahoo_finance_client, normalize_yahoo_error

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


def _exchange_currency_for_yahoo(yahoo_symbol: str) -> tuple[str, str]:
    """Heurística de mercado para import (no es provider de constitutivos)."""
    y = yahoo_symbol.strip().upper()
    if y.endswith((".MC", ".MA")):
        return "BME", "EUR"
    if y.endswith(".DE"):
        return "XETRA", "EUR"
    if y.endswith((".PA", ".AS", ".BR", ".MI", ".HE", ".ST", ".LS", ".VI", ".IR")):
        return "UNKNOWN", "EUR"
    if y.endswith((".L", ".LON")):
        return "LSE", "GBP"
    if y.endswith(".HK"):
        return "HKEX", "HKD"
    return "UNKNOWN", "USD"

@dataclass(frozen=True, slots=True)
class SearchMarketIndicesResult:
    hits: list[IndexHit]

@dataclass(frozen=True, slots=True)
class CatalogIndexEntry:
    code: str
    display_name: str
    yahoo_symbol: str
    region: str
    currency: str
    constituent_ready: bool
    expected_count_min: int
    expected_count_max: int
    list_id: str

@dataclass(frozen=True, slots=True)
class SubscribeProgress:
    total: int
    already_present: int
    imported: int
    failed: tuple[str, ...] = ()
    joined: tuple[str, ...] = ()
    left: tuple[str, ...] = ()
    checked: int = 0

@dataclass(frozen=True, slots=True)
class SubscribeMarketIndexResult:
    list_id: str
    index_code: str
    display_name: str
    yahoo_index_symbol: str
    content_hash: str
    instrument_ids: list[str]
    progress: SubscribeProgress
    status: str
    list_detail: InstrumentListDetail

class SearchMarketIndices:
    async def execute(self, query: str, *, limit: int = 12) -> SearchMarketIndicesResult:
        client = get_yahoo_finance_client()

        async def search_fn(q: str, *, quotes_count: int = 10) -> list[dict]:
            try:
                return await client.search_quotes(q, quotes_count=quotes_count)
            except Exception as exc:
                _ = normalize_yahoo_error(exc)
                return []

        hits = await discover_market_indices(query, search_fn=search_fn, limit=limit)
        return SearchMarketIndicesResult(hits=hits)

class ListMarketIndexCatalog:
    """Catálogo fijo de índices bursátiles estándar (lista de listas)."""

    def execute(self) -> list[CatalogIndexEntry]:
        return [
            CatalogIndexEntry(
                code=known.code,
                display_name=known.display_name,
                yahoo_symbol=known.yahoo_symbol,
                region=known.region,
                currency=known.currency,
                constituent_ready=index_constituents_ready(known.code),
                expected_count_min=known.expected_count_min,
                expected_count_max=known.expected_count_max,
                list_id=catalog_list_id_for_index(known.code),
            )
            for known in KNOWN_INDICES.values()
        ]

class ResolveIndexConstituents:
    async def execute(self, index_code_or_yahoo: str) -> ConstituentSet | None:
        return await default_constituent_provider().resolve(index_code_or_yahoo)

class SubscribeMarketIndex:
    def __init__(
        self,
        list_repo: SqlAlchemyListRepository,
        instrument_repo: SqlAlchemyInstrumentRepository,
        import_use_case: ImportInstrument,
    ) -> None:
        self._list_repo = list_repo
        self._instruments = instrument_repo
        self._import = import_use_case

    async def execute(
        self,
        index_key: str,
        *,
        sync_bars: bool = False,
        years_back: int = 2,
        on_progress: ProgressCallback | None = None,
    ) -> SubscribeMarketIndexResult:
        known = get_known_index(index_key)
        constituents = await default_constituent_provider().resolve(index_key)
        if constituents is None:
            label = known.display_name if known else index_key
            raise ValueError(
                f"Constituents no disponibles aún para «{label}». "
                "Revisa provider del catálogo (IBEX curado; SPX/OEX/DAX/NDX/STOXX remoto).",
            )

        display_name = known.display_name if known else constituents.index_code
        list_id = catalog_list_id_for_index(constituents.index_code)
        total = len(constituents.members)

        if on_progress:
            await on_progress(
                {
                    "phase": "resolve",
                    "indexCode": constituents.index_code,
                    "checked": 0,
                    "total": total,
                    "alreadyPresent": 0,
                    "imported": 0,
                    "failed": [],
                },
            )

        existing_list = await self._list_repo.get_by_id(list_id)
        if existing_list is None and constituents.index_code == "IBEX35":
            for summary in await self._list_repo.list_all():
                if summary.source == "catalog" and summary.name == "IBEX 35":
                    existing_list = await self._list_repo.get_by_id(summary.id)
                    if existing_list is not None:
                        list_id = existing_list.id
                    break

        old_ids = set(existing_list.instrument_ids) if existing_list else set()
        already = 0
        imported = 0
        failed: list[str] = []

        for idx, member in enumerate(constituents.members, start=1):
            existing = await self._instruments.get_by_yahoo_symbol(member.yahoo_symbol)
            if existing is not None:
                already += 1
            else:
                try:
                    exchange, currency = _exchange_currency_for_yahoo(member.yahoo_symbol)
                    result = await self._import.execute(
                        yahoo_symbol=member.yahoo_symbol,
                        symbol=member.symbol,
                        name=member.name or member.symbol,
                        exchange=exchange,
                        currency=currency,
                        sync=sync_bars,
                        years_back=years_back,
                    )
                    if result is None:
                        failed.append(member.yahoo_symbol)
                    else:
                        imported += 1
                except Exception as exc:
                    failed.append(f"{member.yahoo_symbol}: {exc}")

            if on_progress and (idx == total or idx % 5 == 0 or idx == 1):
                await on_progress(
                    {
                        "phase": "hydrate",
                        "indexCode": constituents.index_code,
                        "checked": idx,
                        "total": total,
                        "alreadyPresent": already,
                        "imported": imported,
                        "failed": failed[-8:],
                        "currentSymbol": member.yahoo_symbol,
                    },
                )

        by_yahoo = await self._instruments.get_ids_by_yahoo_symbols(constituents.yahoo_symbols)
        ordered_ids = [
            by_yahoo[m.yahoo_symbol]
            for m in constituents.members
            if m.yahoo_symbol in by_yahoo
        ]
        new_ids = set(ordered_ids)
        joined_ids = tuple(sorted(new_ids - old_ids))
        left_ids = tuple(sorted(old_ids - new_ids))
        changelog = {
            "at": datetime.now(UTC).isoformat(),
            "joined": list(joined_ids)[:40],
            "left": list(left_ids)[:40],
            "joinedCount": len(joined_ids),
            "leftCount": len(left_ids),
        }

        if existing_list is None:
            detail = await self._list_repo.create(
                name=display_name,
                source="catalog",
                instrument_ids=ordered_ids,
                list_id=list_id,
                kind="linked_universe",
                universe_code=constituents.index_code,
                last_synced_at=datetime.now(UTC),
                content_hash=constituents.content_hash,
                membership_changelog=changelog,
            )
        else:
            if existing_list.instrument_ids != ordered_ids:
                await self._list_repo.replace_catalog_membership(list_id, ordered_ids)
            if existing_list.name != display_name:
                await self._list_repo.update(list_id, name=display_name)
            detail = await self._list_repo.mark_universe_sync(
                list_id,
                universe_code=constituents.index_code,
                content_hash=constituents.content_hash,
                membership_changelog=changelog,
            )
            assert detail is not None

        progress = SubscribeProgress(
            total=total,
            already_present=already,
            imported=imported,
            failed=tuple(failed),
            joined=joined_ids,
            left=left_ids,
            checked=total,
        )
        status = "ready" if not failed and len(ordered_ids) == progress.total else "partial"
        return SubscribeMarketIndexResult(
            list_id=detail.id,
            index_code=constituents.index_code,
            display_name=display_name,
            yahoo_index_symbol=constituents.yahoo_index_symbol,
            content_hash=constituents.content_hash,
            instrument_ids=list(detail.instrument_ids),
            progress=progress,
            status=status,
            list_detail=detail,
        )

class SyncSubscribedCatalogIndices:
    def __init__(self, subscribe: SubscribeMarketIndex, list_repo: SqlAlchemyListRepository) -> None:
        self._subscribe = subscribe
        self._list_repo = list_repo

    async def execute(self, *, sync_bars: bool = False) -> list[SubscribeMarketIndexResult]:
        summaries: list[InstrumentListSummary] = await self._list_repo.list_all()
        results: list[SubscribeMarketIndexResult] = []
        seen_codes: set[str] = set()
        for summary in summaries:
            if summary.source != "catalog" and summary.kind != "linked_universe":
                continue
            code = summary.universe_code or index_code_from_catalog_list_id(summary.id)
            if code is None and summary.name.strip().upper() in {"IBEX 35", "IBEX35"}:
                code = "IBEX35"
            if code is None or code in seen_codes:
                continue
            if await default_constituent_provider().resolve(code) is None:
                continue
            seen_codes.add(code)
            try:
                results.append(await self._subscribe.execute(code, sync_bars=sync_bars, years_back=2))
            except Exception:
                continue
        return results

class EnqueueIndexSubscribeJob:
    def __init__(self, jobs: SqlAlchemyIndexSubscribeJobRepository) -> None:
        self._jobs = jobs

    async def execute(
        self,
        *,
        index_key: str,
        sync_bars: bool = False,
        years_back: int = 2,
    ) -> IndexSubscribeJobRecord:
        return await self._jobs.create(
            payload={"indexKey": index_key, "syncBars": sync_bars, "yearsBack": years_back},
        )

class ProcessIndexSubscribeJob:
    def __init__(
        self,
        jobs: SqlAlchemyIndexSubscribeJobRepository,
        subscribe: SubscribeMarketIndex,
    ) -> None:
        self._jobs = jobs
        self._subscribe = subscribe

    async def execute(self, job_id: str | None = None) -> IndexSubscribeJobRecord | None:
        record = await (self._jobs.claim_by_id(job_id) if job_id else self._jobs.claim_next())
        if record is None:
            return None

        payload = record.payload
        index_key = str(payload.get("indexKey") or "")
        sync_bars = bool(payload.get("syncBars") or False)
        years_back = int(payload.get("yearsBack") or 2)

        async def on_progress(progress: dict[str, Any]) -> None:
            await self._jobs.update_progress(record.id, progress)
            await self._jobs._session.commit()  # noqa: SLF001

        try:
            result = await self._subscribe.execute(
                index_key,
                sync_bars=sync_bars,
                years_back=years_back,
                on_progress=on_progress,
            )
            return await self._jobs.mark_completed(
                record.id,
                {
                    "listId": result.list_id,
                    "indexCode": result.index_code,
                    "displayName": result.display_name,
                    "yahooIndexSymbol": result.yahoo_index_symbol,
                    "contentHash": result.content_hash,
                    "instrumentIds": result.instrument_ids,
                    "status": result.status,
                    "checked": result.progress.checked,
                    "total": result.progress.total,
                    "alreadyPresent": result.progress.already_present,
                    "imported": result.progress.imported,
                    "failed": list(result.progress.failed),
                    "joined": list(result.progress.joined),
                    "left": list(result.progress.left),
                },
            )
        except Exception as exc:
            return await self._jobs.mark_failed(record.id, str(exc))

class GetIndexSubscribeJob:
    def __init__(self, jobs: SqlAlchemyIndexSubscribeJobRepository) -> None:
        self._jobs = jobs

    async def execute(self, job_id: str) -> IndexSubscribeJobRecord | None:
        return await self._jobs.get(job_id)
