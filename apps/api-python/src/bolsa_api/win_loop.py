"""Event loop factory for Windows + psycopg async.

Uvicorn 0.36+ uses ProactorEventLoop on win32 when not in a reload subprocess.
psycopg async requires SelectorEventLoop.

Important: for a custom `loop="pkg:factory"` string, uvicorn imports the callable
and uses it as-is (does NOT call it with use_subprocess first). asyncio.Runner
then does `loop = factory()`, so this must return a loop *instance*.
"""

from __future__ import annotations

import asyncio


def selector_event_loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
