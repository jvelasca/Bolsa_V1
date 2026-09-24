"""AUTO-15 — la racha de fallos del gate como estado DURABLE (contrato puro + gemelo in-memory).

Lo que se prueba aquí es el **contrato** del store, no el acceso a datos (eso lo certifica el test
PG del job ``auto-v2-durable-pg``): que la racha sea **consecutiva** (un éxito la resetea, un fallo
tras un éxito vuelve a empezar en 1), que una fila ausente sea "sin constancia durable" (racha 0) y
**nunca** un cero fabricado, y que el reset del éxito **no amplifique** escrituras: sin racha viva
no se escribe nada, que es lo que mantiene el camino caliente del turno igual de barato.

El invariante de la fase —«no acusar sin prueba» sobrevive a un reinicio— depende de que el número
que el worker siembra al arrancar salga de aquí con la misma semántica que tenía el contador de
proceso que sustituye. Y el store escribe en la sesión del TICK: un fallo de escritura tiene que
**limpiarla** (``rollback``) y subir el error, o el siguiente store del turno se cae con
``PendingRollbackError``; eso también se mide aquí, con una sesión que falla (hermético).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from bolsa_application.adaptive_gate_store import (
    AdaptiveGateState,
    InMemoryAdaptiveGateStore,
    PostgresAdaptiveGateStore,
    sink_failures_from_state,
)

_ACCOUNT = "acc-1"
_ENGINE = "engine-1"
_T0 = "2026-09-23T10:00:00Z"
_T1 = "2026-09-23T10:01:00Z"
_T2 = "2026-09-23T10:02:00Z"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_absent_row_is_zero_failures_and_never_an_invented_one() -> None:
    """Sin fila: racha 0 (no se observó un fallo), y el hueco lo declara el llamante."""
    assert sink_failures_from_state(None) == 0


def test_a_negative_or_corrupt_count_is_clamped_at_zero() -> None:
    """Una fila con un número imposible no puede fabricar una racha negativa."""
    assert sink_failures_from_state(AdaptiveGateState(sink_failures=-3)) == 0


def test_an_absent_row_loads_as_none_not_as_a_zero_state() -> None:
    """``load`` de una cuenta+motor sin fila devuelve ``None``: la ausencia es información."""
    store = InMemoryAdaptiveGateStore()

    assert _run(store.load(_ACCOUNT, _ENGINE)) is None
    assert len(store) == 0


def test_failures_increment_consecutively_and_stamp_the_failure_instant() -> None:
    """Tres fallos seguidos dan racha 1, 2 y 3, cada uno con su instante de fallo."""
    store = InMemoryAdaptiveGateStore()

    assert _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0)) == 1
    assert _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T1)) == 2
    assert _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T2)) == 3

    state = _run(store.load(_ACCOUNT, _ENGINE))
    assert state is not None
    assert state.sink_failures == 3
    assert state.last_failure_at == _T2


def test_a_success_resets_a_live_streak_and_keeps_the_failure_trail() -> None:
    """El éxito resetea la racha a 0 y fecha la curación; el rastro del fallo no se borra."""
    store = InMemoryAdaptiveGateStore()
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0))
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T1))

    reset = _run(store.record_success(_ACCOUNT, _ENGINE, at=_T2))

    assert reset == 1
    state = _run(store.load(_ACCOUNT, _ENGINE))
    assert state is not None
    assert state.sink_failures == 0
    assert state.last_success_at == _T2
    # "cuándo empezó a fallar" sigue siendo auditable después de curarse.
    assert state.last_failure_at == _T1


def test_a_success_without_a_streak_does_not_write_anything() -> None:
    """Sin racha viva no se escribe: el camino sano no amplifica escrituras por tick.

    Doble control: ni con tabla vacía (no se crea fila), ni con una racha ya a 0 (no se toca).
    """
    store = InMemoryAdaptiveGateStore()

    assert _run(store.record_success(_ACCOUNT, _ENGINE, at=_T0)) == 0
    assert len(store) == 0

    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0))
    assert _run(store.record_success(_ACCOUNT, _ENGINE, at=_T1)) == 1
    before = _run(store.load(_ACCOUNT, _ENGINE))

    assert _run(store.record_success(_ACCOUNT, _ENGINE, at=_T2)) == 0
    assert _run(store.load(_ACCOUNT, _ENGINE)) == before


def test_a_failure_after_a_success_starts_the_streak_again_at_one() -> None:
    """La racha es CONSECUTIVA: curarse y volver a fallar no resucita la cuenta vieja."""
    store = InMemoryAdaptiveGateStore()
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0))
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T1))
    _run(store.record_success(_ACCOUNT, _ENGINE, at=_T1))

    assert _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T2)) == 1


def test_the_streak_is_per_account_and_engine_and_never_leaks_across() -> None:
    """Una racha no cura ni contagia a otra cuenta ni a otro motor de la misma cuenta."""
    store = InMemoryAdaptiveGateStore()
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0))
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T1))
    _run(store.record_failure(_ACCOUNT, "engine-2", at=_T1))

    assert _run(store.record_success(_ACCOUNT, _ENGINE, at=_T2)) == 1
    other_engine = _run(store.load(_ACCOUNT, "engine-2"))
    other_account = _run(store.load("acc-2", _ENGINE))

    assert other_engine is not None and other_engine.sink_failures == 1
    assert other_account is None


def test_the_state_travels_to_the_log_with_its_own_field_names() -> None:
    """El resumen publicable lleva los nombres de campo con los que se audita."""
    store = InMemoryAdaptiveGateStore()
    _run(store.record_failure(_ACCOUNT, _ENGINE, at=_T0))
    state = _run(store.load(_ACCOUNT, _ENGINE))

    assert state is not None
    assert state.to_dict() == {
        "accountId": _ACCOUNT,
        "engineId": _ENGINE,
        "sinkFailures": 1,
        "lastFailureAt": _T0,
        "lastSuccessAt": None,
        "updatedAt": _T0,
    }


class _BrokenSession:
    """Sesión que falla al escribir: mide el contrato de LIMPIEZA, no el acceso a datos."""

    def __init__(self) -> None:
        self.rollbacks = 0
        self.commits = 0

    async def execute(self, _statement: Any) -> Any:
        raise RuntimeError("la base no responde")

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def test_a_failed_write_cleans_the_tick_session_and_lets_the_error_up() -> None:
    """Un fallo de escritura NO envenena la sesión del turno, y el error SUBE (se declara).

    El worker escribe la racha en la MISMA sesión del tick: sin ``rollback`` el siguiente store
    del turno fallaría con ``PendingRollbackError`` y esa traza rota tumbaría el compromiso de
    capital. Se mide el contrato con una sesión que falla (hermético, sin PG): un ``rollback`` por
    intento, ningún ``commit``, y el error hacia arriba para que el worker lo declare.
    """
    session = _BrokenSession()
    store = PostgresAdaptiveGateStore(session)

    with pytest.raises(RuntimeError):
        _run(store.record_failure(_ACCOUNT, _ENGINE))
    with pytest.raises(RuntimeError):
        _run(store.record_success(_ACCOUNT, _ENGINE, at=_T0))

    assert session.rollbacks == 2, "cada escritura fallida limpia la sesión del tick"
    assert session.commits == 0, "un fallo de escritura no commitea nada"
