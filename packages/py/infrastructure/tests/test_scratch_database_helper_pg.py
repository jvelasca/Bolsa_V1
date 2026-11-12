"""Ciclo de vida del arnés scratch: nombre único, sin colisión con ``DATABASE_URL`` y borrado.

El resto de roundtrips (``041``/``061``/``062``/``067``) delega en ``scratch_database`` el
aislamiento completo: que la base se borre aunque el cuerpo lance, que dos ejecuciones
concurrentes no compartan nombre y que jamás pueda apuntar a la BD de ``DATABASE_URL``.

Ese arnés no tenía prueba propia: un fallo suyo se manifestaba como «el test PG skipeó» o,
peor, como escrituras sobre la base de desarrollo. Esta batería lo fija con PostgreSQL real
y **sin** crear la base fuera de ``scratch_database`` (salvo la sonda depuradora del
``KeyboardInterrupt``, que solo observa).

Gate: ``SCRATCH_DB_GUARD_PG_REQUIRED=1`` convierte el skip en fallo duro.
"""

from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

import psycopg
import pytest
from _profile_pg_helpers import (
    _configured_database_name,
    _drop_scratch,
    _scratch_name,
    admin_url,
    database_exists,
    database_url,
    require_or_skip,
    scratch_database,
)

_REQUIRED_ENV = "SCRATCH_DB_GUARD_PG_REQUIRED"
_PREFIX = "bolsa_guard"


@pytest.fixture(scope="module", autouse=True)
def _require_scratch_database() -> None:
    """Skip honesto sin PostgreSQL; fallo duro si el job PG exige la certificación."""
    try:
        with psycopg.connect(admin_url(), autocommit=True) as conn:
            row = conn.execute(
                "SELECT rolcreatedb OR rolsuper FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
        if not row or not row[0]:
            raise RuntimeError("el usuario de BD no puede crear bases scratch (rolcreatedb)")
    except Exception as exc:  # noqa: BLE001 - el llamante decide skip/fail
        require_or_skip(
            exc,
            required_env=_REQUIRED_ENV,
            what="ciclo de vida de la BD scratch",
        )


def _name_of(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def _fake_uuid(hex_prefix: str) -> UUID:
    """``UUID`` cuyo ``.hex`` empieza por ``hex_prefix`` (el nombre usa ``hex[:10]``)."""
    return UUID(hex=(hex_prefix + "0" * (32 - len(hex_prefix))))


def test_creates_and_drops_the_database() -> None:
    with scratch_database(_PREFIX) as url:
        name = _name_of(url)
        assert name.startswith(f"{_PREFIX}_")
        assert database_exists(name) is True
    assert database_exists(name) is False, "la BD scratch sobrevivió al contexto"


def test_drops_the_database_when_the_body_raises() -> None:
    name = ""
    with pytest.raises(RuntimeError, match="fallo simulado"):
        with scratch_database(_PREFIX) as url:
            name = _name_of(url)
            raise RuntimeError("fallo simulado")
    assert name, "el contexto debió entregar una URL antes de fallar"
    assert database_exists(name) is False, "la BD scratch sobrevivió a la excepción"


def test_drops_the_database_on_keyboard_interrupt() -> None:
    """``KeyboardInterrupt`` no hereda de ``Exception``: el ``finally`` debe cubrirlo igual."""
    name = ""
    with pytest.raises(KeyboardInterrupt):
        with scratch_database(_PREFIX) as url:
            name = _name_of(url)
            raise KeyboardInterrupt
    assert name, "el contexto debió entregar una URL antes de la interrupción"
    assert database_exists(name) is False, "la BD scratch sobrevivió a la interrupción"


def test_drop_failure_does_not_mask_the_body_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el ``DROP`` del ``finally`` falla, el error del cuerpo sigue siendo la causa raíz."""

    def _boom(name: str) -> None:
        raise RuntimeError("drop roto")

    monkeypatch.setattr("_profile_pg_helpers._drop_scratch", _boom)
    name = ""
    with pytest.raises(RuntimeError, match="drop roto") as info:
        with scratch_database(_PREFIX) as url:
            name = _name_of(url)
            raise ValueError("cuerpo roto")
    assert isinstance(info.value.__cause__, ValueError), "se enmascaró la excepción del cuerpo"
    _drop_scratch(name)  # limpieza real: el ``DROP`` parcheado no borró la base
    assert database_exists(name) is False


def test_two_contexts_get_distinct_names_and_both_are_dropped() -> None:
    with scratch_database(_PREFIX) as first, scratch_database(_PREFIX) as second:
        first_name, second_name = _name_of(first), _name_of(second)
        assert first_name != second_name, "dos contextos vivos compartieron nombre"
        assert database_exists(first_name) is True
        assert database_exists(second_name) is True
    assert database_exists(first_name) is False
    assert database_exists(second_name) is False


def test_suffixes_are_unique_across_many_calls() -> None:
    names = {_scratch_name(_PREFIX) for _ in range(50)}
    assert len(names) == 50, "el sufijo aleatorio repitió nombre"
    assert "postgres" not in names


def test_never_reuses_the_database_configured_in_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aunque ``uuid4`` devuelva el sufijo exacto de ``DATABASE_URL``, se sortea otro nombre."""
    configured = f"{_PREFIX}_deadbeef00"
    monkeypatch.setattr("_profile_pg_helpers._configured_database_name", lambda: configured)
    sequence = iter([_fake_uuid("deadbeef00"), _fake_uuid("cafebabe11")])
    monkeypatch.setattr("_profile_pg_helpers.uuid4", lambda: next(sequence))

    name = _scratch_name(_PREFIX)

    assert name == f"{_PREFIX}_cafebabe11"
    assert name != configured
    assert name != "postgres"


def test_fails_closed_when_every_candidate_collides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agotado el tope de intentos no se crea nada: mejor error que la base equivocada."""
    configured = f"{_PREFIX}_deadbeef00"
    monkeypatch.setattr("_profile_pg_helpers._configured_database_name", lambda: configured)
    monkeypatch.setattr("_profile_pg_helpers.uuid4", lambda: _fake_uuid("deadbeef00"))

    with pytest.raises(RuntimeError, match="colisione"):
        _scratch_name(_PREFIX)


def test_rejects_an_invalid_prefix() -> None:
    with pytest.raises(ValueError, match="nombre de BD inválido"):
        _scratch_name("bolsa; DROP DATABASE postgres")


def test_configured_database_name_matches_database_url() -> None:
    """La guarda compara contra el nombre real de ``DATABASE_URL``, no contra una constante."""
    assert _configured_database_name() == _name_of(database_url())
