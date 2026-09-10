"""V2.27 / A10 — adaptador ESTUDIO del Auto Orchestrator (tests herméticos).

``make_estudio_universe_resolver`` es composición pura: reutiliza
``resolve_estudio_universe`` y cumple el contrato ``resolve_universe`` del
orquestador (``status`` + ``instrument_ids``), incluida la distinción
``empty``/``unavailable`` (fail-closed, sin candidatas inventadas).
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.orchestrator_universe import make_estudio_universe_resolver


class _ListDetail:
    def __init__(self, instrument_ids: list[str]) -> None:
        self.instrument_ids = instrument_ids


class _FakeEstudioList:
    def __init__(self, detail: Any) -> None:
        self._detail = detail
        self.calls: list[str] = []

    async def execute(self, list_id: str) -> Any:
        self.calls.append(list_id)
        if isinstance(self._detail, Exception):
            raise self._detail
        return self._detail


@pytest.mark.asyncio
async def test_resolver_reuses_estudio_list() -> None:
    port = _FakeEstudioList(_ListDetail(["AAA", "BBB"]))
    resolution = await make_estudio_universe_resolver(port)()

    assert resolution.status == "ok"
    assert resolution.instrument_ids == ["AAA", "BBB"]
    assert port.calls == ["estudio"]


@pytest.mark.asyncio
async def test_resolver_empty_universe_is_not_unavailable() -> None:
    port = _FakeEstudioList(_ListDetail([]))
    resolution = await make_estudio_universe_resolver(port)()

    assert resolution.status == "empty"


@pytest.mark.asyncio
async def test_resolver_none_port_is_unavailable() -> None:
    resolution = await make_estudio_universe_resolver(None)()
    assert resolution.status == "unavailable"


@pytest.mark.asyncio
async def test_resolver_port_failure_is_unavailable() -> None:
    port = _FakeEstudioList(RuntimeError("db down"))
    resolution = await make_estudio_universe_resolver(port)()
    assert resolution.status == "unavailable"
