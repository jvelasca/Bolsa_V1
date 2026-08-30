"""V1.33+ — Wire Estudio dictamen/alarma → hit AUTO (A-δ).

Produce hits con ``autoSource`` Estudio + TradePlan TRIGGERED (paridad SEMI).
Sizing libro / Paper D / Radar / Hoy = fuera de alcance.

Execute opcional: mismo gate ``PAPER_D_EXECUTE`` que Paper D (default off).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import uuid4

from bolsa_application.paper_d_propose import (
    PAPER_D_EXECUTE_ENV,
    paper_d_allowed_account_id,
    paper_d_execute_allowed,
)
from bolsa_infrastructure.alerts.estudio_opinion_email import map_opinion_to_channel

ESTUDIO_AUTO_PROPOSE_VERSION = "estudio_auto_propose_v1"

# Placeholder: propose exige qty>0; autoridad real = TradePlan TRIGGERED (A-β).
_PROPOSE_QTY_PLACEHOLDER = 1.0


class _OpinionLike(Protocol):
    instrument_id: str
    stance: str
    dictamen_stars: int
    as_of_bar_date: date


class _ProposePort(Protocol):
    async def execute(self, **kwargs: Any) -> Any: ...


class _ExecutionRouter(Protocol):
    async def execute(self, policy_id: str, hits: list[dict[str, Any]]) -> Any: ...


class _PolicyRepo(Protocol):
    async def get_policy(self, policy_id: str) -> Any: ...


class _OpinionQuery(Protocol):
    async def query(self, **kwargs: Any) -> list[Any]: ...


class _InstrumentLookup(Protocol):
    async def get_by_id(self, instrument_id: str) -> Any: ...


def resolve_estudio_auto_source(*, stance: str, dictamen_stars: int) -> str | None:
    """Map stance/stars → autoSource de apertura AUTO.

    Solo ``buy``. Alarma → ``estudio_alarma``; aviso → ``estudio_dictamen``.
    Silent / no-buy → None (no hit de apertura).
    """
    if str(stance).strip() != "buy":
        return None
    channel = map_opinion_to_channel(
        stance="buy",
        dictamen_stars=int(dictamen_stars),
    )
    if channel == "alarma":
        return "estudio_alarma"
    if channel == "aviso":
        return "estudio_dictamen"
    return None


def select_estudio_opening_candidates(
    rows: list[Any],
    *,
    max_candidates: int = 25,
) -> list[dict[str, Any]]:
    """Filtra opiniones accionables de apertura (buy aviso|alarma)."""
    out: list[dict[str, Any]] = []
    for row in rows:
        stance = str(getattr(row, "stance", "") or "")
        stars = int(getattr(row, "dictamen_stars", 0) or 0)
        auto_source = resolve_estudio_auto_source(stance=stance, dictamen_stars=stars)
        if auto_source is None:
            continue
        as_of = getattr(row, "as_of_bar_date", None)
        as_of_s = as_of.isoformat() if isinstance(as_of, date) else str(as_of or "")[:10]
        out.append(
            {
                "instrumentId": str(getattr(row, "instrument_id")),
                "stance": stance,
                "dictamenStars": stars,
                "autoSource": auto_source,
                "asOfBarDate": as_of_s,
                "channel": map_opinion_to_channel(stance=stance, dictamen_stars=stars),
            }
        )
    # Prefer alarma (★≥4) then higher stars.
    out.sort(
        key=lambda c: (
            0 if c["autoSource"] == "estudio_alarma" else 1,
            -int(c["dictamenStars"]),
            str(c["instrumentId"]),
        )
    )
    cap = max(1, min(int(max_candidates), 100))
    return out[:cap]


def build_estudio_auto_hit(
    *,
    instrument_id: str,
    symbol: str | None,
    auto_source: str,
    trade_plan: dict[str, Any],
    price: float,
    strategy_definition_id: str | None,
    plan_id: str,
    as_of: str,
    policy_id: str | None = None,
) -> dict[str, Any]:
    """Hit estilo scan para ``entry_long`` con autoSource Estudio + TradePlan."""
    ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    day = (as_of or "")[:10] or as_of_from_day(ts)
    pol = (policy_id or "estudio")[:8]
    iid_short = instrument_id[:8]
    strat = strategy_definition_id or "estudio_unbound"
    return {
        "instrumentId": instrument_id,
        "symbol": symbol or instrument_id,
        "scanId": plan_id,
        "autoSource": auto_source,
        "tradePlan": trade_plan,
        "signal": {
            "id": f"edo-{day}-{pol}-{iid_short}",
            "instrumentId": instrument_id,
            "timestamp": ts,
            "kind": "entry_long",
            "strategyDefinitionId": strat,
            "strategyVersion": 1,
            "barIndex": 0,
            "price": float(price),
            "presetKey": "estudio_auto",
        },
    }


def as_of_from_day(ts: str) -> str:
    from bolsa_application.auto_execute_idempotency import as_of_from_iso

    return as_of_from_iso(ts)


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


def _extract_trade_plan(propose_result: Any) -> dict[str, Any] | None:
    plan = getattr(propose_result, "trade_plan", None)
    if isinstance(plan, dict):
        return plan
    if isinstance(propose_result, dict):
        raw = propose_result.get("tradePlan") or propose_result.get("trade_plan")
        return raw if isinstance(raw, dict) else None
    return None


def _extract_last_close(propose_result: Any) -> float | None:
    close = getattr(propose_result, "last_close", None)
    if isinstance(close, (int, float)) and not isinstance(close, bool) and float(close) > 0:
        return float(close)
    if isinstance(propose_result, dict):
        raw = propose_result.get("lastClose")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool) and float(raw) > 0:
            return float(raw)
    return None


class ProposeEstudioAutoOpenings:
    """Lee dictámenes Estudio → propose SEMI → hits AUTO (dry-run o execute)."""

    def __init__(
        self,
        opinions: _OpinionQuery,
        propose: _ProposePort,
        *,
        instruments: _InstrumentLookup | None = None,
        router: _ExecutionRouter | None = None,
        policies: _PolicyRepo | None = None,
    ) -> None:
        self._opinions = opinions
        self._propose = propose
        self._instruments = instruments
        self._router = router
        self._policies = policies

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        instrument_ids = [
            str(i).strip()
            for i in (payload.get("instrumentIds") or [])
            if isinstance(i, str) and str(i).strip()
        ]
        if not instrument_ids:
            raise ValueError("instrumentIds requerido")

        as_of_raw = payload.get("asOfBarDate")
        as_of_date: date | None = None
        if isinstance(as_of_raw, date):
            as_of_date = as_of_raw
        elif isinstance(as_of_raw, str) and as_of_raw.strip():
            as_of_date = date.fromisoformat(as_of_raw.strip()[:10])

        account_id = (payload.get("accountId") or "").strip() or None
        max_candidates = int(payload.get("maxCandidates") or 25)
        execute_requested = payload.get("execute") is True
        execute_env = paper_d_execute_allowed()
        policy_id = (payload.get("executionPolicyId") or "").strip() or None
        force_refresh = payload.get("forceRefresh") is True

        rows = await self._opinions.query(
            instrument_ids=instrument_ids,
            as_of_bar_date=as_of_date,
            account_id=account_id,
            force_refresh=force_refresh,
            hints=[],
        )
        candidates = select_estudio_opening_candidates(
            rows, max_candidates=max_candidates
        )

        plan_id = f"edo_{uuid4().hex[:12]}"
        notes: list[str] = [
            f"{ESTUDIO_AUTO_PROPOSE_VERSION}: Estudio buy aviso|alarma → TradePlan → hit",
            "≠ Paper D Composite · ≠ Radar · ≠ cola Hoy.",
        ]

        strategy_definition_id: str | None = None
        if policy_id and self._policies is not None:
            pol = await self._policies.get_policy(policy_id)
            if pol is not None:
                strategy_definition_id = getattr(pol, "strategy_definition_id", None)

        hits: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for cand in candidates:
            iid = str(cand["instrumentId"])
            symbol: str | None = None
            if self._instruments is not None:
                inst = await self._instruments.get_by_id(iid)
                if inst is not None:
                    symbol = (
                        getattr(inst, "symbol", None)
                        or getattr(inst, "ticker", None)
                        or None
                    )
                    if symbol is not None:
                        symbol = str(symbol)

            try:
                propose_result = await self._propose.execute(
                    instrument_id=iid,
                    suggested_quantity=_PROPOSE_QTY_PLACEHOLDER,
                    account_id=account_id,
                    symbol=symbol,
                    action_override="recommend_long",
                )
            except Exception as exc:  # noqa: BLE001 — skip instrumento, no tumbar batch
                skipped.append(
                    {
                        "instrumentId": iid,
                        "autoSource": cand["autoSource"],
                        "reason": f"propose_error:{exc}",
                    }
                )
                continue

            trade_plan = _extract_trade_plan(propose_result)
            status = trade_plan.get("status") if isinstance(trade_plan, dict) else None
            if not isinstance(trade_plan, dict) or status != "TRIGGERED":
                skipped.append(
                    {
                        "instrumentId": iid,
                        "autoSource": cand["autoSource"],
                        "reason": "no_tradeplan",
                        "tradePlanStatus": status,
                    }
                )
                continue

            price = _extract_last_close(propose_result)
            entry = trade_plan.get("entry")
            if price is None and isinstance(entry, (int, float)) and float(entry) > 0:
                price = float(entry)
            if price is None or price <= 0:
                skipped.append(
                    {
                        "instrumentId": iid,
                        "autoSource": cand["autoSource"],
                        "reason": "sin_precio",
                    }
                )
                continue

            as_of = str(cand.get("asOfBarDate") or "")[:10]
            hits.append(
                build_estudio_auto_hit(
                    instrument_id=iid,
                    symbol=symbol,
                    auto_source=str(cand["autoSource"]),
                    trade_plan=trade_plan,
                    price=float(price),
                    strategy_definition_id=strategy_definition_id,
                    plan_id=plan_id,
                    as_of=as_of,
                    policy_id=policy_id,
                )
            )

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
                raise ValueError("Estudio AUTO execute requiere mode=paper_auto")
            allowed_acct = paper_d_allowed_account_id()
            policy_acct = getattr(policy, "account_id", None)
            if not allowed_acct:
                raise ValueError(
                    "PAPER_D_ACCOUNT_ID requerido para execute=true (fail-closed A5)"
                )
            if policy_acct and str(policy_acct) != allowed_acct:
                raise ValueError(
                    f"A5 opt-in: PAPER_D_ACCOUNT_ID={allowed_acct} "
                    f"no coincide con policy.accountId={policy_acct}"
                )
            kinds = set((policy.definition or {}).get("signalKinds") or [])
            if "entry_long" not in kinds:
                raise ValueError("La política debe permitir signalKind entry_long")

            if not hits:
                execute_status = "executed"
                execution = {
                    "policyId": policy_id,
                    "mode": "paper_auto",
                    "actions": [],
                    "hitCount": 0,
                    "skipped": skipped,
                }
                notes.append("Ningún hit TRIGGERED; no se llamó al Router.")
            else:
                route = await self._router.execute(policy_id, hits)
                execution = _route_result_to_dict(route)
                execution["hitCount"] = len(hits)
                execution["skipped"] = skipped
                execute_status = "executed"
                notes.append(
                    f"ExecutionRouter paper_auto: {len(hits)} hit(s) Estudio "
                    f"(Gate cognitivo / EdgeReport aplican)."
                )
        else:
            notes.append("Modo dry-run (execute=false).")

        out = {
            "proposeVersion": ESTUDIO_AUTO_PROPOSE_VERSION,
            "planId": plan_id,
            "scannedCount": len(instrument_ids),
            "candidateCount": len(candidates),
            "hitCount": len(hits),
            "candidates": candidates,
            "hits": hits,
            "skipped": skipped,
            "executeAllowedByEnv": execute_env,
            "executeRequested": execute_requested,
            "executeStatus": execute_status,
            "execution": execution,
            "notes": notes,
            "generatedAt": datetime.now(UTC).isoformat(),
        }
        from bolsa_application.estudio_auto_telemetry import remember_estudio_auto_propose

        remember_estudio_auto_propose(out)
        return out
