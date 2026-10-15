"""054: guardas herméticas de la migración (cadena y límite ``varchar(32)``).

El identificador de revisión viaja a ``alembic_version.version_num`` (``varchar(32)``), así que
un ``revision`` de más de 32 caracteres rompe ``upgrade head`` en PostgreSQL (lección medida en
``v2.88.72`` → ``v2.88.73``). Aquí se fija por test hermético, además de la cadena lineal.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "054_dia_d_verified_and_alerts.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("migration_054", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_054_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "054_dia_d_verified_and_alerts"
    assert len(migration.revision) <= 32


def test_054_hangs_from_053_dia_d_cycle_verifications() -> None:
    migration = _load()
    assert migration.down_revision == "053_dia_d_cycle_verifications"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_054_is_linear_and_single_head() -> None:
    """Ninguna otra revisión declara ``053`` como padre: la cabeza sigue siendo única."""
    versions = _PATH.parent
    parents = []
    for path in versions.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("down_revision = ") and "053_dia_d_cycle_verifications" in stripped:
                parents.append(path.name)
    assert parents == ["054_dia_d_verified_and_alerts.py"]
