"""Guardia hermética: migrar EN PROCESO no puede reconfigurar el logging de la app.

Defecto medido (tag ``v2.88.162-beta``)
--------------------------------------
``ensure_migrated`` ejecuta ``alembic upgrade head`` dentro del proceso (bootstrap de
workers, API y tests PG). ``alembic/env.py`` llamaba a ``fileConfig`` con
``disable_existing_loggers=False``, que evita *deshabilitar* loggers pero **sí** aplica
``[logger_root] level = WARN`` de ``alembic.ini`` al logger raíz del proceso. Resultado:
después del bootstrap, todo ``logger.info(...)`` de la aplicación se descarta.

El job ``playwright (live AUTO daily chain)`` del tag lo expuso del modo más caro:
esperaba la línea ``Worker AUTO_OPS_JOB iniciado`` y nunca la vio —el worker estaba vivo,
tanto que su siguiente ``logger.warning`` sí apareció— y el job quedó ROJO con el mensaje
«el worker no arrancó». Un fallo de observabilidad se disfrazó de fallo de arranque.

Las tres pruebas de aquí fijan el contrato por sus dos extremos:

1. ``fileConfig`` sobre el ``alembic.ini`` real **degrada** el raíz a WARN (documenta el
   daño: si esto dejara de ser cierto, el «fix» sería innecesario).
2. ``ensure_migrated`` marca ``configure_logger=False`` antes de migrar (comportamiento,
   con ``command.upgrade`` y el engine sustituidos: hermética, sin BD).
3. ``env.py`` sólo llama a ``fileConfig`` cuando ese atributo no está en ``False``
   (estructura: el CLI de Alembic sigue configurando logging como siempre).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from logging.config import fileConfig
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config

from bolsa_infrastructure.database import migrations

_INFRA_ROOT = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _INFRA_ROOT / "alembic.ini"
_ENV_PY = _INFRA_ROOT / "alembic" / "env.py"


def test_the_ini_would_clobber_the_root_level() -> None:
    """``fileConfig(alembic.ini)`` baja el raíz a WARN: ese es el daño que se evita.

    Falsable: si ``alembic.ini`` dejara de fijar ``[logger_root] level = WARN``, este
    test cae y la guardia de ``configure_logger`` queda sin motivo — se sabría.
    """
    root = logging.getLogger()
    previous = root.level
    try:
        root.setLevel(logging.INFO)
        fileConfig(str(_ALEMBIC_INI), disable_existing_loggers=False)
        assert root.level > logging.INFO, (
            "se esperaba que fileConfig degradara el nivel del raíz; si ya no lo hace, "
            "revisa si la guardia configure_logger sigue siendo necesaria"
        )
    finally:
        root.setLevel(previous)


class _FakeConnection:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConnection:
        return _FakeConnection()

    def dispose(self) -> None:
        return None


class _FakeSettings:
    database_url = "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1"


@pytest.fixture()
def _embedded_upgrade(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """Sustituye el upgrade real por una captura del ``Config`` que se le pasa."""
    captured: dict[str, Any] = {}

    def fake_upgrade(config: Any, revision: str) -> None:
        captured["config"] = config
        captured["revision"] = revision

    monkeypatch.setattr(migrations, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(migrations, "create_engine", lambda *a, **k: _FakeEngine())
    monkeypatch.setattr(migrations.command, "upgrade", fake_upgrade)
    yield captured


def test_ensure_migrated_disables_logging_reconfiguration(
    _embedded_upgrade: dict[str, Any],
) -> None:
    """El bootstrap en proceso pide a ``env.py`` que NO toque el logging.

    Falsable: si alguien quita ``configure_logger=False`` de ``ensure_migrated``, el
    ``fileConfig`` de ``env.py`` vuelve a degradar el raíz y los ``INFO`` del worker
    desaparecen otra vez (el rojo del tag ``v2.88.162-beta``).
    """
    assert migrations.ensure_migrated() is True

    config = _embedded_upgrade["config"]
    assert _embedded_upgrade["revision"] == "head"
    assert config.attributes.get("configure_logger") is False, (
        "ensure_migrated debe marcar configure_logger=False: migrar en proceso no puede "
        "reescribir el nivel del logger raíz"
    )
    assert config.attributes.get("DATABASE_URL"), (
        "el bootstrap sigue inyectando el URL resuelto del proceso"
    )


def test_env_py_only_configures_logging_when_not_embedded() -> None:
    """``fileConfig`` queda detrás de ``configure_logger`` (CLI intacto)."""
    source = _ENV_PY.read_text(encoding="utf-8")
    header = source.split("\ntarget_metadata", 1)[0]

    assert 'config.attributes.get("configure_logger", True)' in header, (
        "desapareció la guardia configure_logger de env.py: el bootstrap en proceso "
        "volvería a silenciar los INFO de la app"
    )
    assert "fileConfig(" in header, "env.py dejó de configurar el logging del CLI"
    # El default True es lo que mantiene el CLI de Alembic igual que siempre.
    assert "disable_existing_loggers=False" in header


def _offline_config(*, guard: bool) -> Config:
    """``Config`` de Alembic real, sin BD: la ruta OFFLINE sólo emite SQL."""
    config = Config(str(_ALEMBIC_INI))
    config.set_main_option("script_location", str(_INFRA_ROOT / "alembic"))
    config.attributes["DATABASE_URL"] = "postgresql+psycopg://user:pw@localhost:5432/db"
    if guard:
        config.attributes["configure_logger"] = False
    return config


def test_the_real_env_py_keeps_the_root_level_when_embedded() -> None:
    """Prueba de extremo a extremo del guardia, con el ``env.py`` REAL y sin BD.

    La ruta offline de Alembic ejecuta ``env.py`` (donde vive ``fileConfig``) y emite el
    SQL sin tocar PostgreSQL. Se compara el nivel del raíz con y sin el atributo:

    * sin ``configure_logger`` (CLI) ⇒ el raíz cae a WARN, como hoy;
    * con ``configure_logger=False`` (bootstrap en proceso) ⇒ el raíz NO se toca.

    El ``upgrade`` offline puede fallar más adelante (una migración que necesita
    introspección no tiene conexión real); da igual: la configuración de logging ocurre
    al importar ``env.py``, antes de ese punto, y es lo único que se asevera.
    """
    root = logging.getLogger()
    previous = root.level
    try:
        root.setLevel(logging.INFO)
        with pytest.raises(Exception):  # noqa: B017 — el fallo esperado es posterior
            command.upgrade(_offline_config(guard=True), "head", sql=True)
        assert root.level == logging.INFO, (
            "con configure_logger=False el env.py real NO debe tocar el nivel del raíz"
        )

        root.setLevel(logging.INFO)
        with pytest.raises(Exception):  # noqa: B017
            command.upgrade(_offline_config(guard=False), "head", sql=True)
        assert root.level > logging.INFO, (
            "sin el guardia, el env.py real degrada el raíz: es el defecto que el "
            "bootstrap en proceso debe evitar"
        )
    finally:
        root.setLevel(previous)


def test_worker_bootstrap_path_is_the_one_that_needs_the_guard() -> None:
    """El scheduler arranca sus workers DESPUÉS del bootstrap: por eso importa.

    Estructural y falsable: si el orden cambiara (workers antes de
    ``database_bootstrap``), este test caería y la guardia merecería revisión.
    """
    source = (
        _INFRA_ROOT.parents[2]
        / "apps"
        / "api-python"
        / "src"
        / "bolsa_api"
        / "workers"
        / "scheduler_worker.py"
    ).read_text(encoding="utf-8")

    bootstrap = source.index("await database_bootstrap(")
    starters = source.index("_start_workers(_event_loop_starters()")
    assert bootstrap < starters, (
        "el scheduler debe bootstrapear la BD ANTES de arrancar los workers: los "
        "starters emiten su línea de disponibilidad (nivel INFO) al arrancar"
    )
