#!/usr/bin/env python3
"""Canonical verifier R-12 A3 — invariantes financieras A–E.

Orquesta A+B (reusa ``verify_ledger_balance_chain._run`` en proceso) y los
chequeos C (atomicidad trade+fee), D (unicidad de idempotencia) y E
(custodia APPLIED ↔ ledger). Exit 0 si todo OK; exit 1 si alguno falla.

No hace backfill (D6). No añade CHECK CONSTRAINT. CI cubre los tests unitarios
C/D/E (sin Postgres); este script en vivo es herramienta de mantenimiento
contra la DB de desarrollo.

Uso (repo root):
  uv run python scripts/verify/verify_financial_invariants.py
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
for _p in (
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "packages" / "py" / "domain" / "src",
    ROOT / "packages" / "py" / "market" / "src",
    ROOT / "packages" / "py" / "application" / "src",
    Path(__file__).resolve().parent,
):
    if str(_p) not in sys.path:
        sys.path[:0] = [str(_p)]

# psycopg async no soporta ProactorEventLoop en Windows (convención de infra).
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001 - ya seguro en plataformas sin esta política
        pass

_TRADE_TYPES = frozenset({"buy", "sell"})


class TradeFeeRow(NamedTuple):
    """Fila ledger ``reference_type='transaction'`` para el invariante C."""

    id: str
    account_id: str
    entry_type: str
    amount: Decimal
    balance_after: Decimal
    reference_id: str
    executed_at: datetime


class LedgerKeyRow(NamedTuple):
    """Clave del UNIQUE parcial ``uq_ledger_entries_account_reference`` (D)."""

    account_id: str
    reference_type: str | None
    reference_id: str | None
    entry_type: str


class TxKeyRow(NamedTuple):
    """Clave UniqueConstraint ``(portfolio_id, idempotency_key)`` (D)."""

    portfolio_id: str
    idempotency_key: str | None


class CustodyObligationCheck(NamedTuple):
    """Fila ``custody_obligations`` para el invariante E."""

    account_id: str
    period: str
    status: str
    outstanding: Decimal


class CustodyLedgerRef(NamedTuple):
    """Referencia ledger de custodia (``reference_type='custody'``) para E."""

    account_id: str
    reference_type: str
    reference_id: str


def _load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def _validate_trade_fee_atomicity(rows: Sequence[TradeFeeRow]) -> list[str]:
    """Invariante C — atomicidad trade+fee por ``(account_id, reference_id)``.

    Conservador: FAIL solo si un ``fee`` no tiene sibling ``buy``/``sell``, o si
    el par trade+fee viola ``balance_after[n] == prev + amount[n]`` ordenado
    por ``(executed_at, id)``. Un buy/sell sin fila fee es OK (comisión 0).
    """
    grouped: dict[tuple[str, str], list[TradeFeeRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.account_id, row.reference_id)].append(row)

    failures: list[str] = []
    for (account_id, reference_id), group in grouped.items():
        types = {r.entry_type for r in group}
        has_trade = bool(types & _TRADE_TYPES)
        has_fee = "fee" in types
        if has_fee and not has_trade:
            failures.append(
                f"FAIL(cuenta {account_id}) C fee huérfano "
                f"reference_id={reference_id} (sin sibling buy/sell)"
            )
            continue
        if not (has_trade and has_fee):
            continue
        ordered = sorted(group, key=lambda r: (r.executed_at, r.id))
        prev_balance = ordered[0].balance_after
        for r in ordered[1:]:
            expected = prev_balance + r.amount
            if r.balance_after != expected:
                failures.append(
                    f"FAIL(cuenta {account_id}) C par no secuencial "
                    f"reference_id={reference_id} fila {r.id}: "
                    f"balance_after {r.balance_after} != prev {prev_balance} "
                    f"+ amount {r.amount} = {expected}"
                )
                break
            prev_balance = r.balance_after
    return failures


def _validate_ledger_reference_uniqueness(rows: Sequence[LedgerKeyRow]) -> list[str]:
    """Invariante D (ledger) — duplicados de ``(account_id, reference_type, reference_id, type)``.

    Ignora filas con ``reference_type`` o ``reference_id`` nulos (el índice
    parcial ``uq_ledger_entries_account_reference`` no las cubre).
    """
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for row in rows:
        if row.reference_type is None or row.reference_id is None:
            continue
        counts[(row.account_id, row.reference_type, row.reference_id, row.entry_type)] += 1
    failures: list[str] = []
    for (account_id, reference_type, reference_id, entry_type), n in sorted(counts.items()):
        if n > 1:
            failures.append(
                f"FAIL(cuenta {account_id}) D ledger duplicado "
                f"(reference_type={reference_type}, reference_id={reference_id}, "
                f"type={entry_type}) count={n}"
            )
    return failures


def _validate_transaction_idempotency_uniqueness(rows: Sequence[TxKeyRow]) -> list[str]:
    """Invariante D (transactions) — duplicados de ``(portfolio_id, idempotency_key)``.

    Ignora ``idempotency_key`` nulo (el UniqueConstraint permite varios NULL).
    """
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        if row.idempotency_key is None:
            continue
        counts[(row.portfolio_id, row.idempotency_key)] += 1
    failures: list[str] = []
    for (portfolio_id, idempotency_key), n in sorted(counts.items()):
        if n > 1:
            failures.append(
                f"FAIL(portfolio {portfolio_id}) D transactions duplicado "
                f"idempotency_key={idempotency_key} count={n}"
            )
    return failures


def _validate_idempotency_uniqueness(
    ledger_keys: Sequence[LedgerKeyRow],
    tx_keys: Sequence[TxKeyRow],
) -> list[str]:
    """Invariante D — unicidad ledger + transactions (corrupción de datos si count>1)."""
    return _validate_ledger_reference_uniqueness(ledger_keys) + (
        _validate_transaction_idempotency_uniqueness(tx_keys)
    )


def _validate_custody_obligation_ledger(
    obligations: Sequence[CustodyObligationCheck],
    custody_ledger: Sequence[CustodyLedgerRef],
) -> list[str]:
    """Invariante E — obligación APPLIED debe tener fila ledger ``custody-{period}``.

    PENDING puede no tener filas (cash insuficiente / aún no cobrado). No exige
    ledger para PENDING. FAIL si APPLIED no tiene ninguna fila
    ``reference_type='custody'`` y ``reference_id='custody-{period}'``.
    """
    refs: set[tuple[str, str]] = {
        (r.account_id, r.reference_id)
        for r in custody_ledger
        if r.reference_type == "custody"
    }
    failures: list[str] = []
    for obl in obligations:
        if obl.status != "APPLIED":
            continue
        expected = f"custody-{obl.period}"
        if (obl.account_id, expected) not in refs:
            failures.append(
                f"FAIL(cuenta {obl.account_id}) E APPLIED period={obl.period} "
                f"sin fila ledger reference_type=custody reference_id={expected}"
            )
    return failures


def _print_check(letter: str, title: str, failures: list[str]) -> int:
    """Imprime OK o cada FAIL de un chequeo. Devuelve el número de fallos."""
    if failures:
        for msg in failures:
            print(f"  {msg}")
        return len(failures)
    print(f"  OK ({letter} {title})")
    return 0


async def _run_cde() -> int:
    """Ejecuta C+D+E contra Postgres. Devuelve 0/1. No hace backfill."""
    _load_env()
    from sqlalchemy import select, text

    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import (
        CustodyObligationRow,
        LedgerEntryRow,
        TransactionRow,
    )
    from bolsa_infrastructure.database.session import create_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    print("=== verify_financial_invariants C/D/E ===")
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        print(f"FAIL: no se pudo conectar a PostgreSQL ({exc})")
        return 1

    failures = 0
    async with engine.connect() as conn:
        c_res = await conn.execute(
            select(
                LedgerEntryRow.id,
                LedgerEntryRow.account_id,
                LedgerEntryRow.type,
                LedgerEntryRow.amount,
                LedgerEntryRow.balance_after,
                LedgerEntryRow.reference_id,
                LedgerEntryRow.executed_at,
            ).where(
                LedgerEntryRow.reference_type == "transaction",
                LedgerEntryRow.reference_id.is_not(None),
            )
        )
        c_rows = [
            TradeFeeRow(
                str(r[0]),
                str(r[1]),
                str(r[2]),
                r[3],
                r[4],
                str(r[5]),
                r[6],
            )
            for r in c_res.all()
        ]
        failures += _print_check(
            "C",
            "trade+fee atomicity",
            _validate_trade_fee_atomicity(c_rows),
        )

        d_ledger_res = await conn.execute(
            select(
                LedgerEntryRow.account_id,
                LedgerEntryRow.reference_type,
                LedgerEntryRow.reference_id,
                LedgerEntryRow.type,
            )
        )
        d_ledger = [
            LedgerKeyRow(str(r[0]), r[1], r[2], str(r[3])) for r in d_ledger_res.all()
        ]
        d_tx_res = await conn.execute(
            select(TransactionRow.portfolio_id, TransactionRow.idempotency_key)
        )
        d_tx = [TxKeyRow(str(r[0]), r[1]) for r in d_tx_res.all()]
        failures += _print_check(
            "D",
            "idempotency uniqueness",
            _validate_idempotency_uniqueness(d_ledger, d_tx),
        )

        e_obl_res = await conn.execute(
            select(
                CustodyObligationRow.account_id,
                CustodyObligationRow.period,
                CustodyObligationRow.status,
                CustodyObligationRow.outstanding,
            )
        )
        e_obl = [
            CustodyObligationCheck(str(r[0]), str(r[1]), str(r[2]), r[3])
            for r in e_obl_res.all()
        ]
        e_led_res = await conn.execute(
            select(
                LedgerEntryRow.account_id,
                LedgerEntryRow.reference_type,
                LedgerEntryRow.reference_id,
            ).where(
                LedgerEntryRow.reference_type == "custody",
                LedgerEntryRow.reference_id.is_not(None),
            )
        )
        e_led = [
            CustodyLedgerRef(str(r[0]), str(r[1]), str(r[2])) for r in e_led_res.all()
        ]
        failures += _print_check(
            "E",
            "custody obligation <-> ledger",
            _validate_custody_obligation_ledger(e_obl, e_led),
        )

    await engine.dispose()
    if failures:
        print(f"FAIL: {failures} incumplimiento(s) C/D/E")
        return 1
    print("OK: invariantes C (trade+fee), D (unicidad) y E (custodia <-> ledger)")
    return 0


async def _run_all() -> int:
    """Orquesta A+B (script existente) y C/D/E. Exit 0 solo si todos OK."""
    from verify_ledger_balance_chain import _run

    print("=== verify_financial_invariants A-E ===")
    ab_rc = await _run()
    cde_rc = await _run_cde()
    if ab_rc == 0 and cde_rc == 0:
        print("OK: todas las invariantes A-E se cumplen")
        return 0
    print("FAIL: alguna invariante A-E no se cumple")
    return 1


def main() -> int:
    try:
        return asyncio.run(_run_all())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
