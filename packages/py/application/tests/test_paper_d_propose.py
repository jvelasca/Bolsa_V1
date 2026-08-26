"""Paper D — ProposePaperDPlan + execute → Router mock."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bolsa_application.paper_d_propose import (
    ProposePaperDPlan,
    build_paper_d_hits,
    paper_d_execute_allowed,
)


class _FakeListDetail:
    def __init__(self, list_id: str, ids: list[str]) -> None:
        self.id = list_id
        self.instrument_ids = ids


class _FakeLists:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    async def get_by_id(self, list_id: str):
        if list_id == "wl-1":
            return _FakeListDetail(list_id, self._ids)
        return None


class _FakeInstruments:
    def __init__(self, rows: dict[str, dict]) -> None:
        self._rows = rows

    async def get_by_id(self, instrument_id: str):
        if instrument_id not in self._rows:
            return None
        return SimpleNamespace(id=instrument_id, symbol=self._rows[instrument_id]["symbol"])

    async def get_fundamentals(self, instrument_id: str):
        return self._rows.get(instrument_id, {}).get("fund")

    async def get_quotes_by_ids(self, instrument_ids: list[str]):
        out = []
        for iid in instrument_ids:
            row = self._rows.get(iid)
            if not row:
                continue
            out.append(
                SimpleNamespace(
                    id=iid,
                    last_close=row.get("price", 100.0),
                )
            )
        return out


class _FakePolicies:
    def __init__(self, policy) -> None:
        self._policy = policy

    async def get_policy(self, policy_id: str):
        if self._policy and self._policy.id == policy_id:
            return self._policy
        return None


class _FakeRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list]] = []

    async def execute(self, policy_id: str, hits: list):
        self.calls.append((policy_id, hits))
        return SimpleNamespace(
            policy_id=policy_id,
            mode="paper_auto",
            actions=[
                SimpleNamespace(
                    instrument_id=hits[0]["instrumentId"],
                    signal_kind="entry_long",
                    status="trade_executed",
                    reason=None,
                    transaction_id="tx-1",
                )
            ]
            if hits
            else [],
        )


def _fund(**over):
    base = {
        "marketCap": 5e10,
        "trailingPe": 14.0,
        "sector": "Technology",
        "roe": 0.2,
        "operatingMargin": 0.15,
        "debtToEquity": 0.4,
        "currentRatio": 1.6,
        "fcfYield": 0.04,
        "altmanZ": 3.2,
        "fetchedAt": "2026-07-29T12:00:00Z",
        "sourceVersion": "yahoo_quote_summary_v3",
    }
    base.update(over)
    return base


def _paper_policy():
    return SimpleNamespace(
        id="pol-1",
        name="Paper D",
        mode="paper_auto",
        enabled=True,
        account_id="acc-1",
        strategy_definition_id="strat-1",
        definition={"signalKinds": ["entry_long"], "requireValidatedBacktest": False},
    )


@pytest.mark.asyncio
async def test_propose_ranks_eligible(monkeypatch):
    monkeypatch.setattr(
        "bolsa_application.scan_universe.validate_scan_universe_size",
        lambda *_a, **_k: None,
    )
    instruments = _FakeInstruments(
        {
            "a": {"symbol": "AAA", "fund": _fund()},
            "b": {"symbol": "BBB", "fund": _fund(trailingPe=80, roe=0.02, altmanZ=0.5)},
        }
    )
    uc = ProposePaperDPlan(instruments, _FakeLists(["a", "b"]))
    out = await uc.execute(
        {
            "universe": {"listId": "wl-1"},
            "minScoreDisplay100": 40,
            "respectVetoNewLong": True,
            "execute": False,
        }
    )
    assert out["proposeVersion"] == "paper_d_propose_v2"
    assert out["rankingReady"] is True
    assert out["executeStatus"] == "dry_run"
    assert out["eligibleCount"] >= 1
    assert any(c["ticker"] == "AAA" and c["status"] == "eligible" for c in out["candidates"])


@pytest.mark.asyncio
async def test_execute_blocked_without_env(monkeypatch):
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    monkeypatch.setattr(
        "bolsa_application.scan_universe.validate_scan_universe_size",
        lambda *_a, **_k: None,
    )
    assert paper_d_execute_allowed() is False
    instruments = _FakeInstruments({"a": {"symbol": "AAA", "fund": _fund()}})
    out = await ProposePaperDPlan(instruments, _FakeLists(["a"])).execute(
        {"universe": {"listId": "wl-1"}, "execute": True, "minScoreDisplay100": 0}
    )
    assert out["executeStatus"] == "blocked_env"


@pytest.mark.asyncio
async def test_execute_calls_router(monkeypatch):
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-1")
    monkeypatch.setattr(
        "bolsa_application.scan_universe.validate_scan_universe_size",
        lambda *_a, **_k: None,
    )
    instruments = _FakeInstruments(
        {"a": {"symbol": "AAA", "fund": _fund(), "price": 42.5}}
    )
    router = _FakeRouter()
    uc = ProposePaperDPlan(
        instruments,
        _FakeLists(["a"]),
        router=router,
        policies=_FakePolicies(_paper_policy()),
    )
    out = await uc.execute(
        {
            "universe": {"listId": "wl-1"},
            "execute": True,
            "executionPolicyId": "pol-1",
            "minScoreDisplay100": 0,
        }
    )
    assert out["executeStatus"] == "executed"
    assert out["execution"] is not None
    assert out["execution"]["actions"][0]["status"] == "trade_executed"
    assert len(router.calls) == 1
    assert router.calls[0][1][0]["signal"]["kind"] == "entry_long"
    assert router.calls[0][1][0]["signal"]["price"] == 42.5


def test_build_hits_skips_missing_price():
    hits, skips = build_paper_d_hits(
        [{"instrumentId": "x", "ticker": "X"}],
        strategy_definition_id="s1",
        prices={},
        plan_id="pd_test",
    )
    assert hits == []
    assert len(skips) == 1
