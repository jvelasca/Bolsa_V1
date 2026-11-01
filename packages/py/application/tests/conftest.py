"""Config pytest para application (Windows + psycopg async)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

# psycopg async no soporta ProactorEventLoop en Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def _load_repo_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


@pytest.fixture(autouse=True)
def _reset_yahoo_traffic_gate() -> Any:
    """N-1 — el semáforo de Yahoo es estado de PROCESO: cada test lo deja habilitado.

    Un test que resuelve configuración con Yahoo deshabilitado lo apaga para el resto del
    proceso; sin esta guarda, un test posterior que sí espera tráfico fallaría según el
    orden de ejecución (y no por su propio código).
    """
    from bolsa_market.yahoo_client import set_yahoo_traffic_enabled

    yield
    set_yahoo_traffic_enabled(True)
