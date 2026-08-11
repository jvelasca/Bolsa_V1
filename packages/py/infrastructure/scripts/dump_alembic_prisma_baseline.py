"""Genera la migración Alembic `003_prisma_schema_baseline` desde `Base.metadata` (D2/F3a).

P0.5/D2: **Alembic pasa a ser la única autoridad de esquema PostgreSQL.** Este script
es una herramienta de BUILD (offline, no requiere BD) que regenera/verifica la
migración baseline `003_prisma_schema_baseline.py` que representa el esquema runtime
completo (SQLAlchemy ``Base.metadata`` → 53 tablas) de forma **idempotente**:

- enum types PostgreSQL: guarda ``pg_type``/``pg_namespace`` + ``CREATE TYPE``
  con identificador quoted (``"InstrumentType"``) para conservar la case exacta que
  Prisma deja en la BD real y a la que referencian las columnas
  (PostgreSQL no soporta ``CREATE TYPE IF NOT EXISTS``).
- ``op.create_table(name, *columns, *FK+UC, if_not_exists=True)`` por tabla. Se pasan
  las ``Column`` explícitas (el runtime no tiene ``Index`` separados, 0 en
  ``table.indexes``) y, como objetos, los ``ForeignKeyConstraint`` (las columnas solas
  NO renderizan FK) y los ``UniqueConstraint`` no cubiertos ya por ``column.unique``.
  Se evita el ``create_foreign_key`` por separado (constraints inline sin nombre, y
  riesgo de duplicar). ``op.create_table(Table, ...)`` con un objeto Table +
  ``if_not_exists`` es un huevo de Alembic: crea la tabla sin columnas.

``sorted_tables`` garantiza el orden topológico → las tablas referenciadas (FK) se
crean antes que las referentes. Sobre la BD actual (ya migrada por Prisma) es un
**no-op**; sobre una BD limpia recrea el esquema sin depender de Prisma.

Uso (desde packages/py/infrastructure):
    $env:PYTHONIOENCODING="utf-8"
    uv run python scripts/dump_alembic_prisma_baseline.py               # regenera
    uv run python scripts/dump_alembic_prisma_baseline.py --check       # compara
"""

from __future__ import annotations

import sys
from pathlib import Path

# Importar los modules de modelos para poblar Base.metadata por completo.
import bolsa_infrastructure.database.models  # noqa: F401  (registra tablas en metadata)
from bolsa_infrastructure.database.models import Base

_OUT_REV = "002_research_data_epoch"
_REV_ID = "003_prisma_schema_baseline"
_VERSION_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / f"{_REV_ID}.py"


def _enum_types() -> dict[str, list[str]]:
    """Enum types PostgreSQL usados por columnas de ``Base.metadata``."""
    from sqlalchemy.dialects import postgresql

    collected: dict[str, list[str]] = {}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            typ = column.type
            if not isinstance(typ, postgresql.ENUM):
                continue
            if typ.name and typ.enums and typ.name not in collected:
                collected[typ.name] = list(typ.enums)
    return collected


def _generate() -> str:
    L: list[str] = []
    L.append(
        '"""schema baseline del runtime completo (Prisma takeover) — D2/F3a. '
        "Generado por `dump_alembic_prisma_baseline`. NO editar a mano; regenerar."
    )
    L.append('"""')
    L.append("from __future__ import annotations")
    L.append("")
    L.append("import sqlalchemy as sa")
    L.append("from alembic import op")
    L.append("")
    L.append("from bolsa_infrastructure.database.models import Base")
    L.append("")
    L.append(f'revision = "{_REV_ID}"')
    L.append(f'down_revision = "{_OUT_REV}"')
    L.append("branch_labels = None")
    L.append("depends_on = None")
    L.append("")
    L.append("")
    L.append("def _type_exists(bind, name: str) -> bool:")
    type_sql = "SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = :n AND n.nspname = 'public'"
    L.append(f"    return bind.scalar(sa.text({type_sql!r}), {{'n': name}}) is not None")
    L.append("")
    L.append("")
    L.append("def upgrade() -> None:")
    L.append("    bind = op.get_bind()")
    L.append("")
    # ---- enums ----
    L.append(
        "    # ---- PostgreSQL enum types (nombre EXACTO, quoted: Prisma crea enum en Mayúscula) ----"
    )
    for name, values in _enum_types().items():
        vals = ", ".join(repr(v) for v in values)
        if_stmt = f'if not _type_exists(bind, "{name}"):'
        L.append(f"    {if_stmt}")
        # quoted identifier -> guarda el typname exacto (`"InstrumentType"`), igual que el
        # enum real ('InstrumentType'), y que el tipo al que las columnas hacen referencia.
        sql = f'CREATE TYPE "{name}" AS ENUM ({vals})'
        L.append(f"        op.execute({sql!r})")
    L.append("")
    # ---- tables ----
    L.append("    # ---- tablas (orden topológico -> FKs referencian tipos ya creados) ----")
    for table in Base.metadata.sorted_tables:
        name = table.name
        cols_ref = f'*Base.metadata.tables["{name}"].columns.values()'
        # FKs se añaden como ForeignKeyConstraint objetos; UniqueConstraints solo si no
        # ya cubiertos por un column.unique=True inline (evita UNIQUE doblado).
        cons_ref = (
            f'*(c for c in Base.metadata.tables["{name}"].constraints '
            f"if isinstance(c, sa.ForeignKeyConstraint) or "
            f"(isinstance(c, sa.UniqueConstraint) and not all(col.unique for col in c.columns)))"
        )
        L.append("    op.create_table(")
        L.append(f'        "{name}",')
        L.append(f"        {cols_ref},")
        L.append(f"        {cons_ref},")
        L.append("        if_not_exists=True,")
        L.append("    )")
    L.append("")
    # ---- indexes ----
    # No hay Index() separado en el runtime (0 en table.indexes): los únicos
    # constraints son PK (de las columnas), FK y Unique — ambos pasados arriba.
    L.append("    # ---- (sin Index separados; PK de columnas, FK/Unique pasados arriba) ----")
    L.append("")
    L.append("def downgrade() -> None:")
    L.append("    # Takeover de esquema: sobre la BD de Prisma el upgrade es no-op, por lo que")
    L.append("    # un downgrade destructivo (drop de tablas) NO se emite para no borrar datos")
    L.append("    # de produccion. En una BD limpia el schema se recrea via seed/ciclo normal.")
    L.append("    return")
    return "\n".join(L) + "\n"


def main() -> int:
    generated = _generate()
    if "--check" in sys.argv:
        if not _VERSION_PATH.exists():
            print(f"FALTA {_VERSION_PATH.relative_to(Path.cwd())}")
            return 1
        current = _VERSION_PATH.read_text(encoding="utf-8")
        if current != generated:
            print("DIVERGE 003: el fichero versionado no coincide con Base.metadata.")
            return 1
        print("OK 003 reproducido byte-a-byte.")
        return 0
    _VERSION_PATH.write_text(generated, encoding="utf-8", newline="\n")
    rel = _VERSION_PATH.relative_to(Path.cwd())
    print(f"Escrito {rel} ({len(Base.metadata.tables)} tablas).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
