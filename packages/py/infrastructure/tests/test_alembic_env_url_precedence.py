"""Guardia hermética de la precedencia del URL en `alembic/env.py` (defecto medido v111).

Defecto que fija este test
--------------------------
La cabecera de `alembic/env.py` documenta una precedencia explícita::

    1. variable de entorno DATABASE_URL
    2. config ``sqlalchemy.url`` del alembic.ini

pero la ruta **online** (`run_migrations_online`) construía el engine con
``engine_from_config(config.get_section(...))`` a secas — es decir, **siempre** desde
`alembic.ini`, ignorando `DATABASE_URL` y `config.attributes["DATABASE_URL"]`. La ruta
**offline** sí usaba ``_resolved_url()``, así que el desajuste era invisible en
``alembic upgrade head --sql`` y sólo se manifestaba en el uso real: ``alembic upgrade
head`` desde el CLI migraba **otra** base de datos que la que consultaba el proceso, con
la BD de desarrollo como destino silencioso (``.env`` apunta a ella).

Por qué un test de fuente y no de comportamiento
------------------------------------------------
``_resolved_url()`` es una función del contexto de Alembic (lee el ``config`` global del
módulo) y no es importable sin montar ese contexto. La afirmación que hay que proteger es
estructural —«la ruta online respeta la precedencia documentada»—, y la forma más
directa y falsable de fijarla es sobre el propio fuente de ``env.py``: si alguien vuelve
a construir el engine desde el ini sin inyectar el URL resuelto, este test cae.
"""

from __future__ import annotations

from pathlib import Path

_ENV_PY = (
    Path(__file__).resolve().parents[1] / "alembic" / "env.py"
)


def _source() -> str:
    return _ENV_PY.read_text(encoding="utf-8")


def test_env_py_exists() -> None:
    assert _ENV_PY.is_file(), f"no se encontró el env.py de Alembic: {_ENV_PY}"


def test_resolved_url_honours_the_documented_precedence() -> None:
    """``_resolved_url`` lee el entorno Y ``config.attributes``, y normaliza a psycopg."""
    source = _source()
    assert "def _resolved_url" in source, "desapareció el resolutor único de URL"

    resolver = source.split("def _resolved_url", 1)[1].split("\ndef ", 1)[0]
    assert 'os.environ.get("DATABASE_URL")' in resolver, (
        "el resolutor dejó de leer la variable de entorno DATABASE_URL"
    )
    assert '"DATABASE_URL" in config.attributes' in resolver, (
        "el resolutor dejó de honrar config.attributes['DATABASE_URL'] (vía "
        "ensure_migrated, que inyecta la conexión del proceso)"
    )
    assert "postgresql+psycopg://" in resolver, (
        "el resolutor dejó de normalizar el prefijo del driver a psycopg"
    )


def test_online_path_uses_the_resolved_url() -> None:
    """La ruta ONLINE construye el engine con el URL resuelto, no con el del alembic.ini.

    Falsable: si se restaura el bug (``engine_from_config(config.get_section(...))`` sin
    ``section["sqlalchemy.url"] = _resolved_url()``), la aserción cae.
    """
    source = _source()
    assert "def run_migrations_online" in source, "desapareció la ruta online"

    online = source.split("def run_migrations_online", 1)[1].split("\ndef ", 1)[0]
    assert "_resolved_url()" in online, (
        "la ruta online volvió a ignorar la precedencia de DATABASE_URL: `alembic upgrade "
        "head` migraría una BD distinta de la que consulta el proceso"
    )
    assert 'section["sqlalchemy.url"] = _resolved_url()' in online, (
        "la ruta online debe inyectar el URL resuelto en la sección del engine"
    )


def test_offline_path_still_uses_the_resolved_url() -> None:
    """La ruta OFFLINE mantiene el resolutor (era la única que lo usaba antes del fix)."""
    source = _source()
    offline = source.split("def run_migrations_offline", 1)[1].split("\ndef ", 1)[0]
    assert "url=_resolved_url()" in offline, (
        "la ruta offline dejó de resolver el URL por precedencia"
    )


def test_injected_connection_path_is_preserved() -> None:
    """``config.attributes['connection']`` sigue mandando (la usa ``ensure_migrated``).

    Si esta rama desapareciera, ``ensure_migrated`` abriría un engine propio en lugar de
    reutilizar la conexión del proceso, y el bootstrap de BD dejaría de ser el camino
    único que aplica las migraciones.
    """
    source = _source()
    online = source.split("def run_migrations_online", 1)[1].split("\ndef ", 1)[0]
    assert 'config.attributes.get("connection")' in online, (
        "desapareció la rama que reutiliza la conexión inyectada por ensure_migrated"
    )
