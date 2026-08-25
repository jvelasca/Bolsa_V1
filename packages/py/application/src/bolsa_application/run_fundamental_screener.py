"""Caso de uso F4 — Screener FA (universo × gate → hits; persist opcional)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_analytics.signals.fundamental_gate import (
    definition_has_fundamental_gate,
    fundamental_gate_max_age_days,
)
from bolsa_analytics.signals.fundamental_screener import (
    FUNDAMENTAL_SCREENER_VERSION,
    assemble_screener_result,
    evaluate_fundamental_candidate,
    week_key_utc,
)
from bolsa_domain.repositories.instrument_repository import InstrumentRepository

from bolsa_application.refresh_instrument_fundamentals import RefreshFundamentalsBatch
from bolsa_application.scan_universe import resolve_scan_universe_instrument_ids


class _ListRepo(Protocol):
    async def get_by_id(self, list_id: str) -> Any: ...

    async def create(
        self,
        *,
        name: str,
        source: str,
        instrument_ids: list[str],
        list_id: str | None = None,
        kind: str | None = None,
        universe_code: str | None = None,
        last_synced_at: datetime | None = None,
        content_hash: str | None = None,
        membership_changelog: dict[str, Any] | None = None,
    ) -> Any: ...

    async def update(
        self,
        list_id: str,
        *,
        name: str | None = None,
        instrument_ids: list[str] | None = None,
    ) -> Any: ...


class RunFundamentalScreener:
    """
    Solo gate fundamental (sin barras / technical_rating).
    Opcionalmente materializa hits en una lista ``kind=snapshot``.
    """

    def __init__(
        self,
        instruments: InstrumentRepository,
        lists: _ListRepo,
        *,
        refresher: RefreshFundamentalsBatch | None = None,
    ) -> None:
        self._instruments = instruments
        self._lists = lists
        self._refresher = refresher

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        universe = payload.get("universe") or {}
        list_id = universe.get("listId")
        instrument_ids = universe.get("instrumentIds")
        gate = payload.get("fundamentalGate")
        if not isinstance(gate, dict):
            raise ValueError("fundamentalGate requerido")

        definition = {"hybrid": {"fundamentalGate": gate}, "kind": "fundamental_screener"}
        if not definition_has_fundamental_gate(definition):
            raise ValueError("fundamentalGate vacío (condiciones o sectores)")

        max_results = int(payload.get("maxResults") or 100)
        max_results = max(1, min(max_results, 500))
        refresh_stale = payload.get("refreshStale", True) is not False

        resolved = await resolve_scan_universe_instrument_ids(
            self._lists,  # type: ignore[arg-type]
            list_id=list_id,
            instrument_ids=instrument_ids,
            async_job=False,
        )

        refreshed = 0
        if refresh_stale and self._refresher is not None:
            max_age = fundamental_gate_max_age_days(definition)
            batch = await self._refresher.execute(
                resolved, max_age_days=max_age, only_stale=True
            )
            refreshed = int(getattr(batch, "refreshed_count", 0) or 0)

        hits: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for instrument_id in resolved:
            instrument = await self._instruments.get_by_id(instrument_id)
            if instrument is None:
                skipped.append(
                    {
                        "instrumentId": instrument_id,
                        "symbol": None,
                        "reason": "Instrumento no encontrado",
                    }
                )
                continue
            symbol = str(getattr(instrument, "symbol", None) or instrument_id)
            name = getattr(instrument, "name", None)
            fundamentals = await self._instruments.get_fundamentals(instrument_id)
            hit, skip = evaluate_fundamental_candidate(
                instrument_id=instrument_id,
                symbol=symbol,
                name=str(name) if name else None,
                fundamentals=fundamentals,
                gate=gate,
            )
            if hit is not None:
                hits.append(hit)
            elif skip is not None:
                skipped.append(skip)

        # Orden: Score_FUND display desc, luego símbolo (None/incorrecto → -1 → 1 asc).
        hits.sort(
            key=lambda h: (
                -(h["scoreDisplay100"])
                if isinstance(h.get("scoreDisplay100"), (int, float))
                else 1,
                str(h.get("symbol") or ""),
            )
        )

        persisted_list_id: str | None = None
        persist = payload.get("persist")
        if isinstance(persist, dict) and hits:
            persisted_list_id = await self._persist_whitelist(
                persist,
                [str(h["instrumentId"]) for h in hits[:max_results]],
            )

        return assemble_screener_result(
            hits=hits,
            skipped=skipped,
            scanned_count=len(resolved),
            refreshed_count=refreshed,
            list_id=list_id,
            persisted_list_id=persisted_list_id,
            max_results=max_results,
        )

    async def _persist_whitelist(
        self,
        persist: dict[str, Any],
        instrument_ids: list[str],
    ) -> str:
        existing_id = (persist.get("listId") or "").strip() or None
        week = week_key_utc()
        default_name = f"FA whitelist {week}"
        name = (persist.get("name") or "").strip() or default_name

        if existing_id:
            detail = await self._lists.update(
                existing_id, name=name, instrument_ids=instrument_ids
            )
            if detail is None:
                raise ValueError(f"Lista {existing_id} no encontrada")
            return existing_id

        created = await self._lists.create(
            name=name,
            source="custom",
            instrument_ids=instrument_ids,
            kind="snapshot",
            universe_code=f"fa_whitelist_{week}",
            last_synced_at=datetime.now(UTC),
            membership_changelog={
                "source": FUNDAMENTAL_SCREENER_VERSION,
                "weekKey": week,
                "hitCount": len(instrument_ids),
            },
        )
        return str(created.id)
