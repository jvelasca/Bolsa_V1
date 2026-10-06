"""049 aborta si hay cash o cantidad negativos y no borra filas."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "049_cash_quantity_nonneg_check.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_049", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_049_aborts_when_cash_or_quantity_is_negative() -> None:
    migration = _load()
    with pytest.raises(RuntimeError, match="no borra nada"):
        migration.assert_no_negative_balances(
            1,
            0,
            [("pf-1", "-0.01")],
            [],
        )
    migration.assert_no_negative_balances(0, 0, [], [])


def test_049_source_does_not_delete_rows() -> None:
    source = _PATH.read_text(encoding="utf-8")
    assert "DELETE" not in source.upper()
    assert "cash >= 0" in source
    assert "quantity >= 0" in source
