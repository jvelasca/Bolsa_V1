"""Windows loop factory must return a SelectorEventLoop instance for uvicorn."""

from __future__ import annotations

import asyncio

from bolsa_api.win_loop import selector_event_loop_factory


def test_selector_event_loop_factory_returns_instance() -> None:
    loop = selector_event_loop_factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
        assert not isinstance(loop, type)
    finally:
        loop.close()
