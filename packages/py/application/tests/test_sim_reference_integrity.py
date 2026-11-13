"""Tests puros del guardián de integridad referencial de las tablas SIM.

No hay base de datos: se pasan filas como ``dict`` y los ids conocidos como listas. Lo que se
prueba es la DISCIPLINA del recuento, no SQL: que una fila rota por cuenta y por instrumento
se cuente en ambos motivos sin inflar ``orphan_rows``, que un id vacío se declare huérfano en
vez de darse por bueno, y que el informe sea determinista (mismo estado ⇒ mismo ``to_dict``).
"""

from __future__ import annotations

from bolsa_application.sim_reference_integrity import (
    REASON_ACCOUNT_MISSING,
    REASON_INSTRUMENT_MISSING,
    find_orphan_sim_rows,
)

_ACCOUNTS = ("acc-1", "acc-2")
_INSTRUMENTS = ("AAA", "BBB")


def _position(account_id: object, symbol: object) -> dict[str, object]:
    """Fila mínima de ``sim_auto_positions`` (el instrumento es ``symbol``)."""
    return {"account_id": account_id, "symbol": symbol}


def _fill(account_id: object, instrument_id: object) -> dict[str, object]:
    """Fila mínima de ``sim_fill_finance_context`` (el instrumento es ``instrument_id``)."""
    return {"account_id": account_id, "instrument_id": instrument_id}


def test_clean_rows_produce_no_orphans() -> None:
    """Todo apunta a entidades existentes: el informe queda limpio y sin ids listados."""
    report = find_orphan_sim_rows(
        positions=[_position("acc-1", "AAA"), _position("acc-2", "BBB")],
        fills=[_fill("acc-1", "BBB")],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert report.clean is True
    assert report.orphan_rows == 0
    assert report.positions.total_rows == 2
    assert report.fills.total_rows == 1
    assert report.positions.orphan_account_ids == ()
    assert report.positions.orphan_instrument_ids == ()
    assert report.to_dict()["clean"] is True


def test_position_with_unknown_account_is_reported() -> None:
    """Una posición cuya cuenta no existe se cuenta por cuenta, no por instrumento."""
    report = find_orphan_sim_rows(
        positions=[_position("acc-borrada", "AAA")],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    positions = report.positions
    assert report.clean is False
    assert positions.orphan_rows == 1
    assert positions.account_orphan_rows == 1
    assert positions.instrument_orphan_rows == 0
    assert positions.both_orphan_rows == 0
    assert positions.orphan_account_ids == ("acc-borrada",)
    assert positions.orphan_instrument_ids == ()
    assert positions.orphan_reasons == (REASON_ACCOUNT_MISSING,)
    assert report.fills.clean is True


def test_fill_with_unknown_instrument_is_reported() -> None:
    """Un fill cuyo ``instrument_id`` no existe se cuenta como instrumento huérfano."""
    report = find_orphan_sim_rows(
        positions=[],
        fills=[_fill("acc-1", "NO-EXISTE")],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    fills = report.fills
    assert report.clean is False
    assert fills.orphan_rows == 1
    assert fills.account_orphan_rows == 0
    assert fills.instrument_orphan_rows == 1
    assert fills.both_orphan_rows == 0
    assert fills.orphan_instrument_ids == ("NO-EXISTE",)
    assert fills.orphan_reasons == (REASON_INSTRUMENT_MISSING,)


def test_row_failing_both_reasons_is_counted_in_both_and_declared() -> None:
    """Cuenta E instrumento inexistentes: la fila se cuenta en ambos motivos, una sola vez."""
    report = find_orphan_sim_rows(
        positions=[_position("acc-borrada", "SIMBOLO-BORRADO")],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    positions = report.positions
    # Los dos recuentos por motivo incluyen la fila; ``orphan_rows`` no la duplica.
    assert positions.account_orphan_rows == 1
    assert positions.instrument_orphan_rows == 1
    assert positions.both_orphan_rows == 1
    assert positions.orphan_rows == 1
    assert positions.orphan_reasons == (
        REASON_ACCOUNT_MISSING,
        REASON_INSTRUMENT_MISSING,
    )
    assert report.to_dict()["tables"]["sim_auto_positions"]["doubleCountedRows"] == 1


def test_blank_or_none_symbol_is_declared_orphan() -> None:
    """``symbol`` vacío o ``None`` es huérfano declarado, no un instrumento válido."""
    report = find_orphan_sim_rows(
        positions=[_position("acc-1", ""), _position("acc-1", None), _position("acc-1", "  ")],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    positions = report.positions
    assert positions.orphan_rows == 3
    assert positions.blank_instrument_rows == 3
    assert positions.instrument_orphan_rows == 3
    # None y blanco se colapsan a "" al listar ids distintos (declarado en el informe).
    assert positions.orphan_instrument_ids == ("",)
    assert positions.account_orphan_rows == 0


def test_blank_or_none_account_id_is_declared_orphan() -> None:
    """``account_id`` vacío o ``None`` también es huérfano: no se acredita a nadie."""
    report = find_orphan_sim_rows(
        positions=[],
        fills=[_fill(None, "AAA"), _fill("", "AAA")],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    fills = report.fills
    assert fills.orphan_rows == 2
    assert fills.blank_account_rows == 2
    assert fills.account_orphan_rows == 2
    assert fills.orphan_account_ids == ("",)
    assert fills.orphan_instrument_ids == ()


def test_report_is_deterministic_and_ids_are_sorted() -> None:
    """Mismo estado con distinto orden de entrada ⇒ mismo ``to_dict`` y ids ordenados."""
    positions = [
        _position("zeta", "ZZZ"),
        _position("alfa", "AAA"),
        _position("acc-1", "MMM"),
    ]
    fills = [_fill("beta", "BBB"), _fill("acc-2", "NNN")]

    first = find_orphan_sim_rows(
        positions=positions,
        fills=fills,
        known_account_ids=["acc-1", "acc-2"],
        known_instrument_ids=["AAA", "BBB"],
    )
    second = find_orphan_sim_rows(
        positions=reversed(positions),
        fills=reversed(fills),
        known_account_ids=("acc-2", "acc-1"),
        known_instrument_ids=("BBB", "AAA"),
    )

    assert first.to_dict() == second.to_dict()
    assert first.positions.orphan_account_ids == ("alfa", "zeta")
    assert first.positions.orphan_instrument_ids == ("MMM", "ZZZ")
    assert first.fills.orphan_account_ids == ("beta",)
    assert first.fills.orphan_instrument_ids == ("NNN",)
    assert first.orphan_account_ids == ("alfa", "beta", "zeta")


def test_orphan_ids_are_deduplicated_but_rows_are_counted() -> None:
    """Varias filas con la misma cuenta rota cuentan como filas, pero el id se lista una vez."""
    report = find_orphan_sim_rows(
        positions=[
            _position("acc-borrada", "AAA"),
            _position("acc-borrada", "BBB"),
            _position("acc-borrada", "AAA"),
        ],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    positions = report.positions
    assert positions.orphan_rows == 3
    assert positions.account_orphan_rows == 3
    assert positions.orphan_account_ids == ("acc-borrada",)
    assert positions.both_orphan_rows == 0


def test_positions_use_symbol_and_ignore_instrument_id() -> None:
    """La trampa de PR #120: en ``sim_auto_positions`` manda ``symbol``, no ``instrument_id``."""
    # El ``instrument_id`` inventado NO debe mirarse: el símbolo es válido.
    report = find_orphan_sim_rows(
        positions=[{"account_id": "acc-1", "symbol": "AAA", "instrument_id": "NO-EXISTE"}],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert report.positions.clean is True

    # ... y al revés: un símbolo roto no se salva por tener un ``instrument_id`` válido.
    broken = find_orphan_sim_rows(
        positions=[{"account_id": "acc-1", "symbol": "NO-EXISTE", "instrument_id": "AAA"}],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert broken.positions.orphan_instrument_ids == ("NO-EXISTE",)


def test_fills_use_instrument_id_and_ignore_symbol() -> None:
    """En ``sim_fill_finance_context`` el instrumento es ``instrument_id``, no ``symbol``."""
    report = find_orphan_sim_rows(
        positions=[],
        fills=[{"account_id": "acc-1", "instrument_id": "BBB", "symbol": "NO-EXISTE"}],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert report.fills.clean is True

    broken = find_orphan_sim_rows(
        positions=[],
        fills=[{"account_id": "acc-1", "instrument_id": "NO-EXISTE", "symbol": "BBB"}],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert broken.fills.orphan_instrument_ids == ("NO-EXISTE",)


def test_missing_column_is_treated_as_orphan() -> None:
    """Una fila sin la columna esperada es huérfana: asumir que apunta a algo sería el fallo."""
    report = find_orphan_sim_rows(
        positions=[{"account_id": "acc-1"}],
        fills=[{"account_id": "acc-1"}],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert report.positions.blank_instrument_rows == 1
    assert report.positions.instrument_orphan_rows == 1
    assert report.fills.blank_instrument_rows == 1
    assert report.fills.instrument_orphan_rows == 1


def test_empty_inputs_are_clean() -> None:
    """Sin filas no hay nada que declarar: informe limpio, contadores a cero."""
    report = find_orphan_sim_rows(
        positions=[],
        fills=[],
        known_account_ids=_ACCOUNTS,
        known_instrument_ids=_INSTRUMENTS,
    )

    assert report.clean is True
    assert report.orphan_rows == 0
    assert report.positions.total_rows == 0
    assert report.fills.total_rows == 0
    assert report.known_account_count == 2
    assert report.known_instrument_count == 2


def test_known_ids_are_normalized_but_blank_known_ids_do_not_match() -> None:
    """Los ids conocidos se comparan sin bordes; un id conocido vacío no acredita a nadie."""
    report = find_orphan_sim_rows(
        positions=[_position(" acc-1 ", "AAA ")],
        fills=[_fill("", "")],
        known_account_ids=["acc-1", "   "],
        known_instrument_ids=["AAA", ""],
    )

    assert report.positions.clean is True
    # La fila con ids vacíos sigue siendo huérfana aunque "" estuviera en los conocidos.
    assert report.fills.account_orphan_rows == 1
    assert report.fills.instrument_orphan_rows == 1
    assert report.known_account_count == 1
    assert report.known_instrument_count == 1
