"""V2.76 — apagado ORDENADO del forward: se suelta el LEASE antes de cerrar el pool.

Deuda medida en la auditoría del PAPER vivo (2026-11-06): el ``finally`` de ``_run`` sólo
hacía ``engine.dispose()``. ``run_tick`` adquiere el lease durable de ``auto_engine_runs``
(migración 063) y lo renueva en cada turno, así que el proceso terminaba dejando el lease
VIVO hasta que vencía su TTL (180 s por defecto) y una reanudación inmediata lo esperaba.

Lo que se blinda aquí, sin PostgreSQL:

* el apagado suelta el lease **con el pool todavía abierto** (``close()`` abre una sesión) y
  libera el pool DESPUÉS — el orden es el contrato;
* una corrida que nunca compuso runtime (preflight, error de watch) sólo libera el pool;
* ``close()`` es un **no-op** cuando este proceso no tiene lease: no abre sesión;
* ``close()`` suelta el lease que sí tiene y limpia el estado;
* un store roto **no** rompe el apagado: el lease se limpia igual (nunca deja el proceso
  atado a un recurso que ya no puede liberar).
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimRuntime
from bolsa_application.auto_engine_state_store import AutoEngineLease

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_76_forward_market_material.py"

_T0 = datetime(2026, 11, 6, 7, 30, tzinfo=UTC)


def _load_cli() -> Any:
    name = "v2_76_forward_market_material_shutdown"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Engine:
    """Pool mínimo: sólo registra el orden del apagado."""

    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def dispose(self) -> None:
        self._order.append("dispose")


class _Runtime:
    """Runtime mínimo: ``close()`` es lo único que el apagado necesita."""

    def __init__(self, order: list[str]) -> None:
        self._order = order

    async def close(self) -> None:
        self._order.append("close")


class _SessionCM:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Factory:
    """``session_factory`` falso: cuenta las sesiones y puede explotar si se abre."""

    def __init__(self, *, explode: bool = False) -> None:
        self.calls = 0
        self._explode = explode

    def __call__(self) -> _SessionCM:
        self.calls += 1
        if self._explode:
            raise AssertionError("close() sin lease NO debe abrir sesión")
        return _SessionCM()


def _runtime(factory: Any) -> AutoSimRuntime:
    return AutoSimRuntime(
        factory,
        worker=SimpleNamespace(),
        engine_id="auto-sim-shutdown",
        account_id="acc-test",
    )


def _lease() -> AutoEngineLease:
    return AutoEngineLease(
        engine_id="auto-sim-shutdown",
        owner="auto-sim-1",
        generation=2,
        expires_at=_T0 + timedelta(seconds=180),
    )


# ── Orden del apagado ────────────────────────────────────────────────────────


def test_shutdown_releases_the_lease_before_disposing_the_pool() -> None:
    """El lease se suelta con el pool VIVO: ``close()`` abre una sesión con el factory."""
    cli = _load_cli()
    order: list[str] = []

    asyncio.run(cli._shutdown(_Runtime(order), _Engine(order)))

    assert order == ["close", "dispose"]


def test_shutdown_without_runtime_only_disposes_the_pool() -> None:
    """Preflight o error de watch: no hay lease que soltar y el pool se libera igual."""
    cli = _load_cli()
    order: list[str] = []

    asyncio.run(cli._shutdown(None, _Engine(order)))

    assert order == ["dispose"]


def test_shutdown_disposes_the_pool_even_if_close_is_interrupted() -> None:
    """``CancelledError`` no lo absorbe ``close()``: el pool se libera en cualquier caso."""
    cli = _load_cli()
    order: list[str] = []

    class _Interrupted(_Runtime):
        async def close(self) -> None:
            order.append("close")
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(cli._shutdown(_Interrupted(order), _Engine(order)))

    assert order == ["close", "dispose"]


# ── Contrato de ``AutoSimRuntime.close()`` ───────────────────────────────────


def test_close_without_lease_is_a_noop_and_does_not_open_a_session() -> None:
    """Un proceso que ya perdió el lease no puede ni abrir sesión para «soltarlo»."""
    runtime = _runtime(_Factory(explode=True))

    asyncio.run(runtime.close())

    assert runtime._lease is None


def test_close_releases_the_held_lease_and_clears_it(
    monkeypatch: Any,
) -> None:
    """El lease se suelta con SU dueño y generación, y el estado local queda limpio."""
    from bolsa_application import auto_engine_state_store as store_module

    released: list[AutoEngineLease] = []

    async def fake_release(_self: Any, lease: AutoEngineLease) -> bool:
        released.append(lease)
        return True

    monkeypatch.setattr(store_module.PostgresAutoEngineStore, "release_lease", fake_release)
    factory = _Factory()
    runtime = _runtime(factory)
    lease = _lease()
    runtime._lease = lease  # noqa: SLF001 — estado del runtime que el apagado debe soltar.

    asyncio.run(runtime.close())

    assert released == [lease], "se suelta exactamente el lease de este proceso"
    assert runtime._lease is None
    assert factory.calls == 1, "close() usa una sola sesión: abrir y soltar"


def test_close_swallows_a_broken_store_and_still_clears_the_lease(
    monkeypatch: Any,
) -> None:
    """Un fallo al soltar no rompe el apagado: el proceso no queda atado al recurso."""
    from bolsa_application import auto_engine_state_store as store_module

    async def broken_release(_self: Any, _lease: AutoEngineLease) -> bool:
        raise RuntimeError("PG no responde")

    monkeypatch.setattr(store_module.PostgresAutoEngineStore, "release_lease", broken_release)
    runtime = _runtime(_Factory())
    runtime._lease = _lease()  # noqa: SLF001 — mismo seam que el caso anterior.

    asyncio.run(runtime.close())

    assert runtime._lease is None
