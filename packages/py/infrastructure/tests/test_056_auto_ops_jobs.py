"""056: guardas herméticas de la cola ``auto_ops_jobs``.

Sin PostgreSQL: fija la cadena lineal (``055`` → ``056``), que el identificador cabe en
``alembic_version.version_num`` (``varchar(32)``) y que la idempotencia activa se
implementa con un índice único PARCIAL sobre ``(kind, coalesce(account_id, ''), day)``
restringido a ``queued|running`` (un job terminado libera el hueco).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[1] / "alembic" / "versions" / "056_auto_ops_jobs.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_056", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_056_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "056_auto_ops_jobs"
    assert len(migration.revision) <= 32


def test_056_hangs_linearly_from_055() -> None:
    migration = _load()
    assert migration.down_revision == "055_dia_d_identity_nullable"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_056_is_linear_and_single_head() -> None:
    versions = _PATH.parent
    parents = []
    for path in versions.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if (
                stripped.startswith("down_revision = ")
                and "055_dia_d_identity_nullable" in stripped
            ):
                parents.append(path.name)
    assert parents == ["056_auto_ops_jobs.py"]


def test_056_active_slot_is_a_partial_unique_index() -> None:
    text = _PATH.read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX" in text
    assert "coalesce(account_id, '')" in text
    assert "WHERE status IN ('queued', 'running')" in text


def test_056_upgrade_is_aditive_and_downgrade_is_symmetric() -> None:
    text = _PATH.read_text(encoding="utf-8")
    assert "if _table_exists(bind):" in text
    assert "DROP INDEX IF EXISTS" in text
    assert "drop_table" in text
