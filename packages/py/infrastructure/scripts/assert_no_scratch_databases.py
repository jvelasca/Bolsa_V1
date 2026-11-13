"""Verifica que ninguna BD scratch sobreviva a la batería de migraciones (fuga del arnés).

``scratch_database`` borra su base en un ``finally``, así que una excepción o un
``KeyboardInterrupt`` dentro del test **no** dejan residuo. Lo que no puede garantizar el
propio proceso es un ``SIGKILL`` del runner (timeout del job, cancelación del workflow):
ahí no corre ningún ``finally``. Esta sonda cierra ese hueco en CI.

Corre como paso ``if: always()`` del job ``lifecycle-pg``: si un test PG falla o el job se
cancela, la comprobación **también** se ejecuta y delata las bases huérfanas que la
siguiente ejecución reutilizaría (o que harían crecer el volumen del servidor).

Qué considera una scratch: el nombre que acuña ``_scratch_name`` en
``packages/py/infrastructure/tests/_profile_pg_helpers.py``, ``<prefijo>_<10 hex>``. No se
usa un ``bolsa%`` genérico porque bases dedicadas legítimas (``bolsa_v1_iso``,
``bolsa_v1_a7``) conviven en el mismo servidor dentro del job del tag y darían un falso
positivo; el sufijo hexadecimal de 10 caracteres es la firma real del arnés.

Uso (desde la raíz del repo):
    uv run python packages/py/infrastructure/scripts/assert_no_scratch_databases.py

Códigos de salida: ``0`` sin fugas; ``1`` con fugas o sin ``DATABASE_URL`` (el guard no
puede pasar en silencio).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

#: Firma del nombre que acuña ``_scratch_name`` (``<prefijo>_<uuid4().hex[:10]>``).
_SCRATCH_RE = re.compile(r"^bolsa.*_[0-9a-f]{10}$")
_CONNECT_TIMEOUT = 10
_DOTENV = Path(__file__).resolve().parents[4] / ".env"


def _load_env() -> None:
    """Carga ``.env`` sin pisar variables ya exportadas (convención del repo)."""
    if not _DOTENV.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv es dev-dependency
        return
    load_dotenv(_DOTENV, override=False)


def _normalize(raw: str) -> str:
    return re.sub(r"^\s*postgresql(\+psycopg)?://", "postgresql://", raw.strip()).split("?", 1)[0]


def _database_url() -> str:
    _load_env()
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL no configurado: no se puede auditar el servidor")
    return _normalize(raw)


def _split(url: str) -> tuple[str, str]:
    """``(admin_url, dbname)`` a partir de una URL ya normalizada."""
    parts = urlsplit(url)
    admin = urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    return admin, parts.path.lstrip("/")


def surviving_scratch_databases(url: str) -> tuple[list[str], list[str]]:
    """``(fugas, inventario)``: bases scratch vivas y todas las ``bolsa%`` del servidor."""
    import psycopg

    admin, configured = _split(url)
    with psycopg.connect(admin, autocommit=True, connect_timeout=_CONNECT_TIMEOUT) as conn:
        rows = conn.execute(
            "SELECT datname FROM pg_database "
            "WHERE NOT datistemplate AND datname LIKE 'bolsa%' ORDER BY datname"
        ).fetchall()
    inventory = [str(row[0]) for row in rows]
    leaks = [name for name in inventory if name != configured and _SCRATCH_RE.match(name)]
    return leaks, inventory


def main() -> int:
    try:
        url = _database_url()
    except RuntimeError as exc:
        print(f"FALLO: {exc}", file=sys.stderr)
        return 1
    try:
        leaks, inventory = surviving_scratch_databases(url)
    except Exception as exc:  # noqa: BLE001 - el guard debe fallar, no skipear
        print(f"FALLO: no se pudo consultar el servidor: {exc}", file=sys.stderr)
        return 1

    print(f"bases bolsa* en el servidor: {inventory or 'ninguna'}")
    if leaks:
        print(f"FALLO: {len(leaks)} BD scratch sobrevivieron al arnés: {leaks}", file=sys.stderr)
        return 1
    print("scratch databases: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
