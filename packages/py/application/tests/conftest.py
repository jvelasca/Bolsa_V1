"""Config pytest para application (Windows + psycopg async)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

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
