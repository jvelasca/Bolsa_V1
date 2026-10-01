"""W4 (``v2.88.17-beta``) — fail-closed por símbolo y coherencia de fronteras (hermético).

Prueba la conducta que ``W4`` AÑADE: con el seam ``price_source`` inyectado, el motor deja
de fabricar precio. Dos invariantes:

1. **Sin precio ⇒ no se ejecuta.** Un símbolo sin precio no abre posición (``HOLD``
   fail-closed) y la ausencia queda **declarada y contada** (``price_missing_counts``).
   Antes ese caso tenía dos finales silenciosos: ``base_mid = ... or 100.0`` y
   ``price = ... or 0`` (que el ``if price > 0`` descartaba sin decirlo).
2. **Las DOS fronteras son distintas y cada una gobierna lo suyo** (§3.1): la geometría de
   la señal (``signal.price`` → ``entry_price``/stop/T1) lee ``mid`` (decisión,
   ``close(B-1)``); el precio de la posición y el *fill* leen ``execution`` (``open(B)``).
   Con una fuente que da ``mid = 50`` y ``execution = 55``, el plan ancla en ``50`` y la
   entrada en ``55``: nunca ``100.0``.

El camino hermético (``price_source=None``) NO se toca: lee ``price_script`` en vivo, que es
lo que hace que este incremento sea ``Δ = 0`` para replay y para el resto de la suite.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

import pytest

from bolsa_api.background.auto_price_provider import MappingPriceSource, PriceSource
from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV, EdgeReportSource
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore

_SYMBOLS = ("AAA",)


class _Prov(Protocol):
    def __call__(self, symbol: str) -> DecisionPackage: ...


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", ",".join(_SYMBOLS))
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _buy_lot(lot: float = 250.0) -> _Prov:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=lot)

    return _d


def _edge_source(value: float = 0.9) -> EdgeReportSource:
    async def _read(_strategy_ref: str, _account_id: str | None) -> float | None:
        return value

    return EdgeReportSource(reader=_read)


class _SplitSource:
    """``PriceSource`` de prueba con fronteras SEPARADAS (no existe en producción).

    Es un Protocol estructural: basta con los cuatro métodos. Sirve para demostrar que
    ``mid`` y ``execution`` gobiernan cosas distintas (si alguien las confunde, el plan
    ancla en el precio equivocado y el test rompe).
    """

    def __init__(
        self, *, mid: Mapping[str, float | None], exec_: Mapping[str, float | None]
    ) -> None:
        self._mid = dict(mid)
        self._exec = dict(exec_)

    async def refresh(self) -> None:
        return None

    def mid(self, symbol: str) -> float | None:
        return self._mid.get(symbol)

    def execution(self, symbol: str) -> float | None:
        return self._exec.get(symbol)

    def missing(self, symbols: Sequence[str]) -> tuple[str, ...]:
        return tuple(s for s in symbols if self._exec.get(s) is None)


def _worker(price_source: PriceSource | None) -> AutoSimulationWorker:
    return AutoSimulationWorker(
        clock=step_minute_clock(datetime(2026, 9, 15, 9, 0, tzinfo=UTC))[1],
        exec_store=InMemoryExecutionEventStore(),
        sector_source=lambda _symbol: "tech",
        liquidity_source=lambda _symbol: 1_000_000.0,
        edge_source=_edge_source(),
        price_source=price_source,
        engine_id="w4-price",
    )


# ── 1. Sin precio ⇒ HOLD fail-closed, declarado y contado ──────────────────────


@pytest.mark.asyncio
async def test_symbol_without_price_does_not_open_and_is_declared(v2_env: None) -> None:
    """Sin precio el símbolo NO abre (fail-closed) y la ausencia queda CONTADA.

    Es el caso que ``W4`` mata: antes ``base_mid = ... or 100.0`` fabricaba un precio y la
    posición se abría igual, así que la ausencia era indetectable.
    """
    worker = _worker(MappingPriceSource({}))  # ningún símbolo tiene precio
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0, "sin precio no puede ejecutarse"
    assert worker.price_missing_counts.get("AAA", 0) >= 1, "la ausencia debe DECLARARSE"


@pytest.mark.asyncio
async def test_missing_price_is_not_recorded_when_the_source_has_it(v2_env: None) -> None:
    """Contraprueba: con precio NO se declara ninguna ausencia (el contador es honesto)."""
    worker = _worker(MappingPriceSource({"AAA": 100.0}))
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) > 0
    assert worker.price_missing_counts == {}


@pytest.mark.asyncio
async def test_decision_price_without_execution_does_not_open(v2_env: None) -> None:
    """Con precio de DECISIÓN pero **sin** precio de EJECUCIÓN no se abre (caza ``M283``).

    Aísla la caída a la constante: si ``_v2_price_exec`` fabricara un ``100.0`` cuando la
    fuente no tiene ejecución, la posición se abriría con un precio inventado.
    """
    source = _SplitSource(mid={"AAA": 50.0}, exec_={})
    worker = _worker(source)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0, "sin precio de EJECUCIÓN no se abre"
    assert worker.price_missing_counts.get("AAA", 0) >= 1, "la ausencia se declara"


@pytest.mark.asyncio
async def test_missing_decision_price_is_declared_even_with_execution(v2_env: None) -> None:
    """Sin precio de DECISIÓN (aunque haya ejecución) la ausencia se DECLARA (caza ``M285``).

    Aísla el regreso del ``or 0``: si la geometría cayera a ``0`` en vez de declarar la
    ausencia, el símbolo desaparecería del recuento de precios ausentes de decisión.
    """
    source = _SplitSource(mid={}, exec_={"AAA": 55.0})
    worker = _worker(source)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) == 0, "sin decisión no hay señal que ejecutar"
    assert worker.price_missing_counts.get("AAA", 0) >= 1, "la ausencia de DECISIÓN se declara"


# ── 2. Cada frontera gobierna lo suyo (§3.1) ───────────────────────────────────


@pytest.mark.asyncio
async def test_decision_geometry_uses_mid_while_entry_uses_execution(v2_env: None) -> None:
    """La geometría ancla en ``mid`` (decisión) y la entrada en ``execution`` — nunca 100.0.

    Con ``mid = 50`` y ``execution = 55``: ATR fallback = 2 % del precio de DECISIÓN = 1,
    así que el stop es ``50 − 1.5·1 = 48.5`` y T1 ``50 + 1.5·1 = 51.5``. Si alguien hiciera
    leer la geometría de ``execution`` (o cayera al 100.0 de antes) el stop sería otro.
    """
    source = _SplitSource(mid={"AAA": 50.0}, exec_={"AAA": 55.0})
    worker = _worker(source)
    worker._decider = _buy_lot()
    await worker.auto_turn()

    position = worker._v2_positions.get("AAA")
    assert position is not None, "con precio de decisión y de ejecución debe abrir"
    assert position.initial_stop == pytest.approx(48.5, abs=1e-6), (
        "el stop sale del precio de DECISIÓN (mid=50), no de la ejecución ni del 100.0"
    )
    assert position.target1 == pytest.approx(51.5, abs=1e-6)
    # La referencia de PROTECCIÓN de la posición es el precio de EJECUCIÓN del tick de
    # apertura (``_entry_price``), que es lo que el motor usa para el trailing.
    assert worker._entry_price.get("AAA") == Decimal("55.0"), (
        "la entrada ancla en la frontera de EJECUCIÓN (open de la barra corriente)"
    )
    assert worker.price_missing_counts == {}


@pytest.mark.asyncio
async def test_no_fabricated_100_is_ever_used(v2_env: None) -> None:
    """El precio ``100.0`` no aparece por ningún lado cuando la fuente dice otra cosa.

    Es la afirmación literal de ``W4``: muere el ``100.0`` silencioso. Con una fuente que
    sólo conoce ``7.5``, ni el plan, ni la entrada, ni la marca pueden valer ``100.0``.
    """
    worker = _worker(MappingPriceSource({"AAA": 7.5}))
    worker._decider = _buy_lot()
    await worker.auto_turn()

    assert worker._open.get("AAA", Decimal("0")) > 0
    assert worker._entry_price.get("AAA") == Decimal("7.5")
    position = worker._v2_positions.get("AAA")
    assert position is not None
    assert position.initial_stop < 7.5 < position.target1, "geometría alrededor del precio real"


def test_protocol_shape_of_the_test_double() -> None:
    """El doble de prueba cumple el Protocol (si no, no probaría el seam real)."""
    source: Any = _SplitSource(mid={"A": 1.0}, exec_={"A": 2.0})
    assert isinstance(source, PriceSource)


# ── 3. Costura INERTE: el precio real está OFF salvo declaración explícita ──────


def test_real_price_is_inert_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """El proveedor real NO se activa solo (default OFF ⇒ Δ = 0 y tests PG verdes).

    Es la política de rollout decidida por el propietario (2026-10-01): activar el precio
    real es un acto **explícito**, no un efecto colateral de actualizar el código.
    """
    from bolsa_api.background.auto_simulation_worker import (
        AUTO_REAL_PRICE_ENV,
        real_price_enabled,
    )

    monkeypatch.delenv(AUTO_REAL_PRICE_ENV, raising=False)
    assert real_price_enabled() is False
    for on in ("1", "true", "TRUE", "on", "yes"):
        monkeypatch.setenv(AUTO_REAL_PRICE_ENV, on)
        assert real_price_enabled() is True, f"{on!r} debe activar el precio real"
    for off in ("", "0", "false", "no", "off", "  "):
        monkeypatch.setenv(AUTO_REAL_PRICE_ENV, off)
        assert real_price_enabled() is False, f"{off!r} NO debe activar el precio real"
