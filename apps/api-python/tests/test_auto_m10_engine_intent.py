"""M10 — la intención durable del operador: un OFF explícito gana al env en cada tick.

El fallo que se cierra: AUTO se habilitaba sólo por ``AUTO_SIMULATION_WORKER_ENABLED``. Un
reinicio con la variable puesta volvía a arrancar el motor aunque el operador lo hubiera
apagado, porque no existía ningún latch durable del apagado.

La ausencia de intención NO se convierte en OFF (apagaría motores que hoy funcionan): el env
sigue decidiendo. Y un estado ilegible tampoco es una decisión.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.api.v1.routes.auto_engine_intent import _dto
from bolsa_api.background.auto_simulation_worker import (
    OPERATOR_INTENT_OFF,
    OPERATOR_INTENT_UNREADABLE,
    AutoSimRuntime,
)
from bolsa_application.auto_engine_intent_store import (
    INTENT_OFF,
    INTENT_ON,
    AutoEngineIntent,
    InMemoryAutoEngineIntentStore,
    coerce_intent_state,
)

_ACCOUNT = "acc-m10"
_ENGINE = "eng-m10"


# ── El store ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_roundtrip_and_versioning() -> None:
    store = InMemoryAutoEngineIntentStore()

    assert await store.load(_ACCOUNT, _ENGINE) is None, "sin fila no hay decisión"

    first = AutoEngineIntent(
        account_id=_ACCOUNT, engine_id=_ENGINE, desired_state=INTENT_OFF, reason="maint"
    )
    assert await store.save(first) is True
    loaded = await store.load(_ACCOUNT, _ENGINE)
    assert loaded is not None and loaded.is_off
    assert loaded.version == 1

    again = AutoEngineIntent(account_id=_ACCOUNT, engine_id=_ENGINE, desired_state=INTENT_ON)
    assert await store.save(again) is False, "la segunda escritura actualiza"
    loaded = await store.load(_ACCOUNT, _ENGINE)
    assert loaded is not None and loaded.desired_state == INTENT_ON
    assert loaded.version == 2, "la versión cuenta escrituras"


def test_only_on_and_off_are_decisions() -> None:
    assert coerce_intent_state(" on ") == INTENT_ON
    assert coerce_intent_state("Off") == INTENT_OFF
    assert coerce_intent_state("auto") is None
    assert coerce_intent_state("") is None
    assert coerce_intent_state(None) is None


# ── El gate del runtime ──────────────────────────────────────────────────────────


class _Result:
    def __init__(self, row: Any) -> None:
        self._row = row

    def scalar_one_or_none(self) -> Any:
        return self._row


class _Session:
    def __init__(self, row: Any) -> None:
        self._row = row

    async def execute(self, _statement: Any) -> _Result:
        return _Result(self._row)

    async def commit(self) -> None:
        return None


class _SessionContext:
    def __init__(self, row: Any) -> None:
        self._session = _Session(row)

    async def __aenter__(self) -> _Session:
        return self._session

    async def __aexit__(self, *_exc: Any) -> bool:
        return False


def _row(state: str) -> Any:
    return SimpleNamespace(
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        desired_state=state,
        reason="maintenance",
        actor="ops",
        updated_at=None,
        version=3,
    )


@pytest.mark.asyncio
async def test_runtime_refuses_the_turn_when_the_operator_turned_auto_off() -> None:
    runtime = AutoSimRuntime(
        lambda: _SessionContext(_row(INTENT_OFF)),
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
    )

    report = await runtime.run_tick()

    assert report is None, "sin intención ON no se conduce el turno"
    assert runtime._worker._last_gate_reason == (OPERATOR_INTENT_OFF,)


@pytest.mark.asyncio
async def test_absent_intent_is_not_off() -> None:
    """Sin fila el env decide: el gate no puede inventar un apagado."""
    runtime = AutoSimRuntime(
        lambda: _SessionContext(None),
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
    )

    session = _Session(None)
    assert await runtime._operator_intent_blocks_turn(session) is False
    assert runtime._worker._last_gate_reason != (OPERATOR_INTENT_OFF,)


@pytest.mark.asyncio
async def test_readable_intent_on_does_not_block() -> None:
    runtime = AutoSimRuntime(
        lambda: _SessionContext(_row(INTENT_ON)),
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
    )

    session = _Session(_row(INTENT_ON))
    assert await runtime._operator_intent_blocks_turn(session) is False
    assert runtime._worker._last_gate_reason != (OPERATOR_INTENT_OFF,)


@pytest.mark.asyncio
async def test_unreadable_intent_fails_closed() -> None:
    """Si la intención no se puede leer no hay permiso declarado: no se opera."""
    runtime = AutoSimRuntime(
        lambda: _SessionContext(None),
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
    )

    class _BrokenSession:
        async def execute(self, _statement: Any) -> Any:
            raise RuntimeError("auto_engine_intent ilegible")

    assert await runtime._operator_intent_blocks_turn(_BrokenSession()) is True
    assert runtime._worker._last_gate_reason == (OPERATOR_INTENT_UNREADABLE,)


# ── El DTO de la API ────────────────────────────────────────────────────────────


def _intent(state: str) -> AutoEngineIntent:
    return AutoEngineIntent(
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        desired_state=state,
        updated_at=datetime(2026, 11, 5, 9, 0, tzinfo=UTC).isoformat(),
    )


def test_effective_state_requires_env_and_no_operator_off() -> None:
    assert _dto(account_id=_ACCOUNT, engine_id=_ENGINE, intent=None, env_enabled=True).effectiveEnabled
    assert not _dto(
        account_id=_ACCOUNT, engine_id=_ENGINE, intent=_intent(INTENT_OFF), env_enabled=True
    ).effectiveEnabled
    assert not _dto(
        account_id=_ACCOUNT, engine_id=_ENGINE, intent=_intent(INTENT_ON), env_enabled=False
    ).effectiveEnabled, "el env sigue siendo el interruptor duro"


def test_dto_declares_which_side_decided() -> None:
    dto = _dto(account_id=_ACCOUNT, engine_id=_ENGINE, intent=None, env_enabled=True)
    assert dto.operatorState is None and dto.envEnabled is True
    assert dto.notes == []

    dto = _dto(
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        intent=_intent(INTENT_OFF),
        env_enabled=True,
        notes=["no_account_scope"],
    )
    assert dto.operatorState == INTENT_OFF
    assert dto.reason is None and dto.actor is None
    assert dto.notes == ["no_account_scope"]
