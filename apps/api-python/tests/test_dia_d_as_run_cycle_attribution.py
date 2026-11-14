"""Atribución de ciclo por id de orden en el as-run (``v2_102``).

El ``cycle_id`` del fill está a NULL en las filas anteriores al sellado por fill, pero el
ciclo de esa misma corrida sí quedó durable en el linaje de la orden. Estos tests fijan el
**join exacto** por id de orden, que es lo que permite agrupar por posición canónica en vez
de inferir episodios: si se rompiera, la reentrada volvería a compartir denominador de R sin
que ningún test de dominio lo notara.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from typing import Any

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str) -> Any:
    path = _SCRIPTS / name
    spec = importlib.util.spec_from_file_location(f"test_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner() -> Any:
    return _load("v2_102_dia_d_as_run.py")


def test_buy_fill_resolves_its_cycle_by_order_id(runner: Any) -> None:
    """``execution_id`` = ``<orderId>#<tramo>``: todos los tramos de la orden son el ciclo."""
    order = "sim-autowindow1-acc-buy-INST1-tail-buy-INST1-1"
    buy_cycles = {order: "cyc-a"}

    for fragment in ("#1", "#2", "#7"):
        assert runner._cycle_for_fill(order + fragment, "buy", buy_cycles, {}) == "cyc-a"


def test_sell_fill_resolves_its_cycle_by_exit_order_id(runner: Any) -> None:
    """La orden de venta termina en el ULID de ``auto_exit_orders.exit_order_id`` (sin ``-``)."""
    exit_order = "01M79Z1ZZ8BKFEY5V74WC6AFBQ"  # ULID de 26 caracteres, como en la tabla
    execution = f"sim-auto-sell-INST1-auto-sell-INST1{exit_order}#3"
    sell_cycles = {exit_order: "cyc-a"}

    assert runner._cycle_for_fill(execution, "sell", {}, sell_cycles) == "cyc-a"


def test_sell_fill_supports_the_legacy_exit_id_lengths(runner: Any) -> None:
    """La ventana AUTO antigua usa ids de 17: la extracción no puede fijar una sola longitud."""
    exit_order = "01M70NRDZ5TBBKY59"  # 17 caracteres, formato antiguo
    execution = f"sim-autowindow1-acc-sell-INST1-autowindow1sellINST1{exit_order}#1"
    sell_cycles = {exit_order: "cyc-a"}

    assert runner._cycle_for_fill(execution, "sell", {}, sell_cycles) == "cyc-a"


def test_unknown_order_or_missing_id_is_declared_as_no_cycle(runner: Any) -> None:
    """Sin orden en el linaje no se inventa ciclo: la posición cae al episodio declarado."""
    assert runner._cycle_for_fill("sim-x-buy-INST1-unknown#1", "buy", {}, {}) is None
    assert runner._cycle_for_fill(None, "buy", {}, {}) is None
    assert runner._cycle_for_fill("", "sell", {}, {}) is None


def test_fragment_suffix_does_not_confuse_the_order_lookup(runner: Any) -> None:
    """El ``#tramo`` se recorta antes de buscar: un id con ``#`` no pierde la atribución."""
    execution = "sim-order#4"
    assert runner._cycle_for_fill(execution, "buy", {"sim-order": "cyc-b"}, {}) == "cyc-b"
