"""Errores de dominio — R-8A (idempotencia concurrente).

Excepciones semánticas de la capa de dominio, que permiten a los use-cases y a la
capa HTTP distinguir un fallo de idempotencia (colisión por `idempotency_key`` ya
ejecutada) de otros errores, sin filtrar excepciones de SQLAlchemy.
"""

from __future__ import annotations


class IdempotencyKeyExists(Exception):
    """Una operación con la misma ``idempotency_key`` ya fue persistida.

    Es el backstop que convierte la colisión concurrente (dos peticiones con la
    misma clave que pasan el pre-check a la vez) en la misma respuesta "ya
    ejecutado" en lugar de un error 500/IntegrityError. El `reference_id` es la
    clave con la que ya existe la operación (en movimientos de cash, el
    ``reference_id`` ES la ``idempotency_key``).
    """

    def __init__(self, reference_id: str) -> None:
        self.reference_id = reference_id
        super().__init__(
            f"Operación con idempotency_key={reference_id!r} ya fue ejecutada",
        )


__all__ = ["IdempotencyKeyExists"]
