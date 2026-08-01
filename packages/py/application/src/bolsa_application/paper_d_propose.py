"""Paper D — propose + execute opcional vía ExecutionRouter.

Propose: Composite × universo (dry-run).
Execute: requiere ``PAPER_D_EXECUTE=1``, ``execute=true``, ``executionPolicyId``
modo ``paper_auto``. Distinto de radar (B) y Supervisado (C).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from bolsa_analytics.knowledge.composite_score import build_composite_card
from bolsa_analytics.signals.fundamental_screener import week_key_utc
from bolsa_application.scan_universe import resolve_scan_universe_instrument_ids
from bolsa_domain.repositories.instrument_repository import InstrumentRepository

PAPER_D_PROPOSE_VERSION = "paper_d_propose_v2"
PAPER_D_EXECUTE_ENV = "PAPER_D_EXECUTE"


class _ListRepo(Protocol):
    async def get_by_id(self, list_id: str) -> Any: ...


class _ExecutionRouter(Protocol):
    async def execute(self, policy_id: str, hits: list[dict[str, Any]]) -> Any: ...


class _PolicyRepo(Protocol):
    async def get_policy(self, policy_id: str) -> Any: ...


def paper_d_execute_allowed() -> bool:
    raw = (os.getenv(PAPER_D_EXECUTE_ENV) or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def build_paper_d_hits(
    eligible: list[dict[str, Any]],
    *,
    strategy_definition_id: str | None,
    prices: dict[str, float],
    plan_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Construye hits estilo scan para ``entry_long``. Returns (hits, skipped)."""
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    hits: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    strat = strategy_definition_id or "paper_d_unbound"
    for cand in eligible:
        iid = str(cand["instrumentId"])
        price = prices.get(iid)
        if price is None or price <= 0:
            skipped.append(
                {
                    "instrumentId": iid,
                    "ticker": cand.get("ticker"),
                    "reason": "Sin precio last_close para sizing",
                }
            )
            continue
        hits.append(
            {
                "instrumentId": iid,
                "symbol": cand.get("ticker") or iid,
                "scanId": plan_id,
                "signal": {
                    "id": f"pd-{plan_id}-{iid[:8]}",
                    "instrumentId": iid,
                    "timestamp": ts,
                    "kind": "entry_long",
                    "strategyDefinitionId": strat,
                    "strategyVersion": 1,
                    "barIndex": 0,
                    "price": float(price),
                    "presetKey": "paper_d",
                },
            }
        )
    return hits, skipped


def _route_result_to_dict(result: Any) -> dict[str, Any]:
    actions = []
    for a in getattr(result, "actions", []) or []:
        actions.append(
            {
                "instrumentId": a.instrument_id,
                "signalKind": a.signal_kind,
                "status": a.status,
                "reason": a.reason,
                "transactionId": a.transaction_id,
            }
        )
    return {
        "policyId": getattr(result, "policy_id", None),
        "mode": getattr(result, "mode", None),
        "actions": actions,
    }


class ProposePaperDPlan:
    """Rankea candidatos Composite; opcionalmente ejecuta paper_auto vía Router."""

    def __init__(
        self,
        instruments: InstrumentRepository,
        lists: _ListRepo,
        *,
        router: _ExecutionRouter | None = None,
        policies: _PolicyRepo | None = None,
    ) -> None:
        self._instruments = instruments
        self._lists = lists
        self._router = router
        self._policies = policies

    async def _resolve_prices(self, instrument_ids: list[str]) -> dict[str, float]:
        getter = getattr(self._instruments, "get_quotes_by_ids", None)
        if getter is None or not instrument_ids:
            return {}
        metas = await getter(instrument_ids)
        out: dict[str, float] = {}
        for meta in metas or []:
            close = getattr(meta, "last_close", None)
            mid = getattr(meta, "id", None)
            if mid and close is not None and float(close) > 0:
                out[str(mid)] = float(close)
        return out

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        universe = payload.get("universe") or {}
        list_id = universe.get("listId")
        instrument_ids = universe.get("instrumentIds")
        horizon = payload.get("horizon") or "swing"
        if horizon not in {"intraday", "swing", "position", "long_term"}:
            horizon = "swing"
        regime = payload.get("regime") or "neutral"
        if regime not in {"risk_on", "neutral", "risk_off", "crisis", "uncertain"}:
            regime = "neutral"

        min_display = int(payload.get("minScoreDisplay100") or 55)
        min_display = max(0, min(100, min_display))
        respect_veto = payload.get("respectVetoNewLong", True) is not False
        max_candidates = int(payload.get("maxCandidates") or 25)
        max_candidates = max(1, min(max_candidates, 100))
        execute_requested = payload.get("execute") is True
        execute_env = paper_d_execute_allowed()
        policy_id = (payload.get("executionPolicyId") or "").strip() or None

        resolved = await resolve_scan_universe_instrument_ids(
            self._lists,  # type: ignore[arg-type]
            list_id=list_id,
            instrument_ids=instrument_ids,
            async_job=False,
        )

        candidates: list[dict[str, Any]] = []
        notes: list[str] = [
            f"{PAPER_D_PROPOSE_VERSION}: Composite × universo",
            "Distinto de radar (B) y Supervisado Proponer (C).",
        ]

        for instrument_id in resolved:
            instrument = await self._instruments.get_by_id(instrument_id)
            if instrument is None:
                candidates.append(
                    {
                        "instrumentId": instrument_id,
                        "ticker": instrument_id,
                        "status": "skipped",
                        "combinedScore": None,
                        "scoreDisplay100": None,
                        "confidence": None,
                        "regime": regime,
                        "vetoNewLong": False,
                        "reason": "Instrumento no encontrado",
                    }
                )
                continue

            ticker = str(getattr(instrument, "symbol", None) or instrument_id)
            fundamentals = await self._instruments.get_fundamentals(instrument_id)
            card = build_composite_card(
                instrument_id=instrument_id,
                ticker=ticker,
                fundamentals=fundamentals,
                horizon=horizon,  # type: ignore[arg-type]
                regime=regime,  # type: ignore[arg-type]
            )
            display = card.get("scoreDisplay100")
            combined = card.get("combinedScore")
            meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
            weights = card.get("weights") if isinstance(card.get("weights"), dict) else {}
            veto = bool(weights.get("vetoNewLong"))
            confidence = meta.get("confidence")

            status = "eligible"
            reason: str | None = None
            if display is None and combined is None:
                status = "missing_composite"
                reason = "Sin Composite (faltan datos)"
            elif respect_veto and veto:
                status = "vetoed_regime"
                reason = "WeightRules veto_new_long"
            elif display is not None and int(display) < min_display:
                status = "below_threshold"
                reason = f"scoreDisplay100 {display} < {min_display}"

            candidates.append(
                {
                    "instrumentId": instrument_id,
                    "ticker": ticker,
                    "status": status,
                    "combinedScore": combined,
                    "scoreDisplay100": display,
                    "confidence": confidence,
                    "regime": meta.get("regime") or regime,
                    "vetoNewLong": veto,
                    "reason": reason,
                }
            )

        eligible = [c for c in candidates if c["status"] == "eligible"]
        eligible.sort(
            key=lambda c: (
                -(c["scoreDisplay100"] if c["scoreDisplay100"] is not None else -1),
                str(c.get("ticker") or ""),
            )
        )
        eligible = eligible[:max_candidates]

        others = [c for c in candidates if c["status"] != "eligible"]
        others.sort(key=lambda c: str(c.get("ticker") or ""))
        ordered = eligible + others[: max(0, 40 - len(eligible))]

        plan_id = f"pd_{uuid4().hex[:12]}"
        execution: dict[str, Any] | None = None
        execute_status = "dry_run"

        if execute_requested and not execute_env:
            execute_status = "blocked_env"
            notes.append(
                f"execute=true bloqueado: define {PAPER_D_EXECUTE_ENV}=1"
            )
        elif execute_requested and execute_env:
            if not policy_id:
                raise ValueError("executionPolicyId requerido cuando execute=true")
            if self._router is None or self._policies is None:
                raise ValueError("ExecutionRouter no configurado")
            policy = await self._policies.get_policy(policy_id)
            if policy is None:
                raise ValueError("Política de ejecución no encontrada")
            if not getattr(policy, "enabled", False):
                raise ValueError("Política de ejecución deshabilitada")
            if getattr(policy, "mode", None) != "paper_auto":
                raise ValueError("Paper D execute requiere mode=paper_auto")
            kinds = set((policy.definition or {}).get("signalKinds") or [])
            if "entry_long" not in kinds:
                raise ValueError("La política debe permitir signalKind entry_long")

            prices = await self._resolve_prices([str(c["instrumentId"]) for c in eligible])
            hits, price_skips = build_paper_d_hits(
                eligible,
                strategy_definition_id=getattr(policy, "strategy_definition_id", None),
                prices=prices,
                plan_id=plan_id,
            )
            if price_skips:
                notes.append(f"Sin precio: {len(price_skips)} elegible(s) omitidos")
            if not hits:
                execute_status = "executed"
                execution = {
                    "policyId": policy_id,
                    "mode": "paper_auto",
                    "actions": [],
                    "priceSkips": price_skips,
                }
                notes.append("Ningún hit con precio válido; no se llamó al Router.")
            else:
                route = await self._router.execute(policy_id, hits)
                execution = _route_result_to_dict(route)
                execution["priceSkips"] = price_skips
                execution["hitCount"] = len(hits)
                execute_status = "executed"
                notes.append(
                    f"ExecutionRouter paper_auto: {len(hits)} hit(s) enviados "
                    f"(Gate cognitivo aplica)."
                )
        else:
            notes.append("Modo dry-run (execute=false).")

        return {
            "proposeVersion": PAPER_D_PROPOSE_VERSION,
            "planId": plan_id,
            "weekKey": week_key_utc(),
            "scannedCount": len(resolved),
            "eligibleCount": len(eligible),
            "candidates": ordered,
            "rankingReady": True,
            "executeAllowedByEnv": execute_env,
            "executeRequested": execute_requested,
            "executeStatus": execute_status,
            "execution": execution,
            "notes": notes,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
        }
