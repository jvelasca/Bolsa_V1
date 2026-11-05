"""064: guardas herméticas del ámbito de CUENTA de las promociones (M16, auditoría .183).

Sin PostgreSQL: fija la cadena lineal (``063`` → ``064``), que el identificador cabe en
``alembic_version.version_num`` (``varchar(32)``) y el contrato de la migración:

* añade ``strategy_promotions.account_id`` como columna NULLABLE y SIN backfill — rellenarla
  desde ``instrument_id`` sería volver a confundir cuenta e instrumento, que es el hallazgo;
* crea el índice ``(account_id, promoted)`` que consulta ``get_active_for_account``;
* es idempotente (columnas/índices existentes no se recrean) y tolerante a una base sin la
  tabla de promociones (anterior a la ``030``).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "064_strategy_account_scope.py"
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("migration_064", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    """Doble de ``alembic.op`` que solo registra las mutaciones de esquema."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.dropped: list[str] = []
        self.indexes: list[tuple[str, str, list[str]]] = []
        self.dropped_indexes: list[tuple[str, str]] = []

    def get_bind(self) -> object:
        return object()

    def add_column(self, _table: str, column: Any) -> None:
        self.added.append(column)

    def drop_column(self, _table: str, column: str) -> None:
        self.dropped.append(column)

    def create_index(self, name: str, table: str, columns: list[str]) -> None:
        self.indexes.append((name, table, list(columns)))

    def drop_index(self, name: str, table_name: str) -> None:
        self.dropped_indexes.append((name, table_name))


def _patch_schema(
    monkeypatch: pytest.MonkeyPatch,
    migration: Any,
    *,
    table_exists: bool,
    present_columns: tuple[str, ...] = (),
    present_indexes: tuple[str, ...] = (),
) -> _FakeOp:
    fake = _FakeOp()
    monkeypatch.setattr(migration, "op", fake)
    monkeypatch.setattr(migration, "_table_exists", lambda _bind, _table: table_exists)
    monkeypatch.setattr(
        migration,
        "_column_exists",
        lambda _bind, _table, column: column in present_columns,
    )
    monkeypatch.setattr(
        migration,
        "_index_exists",
        lambda _bind, name: name in present_indexes,
    )
    return fake


def test_064_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "064_strategy_account_scope"
    assert len(migration.revision) <= 32


def test_064_hangs_linearly_from_063() -> None:
    migration = _load()
    assert migration.down_revision == "063_auto_engine_lease"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_064_is_linear_and_single_head() -> None:
    """Ninguna otra revisión declara ``063`` como padre: la cabeza sigue siendo única."""
    parents = []
    for path in _PATH.parent.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("down_revision = ") and "063_auto_engine_lease" in stripped:
                parents.append(path.name)
    assert parents == ["064_strategy_account_scope.py"]


def test_064_upgrade_adds_the_account_column_without_backfill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch_schema(monkeypatch, migration, table_exists=True)

    migration.upgrade()

    assert [column.name for column in fake.added] == ["account_id"]
    column = fake.added[0]
    assert column.nullable is True
    # Sin default: el ámbito ausente es un estado legítimo, no un valor fabricado.
    assert column.server_default is None


def test_064_upgrade_creates_the_account_index(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load()
    fake = _patch_schema(monkeypatch, migration, table_exists=True)

    migration.upgrade()

    assert fake.indexes == [
        (
            "strategy_promotions_account_idx",
            "strategy_promotions",
            ["account_id", "promoted"],
        )
    ]


def test_064_upgrade_is_idempotent_when_column_and_index_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch_schema(
        monkeypatch,
        migration,
        table_exists=True,
        present_columns=("account_id",),
        present_indexes=("strategy_promotions_account_idx",),
    )

    migration.upgrade()

    assert fake.added == []
    assert fake.indexes == []


def test_064_upgrade_is_a_noop_without_the_promotions_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch_schema(monkeypatch, migration, table_exists=False)

    migration.upgrade()

    assert fake.added == []
    assert fake.indexes == []


def test_064_downgrade_tolerates_a_missing_table_and_drops_what_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = _load()
    fake_missing = _patch_schema(monkeypatch, missing, table_exists=False)
    missing.downgrade()
    assert fake_missing.dropped == []
    assert fake_missing.dropped_indexes == []

    present = _load()
    fake_present = _patch_schema(
        monkeypatch,
        present,
        table_exists=True,
        present_columns=("account_id",),
        present_indexes=("strategy_promotions_account_idx",),
    )
    present.downgrade()
    assert fake_present.dropped_indexes == [
        ("strategy_promotions_account_idx", "strategy_promotions")
    ]
    assert fake_present.dropped == ["account_id"]
