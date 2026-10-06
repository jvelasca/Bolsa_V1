"""El turno real usa el equity del libro y no cae a 100_000."""

from bolsa_api.background.auto_simulation_worker import turn_equity_from_book


def test_book_equity_is_authority_when_required() -> None:
    equity, vetoed = turn_equity_from_book(
        54321.25,
        required=True,
        unreadable=False,
        env_raw="100000",
    )
    assert equity == 54321.25
    assert vetoed is False


def test_unreadable_book_vetoes_and_does_not_fall_back_to_100k() -> None:
    equity, vetoed = turn_equity_from_book(
        None,
        required=True,
        unreadable=True,
        env_raw="100000",
    )
    assert equity == 0.0
    assert vetoed is True


def test_hermetic_path_keeps_declared_base() -> None:
    equity, vetoed = turn_equity_from_book(
        None,
        required=False,
        unreadable=False,
        env_raw="",
    )
    assert equity == 100_000.0
    assert vetoed is False
