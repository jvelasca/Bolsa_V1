"""055: guardas herméticas de la migración (cadena, límite ``varchar(32)`` y única head).

La 055 relaja a ``NULLABLE`` las columnas de identidad ``instrument_id``/``symbol`` de
``dia_d_cycle_verifications`` para que un hueco declarado (``None``, nunca ``""``) sobreviva hasta
la fila durable. Estas guardas fijan, sin PostgreSQL, que el identificador cabe en el
``alembic_version.version_num`` (``varchar(32)``), que cuelga linealmente de la 054 y que la cabeza
sigue siendo única.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "055_dia_d_identity_nullable.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_055", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_055_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "055_dia_d_identity_nullable"
    assert len(migration.revision) <= 32


def test_055_hangs_from_054_dia_d_verified_and_alerts() -> None:
    migration = _load()
    assert migration.down_revision == "054_dia_d_verified_and_alerts"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_055_is_linear_and_single_head() -> None:
    """Ninguna otra revisión declara ``054`` como padre: la cabeza sigue siendo única."""
    versions = _PATH.parent
    parents = []
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("down_revision = ") and "054_dia_d_verified_and_alerts" in stripped:
                parents.append(path.name)
    assert parents == ["055_dia_d_identity_nullable.py"]
