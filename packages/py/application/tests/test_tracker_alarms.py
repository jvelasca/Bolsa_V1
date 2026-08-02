from bolsa_application.execution_router import ExecutionActionResult, ExecutionRouteResult
from bolsa_application.tracker_alarms import ALARM_SAFE_MODES, execution_route_to_dict


def test_alarm_safe_modes_exclude_paper() -> None:
    assert "inform_only" in ALARM_SAFE_MODES
    assert "alert" in ALARM_SAFE_MODES
    assert "paper_auto" not in ALARM_SAFE_MODES
    assert "live_auto" not in ALARM_SAFE_MODES


def test_execution_route_to_dict() -> None:
    route = ExecutionRouteResult(
        policy_id="pol-1",
        mode="inform_only",
        actions=[
            ExecutionActionResult(
                instrument_id="i1",
                signal_kind="entry_long",
                status="inform_only",
            )
        ],
    )
    payload = execution_route_to_dict(route)
    assert payload["policyId"] == "pol-1"
    assert payload["mode"] == "inform_only"
    assert payload["actions"][0]["signalKind"] == "entry_long"
