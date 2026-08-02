from bolsa_domain.entities.tracker_definition import TrackerDefinitionRecord

from bolsa_application.trackers import build_tracker_definition_dict, tracker_to_scan_payload


def test_tracker_to_scan_payload() -> None:
    record = TrackerDefinitionRecord(
        id="tracker-1",
        name="EU Daily",
        definition={
            "universe": {"listId": "list-eu"},
            "barLimit": 300,
            "maxResults": 50,
        },
        strategy_definition_id="strat-1",
        strategy_version=2,
        timeframe="1wk",
        evaluation_mode="bar_close",
        origin="manual",
        enabled=True,
        user_id=None,
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )
    payload = tracker_to_scan_payload(record)
    assert payload["trackerDefinitionId"] == "tracker-1"
    assert payload["strategyDefinitionId"] == "strat-1"
    assert payload["universe"] == {"listId": "list-eu"}
    assert payload["timeframe"] == "1wk"
    assert payload["barLimit"] == 300
    assert payload["maxResults"] == 50


def test_build_tracker_definition_dict_roundtrip() -> None:
    definition = build_tracker_definition_dict(
        tracker_id="t-1",
        name="Test",
        strategy_definition_id="s-1",
        strategy_version=None,
        universe={"instrumentIds": ["inst-1"]},
        timeframe="1d",
        bar_limit=500,
        max_results=100,
        evaluation_mode="bar_close",
        rank_by=None,
        default_execution_policy_id=None,
        schedule=None,
        origin="manual",
        source_prompt=None,
        enabled=True,
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )
    assert definition["id"] == "t-1"
    assert definition["strategyDefinitionId"] == "s-1"
    assert definition["universe"]["instrumentIds"] == ["inst-1"]
