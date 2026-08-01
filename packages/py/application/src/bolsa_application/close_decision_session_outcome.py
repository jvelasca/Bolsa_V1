"""Cerrar DecisionSession con Outcome (manual o auto_mark desde OHLCV)."""

from __future__ import annotations

from typing import Any, Protocol

from bolsa_analytics.cognitive.decision_outcome import (
    OutcomeVerdict,
    SessionOutcome,
    attach_outcome_to_payload,
    build_manual_outcome,
    build_outcome_from_prices,
    eval_bars_for_horizon,
    extract_decision_price,
    extract_recommended_action,
    resolve_eval_price_from_bars,
    summarize_session_outcomes,
)
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


class _SessionStore(Protocol):
    async def get_decision_session(self, session_id: str) -> DecisionSessionRecord | None: ...

    async def update_decision_session(
        self, record: DecisionSessionRecord
    ) -> DecisionSessionRecord: ...

    async def list_decision_sessions(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionSessionRecord]: ...


class _OhlcvPort(Protocol):
    async def get_bars(
        self, instrument_id: str, *, timeframe: Any = ..., limit: int = ...
    ) -> list[Any]: ...


class CloseDecisionSessionOutcome:
    """Adjunta Outcome al payload Session y marca status=closed."""

    def __init__(self, store: _SessionStore, ohlcv: _OhlcvPort | None = None) -> None:
        self._store = store
        self._ohlcv = ohlcv

    async def execute(
        self,
        session_id: str,
        *,
        mode: str = "auto",
        verdict: OutcomeVerdict | None = None,
        return_pct: float | None = None,
        price_at_eval: float | None = None,
        notes: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        rec = await self._store.get_decision_session(session_id)
        if rec is None or not rec.payload:
            raise ValueError(f"DecisionSession no encontrada: {session_id}")

        payload = dict(rec.payload)
        if payload.get("outcome") and not force:
            raise ValueError("Session ya tiene Outcome; usa force=true para sobrescribir")

        action = extract_recommended_action(payload)
        horizon = payload.get("horizon")
        hz = horizon if isinstance(horizon, str) else "swing"

        outcome: SessionOutcome
        if mode == "manual":
            if verdict is None:
                raise ValueError("mode=manual requiere verdict")
            price_dec = extract_decision_price(payload)
            outcome = build_manual_outcome(
                action=action,
                horizon=hz,
                verdict=verdict,
                return_pct=return_pct,
                price_at_decision=price_dec,
                price_at_eval=price_at_eval,
                notes=notes,
            )
        else:
            price_dec = extract_decision_price(payload)
            mature = True
            bars_elapsed: int | None = None
            resolved_notes = notes
            eval_price = price_at_eval
            if eval_price is None and self._ohlcv is not None:
                resolved = await self._resolve_eval_from_ohlcv(
                    instrument_id=rec.instrument_id,
                    session_payload=payload,
                    price_at_decision=price_dec,
                )
                eval_price = resolved["price"]
                mature = bool(resolved["mature"])
                bars_elapsed = int(resolved["barsElapsed"])
                auto_note = str(resolved["notes"] or "")
                resolved_notes = f"{notes}; {auto_note}" if notes else auto_note
            outcome = build_outcome_from_prices(
                action=action,
                horizon=hz,
                price_at_decision=price_dec,
                price_at_eval=eval_price,
                source="auto_mark",
                notes=resolved_notes,
                mature=mature,
                bars_elapsed=bars_elapsed,
            )

        next_payload = attach_outcome_to_payload(payload, outcome, close=True)
        updated = DecisionSessionRecord(
            id=rec.id,
            kind=rec.kind,
            status="closed",
            instrument_id=rec.instrument_id,
            created_at=rec.created_at,
            account_id=rec.account_id,
            symbol=rec.symbol,
            recommendation_id=rec.recommendation_id,
            decision_id=rec.decision_id,
            payload=next_payload,
        )
        saved = await self._store.update_decision_session(updated)
        return saved.payload or next_payload

    async def _resolve_eval_from_ohlcv(
        self,
        *,
        instrument_id: str,
        session_payload: dict[str, Any],
        price_at_decision: float | None,
    ) -> dict[str, Any]:
        assert self._ohlcv is not None
        from bolsa_domain.value_objects.timeframe import TimeFrame

        horizon = session_payload.get("horizon")
        need = eval_bars_for_horizon(horizon if isinstance(horizon, str) else None)
        decision_at = session_payload.get("createdAt")
        if not isinstance(decision_at, str):
            decision_at = None

        bars = await self._ohlcv.get_bars(
            instrument_id, timeframe=TimeFrame.D1, limit=max(need + 80, 100)
        )
        return resolve_eval_price_from_bars(
            bars,
            horizon=horizon if isinstance(horizon, str) else None,
            decision_at=decision_at,
            price_at_decision=price_at_decision,
        )


class LoadSessionLearningSummary:
    """Hit-rate agregado de Sessions cerradas (Learning v1)."""

    def __init__(self, store: _SessionStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        account_id: str | None = None,
        instrument_id: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        rows = await self._store.list_decision_sessions(
            limit=limit,
            account_id=account_id,
            instrument_id=instrument_id,
        )
        payloads = [r.payload for r in rows if r.payload]
        return summarize_session_outcomes(payloads)
