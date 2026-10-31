"""Integridad de ``sync_settings`` sin PostgreSQL: 0 filas no es un error.

La fila única se siembra en la primera lectura de proveedores, así que una base recién
migrada (``alembic upgrade head`` sin tráfico) tiene la tabla vacía por diseño. El
diagnóstico no puede declararla rota: eso convertiría un arranque limpio en un falso
positivo y taparía el único caso que sí es un defecto, la duplicidad de la fila.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bolsa_application.database_maintenance import GetDatabaseMaintenance


class _Row:
    def __init__(self, count: int, only_id: str | None) -> None:
        self.n = count
        self.only_id = only_id


class _Result:
    def __init__(self, row: _Row) -> None:
        self._row = row

    def one(self) -> _Row:
        return self._row


class _SyncSettingsSession:
    """Sesión mínima: solo responde a la consulta de la fila única."""

    def __init__(self, count: int) -> None:
        self._count = count

    async def execute(self, *_args: Any, **_kwargs: Any) -> _Result:
        return _Result(_Row(self._count, "default" if self._count else None))


def _check(count: int) -> Any:
    use_case = GetDatabaseMaintenance(
        _SyncSettingsSession(count),
        schema_contract=None,  # type: ignore[arg-type]
        backup_inventory=None,  # type: ignore[arg-type]
    )
    return asyncio.run(use_case._check_singleton())


def test_empty_table_is_a_warning_because_it_seeds_on_first_read() -> None:
    check = _check(0)

    assert check.id == "integrity.sync_settings_singleton"
    assert check.status == "warning"
    assert "se siembra" in check.detail
    assert check.value == "0"


def test_single_row_is_ok() -> None:
    check = _check(1)

    assert check.status == "ok"
    assert check.value == "default"


def test_duplicate_rows_are_an_error() -> None:
    check = _check(2)

    assert check.status == "error"
    assert check.value == "2"
