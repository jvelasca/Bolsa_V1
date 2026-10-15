"""V2.76 · selección del watch del forward — ``--watch-from-estudio`` fail-closed.

Contrato que se blinda (sin PostgreSQL: se monkeypatchean las dos fuentes):

* Con ``--watch-from-estudio`` el watch sale del universo **ESTUDIO** (∩ allowlist).
* **Fail-closed**: sin ESTUDIO ``ok`` el watch queda VACÍO y se DECLARA (``RuntimeError``);
  **nunca** se cae al catálogo (caer fabricaría un universo que no se quiere certificar).
* Sin el flag, el comportamiento histórico no cambia: watch del CLI o del catálogo.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_76_forward_market_material.py"


def _load_cli() -> Any:
    name = "v2_76_forward_market_material_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _resolution(status: str, ids: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(status=status, instrument_ids=ids)


def test_estudio_ok_uses_estudio_watch(monkeypatch: Any) -> None:
    cli = _load_cli()
    captured: dict[str, Any] = {}

    async def fake_estudio(factory: Any, *, allowlist: tuple[str, ...]) -> Any:
        captured["allowlist"] = allowlist
        return _resolution("ok", ("AAA", "BBB"))

    async def forbidden_catalog(*_a: Any, **_k: Any) -> list[str]:  # pragma: no cover
        raise AssertionError("no debe caer al catálogo con ESTUDIO ok")

    monkeypatch.setattr(cli, "_watch_from_estudio", fake_estudio)
    monkeypatch.setattr(cli, "_watch_from_catalog", forbidden_catalog)

    watch, source = asyncio.run(
        cli._resolve_forward_watch(None, from_estudio=True, cli_watch=(), watch_size=20, min_bars=60)
    )
    assert watch == ["AAA", "BBB"]
    assert source == "estudio"
    assert captured["allowlist"] == ()


def test_estudio_allowlist_is_passed_through(monkeypatch: Any) -> None:
    cli = _load_cli()
    captured: dict[str, Any] = {}

    async def fake_estudio(factory: Any, *, allowlist: tuple[str, ...]) -> Any:
        captured["allowlist"] = allowlist
        return _resolution("ok", ("AAA",))

    monkeypatch.setattr(cli, "_watch_from_estudio", fake_estudio)
    watch, source = asyncio.run(
        cli._resolve_forward_watch(
            None, from_estudio=True, cli_watch=["AAA", "ZZZ"], watch_size=20, min_bars=60
        )
    )
    assert watch == ["AAA"]
    assert source == "estudio"
    assert captured["allowlist"] == ("AAA", "ZZZ")


def test_estudio_unavailable_is_fail_closed_and_never_falls_back(monkeypatch: Any) -> None:
    cli = _load_cli()
    catalog_calls: list[int] = []

    async def fake_estudio(factory: Any, *, allowlist: tuple[str, ...]) -> Any:
        return _resolution("unavailable", ())

    async def spy_catalog(*_a: Any, **_k: Any) -> list[str]:
        catalog_calls.append(1)
        return ["CATALOGO"]

    monkeypatch.setattr(cli, "_watch_from_estudio", fake_estudio)
    monkeypatch.setattr(cli, "_watch_from_catalog", spy_catalog)

    import pytest  # local: sólo el caso de error lo necesita

    with pytest.raises(RuntimeError, match="fail-closed"):
        asyncio.run(
            cli._resolve_forward_watch(
                None, from_estudio=True, cli_watch=(), watch_size=20, min_bars=60
            )
        )
    assert catalog_calls == [], "fail-closed: el catálogo NO se consulta con ESTUDIO no ok"


def test_estudio_empty_is_fail_closed(monkeypatch: Any) -> None:
    cli = _load_cli()

    async def fake_estudio(factory: Any, *, allowlist: tuple[str, ...]) -> Any:
        return _resolution("empty", ())

    monkeypatch.setattr(cli, "_watch_from_estudio", fake_estudio)

    import pytest

    with pytest.raises(RuntimeError, match="fail-closed"):
        asyncio.run(
            cli._resolve_forward_watch(
                None, from_estudio=True, cli_watch=(), watch_size=20, min_bars=60
            )
        )


def test_default_off_uses_cli_watch(monkeypatch: Any) -> None:
    cli = _load_cli()

    async def forbidden_estudio(*_a: Any, **_k: Any) -> Any:  # pragma: no cover
        raise AssertionError("sin --watch-from-estudio no se consulta ESTUDIO")

    monkeypatch.setattr(cli, "_watch_from_estudio", forbidden_estudio)

    watch, source = asyncio.run(
        cli._resolve_forward_watch(
            None, from_estudio=False, cli_watch=["ZZZ"], watch_size=20, min_bars=60
        )
    )
    assert watch == ["ZZZ"]
    assert source == "cli"


def test_default_off_falls_back_to_catalog(monkeypatch: Any) -> None:
    cli = _load_cli()

    async def fake_catalog(factory: Any, size: int, *, min_bars: int) -> list[str]:
        return ["CAT1", "CAT2"]

    monkeypatch.setattr(cli, "_watch_from_catalog", fake_catalog)

    watch, source = asyncio.run(
        cli._resolve_forward_watch(
            None, from_estudio=False, cli_watch=(), watch_size=3, min_bars=60
        )
    )
    assert watch == ["CAT1", "CAT2"]
    assert source == "catalog"
