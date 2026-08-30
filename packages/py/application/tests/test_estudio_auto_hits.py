"""V1.33+ — Estudio dictamen/alarma → hit AUTO."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from bolsa_application.estudio_auto_hits import (
    ProposeEstudioAutoOpenings,
    build_estudio_auto_hit,
    resolve_estudio_auto_source,
    select_estudio_opening_candidates,
)


def _opinion(
    *,
    instrument_id: str = "inst-1",
    stance: str = "buy",
    stars: int = 4,
    as_of: date | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        instrument_id=instrument_id,
        stance=stance,
        dictamen_stars=stars,
        as_of_bar_date=as_of or date(2026, 8, 30),
    )


def test_resolve_auto_source_alarma_and_dictamen() -> None:
    assert resolve_estudio_auto_source(stance="buy", dictamen_stars=5) == "estudio_alarma"
    assert resolve_estudio_auto_source(stance="buy", dictamen_stars=4) == "estudio_alarma"
    assert resolve_estudio_auto_source(stance="buy", dictamen_stars=3) == "estudio_dictamen"
    assert resolve_estudio_auto_source(stance="buy", dictamen_stars=2) == "estudio_dictamen"
    assert resolve_estudio_auto_source(stance="buy", dictamen_stars=1) is None
    assert resolve_estudio_auto_source(stance="hold_watch", dictamen_stars=5) is None
    assert resolve_estudio_auto_source(stance="sell_exit", dictamen_stars=5) is None


def test_select_candidates_prefers_alarma_and_caps() -> None:
    rows = [
        _opinion(instrument_id="a", stars=3),
        _opinion(instrument_id="b", stars=5),
        _opinion(instrument_id="c", stars=1),
        _opinion(instrument_id="d", stance="hold_watch", stars=5),
    ]
    selected = select_estudio_opening_candidates(rows, max_candidates=10)
    assert [c["instrumentId"] for c in selected] == ["b", "a"]
    assert selected[0]["autoSource"] == "estudio_alarma"
    assert selected[1]["autoSource"] == "estudio_dictamen"


def test_build_hit_shape() -> None:
    plan = {
        "status": "TRIGGERED",
        "quantity": 7.0,
        "entry": 10.0,
        "structuralStop": 9.0,
        "executionAllowed": True,
    }
    hit = build_estudio_auto_hit(
        instrument_id="inst-abc",
        symbol="SAN",
        auto_source="estudio_alarma",
        trade_plan=plan,
        price=10.0,
        strategy_definition_id="st-1",
        plan_id="edo_test",
        as_of="2026-08-30",
        policy_id="pol-12345678",
    )
    assert hit["autoSource"] == "estudio_alarma"
    assert hit["tradePlan"]["quantity"] == 7.0
    assert hit["signal"]["kind"] == "entry_long"
    assert hit["signal"]["id"].startswith("edo-2026-08-30-")
    assert "paper_d" not in hit["autoSource"]


class _FakeOpinions:
    def __init__(self, rows: list) -> None:
        self.rows = rows
        self.calls: list[dict] = []

    async def query(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class _FakePropose:
    def __init__(self, by_id: dict[str, object]) -> None:
        self.by_id = by_id
        self.calls: list[dict] = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        iid = kwargs["instrument_id"]
        result = self.by_id.get(iid)
        if isinstance(result, Exception):
            raise result
        return result


class _FakeInstruments:
    async def get_by_id(self, instrument_id: str):
        return SimpleNamespace(id=instrument_id, symbol=f"T-{instrument_id[:4]}")


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
            ],
        )


def _triggered_result(*, quantity: float = 5.0, price: float = 10.0):
    return SimpleNamespace(
        trade_plan={
            "status": "TRIGGERED",
            "quantity": quantity,
            "entry": price,
            "structuralStop": price * 0.95,
            "executionAllowed": True,
            "whyNot": [],
        },
        last_close=price,
    )


@pytest.mark.asyncio
async def test_propose_dry_run_emits_estudio_hits(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BOLSA_ESTUDIO_AUTO_PROPOSE_PATH", str(tmp_path / "propose.jsonl"))
    from bolsa_application.estudio_auto_telemetry import reset_last_estudio_auto_propose

    reset_last_estudio_auto_propose()
    uc = ProposeEstudioAutoOpenings(
        _FakeOpinions(
            [
                _opinion(instrument_id="inst-1", stars=5),
                _opinion(instrument_id="inst-2", stars=3),
                _opinion(instrument_id="inst-3", stars=1),
            ]
        ),
        _FakePropose(
            {
                "inst-1": _triggered_result(quantity=4.0),
                "inst-2": SimpleNamespace(
                    trade_plan={"status": "WATCH", "quantity": 0},
                    last_close=10.0,
                ),
            }
        ),
        instruments=_FakeInstruments(),
    )
    out = await uc.execute(
        {
            "instrumentIds": ["inst-1", "inst-2", "inst-3"],
            "asOfBarDate": "2026-08-30",
            "execute": False,
        }
    )
    assert out["hitCount"] == 1
    assert out["hits"][0]["autoSource"] == "estudio_alarma"
    assert out["hits"][0]["tradePlan"]["quantity"] == 4.0
    assert out["executeStatus"] == "dry_run"
    reasons = {s["instrumentId"]: s["reason"] for s in out["skipped"]}
    assert reasons["inst-2"] == "no_tradeplan"
    # silent buy never candidate
    assert "inst-3" not in reasons
    from bolsa_application.estudio_auto_telemetry import last_estudio_auto_propose

    snap = last_estudio_auto_propose()
    assert snap is not None
    assert snap["hitCount"] == 1
    assert snap["skippedByReason"]["no_tradeplan"] == 1
    assert snap["executeStatus"] == "dry_run"


@pytest.mark.asyncio
async def test_propose_execute_blocked_without_env(monkeypatch) -> None:
    monkeypatch.delenv("PAPER_D_EXECUTE", raising=False)
    router = _FakeRouter()
    policy = SimpleNamespace(
        id="pol-1",
        enabled=True,
        mode="paper_auto",
        account_id="acc-demo",
        strategy_definition_id="st-1",
        definition={"signalKinds": ["entry_long"]},
    )
    uc = ProposeEstudioAutoOpenings(
        _FakeOpinions([_opinion(stars=5)]),
        _FakePropose({"inst-1": _triggered_result()}),
        instruments=_FakeInstruments(),
        router=router,
        policies=_FakePolicies(policy),
    )
    out = await uc.execute(
        {
            "instrumentIds": ["inst-1"],
            "execute": True,
            "executionPolicyId": "pol-1",
        }
    )
    assert out["executeStatus"] == "blocked_env"
    assert router.calls == []
    assert out["hitCount"] == 1  # hit built; execute gated


@pytest.mark.asyncio
async def test_propose_execute_routes_estudio_hits(monkeypatch) -> None:
    monkeypatch.setenv("PAPER_D_EXECUTE", "1")
    monkeypatch.setenv("PAPER_D_ACCOUNT_ID", "acc-demo")
    router = _FakeRouter()
    policy = SimpleNamespace(
        id="pol-1",
        enabled=True,
        mode="paper_auto",
        account_id="acc-demo",
        strategy_definition_id="st-1",
        definition={"signalKinds": ["entry_long"]},
    )
    uc = ProposeEstudioAutoOpenings(
        _FakeOpinions([_opinion(stars=4)]),
        _FakePropose({"inst-1": _triggered_result(quantity=9.0)}),
        instruments=_FakeInstruments(),
        router=router,
        policies=_FakePolicies(policy),
    )
    out = await uc.execute(
        {
            "instrumentIds": ["inst-1"],
            "execute": True,
            "executionPolicyId": "pol-1",
            "accountId": "acc-demo",
        }
    )
    assert out["executeStatus"] == "executed"
    assert len(router.calls) == 1
    policy_id, hits = router.calls[0]
    assert policy_id == "pol-1"
    assert hits[0]["autoSource"] == "estudio_alarma"
    assert hits[0]["tradePlan"]["quantity"] == 9.0
