"""Regresión de los huecos R-1, R-2, P-1, P-2 y R-4 de la verificación 2026-10-26.

El anexo ``docs/engineering/verificacion-dictamen-paper-multidia-2026-10-26.md`` (§8) lista
ocho huecos con la prueba que cerraría cada uno. Esta suite implementa los cinco que
dependen del worker AUTO y recorre el camino REAL (``real_turn`` / ``auto_turn``), no los
atajos de test que dejaban el caso fuera de cobertura:

* **R-1** — un fallo de ``read_projection`` en el arranque deja ``_open`` vacío y el tick
  siguiente abre BUY (fail-open). La prueba conduce ``real_turn`` (no ``auto_turn``) y exige
  el veto de aperturas y el reintento de la readopción.
* **R-2** — el canónico es de CUENTA y la proyección es de MOTOR: la reconstrucción escribía
  el total de la cuenta en la fila de un motor y el total proyectado pasaba a 300 (un worker)
  o 400 (dos). La prueba exige el invariante ``Σ filas vivas == canónico``.
* **P-1** — un fallo del ``kill_switch_store.load()`` dejaba el latch desengajado y el
  proceso seguía publicando ``RUNNING``. La prueba distingue fallo persistente de transitorio.
* **P-2** — la protección se evaluaba con ``open(B)``: un ``Low`` intrabar por debajo del
  stop no disparaba. La prueba usa una fuente OHLC de verdad y exige el fill declarado al
  nivel del stop (o al open si el hueco es peor).
* **R-4** — la identidad de motor la fijaba el runner; sin la variable, el arranque durable
  caía a ``auto-sim`` en silencio. La prueba exige un fallo explícito.

Hermético: sin PG, sin red. Reutiliza el banco de ``test_auto_v44_exit_crash_matrix`` (los
mismos stores durables y el mismo ``_restart`` que modela el reinicio como pérdida de RAM).
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from bolsa_analytics.cognitive.exit_plan import (
    build_exit_plan_from_position,
    protective_fill_price,
)
from bolsa_analytics.cognitive.position_ledger import AppliedFillFact
from bolsa_analytics.cognitive.position_state import (
    apply_position_mark,
    apply_position_reduce,
    build_position_state_from_fill,
)
from bolsa_application.applied_fills import CanonicalPositions
from bolsa_application.auto_v2_entry import V2_ENGINE_ENV
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.kill_switch_store import InMemoryKillSwitchStore, KillState
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
)

from bolsa_api.background import auto_simulation_worker as worker_module
from tests.test_auto_v44_exit_crash_matrix import (
    ACCOUNT_ID,
    ENGINE_ID,
    _restart,
    _seed_buy_position,
    _Stores,
)

_SECOND_ENGINE = "auto-sim-b"
_SYMBOL = "AAA"


# ---------------------------------------------------------------------------
# Entorno y utilidades
# ---------------------------------------------------------------------------


@pytest.fixture
def legacy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Camino legacy (``_decider`` conduce la entrada): el de la batería de crash."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")


@pytest.fixture
def v2_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Camino V2 (planificador): el que consulta el HALT durable y gestiona posición."""
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", _SYMBOL)
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")
    monkeypatch.setenv(V2_ENGINE_ENV, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_REGIME", "BULL_TREND")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_EQUITY", "100000")


def _buy() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="BUY", instrument_id=symbol, quantity=200)

    return _d


def _hold() -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)

    return _d


def _sell(quantity: float) -> Any:
    def _d(symbol: str) -> DecisionPackage:
        return DecisionPackage(action="SELL", instrument_id=symbol, quantity=quantity)

    return _d


def _canonical(
    positions: dict[str, Any],
    *,
    facts: tuple[AppliedFillFact, ...] = (),
) -> Any:
    """Lector canónico determinista (libro de fills aplicados)."""

    async def reader(_account_id: str) -> CanonicalPositions:
        return CanonicalPositions(
            {symbol: Decimal(str(qty)) for symbol, qty in positions.items()},
            facts=facts,
        )

    return reader


def _fact(execution_id: str, qty: float) -> AppliedFillFact:
    return AppliedFillFact(
        execution_id=execution_id,
        instrument_id=_SYMBOL,
        side="buy",
        quantity=qty,
        price=100.0,
        account_id=ACCOUNT_ID,
    )


def _live_rows(store: InMemorySimAutoPositionStore, symbol: str = _SYMBOL) -> list[Decimal]:
    """Cantidades de TODAS las filas vivas del símbolo (la suma es el invariante de R-2)."""
    return [
        rows[symbol].quantity
        for (account, _engine), rows in store._rows.items()  # noqa: SLF001 — lectura de test.
        if account == ACCOUNT_ID and symbol in rows and rows[symbol].quantity > 0
    ]


class _ProjectionFailingStore(InMemorySimAutoPositionStore):
    """Falla SÓLO ``read_projection`` (la equity y el resto siguen legibles).

    Es la condición exacta del fail-open de R-1: si el fallo alcanzara también la equity,
    ``_book_equity_unreadable`` vetaría el BUY y el hueco quedaría enmascarado.
    """

    async def read_projection(self, account_id: str, engine_id: str) -> dict[str, Any]:
        raise RuntimeError("projection unreadable (R-1)")


class _FlakyKillSwitchStore(InMemoryKillSwitchStore):
    """``load()`` falla de forma transitoria (``fail_next``) o persistente (``always_fail``)."""

    def __init__(
        self,
        *,
        seed: tuple[KillState, ...] = (),
        fail_next: int = 0,
        always_fail: bool = False,
    ) -> None:
        super().__init__(seed=seed)
        self.fail_next = fail_next
        self.always_fail = always_fail
        self.loads = 0

    async def load(self, account_id: str, engine_id: str) -> KillState | None:
        self.loads += 1
        if self.always_fail or self.fail_next > 0:
            if self.fail_next > 0:
                self.fail_next -= 1
            raise RuntimeError("kill state unreadable (P-1)")
        return await super().load(account_id, engine_id)


class _OhlcPriceSource:
    """Fuente de precio con las DOS fronteras y los EXTREMOS de la barra corriente.

    ``execution``/``mid`` son el contrato ya existente; ``low``/``high`` son lo que el
    motor nunca leía y lo que hace medible el rango intradía de P-2.
    """

    def __init__(self, *, open_: float, low: float, high: float, mid: float) -> None:
        self._open = open_
        self._low = low
        self._high = high
        self._mid = mid
        self.refreshes = 0

    async def refresh(self) -> None:
        self.refreshes += 1

    def mid(self, symbol: str) -> float | None:
        return self._mid

    def execution(self, symbol: str) -> float | None:
        return self._open

    def low(self, symbol: str) -> float | None:
        return self._low

    def high(self, symbol: str) -> float | None:
        return self._high

    def missing(self, symbols: Any) -> tuple[str, ...]:
        return ()


# ---------------------------------------------------------------------------
# R-1 — fail-open de la readopción
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_projection_read_failure_vetoes_openings(
    legacy_env: None,
) -> None:
    """Un fallo de ``read_projection`` NO autoriza abrir: se veta y se REINTENTA.

    Antes: la excepción dejaba ``_open`` vacío, ``_readopted = True`` y ``_reconciliation``
    sin entrada ⇒ ``_openings_vetoed("AAA")`` era ``False`` y el tick siguiente compraba.
    """
    stores = _Stores()
    failing = _ProjectionFailingStore()
    w = _restart(stores, minute=0)
    w._position_store = failing
    w._decider = _buy()

    report = await w.real_turn(
        exec_store=stores.exec_store,
        auto_store=None,
        finance_applier=None,
        account_id=ACCOUNT_ID,
        position_store=failing,
    )

    assert w._openings_vetoed(_SYMBOL) is True, (  # noqa: SLF001
        "sin proyección legible el símbolo NO puede autorizar aperturas"
    )
    assert w._reconciliation.get(_SYMBOL) == "UNKNOWN", (  # noqa: SLF001
        "el estado debe quedar declarado, no ausente"
    )
    assert w._readopted is False, (  # noqa: SLF001
        "un fallo de lectura no consume la única readopción: se reintenta al tick siguiente"
    )
    assert report.proposals == 0, "fail-open: ningún BUY debe llegar a propuesta"
    assert report.fills == 0
    assert report.vetoes >= 1
    assert w.open_symbols == ()
    # R-1 (latch): el veto es GLOBAL, no depende de enumerar el símbolo en el diccionario
    # (``_watch_symbols()`` puede venir vacío con el universo ESTUDIO sin resolver).
    assert w._openings_vetoed("NO_EN_EL_WATCH") is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_r1_the_veto_does_not_depend_on_the_watch_being_enumerable(
    legacy_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Watch vacío + proyección ilegible ⇒ el veto sigue activo (no hay lista que enumerar)."""
    monkeypatch.setattr(worker_module, "_watch_symbols", lambda: [])
    stores = _Stores()
    failing = _ProjectionFailingStore()
    w = _restart(stores, minute=0)
    w._position_store = failing

    await w.readopt_positions()

    assert w._reconciliation == {}, "sin watch no hay símbolos que declarar"  # noqa: SLF001
    assert w._projection_read_failed is True  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is True, (  # noqa: SLF001
        "el latch de lectura no puede depender de que el watch se pueda enumerar"
    )


@pytest.mark.asyncio
async def test_r1_a_valid_read_clears_the_latch(
    legacy_env: None,
) -> None:
    """El latch sólo se libera con una lectura + reconciliación VÁLIDAS."""
    stores = _Stores()
    w = _restart(stores, minute=0)
    w._position_store = _ProjectionFailingStore()
    await w.readopt_positions()
    assert w._projection_read_failed is True  # noqa: SLF001

    # La misma instancia reintenta con el espejo sano (la readopción no se consumió).
    w._position_store = stores.positions
    await w.readopt_positions()

    assert w._projection_read_failed is False  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is False  # noqa: SLF001
    assert w._readopted is True  # noqa: SLF001


class _FlakyCanonicalReader:
    """Lector canónico que falla ``fail_next`` veces y después responde ``positions``."""

    def __init__(
        self,
        positions: dict[str, Any],
        *,
        fail_next: int = 1,
        facts: tuple[AppliedFillFact, ...] = (),
    ) -> None:
        self.positions = positions
        self.fail_next = fail_next
        self.facts = facts
        self.calls = 0

    async def __call__(self, _account_id: str) -> Any:
        self.calls += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise RuntimeError("canonical positions unreadable (R-1)")
        return CanonicalPositions(
            {symbol: Decimal(str(qty)) for symbol, qty in self.positions.items()},
            facts=self.facts,
        )


@pytest.mark.asyncio
async def test_r1_a_transient_canonical_failure_retries_the_readoption(
    legacy_env: None,
) -> None:
    """Un fallo TRANSITORIO del canónico no consume la readopción.

    Antes, ``_reconcile_before_trusting`` enganchaba el veto de aperturas y
    ``readopt_positions`` marcaba ``_readopted = True`` igualmente: el latch quedaba
    cerrado para siempre y sólo un reinicio lo levantaba. Ahora la propia fila se adopta
    (para poder cerrar lo materializado), las aperturas siguen vetadas y el tick
    siguiente reintenta la reconciliación.
    """
    stores = _Stores()
    await _seed_buy_position(
        stores, execution_id="buy-r1-canonical", qty=Decimal("100"), price=Decimal("100")
    )
    # Con las trazas aplicadas la reconciliación converge a OK (sin ellas, el libro en
    # RAM vacío tras el reinicio daría DIVERGENT y el veto sería legítimo, no el latch).
    reader = _FlakyCanonicalReader({_SYMBOL: 100}, facts=(_fact("fill-r1-canonical", 100.0),))
    w = _restart(stores, minute=0)
    w._canonical_positions_reader = reader

    await w.readopt_positions()

    assert w._projection_read_failed is True  # noqa: SLF001
    assert w._readopted is False, "un fallo transitorio no consume la readopción"  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is True  # noqa: SLF001
    assert w._open.get(_SYMBOL) == Decimal("100"), (  # noqa: SLF001
        "la fila propia sí se adopta: sin ella no se podría cerrar lo materializado"
    )

    await w.readopt_positions()

    assert reader.calls >= 2, "se reintenta la lectura del canónico"
    assert w._readopted is True  # noqa: SLF001
    assert w._projection_read_failed is False  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_r1_a_correct_read_lifts_the_veto(
    legacy_env: None,
) -> None:
    """Control positivo: con la proyección legible el mismo decider SÍ abre."""
    stores = _Stores()
    healthy = InMemorySimAutoPositionStore()
    w = _restart(stores, minute=0)
    w._position_store = healthy
    w._decider = _buy()

    report = await w.real_turn(
        exec_store=stores.exec_store,
        auto_store=None,
        finance_applier=None,
        account_id=ACCOUNT_ID,
        position_store=healthy,
    )

    assert w._openings_vetoed(_SYMBOL) is False  # noqa: SLF001
    assert report.proposals >= 1, "el mismo camino, con lectura sana, propone"
    assert w.open_symbols == (_SYMBOL,)


# ---------------------------------------------------------------------------
# R-2 — el total de la CUENTA escrito en la fila de cada MOTOR
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_single_worker_does_not_project_the_account_total(
    legacy_env: None,
) -> None:
    """Un worker reiniciado no puede convertir 100+100 en 200+100.

    Canónico de cuenta = 200, dos filas vivas de 100 (A y B). El veredicto es ``REBUILT``
    y el código escribía ``canonical_qty`` (200) sobre la fila del motor que readopta:
    total proyectado 300. El invariante correcto es ``Σ filas == canónico``.
    """
    stores = _Stores()
    await stores.positions.upsert(ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("100"), entry_price=None)
    await stores.positions.upsert(
        ACCOUNT_ID, _SECOND_ENGINE, _SYMBOL, Decimal("100"), entry_price=None
    )

    w = _restart(stores, minute=0)
    w._canonical_positions_reader = _canonical(
        {_SYMBOL: 200}, facts=(_fact("fill-a", 100.0), _fact("fill-b", 100.0))
    )
    await w.readopt_positions()

    rows = _live_rows(stores.positions)
    assert sorted(rows) == [Decimal("100"), Decimal("100")], (
        f"la fila de UN motor no puede llevar el total de la cuenta; filas={rows}"
    )
    assert sum(rows) == Decimal("200"), "Σ filas vivas == canónico"
    assert w._reconciliation.get(_SYMBOL) == "UNKNOWN", (  # noqa: SLF001
        "un reparto no determinable se declara, no se inventa"
    )
    assert w._openings_vetoed(_SYMBOL) is True  # noqa: SLF001


@pytest.mark.asyncio
async def test_r2_second_engine_does_not_inflate_twice(
    legacy_env: None,
) -> None:
    """Los 400 exigen que AMBOS motores reconstruyan: el invariante debe impedirlo."""
    stores = _Stores()
    await stores.positions.upsert(ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("100"), entry_price=None)
    await stores.positions.upsert(
        ACCOUNT_ID, _SECOND_ENGINE, _SYMBOL, Decimal("100"), entry_price=None
    )
    reader = _canonical({_SYMBOL: 200}, facts=(_fact("fill-a", 100.0), _fact("fill-b", 100.0)))

    first = _restart(stores, minute=0)
    first._canonical_positions_reader = reader
    await first.readopt_positions()

    second = _restart(stores, minute=1, engine_id=_SECOND_ENGINE)
    second._canonical_positions_reader = reader
    await second.readopt_positions()

    rows = _live_rows(stores.positions)
    assert sum(rows) == Decimal("200"), f"dos readopciones del mismo canónico no suman 400: {rows}"
    assert second._openings_vetoed(_SYMBOL) is True  # noqa: SLF001
    # R-2: el motor adopta SU fila, no el total de la cuenta. Antes ``_open`` quedaba en
    # 200 y un SELL de 200 no se clampaba (cerraba títulos de otro motor).
    assert second._open[_SYMBOL] == Decimal("100"), (  # noqa: SLF001
        f"cada motor gestiona su fila (100), no el canónico (200): {second._open}"  # noqa: SLF001
    )


@pytest.mark.asyncio
async def test_r2_a_sell_cannot_liquidate_another_engines_row(
    legacy_env: None,
) -> None:
    """Con dos filas vivas, una venta de 200 desde un motor sólo liquida sus 100.

    ``exec_qty = min(qty, held)``: el clamp usa ``_open``. Si ``_open`` hubiera adoptado
    el canónico (200), este motor habría vendido inventario del otro.
    """
    stores = _Stores()
    await stores.positions.upsert(ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("100"), entry_price=None)
    await stores.positions.upsert(
        ACCOUNT_ID, _SECOND_ENGINE, _SYMBOL, Decimal("100"), entry_price=None
    )
    w = _restart(stores, minute=0)
    w._canonical_positions_reader = _canonical(
        {_SYMBOL: 200}, facts=(_fact("fill-a", 100.0), _fact("fill-b", 100.0))
    )
    await w.readopt_positions()

    w._decider = _sell(200)
    report = await w.auto_turn()

    sold = sum(
        fill.qty
        for fill in w._applied_execution_events  # noqa: SLF001 — lectura de test.
        if fill.side == "sell"
    )
    assert sold == Decimal("100"), f"la venta se clampa a la fila del motor: {sold}"
    assert w._open.get(_SYMBOL, Decimal("0")) == Decimal("0")
    assert report.fills >= 1
    assert sum(_live_rows(stores.positions)) == Decimal("100"), (
        "la fila del otro motor no se toca"
    )


@pytest.mark.asyncio
async def test_r2_single_live_row_still_rebuilds(
    legacy_env: None,
) -> None:
    """Control positivo: con UNA sola fila viva el reparto sí es determinable."""
    stores = _Stores()
    await stores.positions.upsert(ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("100"), entry_price=None)

    w = _restart(stores, minute=0)
    w._canonical_positions_reader = _canonical(
        {_SYMBOL: 200}, facts=(_fact("fill-a", 200.0),)
    )
    await w.readopt_positions()

    projection = await stores.positions.read_projection(ACCOUNT_ID, ENGINE_ID)
    assert projection[_SYMBOL].quantity == Decimal("200")
    assert w._reconciliation.get(_SYMBOL) == "REBUILT"  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is False  # noqa: SLF001
    assert w._multi_engine_symbols == set(), (  # noqa: SLF001
        "una sola fila viva no es una cantidad no reconciliada"
    )


@pytest.mark.asyncio
async def test_r2_the_invariant_report_declares_the_inflation_and_does_not_heal_it(
    legacy_env: None,
) -> None:
    """Informe READ-ONLY: Σ filas vivas (300) ≠ canónico (200), y nada se repara.

    La fila inflada es el residual declarado: el motor no puede repartir el total de la
    cuenta entre motores, así que sólo DECLARA la discrepancia para reconciliación
    explícita. Cualquier "cura" aquí sería una heurística sobre dinero.
    """
    stores = _Stores()
    await stores.positions.upsert(
        ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("150"), entry_price=None
    )
    await stores.positions.upsert(
        ACCOUNT_ID, _SECOND_ENGINE, _SYMBOL, Decimal("150"), entry_price=None
    )
    w = _restart(stores, minute=0)
    w._canonical_positions_reader = _canonical(
        {_SYMBOL: 200}, facts=(_fact("fill-a", 100.0), _fact("fill-b", 100.0))
    )

    report = await w.live_row_invariant_report()

    entry = report[_SYMBOL]
    assert entry["engines"] == sorted([ENGINE_ID, _SECOND_ENGINE])
    assert entry["engineRows"] == {ENGINE_ID: "150", _SECOND_ENGINE: "150"}
    assert entry["projectedTotal"] == "300"
    assert entry["canonical"] == "200"
    assert entry["delta"] == "100"
    assert entry["consistent"] is False

    # No cura: las filas vivas quedan exactamente como estaban.
    assert sorted(_live_rows(stores.positions)) == [Decimal("150"), Decimal("150")]


@pytest.mark.asyncio
async def test_r2_the_multi_engine_symbol_is_flagged_for_declaration(
    legacy_env: None,
) -> None:
    """El símbolo ambiguo queda marcado: el cierre se declara, no se veta ni se adivina."""
    stores = _Stores()
    await stores.positions.upsert(
        ACCOUNT_ID, ENGINE_ID, _SYMBOL, Decimal("100"), entry_price=None
    )
    await stores.positions.upsert(
        ACCOUNT_ID, _SECOND_ENGINE, _SYMBOL, Decimal("100"), entry_price=None
    )
    w = _restart(stores, minute=0)
    w._canonical_positions_reader = _canonical(
        {_SYMBOL: 200}, facts=(_fact("fill-a", 100.0), _fact("fill-b", 100.0))
    )

    await w.readopt_positions()

    assert w._multi_engine_symbols == {_SYMBOL}  # noqa: SLF001
    assert w._open[_SYMBOL] == Decimal("100"), "el cierre se acota a la fila propia"  # noqa: SLF001
    assert w._openings_vetoed(_SYMBOL) is True, "la apertura sí queda vetada"  # noqa: SLF001


# ---------------------------------------------------------------------------
# P-1 — latch durable ilegible
# ---------------------------------------------------------------------------


def _engaged_state() -> KillState:
    return KillState(
        account_id=ACCOUNT_ID,
        engine_id=ENGINE_ID,
        engaged=True,
        reason="RECONCILIATION_FAILURE",
        engaged_at="2026-09-15T09:00:00Z",
        engagement_id="eng-original",
        reengagements=0,
    )


async def _real_turn(worker: Any, stores: _Stores) -> Any:
    return await worker.real_turn(
        exec_store=stores.exec_store,
        auto_store=None,
        finance_applier=None,
        account_id=ACCOUNT_ID,
        position_store=stores.positions,
        reservation_store=stores.reservations,
        exit_order_store=stores.exit_orders,
        kill_switch_store=stores.kill_state,
        canonical_positions_reader=_canonical({}),
    )


@pytest.mark.asyncio
async def test_p1_a_persistent_load_failure_blocks_every_tick(v2_env: None) -> None:
    """Un store ilegible de forma PERSISTENTE no puede dejar el motor abierto."""
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(seed=(_engaged_state(),), always_fail=True)
    w = _restart(stores, minute=1)
    w._decider = _buy()

    for _ in range(3):
        report = await _real_turn(w, stores)
        assert report.proposals == 0, "ningún tick puede abrir con el latch ilegible"
        assert w.open_symbols == ()

    assert w._v2_kill_switch_halted() is True  # noqa: SLF001
    assert w._v2_kill_switch.reason == "KILL_STATE_UNREADABLE"  # noqa: SLF001
    assert stores.kill_state.loads >= 3, "se reintenta leer en cada turno real"


@pytest.mark.asyncio
async def test_p1_a_transient_failure_adopts_the_durable_halt(v2_env: None) -> None:
    """Tras un fallo TRANSITORIO, la lectura siguiente restaura el HALT con su rastro."""
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(seed=(_engaged_state(),), fail_next=1)
    w = _restart(stores, minute=1)
    w._decider = _buy()

    first = await _real_turn(w, stores)
    assert first.proposals == 0
    assert w._v2_kill_switch.reason == "KILL_STATE_UNREADABLE"  # noqa: SLF001

    second = await _real_turn(w, stores)
    assert second.proposals == 0, "la posición no se reabre al recuperar la lectura"
    assert w._v2_kill_switch.reason == "RECONCILIATION_FAILURE"  # noqa: SLF001
    assert w._v2_kill_switch.engagement_id == "eng-original"  # noqa: SLF001
    assert w.open_symbols == ()


@pytest.mark.asyncio
async def test_p1_a_transient_failure_without_a_durable_halt_recovers(
    v2_env: None,
) -> None:
    """El placeholder se LIBERA con la lectura siguiente si no hay HALT durable.

    Antes, un fallo transitorio de ``load()`` enganchaba el latch local y nada lo
    deshacía: el proceso quedaba parado hasta reiniciarse aunque el store ya leyese. La
    lectura válida (sin fila ⇒ la parada nunca se activó) es la única vía de vuelta.
    """
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(fail_next=1)
    w = _restart(stores, minute=1)
    w._decider = _buy()

    first = await _real_turn(w, stores)
    assert first.proposals == 0, "sin lectura no se abre"
    assert w._v2_kill_switch.reason == "KILL_STATE_UNREADABLE"  # noqa: SLF001

    second = await _real_turn(w, stores)
    assert w._v2_kill_switch_halted() is False, (  # noqa: SLF001
        "un fallo TRANSITORIO no puede dejar el motor parado para siempre"
    )
    assert second.proposals >= 1, "con la lectura sana el camino vuelve a proponer"


@pytest.mark.asyncio
async def test_p1_a_valid_read_never_lifts_a_real_durable_halt(v2_env: None) -> None:
    """Control negativo: el placeholder se libera, un HALT durable NO."""
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(seed=(_engaged_state(),), fail_next=1)
    w = _restart(stores, minute=1)
    w._decider = _buy()

    await _real_turn(w, stores)
    await _real_turn(w, stores)

    assert w._v2_kill_switch_halted() is True  # noqa: SLF001
    assert w._v2_kill_switch.reason == "RECONCILIATION_FAILURE"  # noqa: SLF001


@pytest.mark.asyncio
async def test_p1_control_a_readable_store_still_lifts_nothing(v2_env: None) -> None:
    """Control: con el store sano y SIN parada, el mismo decider propone."""
    stores = _Stores()
    w = _restart(stores, minute=1)
    w._decider = _buy()

    report = await _real_turn(w, stores)

    assert report.proposals >= 1, "el camino está vivo: el HALT no se inventa"
    assert w._v2_kill_switch_halted() is False  # noqa: SLF001


@pytest.mark.asyncio
async def test_p1_the_legacy_path_cannot_open_with_a_durable_halt(legacy_env: None) -> None:
    """P-1 — el camino legacy (V2 OFF) también respeta el HALT durable.

    ``kill = self._kill_active()`` sólo consulta la fuente de entorno. Con el motor V2
    apagado, el latch recuperado del espejo (o el placeholder ``KILL_STATE_UNREADABLE``)
    no llegaba al gate y un BUY abría con la parada activa. El veto es de APERTURA: una
    venta sigue permitida porque reducir no empeora el riesgo.
    """
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(seed=(_engaged_state(),))
    w = _restart(stores, minute=1)
    assert w.v2_enabled() is False, "la prueba debe correr por el camino legacy"
    w._decider = _buy()

    report = await _real_turn(w, stores)

    assert w._v2_kill_switch_halted() is True  # noqa: SLF001
    assert report.proposals == 0, "un BUY no puede proponerse con la parada durable activa"
    assert report.fills == 0
    assert report.vetoes >= 1
    assert w.open_symbols == ()


@pytest.mark.asyncio
async def test_p1_the_legacy_path_still_allows_a_protective_exit(legacy_env: None) -> None:
    """Control del veto anterior: el HALT no congela una SALIDA protectora."""
    stores = _Stores()
    stores.kill_state = _FlakyKillSwitchStore(seed=(_engaged_state(),))
    await _seed_buy_position(
        stores, execution_id="buy-p1-sell", qty=Decimal("100"), price=Decimal("100")
    )
    w = _restart(stores, minute=1)
    assert w.v2_enabled() is False, "la prueba debe correr por el camino legacy"
    w._decider = _sell(100)
    await w.readopt_positions()

    report = await _real_turn(w, stores)

    assert report.fills >= 1, "reducir/cerrar es la salida que la parada NO bloquea"
    assert w.open_symbols == ()


# ---------------------------------------------------------------------------
# P-2 — el rango intradía no se ve
# ---------------------------------------------------------------------------


async def _seed_position_with_stop(stores: _Stores, *, stop: str) -> None:
    """Posición viva con un PLAN DURABLE (stop exacto), no una geometría reconstruida.

    El stop se rehidrata tal cual: con un hueco a la baja, la adopción reconstruida
    rechazaría un stop por encima del mercado (``stop_above_market``) y el caso del gap no
    sería observable como tal.
    """
    await _seed_buy_position(
        stores, execution_id="buy-p2", qty=Decimal("200"), price=Decimal("100")
    )
    position = build_position_state_from_fill(
        {
            "decisionId": "d-p2",
            "instrumentId": _SYMBOL,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": float(stop),
            "target1": 110.0,
            "target2": 120.0,
        },
        fill_price=100.0,
        fill_quantity=200.0,
        filled_at="2026-09-15T09:00:00Z",
        max_holding_period_days=30,
    )
    assert position is not None
    await stores.positions.upsert(
        ACCOUNT_ID,
        ENGINE_ID,
        _SYMBOL,
        Decimal("200"),
        entry_price=Decimal("100"),
        high_watermark=Decimal("100"),
        stop_price=Decimal(stop),
        position_state=replace(position, lifecycle_state="OPEN").to_dict(),
    )


def _sell_prices(stores: _Stores) -> list[Decimal]:
    return [
        row.price
        for row in stores.contexts._rows.values()  # noqa: SLF001 — lectura de test.
        if row.side == "sell"
    ]


def _applied_sell_prices(worker: Any) -> list[Decimal]:
    """Precio DECLARADO de cada venta aplicada (el que usa P&L, fill y estado final)."""
    return [
        fill.price
        for fill in worker._applied_execution_events  # noqa: SLF001 — lectura de test.
        if fill.side == "sell"
    ]


@pytest.mark.asyncio
async def test_p2_intraday_low_through_the_stop_sells_at_the_stop(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Open 100 · Low 80`` con stop 95: el stop dispara y el fill se declara a 95.

    Antes: la gestión sólo veía ``open(B) = 100`` ⇒ el stop NO disparaba y el breach
    intradía desaparecía sin rastro.
    """
    # El ATR del plan reconstruido se fija para que el stop de la adopción sea 95.
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "0")
    stores = _Stores()
    await _seed_position_with_stop(stores, stop="95")
    source = _OhlcPriceSource(open_=100.0, low=80.0, high=105.0, mid=101.0)

    w = _restart(stores, minute=1, price_source=source, atr_source=lambda _s: 10.0 / 3.0)
    w._canonical_positions_reader = _canonical({_SYMBOL: 200})
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert "structural_stop" in w._v2_last_exit_reasons.get(_SYMBOL, ()), (  # noqa: SLF001
        "el Low de la barra atravesó el stop: la gestión debe verlo"
    )
    assert w.open_symbols == (), "la posición se cierra en el mismo turno"
    prices = _sell_prices(stores)
    assert prices, "la venta se liquida"
    assert all(price < Decimal("96") for price in prices), (
        f"el fill se declara al stop (95), no al open (100): {prices}"
    )
    # P-2 (contable): el precio declarado es el que usan el hecho aplicado, el P&L y el
    # estado final. Antes sólo lo usaba el settlement: con open 100 y stop 95 el fill
    # quedaba en 95 y el P&L en 0 (la pérdida real es 1.000 sobre 200 títulos).
    declared = _applied_sell_prices(w)
    assert declared, "la venta deja hecho aplicado con su precio"
    assert set(declared) == {Decimal("95")}, (
        f"el hecho aplicado debe usar el stop declarado (95), no el open: {declared}"
    )
    assert w._sim_realized_pnl == Decimal("-1000"), (  # noqa: SLF001
        f"el P&L se mide al precio declarado: (95-100)*200 = -1.000, no 0: "
        f"{w._sim_realized_pnl!r}"  # noqa: SLF001
    )
    # La geometría del plan: entrada 100 y stop 95 ⇒ riesgo 5 por título; salir a 95 es -1R.
    # MAE = (80-100)/5 = -4,0R: es la COTA CONSERVADORA de la excursión de la barra (no se
    # conoce el orden intrabar), no el P&L. El P&L sí usa el precio declarado (95).
    assert w.operation_measurements()[-1].mae == Decimal("-4.0")  # noqa: SLF001


@pytest.mark.asyncio
async def test_p2_overnight_gap_fills_at_the_open(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Open 90`` con stop 95: el stop dispara y el fill se declara al open (mejor precio).

    El gap YA se detectaba con ``open(B)``; lo que esta prueba fija es que el precio de
    ejecución declarado es el del hueco y no el nivel del stop.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "0")
    stores = _Stores()
    await _seed_position_with_stop(stores, stop="95")
    source = _OhlcPriceSource(open_=90.0, low=88.0, high=91.0, mid=101.0)

    w = _restart(stores, minute=1, price_source=source, atr_source=lambda _s: 10.0 / 3.0)
    w._canonical_positions_reader = _canonical({_SYMBOL: 200})
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert "structural_stop" in w._v2_last_exit_reasons.get(_SYMBOL, ())  # noqa: SLF001
    prices = _sell_prices(stores)
    assert prices
    assert all(Decimal("89") < price < Decimal("91") for price in prices), (
        f"el fill se declara al open (90), no al nivel del stop (95): {prices}"
    )
    # P-2 (contable): el hueco manda también en el hecho aplicado y en el P&L.
    declared = _applied_sell_prices(w)
    assert declared
    assert set(declared) == {Decimal("90")}, (
        f"el hecho aplicado debe usar el open del hueco (90), no el stop: {declared}"
    )
    assert w._sim_realized_pnl == Decimal("-2000"), (  # noqa: SLF001
        f"el P&L de un gap a 90 sobre entrada 100 y 200 títulos es -2.000: "
        f"{w._sim_realized_pnl!r}"  # noqa: SLF001
    )
    # MAE con el extremo adverso de la barra: (88-100)/5 = -2,4R.
    assert w.operation_measurements()[-1].mae == Decimal("-2.4")  # noqa: SLF001


def test_p2_the_mark_alone_does_not_see_the_breach() -> None:
    """Caracterización espejo: sin ``bar_low`` un mark de 100 sobre stop 95 no dispara.

    Evita que el arreglo se cuele por el ``mark``: el único dato que aporta el breach es
    el extremo de la barra.
    """
    position = build_position_state_from_fill(
        {
            "decisionId": "d-p2",
            "instrumentId": _SYMBOL,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 95.0,
        },
        fill_price=100.0,
        fill_quantity=200.0,
        filled_at="2026-09-15T09:00:00Z",
    )
    assert position is not None

    plan = build_exit_plan_from_position(position, mark_price=100.0)

    assert plan is not None
    assert "STRUCTURAL_STOP" not in plan.reasons


def _triggered_position(
    *,
    stop: float = 95.0,
    target1: float = 110.0,
    target2: float = 120.0,
) -> Any:
    position = build_position_state_from_fill(
        {
            "decisionId": "d-p2",
            "instrumentId": _SYMBOL,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": stop,
            "target1": target1,
            "target2": target2,
        },
        fill_price=100.0,
        fill_quantity=200.0,
        filled_at="2026-09-15T09:00:00Z",
    )
    assert position is not None
    return position


def test_p2_the_close_r_uses_the_declared_price() -> None:
    """Cifra exacta del cierre: entrada 100, riesgo 10, salida declarada 95 ⇒ −0,5R.

    Es la fórmula que ``_v2_track_reduce`` aplica con ``realized_price``. Con el ``open``
    (100) el cierre habría contabilizado 0R: la pérdida existía en el fill y desaparecía
    del estado final.
    """
    position = build_position_state_from_fill(
        {
            "decisionId": "d-p2",
            "instrumentId": _SYMBOL,
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 100.0,
            "structuralStop": 90.0,
        },
        fill_price=100.0,
        fill_quantity=200.0,
        filled_at="2026-09-15T09:00:00Z",
    )
    assert position is not None
    assert position.initial_risk == 10.0

    at_declared = apply_position_reduce(position, 200, exit_price=95.0)
    assert at_declared is not None
    assert at_declared.realized_r == -0.5
    assert at_declared.status == "CLOSED"

    at_open = apply_position_reduce(position, 200, exit_price=100.0)
    assert at_open is not None
    assert at_open.realized_r == 0.0, "el precio equivocado habría borrado la pérdida"


def test_p2_the_adverse_bar_extreme_feeds_the_mae_and_declares_its_source() -> None:
    """El MAE sale del extremo adverso de la barra, no del ``open`` (y lo declara).

    Entrada 100 · stop 95 ⇒ riesgo 5. ``low(B) = 80`` ⇒ (80-100)/5 = -4,0R. Con sólo el
    mark (100) el peor adverso se quedaba en 0 y la pérdida intradía no existía.
    """
    position = _triggered_position()

    marked = apply_position_mark(position, 100.0, worst_adverse_price=80.0)
    assert marked is not None
    assert marked.mfe_mae["maeR"] == -4.0, "el MAE usa low(B), no el open"
    assert marked.mfe_mae["source"] == "bars", (
        "un MAE medido con el extremo de la barra NO se declara proxy de cierre"
    )

    legacy = apply_position_mark(position, 100.0)
    assert legacy is not None
    assert legacy.mfe_mae["maeR"] == 0.0
    assert legacy.mfe_mae["source"] == "close_proxy", (
        "sin extremo de barra el camino anterior queda byte-idéntico"
    )


def test_p2_stop_wins_when_stop_and_target_share_the_bar() -> None:
    """Convención CONSERVADORA explícita: si stop y objetivo caen en la misma barra, gana
    el stop.

    No es una reconstrucción del orden real de los precios (no hay orden intrabar
    conocida); es la hipótesis declarada por ``EXIT_REASON_PRECEDENCE``. La prueba la
    fija para que nadie la cambie sin querer.
    """
    position = _triggered_position()
    plan = build_exit_plan_from_position(
        position, mark_price=100.0, bar_low=80.0, bar_high=120.0
    )
    assert plan is not None
    assert plan.primary_reason == "STRUCTURAL_STOP"
    assert "TARGET_2" in plan.reasons, (
        "el objetivo también se tocó: viaja como secundario, no se pierde"
    )
    assert "TARGET_1" not in plan.reasons, (
        "H2: T2 subsume T1 (no se reduce la mitad por atajo de T1)"
    )
    assert (
        protective_fill_price(position, open_price=100.0, primary_reason=plan.primary_reason)
        == 95.0
    ), "el fill declarado es el stop (95), no el máximo de la barra"


@pytest.mark.asyncio
async def test_p2_target_partial_books_realized_r_at_the_declared_price(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El estado final del ``PositionState`` usa el MISMO precio declarado que el fill.

    ``high(B) = 110`` toca T1: la venta se declara a 110 (no al open 100) y la mitad
    realizada en R debe ser (110-100)/5 = 2,0R sobre la fracción ejecutada (30% del
    MODERATE ⇒ 60 de 200): ``realized_r = 2,0 · 0,3 = 0,6``.
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "0")
    stores = _Stores()
    await _seed_position_with_stop(stores, stop="95")
    source = _OhlcPriceSource(open_=100.0, low=100.0, high=110.0, mid=101.0)

    w = _restart(stores, minute=1, price_source=source, atr_source=lambda _s: 10.0 / 3.0)
    w._canonical_positions_reader = _canonical({_SYMBOL: 200})
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert "target_1" in w._v2_last_exit_reasons.get(_SYMBOL, ())  # noqa: SLF001
    declared = _applied_sell_prices(w)
    assert declared and set(declared) == {Decimal("110")}, (
        f"la venta parcial se declara al objetivo (110), no al open: {declared}"
    )
    live = w._v2_positions.get(_SYMBOL)  # noqa: SLF001
    assert live is not None, "T1 es parcial: la posición sigue viva"
    assert live.remaining_quantity == 140
    assert live.realized_r == 0.6, (
        f"el estado final contabiliza 2,0R sobre el 30% ejecutado: {live.realized_r}"
    )


@pytest.mark.asyncio
async def test_p2_mae_from_the_bar_survives_in_the_durable_mirror(
    v2_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un tick SIN salida persiste el MAE medido con la barra en el espejo durable.

    ``low(B) = 96`` no toca el stop 95; el peor adverso es (96-100)/5 = -0,8R y debe
    sobrevivir al reinicio (el espejo es la memoria del MAE entre procesos).
    """
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_ATR_REQUIRED", "0")
    stores = _Stores()
    await _seed_position_with_stop(stores, stop="95")
    source = _OhlcPriceSource(open_=100.0, low=96.0, high=101.0, mid=100.5)

    w = _restart(stores, minute=1, price_source=source, atr_source=lambda _s: 10.0 / 3.0)
    w._canonical_positions_reader = _canonical({_SYMBOL: 200})
    await w.readopt_positions()
    w._decider = _hold()
    await w.auto_turn()

    assert w.open_symbols == (_SYMBOL,), "sin tocar el stop la posición sigue viva"
    projection = await stores.positions.read_projection(ACCOUNT_ID, ENGINE_ID)
    state = projection[_SYMBOL].position_state
    assert state is not None
    assert state["mfeMae"]["maeR"] == -0.8, (
        f"el peor adverso queda persistido, no sólo en RAM: {state['mfeMae']}"
    )
    assert state["mfeMae"]["source"] == "bars"


# ---------------------------------------------------------------------------
# R-4 — identidad de motor en el arranque durable
# ---------------------------------------------------------------------------


def test_r4_durable_start_requires_an_explicit_engine_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin ``AUTO_ENGINE_SIM_ENGINE_ID`` el arranque durable FALLA; no cae a ``auto-sim``."""
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "1")
    monkeypatch.delenv("AUTO_ENGINE_SIM_ENGINE_ID", raising=False)

    with pytest.raises(RuntimeError, match="AUTO_ENGINE_SIM_ENGINE_ID"):
        worker_module.start_auto_sim_worker(
            session_factory=object(),
            account_id=ACCOUNT_ID,
            interval_seconds=60.0,
        )


def test_r4_the_durable_identity_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control positivo: con la variable definida la identidad es la declarada."""
    monkeypatch.setenv("AUTO_ENGINE_SIM_ENGINE_ID", "auto-window-test")

    assert worker_module._durable_sim_engine_id() == "auto-window-test"


# ---------------------------------------------------------------------------
# Anexo: el helper del banco debe seguir sirviendo al camino hermético
# ---------------------------------------------------------------------------


def test_the_hermetic_bench_still_uses_the_stable_default_engine() -> None:
    """El constructor hermético conserva ``auto-sim`` (Δ = 0 fuera de la ventana)."""
    stores = _Stores()
    w = _restart(stores, minute=0)
    assert w._engine_id == ENGINE_ID  # noqa: SLF001
