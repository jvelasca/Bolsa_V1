"""061 — guardas herméticas de ``investment_accounts.active_profile_id`` (AUD-03).

Sin PostgreSQL. Fija lo que puede romperse en silencio y que un ``alembic upgrade`` no
vería como error:

* la **cadena lineal** (``060`` → ``061``, cabeza única) y que el identificador cabe en
  ``alembic_version.version_num`` (``varchar(32)``);
* la **idempotencia**: si la FK ya es ``RESTRICT`` (``confdeltype = 'r'``) la revisión
  no hace DROP/CREATE; si es ``SET NULL`` (``'n'``) la recrea preservando nombre,
  columnas y ``ON UPDATE CASCADE``;
* el comportamiento ante un esquema incompleto: sin tabla o sin columna sale sin marcar
  daño (la baseline ``003`` ya crea la FK correcta en bases nuevas);
* el ``downgrade``: vuelve a ``SET NULL`` y es no-op si ya lo es;
* la **coherencia de las tres fuentes** que declaran la acción de borrado (metadatos
  SQLAlchemy, SQL de Prisma y esta migración): si divergen, un ``--autogenerate`` o una
  base provisionada por Prisma reintroducen la desasignación silenciosa.

El comportamiento sobre PostgreSQL real (base nueva, base heredada con datos y
downgrade) vive en ``test_061_profile_delete_restrict_pg.py``.
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
    / "061_profile_delete_restrict.py"
)
_PRISMA_SQL = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "database"
    / "prisma"
    / "migrations"
    / "20260723020000_investor_profiles_catalog"
    / "migration.sql"
)


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("migration_061", _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    """Doble de ``alembic.op``: registra DROP/CREATE de constraints sin tocar la BD."""

    def __init__(self) -> None:
        self.dropped: list[tuple[str, str]] = []
        self.created: list[dict[str, Any]] = []

    def get_bind(self) -> object:
        return object()

    def drop_constraint(self, name: str, table: str, type_: str | None = None) -> None:
        self.dropped.append((name, table))
        assert type_ == "foreignkey", f"se esperaba foreignkey, llegó {type_!r}"

    def create_foreign_key(
        self,
        name: str,
        source: str,
        referent: str,
        local_cols: list[str],
        remote_cols: list[str],
        *,
        ondelete: str | None = None,
        onupdate: str | None = None,
    ) -> None:
        self.created.append(
            {
                "name": name,
                "source": source,
                "referent": referent,
                "local_cols": local_cols,
                "remote_cols": remote_cols,
                "ondelete": ondelete,
                "onupdate": onupdate,
            }
        )


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    migration: Any,
    *,
    table_exists: bool = True,
    column_exists: bool = True,
    action: str | None,
) -> _FakeOp:
    fake = _FakeOp()
    monkeypatch.setattr(migration, "op", fake)
    monkeypatch.setattr(migration, "_table_exists", lambda _bind, _table: table_exists)
    monkeypatch.setattr(migration, "_column_exists", lambda _bind, _t, _c: column_exists)
    monkeypatch.setattr(migration, "_fk_delete_action", lambda _bind: action)
    return fake


def test_061_revision_fits_alembic_version_varchar32() -> None:
    migration = _load()
    assert migration.revision == "061_profile_delete_restrict"
    assert len(migration.revision) <= 32


def test_061_hangs_linearly_from_060() -> None:
    migration = _load()
    assert migration.down_revision == "060_provider_check_policy"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_061_is_linear_and_single_head() -> None:
    """Ninguna otra revisión declara ``060`` como padre: la cabeza sigue siendo única."""
    parents = []
    for path in _PATH.parent.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("down_revision = ") and "060_provider_check_policy" in stripped:
                parents.append(path.name)
    assert parents == ["061_profile_delete_restrict.py"], parents


def test_061_upgrade_is_a_noop_when_the_fk_is_already_restrict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``alembic upgrade head`` idempotente: nada de DROP/CREATE innecesarios."""
    migration = _load()
    fake = _patch(monkeypatch, migration, action="r")

    migration.upgrade()

    assert fake.dropped == []
    assert fake.created == []


def test_061_upgrade_recreates_the_fk_as_restrict_preserving_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch(monkeypatch, migration, action="n")

    migration.upgrade()

    assert fake.dropped == [("investment_accounts_active_profile_id_fkey", "investment_accounts")]
    assert fake.created == [
        {
            "name": "investment_accounts_active_profile_id_fkey",
            "source": "investment_accounts",
            "referent": "investor_profiles",
            "local_cols": ["active_profile_id"],
            "remote_cols": ["id"],
            "ondelete": "RESTRICT",
            "onupdate": "CASCADE",
        }
    ]


def test_061_upgrade_creates_the_fk_when_it_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Una FK ausente no se puede dejar como está: se crea ya en ``RESTRICT``."""
    migration = _load()
    fake = _patch(monkeypatch, migration, action=None)

    migration.upgrade()

    assert fake.dropped == [], "sin constraint previo no hay nada que borrar"
    assert [entry["ondelete"] for entry in fake.created] == ["RESTRICT"]


def test_061_upgrade_does_not_improvise_on_an_incomplete_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()

    missing_table = _patch(monkeypatch, migration, table_exists=False, action="n")
    migration.upgrade()
    assert missing_table.dropped == [] and missing_table.created == []

    missing_column = _patch(monkeypatch, migration, column_exists=False, action="n")
    migration.upgrade()
    assert missing_column.dropped == [] and missing_column.created == []


def test_061_downgrade_is_a_noop_when_the_fk_is_already_set_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch(monkeypatch, migration, action="n")

    migration.downgrade()

    assert fake.dropped == []
    assert fake.created == []


def test_061_downgrade_restores_set_null(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = _load()
    fake = _patch(monkeypatch, migration, action="r")

    migration.downgrade()

    assert len(fake.dropped) == 1
    assert [entry["ondelete"] for entry in fake.created] == ["SET NULL"]
    assert fake.created[0]["onupdate"] == "CASCADE"
    assert fake.created[0]["name"] == "investment_accounts_active_profile_id_fkey"


def test_061_downgrade_does_not_improvise_on_an_incomplete_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _load()
    fake = _patch(monkeypatch, migration, table_exists=False, action="r")

    migration.downgrade()

    assert fake.dropped == [] and fake.created == []


def test_delete_action_is_restrict_in_all_three_sources() -> None:
    """Metadatos, SQL de Prisma y migración deben declarar la misma acción.

    ``SET NULL`` era una segunda vía de desasignación silenciosa (incluso por SQL
    directo). Si una de las tres fuentes se queda atrás, la base heredada y la nueva
    divergen: exactamente el estado que AUD-03 corrige.
    """
    from bolsa_infrastructure.database.models import InvestmentAccountRow

    foreign_keys = [
        fk
        for fk in InvestmentAccountRow.__table__.foreign_keys
        if fk.parent.name == "active_profile_id"
    ]
    assert len(foreign_keys) == 1, foreign_keys
    assert foreign_keys[0].target_fullname == "investor_profiles.id"
    assert foreign_keys[0].ondelete == "RESTRICT", "metadatos: la FK volvió a no ser RESTRICT"

    prisma = _PRISMA_SQL.read_text(encoding="utf-8")
    assert 'ON DELETE RESTRICT ON UPDATE CASCADE' in prisma, "SQL de Prisma sin RESTRICT"
    assert "confdeltype <> 'r'" in prisma, "Prisma no convierte bases con la FK antigua"

    migration_source = _PATH.read_text(encoding="utf-8")
    assert '_replace_fk(bind, "RESTRICT")' in migration_source
    assert '_replace_fk(bind, "SET NULL")' in migration_source
