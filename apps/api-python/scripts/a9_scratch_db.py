"""Sonda puntual (no permanente): crea/borra una BD scratch para reproducir el job de CI.

Uso:
    uv run --no-sync python apps/api-python/scripts/a9_scratch_db.py create <nombre>
    uv run --no-sync python apps/api-python/scripts/a9_scratch_db.py drop <nombre>

El job `lifecycle-pg` de CI corre sobre una BD **vacía** recién migrada; la BD de desarrollo
arrastra residuo de ejecuciones anteriores (tranzas en RETRY de tests de crash), así que un
fallo local puede no reproducirse en CI. Esta sonda permite comparar contra un entorno limpio
sin tocar la BD de desarrollo.
"""

from __future__ import annotations

import os
import sys

import psycopg

ADMIN_URL = os.environ.get(
    "SCRATCH_ADMIN_URL", "postgresql://bolsa:bolsa_dev@localhost:5432/postgres"
)


def main(action: str, name: str) -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn, conn.cursor() as cur:
        if action == "create":
            cur.execute(f'CREATE DATABASE "{name}"')  # noqa: S608 — nombre validado abajo.
            print("created", name)
        elif action == "drop":
            cur.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where datname = %s",
                (name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{name}"')  # noqa: S608
            print("dropped", name)
        else:
            raise SystemExit(f"acción desconocida: {action}")


if __name__ == "__main__":
    target = sys.argv[2]
    if not target.replace("_", "").isalnum():
        raise SystemExit("nombre de BD inválido")
    main(sys.argv[1], target)
