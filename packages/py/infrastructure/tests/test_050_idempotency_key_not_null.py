"""050 aplica NOT NULL solo cuando el conteo de nulos es cero."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "050_transaction_idempotency_key_not_null.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_050", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_050_aborts_when_null_keys_exist() -> None:
    migration = _load()
    with pytest.raises(RuntimeError, match="No se rellenan claves"):
        migration.assert_zero_null_idempotency_keys(3)
    migration.assert_zero_null_idempotency_keys(0)


def test_050_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "050_idem_key_not_null"
    assert len(migration.revision) <= 32


def test_050_source_does_not_backfill_or_drop_unique() -> None:
    source = _PATH.read_text(encoding="utf-8")
    upper = source.upper()
    assert "UPDATE " not in upper
    assert "DROP " not in upper
    assert "idempotency_key IS NULL" in source
    assert "nullable=False" in source
