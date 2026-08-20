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


class IdempotencyKeyReused(Exception):
    """Misma ``idempotency_key`` pero con un payload distinto al persistido.

    Distingue la reutilización de una clave con una request DIFERENTE (R-9.2): un
    retry con la misma clave que PASÓ por el pre-check y se persiste en paralelo
    vuelve en "ya ejecutado" (IdempotencyKeyExists), pero un cliente que reenvía
    la misma clave con campos financieros distintos (p. ej. ``amount``/``price``)
    NO debe rejugarse en silencio: es un conflicto de idempotencia y se mapea a
    HTTP 409. La `reference_id` es la clave reutilizada con otro payload.
    """

    def __init__(self, reference_id: str) -> None:
        self.reference_id = reference_id
        super().__init__(
            f"Idempotency_key={reference_id!r} ya fue utilizada con un payload "
            "distinto al persistido",
        )


__all__ = ["IdempotencyKeyExists", "IdempotencyKeyReused"]
