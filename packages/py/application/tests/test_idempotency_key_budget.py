"""V2.40.3 — regresión de la clave de idempotencia financiera (colisión por recorte).

Bug de dinero que este fichero blinda: la derivación anterior recortaba con
``slug[:presupuesto]``, tirando la COLA del ``execution_id`` — justo donde vive el
``#fill_seq``. Con el ``venue_order_id`` namespaced del AUTO (``auto_venue_order_id``,
P1-03) los N fills de una misma orden colapsaban en UNA clave: ``ExecuteTrade`` veía la
primera ya asentada con OTRO payload, lanzaba ``IdempotencyKeyReused``, el applier lo
degradaba a RETRY y solo la primera trancha movía dinero (el día AUTO no cerraba el
libro; lo destapó ``test_a9_scheduler_process_full_day_pg_zero_human``).

Hermético: sin PG, sin broker. Solo la derivación de claves y su contrato 16..128.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from bolsa_application.idempotency_key import (
    IDEMPOTENCY_KEY_MAX_LEN,
    IDEMPOTENCY_KEY_MIN_LEN,
    bounded_idempotency_key,
)
from bolsa_application.recovery_apply import recovery_idempotency_key
from bolsa_application.simulated_settlement import (
    auto_venue_order_id,
    simulated_idempotency_key,
)

_WHITESPACE = re.compile(r"\s")

# Identidad AUTO realista (P1-03): engine + account UUID + instrument + logical order.
_ENGINE_ID = "auto-a9proc-bcc03924"
_ACCOUNT_ID = "da84acf2-4f00-4aab-ba95-b7ddf9c4b2aa"
_INSTRUMENT_ID = "inst-a9proc-716fd8ea67"


def _auto_venue_order_id(*, side: str, seq: int) -> str:
    """``venue_order_id`` como el que produce el worker (mismo namespace que producción)."""
    return auto_venue_order_id(
        engine_id=_ENGINE_ID,
        account_id=_ACCOUNT_ID,
        instrument_id=_INSTRUMENT_ID,
        side=side,
        logical_order_id=f"{_ENGINE_ID}-1-{side}-{_INSTRUMENT_ID}-{seq}",
    )


def _legacy_simulated_key(execution_id: str) -> str:
    """Derivación anterior (recorte con pérdida), para fijar la compatibilidad exacta."""
    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip()).strip("-") or "unknown"
    return f"sim-fin-{slug[:120]}"[-128:]


def _legacy_recovery_key(execution_id: str) -> str:
    """Idem para el camino recovery (presupuesto histórico de 100)."""
    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip()).strip("-") or "unknown"
    return f"recovery-fin-{slug[:100]}"[-128:]


@pytest.mark.parametrize("side", ["buy", "sell"])
def test_fills_of_one_order_do_not_collapse(side: str) -> None:
    """Los 4 fills de UNA orden generan 4 claves distintas (el bug: generaban 1).

    Con el ``venue_order_id`` namespaced del AUTO (P1-03: engine + UUID de cuenta +
    instrumento + lado + secuencia lógica) la identidad financiera
    ``venue_order_id#fill_seq`` mide ~126-128 chars y cruza el presupuesto histórico
    (120 en SIM, 100 en recovery), así que el recorte se comía justo el ``#fill_seq``
    del final y las 4 tranchas compartían clave (medido: 1 clave distinta para 4 fills,
    en ambos lados y en ambos caminos).
    """
    vid = _auto_venue_order_id(side=side, seq=1)
    execution_ids = [f"{vid}#{i}" for i in (1, 2, 3, 4)]

    # Precondición del bug: con una identidad namespaced como la del worker, el recorte
    # histórico tira el ``#fill_seq`` y las 4 tranchas comparten clave. La identidad se
    # construye con los MISMOS datos que usa el worker (engine + cuenta UUID + instrumento)
    # para que la longitud no sea un caso de laboratorio.
    legacy_keys = [_legacy_simulated_key(e) for e in execution_ids]
    assert len(set(legacy_keys)) < len(legacy_keys), (
        f"el recorte histórico debe colapsar los fills de la orden {side} "
        f"(len={len(execution_ids[0])}); si no, el test ha dejado de ser una regresión"
    )

    keys = [simulated_idempotency_key(e) for e in execution_ids]
    assert len(set(keys)) == len(keys) == 4, (
        f"los fills de una misma orden {side} colapsan en una única clave: {keys}"
    )


def test_legacy_derivation_did_collapse_tails_that_share_prefix() -> None:
    """El defecto era de la COLA: dos execution_id con el mismo prefijo de 120 chars.

    Fija por qué el recorte rompía el contrato: la información que discrimina un fill de
    otro está al final del ``execution_id`` (``#fill_seq``).
    """
    head = "x" * 119
    assert _legacy_simulated_key(f"{head}#1") == _legacy_simulated_key(f"{head}#2")
    assert simulated_idempotency_key(f"{head}#1") != simulated_idempotency_key(f"{head}#2")


def test_short_execution_ids_keep_the_exact_legacy_key() -> None:
    """Compatibilidad exacta en el rango que el recorte NO estropeaba.

    Un fill en vuelo de un deploy anterior re-deriva LA MISMA clave (no se re-aplica
    dinero). El recorte histórico solo actuaba por encima de su presupuesto.
    """
    for execution_id in (
        "xtb-77#3",
        "sim-aaa#1",
        "A" * 100,
        "B" * 110,
        "C" * 115,
        "D" * 120,
    ):
        assert simulated_idempotency_key(execution_id) == _legacy_simulated_key(execution_id)
    for execution_id in ("xtb-77#3", "A" * 90, "B" * 100):
        assert recovery_idempotency_key(execution_id) == _legacy_recovery_key(execution_id)


def test_long_keys_are_structurally_disjoint_from_legacy_ones() -> None:
    """Una clave "larga" lleva ``~``; un slug nunca puede contenerlo.

    Así el camino nuevo no puede colisionar con el viejo (que es ``prefix + slug``), por
    mucho que el digest acabe en algo parecido a un slug.
    """
    assert "~" in simulated_idempotency_key("Z" * 200 + "#7")
    for execution_id in ("xtb-77#3", "A" * 120, "B" * 100):
        # El camino corto (compatible byte a byte con el histórico) no lleva la marca
        # del camino largo.
        assert "~" not in simulated_idempotency_key(execution_id)


@pytest.mark.parametrize(
    ("derive", "prefix"),
    [(simulated_idempotency_key, "sim-fin-"), (recovery_idempotency_key, "recovery-fin-")],
)
def test_contract_range_whitespace_and_stability(derive: Callable[[str], str], prefix: str) -> None:
    """Contrato R-11 C2: 16..128, sin whitespace, prefijo propio y estable."""
    fn = derive
    for execution_id in (
        "",
        "x",
        "unknown",
        "x#1",
        "xtb-77#3",
        "A" * 119 + "#1",
        "A" * 300,
        "A" * 300 + "#9",
        "ñ-á#1",
    ):
        key = fn(execution_id)
        assert IDEMPOTENCY_KEY_MIN_LEN <= len(key) <= IDEMPOTENCY_KEY_MAX_LEN, (execution_id, key)
        assert _WHITESPACE.search(key) is None, key
        assert key.startswith(prefix), key
        assert fn(execution_id) == key, "la clave debe ser estable por execution_id"


def test_keys_are_distinct_across_sides_and_orders() -> None:
    """Inyectividad entre lados, órdenes y secuencias (sin colisiones cruzadas)."""
    keys: set[str] = set()
    expected = 0
    for seq in (1, 2):
        for side in ("buy", "sell"):
            vid = _auto_venue_order_id(side=side, seq=seq)
            for fill_seq in (1, 2, 3, 4):
                keys.add(simulated_idempotency_key(f"{vid}#{fill_seq}"))
                expected += 1
    assert len(keys) == expected


def test_bounded_helper_keeps_the_tail_discriminator() -> None:
    """El helper preserva el ``fill_seq`` en AMBOS caminos (corto y largo)."""
    short = [bounded_idempotency_key("sim-fin-", f"xtb-7#{i}", legacy_budget=120) for i in (1, 2)]
    long_ids = [f"{'p' * 130}#{i}" for i in (1, 2)]
    long = [bounded_idempotency_key("sim-fin-", e, legacy_budget=120) for e in long_ids]
    assert len(set(short)) == 2
    assert len(set(long)) == 2
    assert all(len(k) <= IDEMPOTENCY_KEY_MAX_LEN for k in (*short, *long))


def test_degenerate_execution_id_does_not_collide_with_a_real_one() -> None:
    """El relleno del mínimo usa la marca ``~``: imposible en un slug."""
    degenerate = simulated_idempotency_key("")
    assert len(degenerate) >= IDEMPOTENCY_KEY_MIN_LEN
    assert degenerate.endswith("~")
    assert degenerate not in {simulated_idempotency_key(f"xtb-77#{i}") for i in (1, 2, 3)}
