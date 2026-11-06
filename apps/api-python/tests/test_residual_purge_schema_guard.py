"""Tripwire: la purga global de residuos no habla de una tabla que aún no existe.

Causa raíz (medida el 2026-11-01 en la ejecución controlada de ``chaos/live_a7``): el
fixture autouse de sesión ``_cleanup_residuals_around_session`` purga ANTES de que la
batería lleve su BD a head (``ensure_migrated``). En una BD recién creada —la scratch
``bolsa_v1_a7`` del job ``a7-gate``, DROP+CREATE— el esquema está vacío en la purga de
apertura, así que el ``SELECT id FROM investment_accounts`` emitía::

    relation "investment_accounts" does not exist

Era fail-soft y benigno (la BD estaba vacía), pero **inexacto**: afirmaba un fallo donde
solo había "nada que limpiar". Este test fija las dos mitades de la corrección:

1. ``_relation_present`` distingue "tabla ausente" de "tabla vacía" con ``to_regclass``.
2. Con el esquema sin migrar, ``purge_all_residuals`` sondea y **no emite ni un
   ``DELETE``**; con el esquema migrado sí purga (falsable: un cortocircuito incondicional
   dejaría la purga muerta y el segundo caso lo detecta).
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

_CONFTEST_PY = Path(__file__).with_name("conftest.py")


def _load_conftest() -> ModuleType:
    """Carga ``conftest.py`` por ruta (los tests no viven en un paquete importable)."""
    spec = importlib.util.spec_from_file_location("_bolsa_tests_conftest_purge_guard", _CONFTEST_PY)
    assert spec is not None and spec.loader is not None, "no se pudo especificar conftest.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Dobles de SQLAlchemy: registran el SQL, no tocan ninguna BD
# ---------------------------------------------------------------------------


class _FakeResult:
    """Resultado mínimo: ``scalar``/``scalars``/``all`` con el valor inyectado."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._value or []


class _FakeSession:
    """Sesión que apunta cada sentencia y responde según la forma del SQL."""

    def __init__(self, statements: list[str], *, sentinel_present: bool) -> None:
        self.statements = statements
        self.sentinel_present = sentinel_present

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeResult:
        sql = str(statement)
        self.statements.append(sql)
        if "to_regclass" in sql:
            return _FakeResult("investment_accounts" if self.sentinel_present else None)
        if "SELECT 1" in sql:
            return _FakeResult(1)
        if "SELECT id FROM investment_accounts" in sql:
            return _FakeResult([])
        return _FakeResult(None)

    async def commit(self) -> None:
        return None


class _FakeFactory:
    """``async_sessionmaker`` mínimo: ``async with factory() as session``."""

    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeFactory:
        return self

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        return None


class _FakeEngine:
    async def dispose(self) -> None:
        return None


def _install_doubles(monkeypatch: Any, statements: list[str], *, sentinel_present: bool) -> None:
    """Sustituye settings y el motor por dobles; la purga corre sin PostgreSQL."""
    from bolsa_infrastructure import config as config_module
    from bolsa_infrastructure.database import session as session_module

    class _Settings:
        database_url = "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_a7"

    def _fake_get_settings() -> _Settings:
        return _Settings()

    # ``purge_all_residuals`` usa ``get_settings.cache_clear()`` y ``get_settings().database_url``.
    _fake_get_settings.cache_clear = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setattr(config_module, "get_settings", _fake_get_settings)
    monkeypatch.setattr(session_module, "create_engine", lambda *a, **k: _FakeEngine())
    monkeypatch.setattr(
        session_module,
        "create_session_factory",
        lambda *a, **k: _FakeFactory(
            _FakeSession(statements, sentinel_present=sentinel_present)
        ),
    )


# ---------------------------------------------------------------------------
# Comprobaciones
# ---------------------------------------------------------------------------


def test_relation_present_distinguishes_a_missing_table_from_an_empty_one() -> None:
    """``to_regclass`` NULL ⇒ ausente; nombre resuelto ⇒ presente."""
    conftest = _load_conftest()

    absent = _FakeSession([], sentinel_present=False)
    assert asyncio.run(conftest._relation_present(absent, "investment_accounts")) is False
    assert any("to_regclass" in sql for sql in absent.statements)

    present = _FakeSession([], sentinel_present=True)
    assert asyncio.run(conftest._relation_present(present, "investment_accounts")) is True


def test_an_unmigrated_schema_purges_nothing_and_stays_quiet(monkeypatch: Any) -> None:
    """Sin ``investment_accounts``: sonda y CERO ``DELETE`` (nada que limpiar, nada que avisar)."""
    conftest = _load_conftest()
    statements: list[str] = []
    _install_doubles(monkeypatch, statements, sentinel_present=False)

    asyncio.run(conftest.purge_all_residuals())

    assert any("to_regclass" in sql for sql in statements), "la purga no comprobó el esquema"
    deletes = [sql for sql in statements if sql.lstrip().upper().startswith("DELETE")]
    assert deletes == [], f"purga con esquema sin migrar emitió DELETE: {deletes}"
    reads = [sql for sql in statements if "SELECT id FROM investment_accounts" in sql]
    assert reads == [], "la purga leyó cuentas en una BD sin la tabla (eso era el aviso)"


def test_a_migrated_schema_still_purges(monkeypatch: Any) -> None:
    """Con el esquema migrado la purga sigue viva: limpiar instrumentos y workspaces."""
    conftest = _load_conftest()
    statements: list[str] = []
    _install_doubles(monkeypatch, statements, sentinel_present=True)

    asyncio.run(conftest.purge_all_residuals())

    assert any("SELECT id FROM investment_accounts" in sql for sql in statements)
    deletes = [sql for sql in statements if sql.lstrip().upper().startswith("DELETE")]
    assert any("instruments" in sql for sql in deletes), deletes
    assert any("workspaces" in sql for sql in deletes), deletes
