"""R-12 A3 — tests unitarios de los invariantes C/D/E (sin Postgres).

Importa las funciones validadoras de ``scripts/verify/verify_financial_invariants.py``
y las ejercita con tuplas en memoria. No hace skip.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

_VERIFY_DIR = Path(__file__).resolve().parents[4] / "scripts" / "verify"
if str(_VERIFY_DIR) not in sys.path:
    sys.path.insert(0, str(_VERIFY_DIR))

from verify_financial_invariants import (  # noqa: E402
    CustodyLedgerRef,
    CustodyObligationCheck,
    LedgerKeyRow,
    TradeFeeRow,
    TxKeyRow,
    _validate_custody_obligation_ledger,
    _validate_idempotency_uniqueness,
    _validate_trade_fee_atomicity,
)

_T0 = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(milliseconds=1)


def test_c_happy_pair_trade_fee_ok() -> None:
    rows = [
        TradeFeeRow(
            "le-buy",
            "acc-1",
            "buy",
            Decimal("-100"),
            Decimal("900"),
            "tx-1",
            _T0,
        ),
        TradeFeeRow(
            "le-fee",
            "acc-1",
            "fee",
            Decimal("-1"),
            Decimal("899"),
            "tx-1",
            _T1,
        ),
    ]
    assert _validate_trade_fee_atomicity(rows) == []


def test_c_orphan_fee_fail() -> None:
    rows = [
        TradeFeeRow(
            "le-fee",
            "acc-orphan",
            "fee",
            Decimal("-1.5"),
            Decimal("98.5"),
            "tx-orphan",
            _T0,
        ),
    ]
    fails = _validate_trade_fee_atomicity(rows)
    assert len(fails) == 1
    assert fails[0].startswith("FAIL(cuenta acc-orphan)")
    assert "fee huérfano" in fails[0]
    assert "tx-orphan" in fails[0]


def test_c_pair_sequential_violation_fail() -> None:
    rows = [
        TradeFeeRow(
            "le-buy",
            "acc-seq",
            "buy",
            Decimal("-100"),
            Decimal("900"),
            "tx-seq",
            _T0,
        ),
        TradeFeeRow(
            "le-fee",
            "acc-seq",
            "fee",
            Decimal("-1"),
            Decimal("900"),
            "tx-seq",
            _T1,
        ),
    ]
    fails = _validate_trade_fee_atomicity(rows)
    assert len(fails) == 1
    assert fails[0].startswith("FAIL(cuenta acc-seq)")
    assert "no secuencial" in fails[0]


def test_c_lone_buy_without_fee_ok() -> None:
    rows = [
        TradeFeeRow(
            "le-buy",
            "acc-lone",
            "buy",
            Decimal("-50"),
            Decimal("950"),
            "tx-lone",
            _T0,
        ),
    ]
    assert _validate_trade_fee_atomicity(rows) == []


def test_d_duplicate_ledger_key_fail() -> None:
    rows = [
        LedgerKeyRow("acc-dup", "transaction", "tx-dup", "buy"),
        LedgerKeyRow("acc-dup", "transaction", "tx-dup", "buy"),
        LedgerKeyRow("acc-ok", "transaction", "tx-ok", "buy"),
    ]
    tx_keys = [TxKeyRow("pf-1", "idem-unique")]
    fails = _validate_idempotency_uniqueness(rows, tx_keys)
    assert len(fails) == 1
    assert fails[0].startswith("FAIL(cuenta acc-dup)")
    assert "ledger duplicado" in fails[0]
    assert "tx-dup" in fails[0]


def test_d_duplicate_transaction_idempotency_fail() -> None:
    ledger = [LedgerKeyRow("acc-1", "transaction", "tx-1", "buy")]
    tx_keys = [
        TxKeyRow("pf-dup", "idem-same"),
        TxKeyRow("pf-dup", "idem-same"),
        TxKeyRow("pf-ok", None),
    ]
    fails = _validate_idempotency_uniqueness(ledger, tx_keys)
    assert len(fails) == 1
    assert fails[0].startswith("FAIL(portfolio pf-dup)")
    assert "idem-same" in fails[0]


def test_e_applied_without_ledger_fail() -> None:
    obligations = [
        CustodyObligationCheck("acc-applied", "2026", "APPLIED", Decimal("0")),
    ]
    fails = _validate_custody_obligation_ledger(obligations, [])
    assert len(fails) == 1
    assert fails[0].startswith("FAIL(cuenta acc-applied)")
    assert "APPLIED" in fails[0]
    assert "custody-2026" in fails[0]


def test_e_pending_without_ledger_ok() -> None:
    obligations = [
        CustodyObligationCheck("acc-pending", "2026", "PENDING", Decimal("500")),
    ]
    assert _validate_custody_obligation_ledger(obligations, []) == []


def test_e_applied_with_matching_ledger_ok() -> None:
    obligations = [
        CustodyObligationCheck("acc-ok", "2026", "APPLIED", Decimal("0")),
    ]
    ledger = [CustodyLedgerRef("acc-ok", "custody", "custody-2026")]
    assert _validate_custody_obligation_ledger(obligations, ledger) == []
