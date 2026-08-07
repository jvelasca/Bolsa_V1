"""Punto de entrada dev/test en Windows (SelectorEventLoop para psycopg)."""

from __future__ import annotations

import asyncio
import atexit
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_xtb_mock_proc: subprocess.Popen[bytes] | None = None


def _configure_event_loop() -> None:
    # Legacy policy (pytest/scripts). Uvicorn 0.36+ ignores this and picks Proactor
    # unless we pass loop= — see uvicorn.run(..., loop=...) below.
    if sys.platform == "win32":
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _uvicorn_loop() -> str:
    """Force Selector on Windows so psycopg works without --reload."""
    if sys.platform == "win32":
        return "bolsa_api.win_loop:selector_event_loop_factory"
    return "auto"


def _xtb_bridge_reachable(bridge_url: str) -> bool:
    health_url = f"{bridge_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=1.5) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _stop_xtb_mock() -> None:
    global _xtb_mock_proc
    if _xtb_mock_proc is None or _xtb_mock_proc.poll() is not None:
        return
    _xtb_mock_proc.terminate()
    try:
        _xtb_mock_proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        _xtb_mock_proc.kill()
    _xtb_mock_proc = None


def _ensure_xtb_mock() -> None:
    global _xtb_mock_proc
    if os.environ.get("XTB_BRIDGE_AUTOSTART") == "0":
        return

    bridge_url = os.environ.get("XTB_BRIDGE_URL", "http://localhost:3002").strip()
    if not bridge_url:
        return

    if "localhost" not in bridge_url and "127.0.0.1" not in bridge_url:
        return

    if _xtb_bridge_reachable(bridge_url):
        return

    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "xtb-bridge-mock.mjs"
    if not script.is_file():
        print(f"[dev] No se encontró {script}; el bridge XTB no se iniciará automáticamente.")
        return

    port = os.environ.get("XTB_BRIDGE_PORT", "3002")
    _xtb_mock_proc = subprocess.Popen(
        ["node", str(script)],
        cwd=str(root),
        env={**os.environ, "XTB_BRIDGE_PORT": port},
    )
    atexit.register(_stop_xtb_mock)
    print(f"[dev] Bridge XTB mock iniciado -> http://localhost:{port}")


def _reload_enabled() -> bool:
    """Opt-in: uvicorn --reload doubles cold import (parent + worker)."""
    raw = os.environ.get("BOLSA_API_RELOAD", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def main() -> None:
    import uvicorn

    from bolsa_infrastructure.config import get_settings

    _configure_event_loop()
    _ensure_xtb_mock()
    settings = get_settings()
    port = int(os.environ.get("API_PYTHON_PORT", settings.api_port))
    root = Path(__file__).resolve().parents[2]
    reload = _reload_enabled()
    if settings.environment == "development" and not reload:
        print(
            "[dev] API sin --reload (arranque rápido). "
            "Autoreload Python: BOLSA_API_RELOAD=1",
            flush=True,
        )

    uvicorn.run(
        "bolsa_api.main:app",
        host=settings.api_host,
        port=port,
        loop=_uvicorn_loop(),
        reload=reload,
        reload_dirs=[
            str(root / "apps" / "api-python" / "src"),
            str(root / "packages" / "py"),
        ]
        if reload
        else None,
    )


if __name__ == "__main__":
    main()
