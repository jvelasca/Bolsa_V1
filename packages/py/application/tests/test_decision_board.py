"""F0.6a — GetDecisionBoard: vista de solo lectura + extract_gate_outcome."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.decision_board import GetDecisionBoard, extract_gate_outcome
from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord


# --------------------------------------------------------------------------- #
# extract_gate_outcome (función pura)
# --------------------------------------------------------------------------- #
def test_gate_none_payload_is_unknown() -> None:
    assert extract_gate_outcome(None) == "unknown"
    assert extract_gate_outcome({}) == "unknown"


def test_gate_passed_true_is_pass() -> None:
    payload: dict[str, Any] = {"compliance_check": {"passed": True}}
    assert extract_gate_outcome(payload) == "PASS"


def test_gate_passed_false_is_veto() -> None:
    payload: dict[str, Any] = {"compliance_check": {"passed": False, "vetoReasons": ["x"]}}
    assert extract_gate_outcome(payload) == "VETO"


def test_gate_skipped_deferred_no_opening() -> None:
    payload: dict[str, Any] = {
        "compliance_check": {"passed": True, "skipped": True, "reason": "no_opening_action"}
    }
    assert extract_gate_outcome(payload) == "DEFERRED"
    payload2: dict[str, Any] = {
        "complianceCheck": {"passed": True, "skipped": True, "reason": "deferred_..."}
    }
    assert extract_gate_outcome(payload2) == "DEFERRED"


def test_gate_falls_back_to_camel_and_runtime_package() -> None:
    camel: dict[str, Any] = {"complianceCheck": {"passed": False}}
    assert extract_gate_outcome(camel) == "VETO"

    nested: dict[str, Any] = {
        "runtime": {"decisionPackage": {"complianceCheck": {"passed": True}}}
    }
    assert extract_gate_outcome(nested) == "PASS"


def test_gate_non_dict_compliance_is_unknown() -> None:
    assert extract_gate_outcome({"compliance_check": "nope"}) == "unknown"


# --------------------------------------------------------------------------- #
# H-1: sesiones AUTO del hot-path (top-level policyGate, runtime=None)
# --------------------------------------------------------------------------- #
def test_gate_auto_policy_gate_allowed_false_is_veto() -> None:
    payload: dict[str, Any] = {"policyGate": {"allowed": False, "gate": {"passed": False}}}
    assert extract_gate_outcome(payload) == "VETO"


def test_gate_auto_policy_gate_risk_engine_deny_is_veto() -> None:
    payload: dict[str, Any] = {
        "policyGate": {"riskEngine": {"verdict": "DENY", "allowed": False}}
    }
    assert extract_gate_outcome(payload) == "VETO"


def test_gate_auto_policy_gate_allowed_true_is_pass() -> None:
    payload: dict[str, Any] = {"policyGate": {"allowed": True}}
    assert extract_gate_outcome(payload) == "PASS"


def test_gate_auto_policy_gate_weird_shape_is_unknown() -> None:
    payload: dict[str, Any] = {"policyGate": {"foo": 1}}
    assert extract_gate_outcome(payload) == "unknown"


def test_gate_policy_gate_snake_case_and_risk_allow() -> None:
    snake: dict[str, Any] = {"policy_gate": {"allowed": False}}
    assert extract_gate_outcome(snake) == "VETO"

    risk_allow: dict[str, Any] = {"policyGate": {"riskEngine": {"verdict": "ALLOW", "allowed": True}}}
    assert extract_gate_outcome(risk_allow) == "PASS"


# --------------------------------------------------------------------------- #
# GetDecisionBoard — fakes de los repos de solo lectura
# --------------------------------------------------------------------------- #
def _session(
    *,
    session_id: str,
    kind: str = "propose",
    status: str = "open",
    instrument_id: str = "inst-1",
    symbol: str | None = "AAA",
    decision_id: str | None = "DEC-1",
    payload: dict[str, Any] | None = None,
) -> DecisionSessionRecord:
    return DecisionSessionRecord(
        id=session_id,
        kind=kind,
        status=status,
        instrument_id=instrument_id,
        created_at="2026-08-24T09:00:00Z",
        account_id="acc-1",
        symbol=symbol,
        decision_id=decision_id,
        payload=payload,
    )


class _FakeCognitive:
    def __init__(self, sessions: list[DecisionSessionRecord]) -> None:
        self._sessions = sessions
        self.calls: list[tuple[str, int]] = []

    async def list_decision_sessions(
        self, *, limit: int = 50, account_id: str | None = None, instrument_id: str | None = None
    ) -> list[DecisionSessionRecord]:
        self.calls.append((account_id or "", limit))
        return self._sessions


class _FakeF3:
    def __init__(self, queue: list[dict[str, Any]] | None) -> None:
        self._queue = queue

    async def get(self, account_id: str) -> Any:
        if self._queue is None:
            return None
        return SimpleNamespace(queue=self._queue)


class _FakeSummary:
    def __init__(self, equity: float, free_margin: float) -> None:
        self._equity = equity
        self._free_margin = free_margin

    async def execute(self, account_id: str) -> Any:
        return SimpleNamespace(total_equity=self._equity, free_margin=self._free_margin)


@pytest.mark.asyncio
async def test_board_buckets_and_ordering() -> None:
    sessions = [
        # SEMI-like open + gate VETO → vetoed
        _session(session_id="s-veto", status="open", payload={"compliance_check": {"passed": False}}),
        # open + DEFERRED → deferred
        _session(
            session_id="s-def",
            status="open",
            payload={"compliance_check": {"passed": True, "skipped": True, "reason": "deferred"}},
        ),
        # open + PASS → auto_waiting
        _session(session_id="s-pass", status="open", payload={"compliance_check": {"passed": True}}),
        # closed + VETO → decided (no bucket)
        _session(
            session_id="s-closed",
            status="closed",
            payload={"compliance_check": {"passed": False}},
        ),
        # pending + unknown gate → auto_waiting
        _session(session_id="s-unk", status="pending", payload=None),
    ]
    uc = GetDecisionBoard(
        _FakeCognitive(sessions),  # type: ignore[arg-type]
        _FakeF3(
            [
                {"instrument_id": "inst-1", "symbol": "AAA"},
                {"instrumentId": "inst-2", "symbol": "BBB"},
            ]
        ),  # type: ignore[arg-type]
    )
    bundle = await uc.execute("acc-1")

    counts = bundle.buckets
    assert counts.pending_confirm == 2
    assert counts.vetoed == 1
    assert counts.deferred == 1
    assert counts.auto_waiting == 2  # s-pass + s-unk
    assert counts.total == 6  # 2 semi + 4 sesiones abiertas

    assert len(bundle.decision_sessions) == 5
    by_id = {s.session_id: s for s in bundle.decision_sessions}
    assert by_id["s-veto"].gate == "VETO"
    assert by_id["s-def"].gate == "DEFERRED"
    assert by_id["s-pass"].gate == "PASS"
    assert by_id["s-closed"].gate == "VETO"
    assert by_id["s-unk"].gate == "unknown"

    assert [s.symbol for s in bundle.semi_f3] == ["AAA", "BBB"]
    assert all(s.status == "pending_confirm" for s in bundle.semi_f3)


@pytest.mark.asyncio
async def test_board_auto_policy_gate_buckets() -> None:
    sessions = [
        # AUTO vetoed → bucket vetoed
        _session(
            session_id="s-auto-veto",
            kind="paper_auto",
            status="open",
            payload={"policyGate": {"allowed": False, "gate": {"passed": False}}},
        ),
        # AUTO risk DENY → bucket vetoed
        _session(
            session_id="s-auto-deny",
            kind="live_dry_run",
            status="open",
            payload={"policyGate": {"riskEngine": {"verdict": "DENY", "allowed": False}}},
        ),
        # AUTO PASS → bucket auto_waiting
        _session(
            session_id="s-auto-pass",
            kind="paper_auto",
            status="open",
            payload={"policyGate": {"allowed": True}},
        ),
        # AUTO shape raro sin compliance → unknown → auto_waiting (no rompe)
        _session(
            session_id="s-auto-weird",
            kind="live_dry_run",
            status="open",
            payload={"policyGate": {"foo": 1}},
        ),
    ]
    uc = GetDecisionBoard(
        _FakeCognitive(sessions),  # type: ignore[arg-type]
        _FakeF3(None),  # type: ignore[arg-type]
    )
    bundle = await uc.execute("acc-1")

    counts = bundle.buckets
    assert counts.vetoed == 2
    assert counts.deferred == 0
    assert counts.auto_waiting == 2  # s-auto-pass + s-auto-weird
    assert counts.total == 4

    by_id = {s.session_id: s for s in bundle.decision_sessions}
    assert by_id["s-auto-veto"].gate == "VETO"
    assert by_id["s-auto-deny"].gate == "VETO"
    assert by_id["s-auto-pass"].gate == "PASS"
    assert by_id["s-auto-weird"].gate == "unknown"


@pytest.mark.asyncio
async def test_board_no_queue_and_empty_sessions() -> None:
    uc = GetDecisionBoard(
        _FakeCognitive([]),  # type: ignore[arg-type]
        _FakeF3(None),  # type: ignore[arg-type]
    )
    bundle = await uc.execute("acc-1")
    assert bundle.semi_f3 == []
    assert bundle.decision_sessions == []
    assert bundle.buckets.to_dict() == {
        "pendingConfirm": 0,
        "vetoed": 0,
        "deferred": 0,
        "autoWaiting": 0,
        "total": 0,
    }


@pytest.mark.asyncio
async def test_board_forwards_limit_and_optional_summary() -> None:
    cognitive = _FakeCognitive([_session(session_id="s1")])
    uc = GetDecisionBoard(
        cognitive,  # type: ignore[arg-type]
        _FakeF3(None),  # type: ignore[arg-type]
        _FakeSummary(equity=1000.0, free_margin=500.0),  # type: ignore[arg-type]
        session_limit=25,
    )
    bundle = await uc.execute("acc-1")
    assert cognitive.calls == [("acc-1", 25)]
    assert bundle.equity == 1000.0
    assert bundle.free_margin == 500.0


@pytest.mark.asyncio
async def test_board_summary_failure_does_not_break_view() -> None:
    class _BoomSummary:
        async def execute(self, account_id: str) -> Any:  # pragma: no cover
            raise RuntimeError("boom")

    uc = GetDecisionBoard(
        _FakeCognitive([]),  # type: ignore[arg-type]
        _FakeF3(None),  # type: ignore[arg-type]
        _BoomSummary(),  # type: ignore[arg-type]
    )
    bundle = await uc.execute("acc-1")
    assert bundle.equity is None
    assert bundle.free_margin is None


def test_bundle_to_dict_shape() -> None:
    from bolsa_application.decision_board import (
        DecisionBoardBucketCounts,
        DecisionBoardBundle,
        DecisionSessionView,
        SemiF3View,
    )

    bundle = DecisionBoardBundle(
        account_id="acc-1",
        generated_at="2026-08-24T09:00:00Z",
        semi_f3=[SemiF3View(instrument_id="i1", symbol="AAA")],
        decision_sessions=[
            DecisionSessionView(
                session_id="s1",
                kind="propose",
                status="open",
                instrument_id="inst-1",
                symbol="AAA",
                decision_id="DEC-1",
                created_at="2026-08-24T09:00:00Z",
                gate="PASS",
            )
        ],
        buckets=DecisionBoardBucketCounts(
            pending_confirm=1, vetoed=0, deferred=0, auto_waiting=1, total=2
        ),
    )
    data = bundle.to_dict()
    assert data == {
        "accountId": "acc-1",
        "generatedAt": "2026-08-24T09:00:00Z",
        "buckets": {
            "pendingConfirm": 1,
            "vetoed": 0,
            "deferred": 0,
            "autoWaiting": 1,
            "total": 2,
        },
        "semiF3Queue": [
            {
                "instrumentId": "i1",
                "symbol": "AAA",
                "status": "pending_confirm",
                "extra": {},
            }
        ],
        "decisionSessions": [
            {
                "sessionId": "s1",
                "kind": "propose",
                "status": "open",
                "instrumentId": "inst-1",
                "symbol": "AAA",
                "decisionId": "DEC-1",
                "createdAt": "2026-08-24T09:00:00Z",
                "gate": "PASS",
            }
        ],
    }
    # Los campos opcionales equity/freeMargin solo aparecen cuando se inyectó el summary.
    assert "equity" not in data
    assert "freeMargin" not in data
