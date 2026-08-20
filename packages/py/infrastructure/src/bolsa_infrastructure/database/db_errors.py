"""Helpers de clasificación de errores de base de datos — R-8A (P0-B).

Distingue una violación de unicidad (UniqueViolation, SQLSTATE ``23505``) del resto
de ``IntegrityError`` (ForeignKeyViolation, CheckViolation, NotNullViolation, …).
Es el respaldo para no mal-clasificar como conflicto de idempotencia un error que en
realidad es de otro constraint: solo una colisión de clave única puede corresponder a
una ``idempotency_key`` ya persistida.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

_UNIQUE_VIOLATION_SQLSTATE = "23505"


def _orig_sqlstate(exc: IntegrityError) -> str | None:
    orig = exc.orig
    if orig is None:
        return None
    sqlstate = getattr(orig, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate:
        return sqlstate
    # Algunos drivers exponen el código bajo `.pgcode` o dentro de la cadena.
    pgcode = getattr(orig, "pgcode", None)
    if isinstance(pgcode, str) and pgcode:
        return pgcode
    return None


def is_unique_violation(exc: IntegrityError) -> bool:
    """Devuelve True si el ``IntegrityError`` es una violación 'duplicate key' (SQLSTATE 23505)."""
    return _orig_sqlstate(exc) == _UNIQUE_VIOLATION_SQLSTATE


__all__ = ["is_unique_violation"]
