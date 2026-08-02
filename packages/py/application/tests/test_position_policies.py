from bolsa_domain.platform_kernel import validate_position_execution_mode

from bolsa_application.position_policies import build_position_policy_definition


def test_build_position_policy_definition() -> None:
    definition = build_position_policy_definition(
        policy_id="pp-1",
        account_id="acc-1",
        instrument_id="inst-1",
        mode="exit_strategy",
        exit_strategy_definition_id="strat-exit",
        execution_policy_id=None,
        created_at="2026-07-11T00:00:00+00:00",
        updated_at="2026-07-11T00:00:00+00:00",
    )
    assert definition["id"] == "pp-1"
    assert definition["mode"] == "exit_strategy"
    assert definition["exitStrategyDefinitionId"] == "strat-exit"


def test_validate_position_execution_mode() -> None:
    assert validate_position_execution_mode("manual") == "manual"
    assert validate_position_execution_mode("full_auto") == "full_auto"
