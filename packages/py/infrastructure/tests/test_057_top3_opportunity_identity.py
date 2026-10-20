"""057: guardas herméticas de la identidad del ganador del TOP3.

Sin PostgreSQL: fija la cadena lineal (``056`` → ``057``), que el identificador cabe en
``alembic_version.version_num`` (``varchar(32)``) y, sobre todo, el comportamiento
**fail-closed** ante un esquema incompleto: ``top3_opportunities`` la crea la ``052`` y es
prerrequisito obligatorio, así que si falta la revisión **aborta** en vez de marcarse como
aplicada sin haber creado las columnas (el lector durable fallaría después al seleccionarlas).

``downgrade`` es asimétrico a propósito: sin tabla no hay columnas que retirar y sale sin
error.
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
    / "057_top3_opportunity_identity.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_057", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    """Doble de ``alembic.op`` que solo registra las mutaciones de esquema."""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.dropped: list[Any] = []

    def get_bind(self):  # noqa: ANN201 — el bind real no se usa en las guardas puras.
        return object()

    def add_column(self, _table: str, column: Any) -> None:
        self.added.append(column)

    def drop_column(self, _table: str, column: str) -> None:
        self.dropped.append(column)


def _patch_schema(
    monkeypatch: pytest.MonkeyPatch,
    migration: Any,
    *,
    table_exists: bool,
    present_columns: tuple[str, ...] = (),
) -> _FakeOp:
    fake = _FakeOp()
    monkeypatch.setattr(migration, "op", fake)
    monkeypatch.setattr(migration, "_table_exists", lambda _bind: table_exists)
    monkeypatch.setattr(
        migration,
        "_column_exists",
        lambda _bind, column: column in present_columns,
    )
    return fake


def test_057_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "057_top3_opportunity_identity"
    assert len(migration.revision) <= 32


def test_057_hangs_linearly_from_056() -> None:
    migration = _load()
    assert migration.down_revision == "056_auto_ops_jobs"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_057_is_linear_and_single_head() -> None:
    """Ninguna otra revisión declara ``056`` como padre: la cabeza sigue siendo única."""
    parents = []
    for path in _PATH.parent.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("down_revision = ") and "056_auto_ops_jobs" in stripped:
                parents.append(path.name)
    assert parents == ["057_top3_opportunity_identity.py"]


def test_057_guard_aborts_when_the_base_table_is_missing() -> None:
    """Un esquema incompleto NO se marca como migrado: la guarda falla cerrado."""
    migration = _load()
    with pytest.raises(RuntimeError, match="top3_opportunities"):
        migration.assert_base_table_present(False)


def test_057_guard_is_a_noop_when_the_base_table_exists() -> None:
    migration = _load()
    assert migration.assert_base_table_present(True) is None


def test_057_upgrade_aborts_without_touching_the_schema_when_the_table_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsable en el punto exacto del hallazgo: antes hacía ``return`` y quedaba «aplicada»."""
    migration = _load()
    fake = _patch_schema(monkeypatch, migration, table_exists=False)

    with pytest.raises(RuntimeError, match="Esquema incompleto"):
        migration.upgrade()

    assert fake.added == [], "con la tabla base ausente NO se añade ninguna columna"


def test_057_upgrade_adds_both_identity_columns_as_nullable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch_schema(monkeypatch, migration, table_exists=True)

    migration.upgrade()

    assert [column.name for column in fake.added] == [
        "strategy_preset_key",
        "strategy_version",
    ]
    assert all(column.nullable is True for column in fake.added)
    # Sin default ni backfill: el hueco histórico es un estado legítimo, no un valor.
    assert all(column.server_default is None for column in fake.added)


def test_057_upgrade_is_idempotent_when_the_columns_already_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch_schema(
        monkeypatch,
        migration,
        table_exists=True,
        present_columns=("strategy_preset_key",),
    )

    migration.upgrade()

    assert [column.name for column in fake.added] == ["strategy_version"]


def test_057_downgrade_tolerates_a_missing_table_and_drops_what_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing = _load()
    fake_missing = _patch_schema(monkeypatch, missing, table_exists=False)
    missing.downgrade()
    assert fake_missing.dropped == []

    present = _load()
    fake_present = _patch_schema(
        monkeypatch,
        present,
        table_exists=True,
        present_columns=("strategy_preset_key", "strategy_version"),
    )
    present.downgrade()
    assert fake_present.dropped == ["strategy_preset_key", "strategy_version"]
