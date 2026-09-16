"""V2.40.3 — presupuesto y derivación de las claves de idempotencia financiera.

Contrato de borde (R-11 C2, DTOs ``DepositCashDto``/``WithdrawCashDto``/``TradeRequestDto``):
``16 <= len(key) <= 128`` y sin whitespace. Las claves *de fill* (camino SIM y camino
recovery) se derivan del ``execution_id`` del fill, que en el AUTO es
``f"{venue_order_id}#{fill_seq}"`` con un ``venue_order_id`` namespaced por
``auto_venue_order_id`` (P1-03) que puede superar los 100 caracteres.

Por que existe este modulo (BUG DE DINERO, no cosmético)
--------------------------------------------------------
La derivacion previa recortaba con ``slug[:presupuesto]``, es decir descartaba la *cola*
del ``execution_id`` — justo donde vive el ``#fill_seq``. Con un ``venue_order_id`` largo
el recorte se come el sufijo que distingue un fill de otro y los N fills de una misma
orden colapsan en UNA sola clave: ``ExecuteTrade`` ve la primera ya asentada con otro
payload, lanza ``IdempotencyKeyReused``, el applier lo degrada a RETRY y la posicion se
queda a medias (libro no plano). Fue exactamente el fallo del dia AUTO en
``test_a9_scheduler_process_full_day_pg_zero_human``: el lado SELL del AUTO produce un
``venue_order_id`` de 118 chars (un caracter mas que el BUY por ``sell`` vs ``buy``) y
solo el SELL cruzaba el corte.

El recorte pasa a ser SIN PERDIDA y estructuralmente disjunto del camino corto:

* ``len(slug) <= presupuesto_legacy`` → ``f"{prefix}{slug}"``: **byte a byte** lo mismo
  que la implementacion anterior (que ademas aplicaba un ``[-128:]`` inoperante porque el
  total nunca superaba 128). Compatibilidad exacta ⇒ un fill en vuelo de un deploy
  anterior re-deriva LA MISMA clave y no se re-aplica dinero.
* ``len(slug) > presupuesto_legacy`` → ``f"{prefix}{slug[:head]}{MARK}{digest32}"``, con
  128 caracteres exactos. El marcador ``~`` no puede aparecer en un slug (``re.sub`` manda
  ``[^A-Za-z0-9_]`` a ``-``), asi que ninguna clave "larga" puede coincidir con una
  "corta"; y el digest del ``execution_id`` **completo** discrimina lo que el recorte tira
  (dos ``execution_id`` distintos que normalicen al mismo slug tampoco colisionan).

El camino corto preserva el ``fill_seq`` por construccion; el camino largo lo preserva
por el digest, que es funcion de todo el ``execution_id``.
"""

from __future__ import annotations

import re
from hashlib import sha256

__all__ = [
    "IDEMPOTENCY_KEY_MAX_LEN",
    "IDEMPOTENCY_KEY_MIN_LEN",
    "bounded_idempotency_key",
]

# Rango del contrato de DTOs (R-11 C2). Fuera de aqui el borde rechaza la clave.
IDEMPOTENCY_KEY_MIN_LEN = 16
IDEMPOTENCY_KEY_MAX_LEN = 128

# Marca de linaje "clave larga": imposible en un slug (ver modulo docstring).
_MARK = "~"
# 32 hex = 128 bits de digest: el presupuesto alcanza de sobra y la probabilidad de
# colision queda despreciable para el volumen de fills de una cuenta.
_DIGEST_HEX = 32

_SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9_]")


def _slug(value: object) -> str:
    """Normaliza a ``[A-Za-z0-9_-]`` (misma regla que la implementacion historica)."""
    slug = _SLUG_UNSAFE.sub("-", str(value or "").strip())
    slug = slug.strip("-")
    return slug or "unknown"


def bounded_idempotency_key(
    prefix: str,
    execution_id: object,
    *,
    legacy_budget: int,
) -> str:
    """Clave financiera estable, sin colisiones y dentro de ``16..128`` sin whitespace.

    ``prefix`` distingue el origen (``sim-fin-`` vs ``recovery-fin-``).
    ``legacy_budget`` es el corte que usaba la implementacion anterior
    (``slug[:legacy_budget]``); se conserva como frontera de compatibilidad exacta.

    Estable por ``execution_id`` (mismo fill ⇒ misma clave ⇒ ``ExecuteTrade`` idempotente)
    e inyectiva salvo colision de SHA-256 (``execution_id`` distintos ⇒ claves distintas),
    que es justo lo que el recorte anterior no garantizaba.
    """
    raw = str(execution_id or "").strip()
    slug = _slug(raw)
    if len(slug) <= legacy_budget:
        key = f"{prefix}{slug}"
    else:
        head = max(IDEMPOTENCY_KEY_MAX_LEN - len(prefix) - len(_MARK) - _DIGEST_HEX, 1)
        digest = sha256(raw.encode("utf-8")).hexdigest()[:_DIGEST_HEX]
        key = f"{prefix}{slug[:head]}{_MARK}{digest}"
    if len(key) < IDEMPOTENCY_KEY_MIN_LEN:
        # Slug degenerado (p.ej. ``unknown``): el contrato exige 16. Se rellena con la
        # MISMA marca (imposible en un slug) ⇒ tampoco colisiona con el camino normal.
        key = key.ljust(IDEMPOTENCY_KEY_MIN_LEN, _MARK)
    return key
