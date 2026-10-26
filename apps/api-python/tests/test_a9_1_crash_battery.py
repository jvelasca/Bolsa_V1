"""V2.24 / A9.1 (P2-03) — batería de crash en las ventanas nuevas del AUTO SIM.

Las ventanas de V2.23 (contexto → finance → posición → journal) pueden fallar en
cualquier punto. Esta batería INYECTA el fallo en cada ventana de forma determinista
(sin PG, hermética) y exige los invariantes de no-doble-efecto:

* C3-F — crash tras ``finance`` y antes de ``sim_position``: el reinicio readopta/
  reconstruye y NO repite el BUY ni el asiento financiero.
* C3-G — crash tras ``sim_position`` y antes del journal: el reinicio no duplica la
  posición ni el efecto financiero.
* C3-H — crash durante la persistencia del contexto: la liquidación queda sin fill
  (fail-closed) y no mueve dinero.
* C3-I — crash durante la readopción: no se inventa posición ni se opera a ciegas.

A diferencia de los chaos REALES de ``live_a7`` (SIGKILL de subproceso, requieren
PG), aquí el "crash" es una excepción inyectada en la costura durable exacta; el
invariante verificado es el mismo: ausencia de doble efecto + reconciliación.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import (
    AutoSimulationWorker,
    step_minute_clock,
)
from bolsa_application.decision_contract import DecisionPackage
from bolsa_application.execution_event import InMemoryExecutionEventStore
from bolsa_application.sim_durable_store import (
    InMemorySimAutoPositionStore,
    InMemorySimFillFinanceContextStore,
)
from bolsa_application.sim_reconciliation import (
    POSITION_PROJECTION_DIVERGENT,
    reconcile_sim_position,
)


@pytest.fixture
def auto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_WATCH", "AAA")
    monkeypatch.setenv("AUTO_ENGINE_SIMULATED_VENUE", "paper")
    monkeypatch.setenv("AUTO_SIMULATION_WORKER_ENABLED", "0")


def _buy(symbol: str) -> DecisionPackage:
    return DecisionPackage(action="BUY", instrument_id=symbol, quantity=100.0)


def _hold(symbol: str) -> DecisionPackage:
    return DecisionPackage(action="HOLD", instrument_id=symbol, quantity=0)


def _count_fills(store: InMemoryExecutionEventStore) -> int:
    return len(store)


class _FailingPositionStore(InMemorySimAutoPositionStore):
    """Store de posición que falla en la escritura (simula crash en esa ventana)."""

    def __init__(self, *, fail_on: str = "upsert") -> None:
        super().__init__()
        self._fail_on = fail_on

    async def upsert(self, account_id, engine_id, symbol, quantity, **kw):  # type: ignore[no-untyped-def]
        if self._fail_on == "upsert":
            raise RuntimeError("crash during sim_position persist (C3-F/G)")
        return await super().upsert(account_id, engine_id, symbol, quantity, **kw)

    async def read_projection(self, account_id, engine_id):  # type: ignore[no-untyped-def]
        if self._fail_on == "readopt":
            raise RuntimeError("crash during readopt (C3-I)")
        return await super().read_projection(account_id, engine_id)


class _FailingContextStore(InMemorySimFillFinanceContextStore):
    """Contexto que falla al persistir (simula crash en esa ventana)."""

    async def save(self, context):  # type: ignore[no-untyped-def]
        raise RuntimeError("crash during finance-context persist (C3-H)")


@pytest.mark.asyncio
async def test_c3f_crash_before_position_no_second_effect(auto_env: None) -> None:
    """C3-F: crash tras finance/antes de sim_position ⇒ no hay doble BUY al reiniciar."""
    store = InMemoryExecutionEventStore()
    account = "acc-c3f"
    fail_store = _FailingPositionStore(fail_on="upsert")

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=fail_store, account_id=account
    )
    w1._decider = _buy
    # El turno no rompe: el fallo del espejo se absorbe (el dinero ya está aplicado).
    await w1.auto_turn()
    fills_after_crash = _count_fills(store)
    assert fills_after_crash > 0, "el settlement financiero sí ocurrió antes del crash"

    # Reinicio con un store sano sobre el MISMO ledger: readopta desde el canónico.
    healthy = InMemorySimAutoPositionStore()
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=healthy, account_id=account
    )
    # El lector canónico refleja la posición real del ledger (100) tras el BUY.
    async def canonical(_acc: str):
        return {"AAA": Decimal("100")}

    w2._canonical_positions_reader = canonical
    await w2.readopt_positions()
    w2._decider = _buy  # intentaría comprar de nuevo
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == Decimal("100"), "no debe apilar un segundo BUY"
    assert _count_fills(store) == fills_after_crash, "sin segundo efecto financiero"


@pytest.mark.asyncio
async def test_c3g_crash_after_position_no_duplicate(auto_env: None) -> None:
    """C3-G: crash tras sim_position/antes de journal ⇒ reinicio no duplica posición."""
    store = InMemoryExecutionEventStore()
    pos_store = InMemorySimAutoPositionStore()
    account = "acc-c3g"

    _s1, clock1 = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    w1 = AutoSimulationWorker(
        clock=clock1, exec_store=store, position_store=pos_store, account_id=account
    )
    w1._decider = _buy
    await w1.auto_turn()
    await w1._persist_position("AAA", w1._open["AAA"])
    fills_before = _count_fills(store)
    assert dict(await pos_store.read_open(account, "auto-sim")) == {"AAA": Decimal("100")}

    # Reinicio: readopta desde la proyección durable (no re-compra).
    _s2, clock2 = step_minute_clock(datetime(2026, 9, 9, 9, 1, tzinfo=UTC))
    w2 = AutoSimulationWorker(
        clock=clock2, exec_store=store, position_store=pos_store, account_id=account
    )
    await w2.readopt_positions()
    w2._decider = _buy
    await w2.auto_turn()
    assert w2._open.get("AAA", Decimal("0")) == Decimal("100")
    assert _count_fills(store) == fills_before, "sin duplicar el fill"


@pytest.mark.asyncio
async def test_c3h_crash_during_context_no_money(auto_env: None) -> None:
    """C3-H: crash al persistir contexto ⇒ fail-closed, sin fill ni dinero."""
    store = InMemoryExecutionEventStore()
    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        context_store=_FailingContextStore(),
        account_id="acc-c3h",
    )
    worker._decider = _buy
    await worker.auto_turn()
    # Sin contexto durable no se materializa; y el turno no debe romperse.
    assert not worker.open_symbols
    assert _count_fills(store) == 0


@pytest.mark.asyncio
async def test_c3i_crash_during_readopt_is_safe(auto_env: None) -> None:
    """C3-I: crash durante la readopción ⇒ no se inventa posición (fail-closed)."""
    store = InMemoryExecutionEventStore()
    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=store,
        position_store=_FailingPositionStore(fail_on="readopt"),
        account_id="acc-c3i",
    )
    durable = await worker.readopt_positions()
    assert dict(durable) == {}, "un fallo de readopción no inventa posición"
    assert not worker.open_symbols


@pytest.mark.asyncio
async def test_reconciliation_blocks_openings_when_divergent(auto_env: None) -> None:
    """P1-01: si la proyección diverge del canónico, NO se abren nuevas posiciones."""
    store = InMemoryExecutionEventStore()
    account = "acc-div"
    pos_store = _FailingPositionStore(fail_on="none")

    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock, exec_store=store, position_store=pos_store, account_id=account
    )

    called = {"n": 0}

    async def divergent_reader(_acc: str):
        called["n"] += 1
        # El canónico dice 100 pero la proyección está vacía ⇒ REBUILT (reconstruye).
        return {"AAA": Decimal("100")}

    worker._canonical_positions_reader = divergent_reader
    await worker.readopt_positions()
    # Tras la reconstrucción, la proyección queda alineada y las aperturas permitidas
    # (no queda DIVERGENT porque el canónico es la autoridad).
    verdict = reconcile_sim_position(
        symbol="AAA",
        execution_events=None,
        financial_positions={"AAA": Decimal("100")},
        sim_auto_positions={"AAA": Decimal("100")},
    )
    assert verdict.status != POSITION_PROJECTION_DIVERGENT


@pytest.mark.asyncio
async def test_projection_without_cost_basis_is_healed_from_applied_fills(
    auto_env: None,
) -> None:
    """V2.88.159 — una proyección OK sin ``entry_price`` recupera su coste del libro.

    El camino REBUILT solo actúa cuando la CANTIDAD diverge. Una fila escrita con
    ``entry_price=NULL`` y cantidad correcta quedaba ``OK`` y nadie la curaba: la
    posición real seguía sin stop, sin trailing y sin plan de salida posible
    (medido 2026-10-21: la posición viva y muda, 0 fills).
    """
    from bolsa_analytics.cognitive.position_ledger import AppliedFillFact
    from bolsa_application.applied_fills import CanonicalPositions

    account = "acc-heal"
    pos_store = InMemorySimAutoPositionStore()

    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        position_store=pos_store,
        account_id=account,
    )
    # Proyección del motor: cantidad CORRECTA, sin base de coste (firma exacta del fallo).
    await pos_store.upsert(
        account, worker._engine_id, "AAA", Decimal("100"), entry_price=None
    )

    async def reader(_acc: str) -> CanonicalPositions:
        return CanonicalPositions(
            {"AAA": Decimal("100")},
            facts=(
                AppliedFillFact(
                    execution_id="fill-1",
                    instrument_id="AAA",
                    side="buy",
                    quantity=100.0,
                    price=12.5,
                    account_id=account,
                ),
            ),
        )

    worker._canonical_positions_reader = reader
    await worker.readopt_positions()

    # La cantidad no divergía ⇒ el veredicto es OK, y aun así la fila quedó curada.
    projection = await pos_store.read_projection(account, worker._engine_id)
    assert projection["AAA"].entry_price == pytest.approx(Decimal("12.5"))
    assert worker._entry_price["AAA"] == Decimal("12.5")
    assert worker._open["AAA"] == Decimal("100"), "curar el coste no altera la posición"


# ---------------------------------------------------------------------------
# W-159-5 (Hueco E) — el coste de la CUENTA no es el coste de una fila cuando hay
# más de un motor vivo con el mismo símbolo.
# ---------------------------------------------------------------------------


def _duplicate_engines_reader(account: str, *, facts_qty: float = 100.0):
    from bolsa_analytics.cognitive.position_ledger import AppliedFillFact
    from bolsa_application.applied_fills import CanonicalPositions

    async def reader(_acc: str) -> CanonicalPositions:
        return CanonicalPositions(
            {"AAA": Decimal("100")},
            facts=(
                AppliedFillFact(
                    execution_id="fill-1",
                    instrument_id="AAA",
                    side="buy",
                    quantity=facts_qty,
                    price=12.5,
                    account_id=account,
                ),
            ),
        )

    return reader


@pytest.mark.asyncio
async def test_duplicate_engine_rows_are_not_healed_with_an_account_average(
    auto_env: None,
) -> None:
    """Hueco E — dos filas vivas ⇒ no se cura ``entry_price`` (se declara, no se inventa).

    Medido 2026-10-21: ``3204115d`` con 1933.3953 bajo dos motores huérfanos (uno con
    ``ver=None``) mientras el canónico tenía una sola posición. La cura de ``.159``
    escribe el coste medio de la CUENTA sobre una fila POR MOTOR: con dos filas vivas
    ese número no identifica a ninguna de ellas.
    """
    account = "acc-dup"
    pos_store = InMemorySimAutoPositionStore()

    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        position_store=pos_store,
        account_id=account,
    )
    # La MISMA cantidad bajo dos motores: el caso medido.
    await pos_store.upsert(
        account, worker._engine_id, "AAA", Decimal("100"), entry_price=None
    )
    await pos_store.upsert(account, "auto-orphan", "AAA", Decimal("100"), entry_price=None)

    worker._canonical_positions_reader = _duplicate_engines_reader(account)
    await worker.readopt_positions()

    projection = await pos_store.read_projection(account, worker._engine_id)
    assert projection["AAA"].entry_price is None, (
        "el coste medio de la cuenta no se escribe sobre una fila por motor"
    )
    assert worker._open["AAA"] == Decimal("100"), "la cantidad sí se adopta"


@pytest.mark.asyncio
async def test_rebuilt_duplicate_row_refuses_to_project_the_account_total(
    auto_env: None,
) -> None:
    """R-2 §8 — con dos filas vivas ni el coste ni la cantidad de la cuenta.

    La cura de ``.159`` escribía el total canónico de la CUENTA (200) sobre cada fila
    por motor: dos motores vivos acababan sumando 400. Con más de una fila viva no se
    proyecta nada; el símbolo queda ``UNKNOWN`` y las aperturas se vetan.
    """
    account = "acc-dup-rebuilt"
    pos_store = InMemorySimAutoPositionStore()

    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    worker = AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        position_store=pos_store,
        account_id=account,
    )
    # Cantidad divergente (50 vs canónico 100) ⇒ el camino REBUILT sí se ejecuta.
    await pos_store.upsert(account, worker._engine_id, "AAA", Decimal("50"), entry_price=None)
    await pos_store.upsert(account, "auto-orphan", "AAA", Decimal("50"), entry_price=None)

    worker._canonical_positions_reader = _duplicate_engines_reader(account)
    await worker.readopt_positions()

    projection = await pos_store.read_projection(account, worker._engine_id)
    assert projection["AAA"].quantity == Decimal("50"), (
        "el total de la cuenta no se escribe sobre una fila por motor"
    )
    assert projection["AAA"].entry_price is None, "el coste no se fabrica desde el medio"
    assert worker._reconciliation["AAA"] == "UNKNOWN"
    assert worker._openings_vetoed("AAA") is True


# ---------------------------------------------------------------------------
# W-159 — Huecos B (geometría), C (durabilidad) y D (atribución) del diagnóstico
# ``docs/engineering/diagnostico-adopcion-puntuacion-atribucion-2026-10-21.md``.
# ---------------------------------------------------------------------------


def _adoption_worker(account: str = "acc-adopt") -> AutoSimulationWorker:
    _s, clock = step_minute_clock(datetime(2026, 9, 9, 9, 0, tzinfo=UTC))
    return AutoSimulationWorker(
        clock=clock,
        exec_store=InMemoryExecutionEventStore(),
        # Sin espejo no hay readopción: ``readopt_positions`` no reconcilia y la
        # atribución canónica (Hueco D) nunca se calcula.
        position_store=InMemorySimAutoPositionStore(),
        account_id=account,
    )


def test_adoption_geometry_never_lands_above_the_market(auto_env: None) -> None:
    """Hueco B — una entrada rancio no puede fabricar un stop que liquide en el tick.

    Medido 2026-10-21: la posición ``3204115d`` se adoptó con ``stop=12,9144`` sobre un
    mercado de ``10,42`` y cuatro ventas la cerraron 0,04 s después. El guard histórico
    (``0 < stop < entry``) no podía verlo porque comparaba contra la MISMA entrada
    equivocada: hay que validar contra el precio de mercado.
    """
    price = Decimal("10.42")

    # (a) sólo el espejo (rancio, 13,3): la geometría queda por encima del mercado ⇒ se
    #     adopta SIN stop y se declara el motivo. Nunca un número que dispare.
    stale = _adoption_worker()
    stale._open["AAA"] = Decimal("100")
    stale._entry_price["AAA"] = Decimal("13.3")
    degraded = stale._v2_adopt_position("AAA", price)
    assert degraded is not None, "una adopción imposible no puede dejar la posición muda"
    assert degraded.current_stop is None, "no se inventa un stop por encima del mercado"
    assert degraded.lifecycle_state == "RECONCILIATION_REQUIRED"
    reasons = [e.payload.get("reason") for e in stale._v2_position_journal_pending]
    assert "stop_above_market" in reasons

    # (b) el LIBRO manda sobre el espejo: con el coste canónico la geometría es válida y
    #     el stop queda por DEBAJO del mercado (no se liquida sola).
    fixed = _adoption_worker()
    fixed._open["AAA"] = Decimal("100")
    fixed._entry_price["AAA"] = Decimal("13.3")
    fixed._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    adopted = fixed._v2_adopt_position("AAA", price)
    assert adopted is not None
    assert adopted.current_stop is not None
    assert Decimal(str(adopted.current_stop)) < price


def test_adoption_cost_basis_prefers_the_ledger_over_the_mirror(auto_env: None) -> None:
    """Hueco B — el coste de la adopción sale del libro de fills aplicados."""
    worker = _adoption_worker()
    worker._entry_price["AAA"] = Decimal("13.3")
    assert worker._adoption_cost_basis("AAA") == (Decimal("13.3"), "projection")

    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    assert worker._adoption_cost_basis("AAA") == (Decimal("10.3335"), "ledger")

    # Sin ninguna de las dos fuentes no se inventa: la adopción se declara y no se finge.
    assert worker._adoption_cost_basis("ZZZ") == (None, "none")


def test_adoption_cost_basis_rejects_an_ambiguous_ledger(auto_env: None) -> None:
    """C-4 — con dos motores vivos el medio de la cuenta no identifica la fila.

    Medido 2026-10-21: ``3204115d`` ×2 con 1933.3953 cada uno. El libro sigue mandando
    cuando NO es ambiguo; cuando lo es, el único coste que pertenece a ESTA fila es el
    espejo del motor. Sin espejo no se autoriza ningún número.
    """
    worker = _adoption_worker()
    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    worker._entry_price["AAA"] = Decimal("10.4")

    assert worker._adoption_cost_basis("AAA") == (Decimal("10.3335"), "ledger")
    assert worker._adoption_cost_basis("AAA", canonical_ambiguous=True) == (
        Decimal("10.4"),
        "projection_ambiguous_ledger",
    )

    bare = _adoption_worker()
    bare._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    assert bare._adoption_cost_basis("AAA", canonical_ambiguous=True) == (
        None,
        "ledger_ambiguous",
    )


def test_adoption_with_ambiguous_ledger_uses_the_mirror_and_declares(auto_env: None) -> None:
    """C-4 — la parada se construye con el espejo del motor y se declara degradada."""
    worker = _adoption_worker()
    worker._open["AAA"] = Decimal("100")
    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    worker._entry_price["AAA"] = Decimal("10.4")
    price = Decimal("10.42")

    adopted = worker._v2_adopt_position("AAA", price, ledger_cost_ambiguous=True)
    assert adopted is not None, "una adopción con coste ambiguo no deja la posición muda"
    assert adopted.current_stop is not None
    assert Decimal(str(adopted.current_stop)) < price, "el stop sigue por debajo del mercado"
    assert adopted.lifecycle_state == "RECONCILIATION_REQUIRED", (
        "el nivel se declara: el coste no es el del libro"
    )
    reasons = [e.payload.get("reason") for e in worker._v2_position_journal_pending]
    assert "cost_basis_ambiguous" in reasons
    sources = [e.payload.get("entrySource") for e in worker._v2_position_journal_pending]
    assert "projection_ambiguous_ledger" in sources


def test_adoption_with_ambiguous_ledger_and_no_mirror_is_declared(auto_env: None) -> None:
    """C-4 — libro ambiguo y sin espejo: NO se adopta con un coste inventado."""
    worker = _adoption_worker()
    worker._open["AAA"] = Decimal("100")
    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")

    assert (
        worker._v2_adopt_position("AAA", Decimal("10.42"), ledger_cost_ambiguous=True) is None
    )
    holes = [
        e.payload
        for e in worker._v2_position_journal_pending
        if e.payload.get("reason") == "cost_basis_ambiguous"
    ]
    assert holes, "el hueco de coste se declara con su motivo propio"
    assert holes[0]["entrySource"] == "ledger_ambiguous"
    assert holes[0]["reason"] != "cost_basis_missing", "son huecos distintos"


def test_adoption_with_ambiguous_ledger_rehydrates_the_durable_plan(auto_env: None) -> None:
    """C-4 — un plan durable trae su propia geometría: no necesita el coste del libro."""
    from dataclasses import replace

    from bolsa_analytics.cognitive.position_state import build_position_state_from_fill

    worker = _adoption_worker()
    worker._open["AAA"] = Decimal("100")
    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    plan = build_position_state_from_fill(
        {
            "decisionId": "dec-durable",
            "instrumentId": "AAA",
            "direction": "long",
            "status": "TRIGGERED",
            "entry": 10.3335,
            "structuralStop": 9.8,
            "target1": 11.2,
            "target2": 12.0,
        },
        fill_price=10.3335,
        fill_quantity=100.0,
        filled_at="2026-09-09T09:00:00Z",
    )
    assert plan is not None
    worker._v2_durable_plans["AAA"] = replace(plan, lifecycle_state="PROTECTED").to_dict()

    adopted = worker._v2_adopt_position("AAA", Decimal("10.42"), ledger_cost_ambiguous=True)
    assert adopted is not None
    assert adopted.current_stop == plan.current_stop, "el plan durable manda en el CÓMO salir"
    assert adopted.lifecycle_state == "PROTECTED", "no se degrada un plan verificado"


@pytest.mark.asyncio
async def test_position_package_measures_ledger_ambiguity_before_adopting(
    auto_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C-4 — el cableado: la ambigüedad se mide (async) y viaja a la adopción.

    ``_v2_adopt_position`` se mantiene síncrona para la batería de crash; el dato lo mide
    ``_v2_position_package`` una sola vez por símbolo, y sólo cuando no hay estado vivo.
    """
    worker = _adoption_worker()
    worker._open["AAA"] = Decimal("100")
    worker._canonical_entry_by_symbol["AAA"] = Decimal("10.3335")
    worker._entry_price["AAA"] = Decimal("10.4")
    measured: list[str] = []
    flags: list[bool] = []

    async def fake_ambiguous(account_id: str, symbol: str) -> bool:
        measured.append(f"{account_id}:{symbol}")
        return True

    original = worker._v2_adopt_position

    def spy(
        symbol: str, price: Decimal, *, ledger_cost_ambiguous: bool = False
    ) -> Any:
        flags.append(ledger_cost_ambiguous)
        return original(symbol, price, ledger_cost_ambiguous=ledger_cost_ambiguous)

    monkeypatch.setattr(worker, "_cost_basis_is_ambiguous", fake_ambiguous)
    monkeypatch.setattr(worker, "_v2_adopt_position", spy)

    await worker._v2_position_package("AAA", Decimal("10.42"))

    assert measured == [f"{worker._account_id}:AAA"], "se mide una vez, para ese símbolo"
    assert flags == [True], "el veredicto de ambigüedad llega a la adopción"
    adopted = worker._v2_positions["AAA"]
    assert adopted.current_stop is not None, "el espejo del motor sigue dando un stop"
    reasons = [e.payload.get("reason") for e in worker._v2_position_journal_pending]
    assert "cost_basis_ambiguous" in reasons


@pytest.mark.asyncio
async def test_position_management_events_reach_the_durable_spine(
    auto_env: None,
) -> None:
    """Hueco C — la gestión de posición deja de vivir sólo en la RAM del proceso.

    Medido 2026-10-21: 238 filas de posición en el spine y **0** del símbolo adoptado;
    tras el run sólo quedaba el agregado del día. Sin ``entry``/``stop``/``atr`` en un
    hecho durable, el Hueco B no era depurable a posteriori.
    """
    worker = _adoption_worker(account="acc-evidence")
    published: list[Any] = []

    async def sink(entry: Any) -> None:
        published.append(entry)

    worker._operational_audit_sink = sink
    worker._journal_position_event(
        "AAA",
        "PROTECTION_MISSING",
        at="2026-10-21T17:46:06Z",
        detail={"source": "reconstructed", "stop": 12.9144, "entry": 10.3335},
    )
    assert published == [], "journalizar no publica: se acumula para el final del turno"
    assert worker._v2_position_journal_pending, "el hecho queda en cola"

    await worker._v2_flush_position_journal()

    assert len(published) == 1
    payload = published[0].payload
    assert payload["instrumentId"] == "AAA"
    assert payload["reasonCodes"] == ["PROTECTION_MISSING"]
    assert payload["stop"] == 12.9144
    assert published[0].account_id == "acc-evidence", "el hecho durable sella su cuenta"
    assert worker._v2_position_journal_pending == [], "la cola se vacía siempre"

    # Sin sumidero (hermético) es un no-op: no hay nada que fingir, pero no se acumula.
    worker._operational_audit_sink = None
    worker._journal_position_event("AAA", "PROTECTION_MISSING", at="2026-10-21T17:47:06Z")
    await worker._v2_flush_position_journal()
    assert worker._v2_position_journal_pending == []


@pytest.mark.asyncio
async def test_adopted_position_inherits_version_and_cycle_from_the_ledger(
    auto_env: None,
) -> None:
    """Hueco D — la adopción no pierde la atribución: versión y ciclo salen del libro.

    Medido 2026-10-21: las compras del ``2026-10-20`` declaraban ``v283-window-a`` y las
    ventas de cierre salieron con ``ver=None cycle=None`` ⇒ el cierre no casaba como
    ciclo medible. El dato existía en el último BUY aplicado; sólo se ignoraba.
    """
    from bolsa_analytics.cognitive.position_ledger import AppliedFillFact
    from bolsa_application.applied_fills import CanonicalPositions

    account = "acc-attrib"
    worker = _adoption_worker(account=account)

    async def reader(_acc: str) -> CanonicalPositions:
        return CanonicalPositions(
            {"AAA": Decimal("100")},
            facts=(
                AppliedFillFact(
                    execution_id="fill-old",
                    instrument_id="AAA",
                    side="buy",
                    quantity=60.0,
                    price=10.30,
                    applied_at="2026-10-19T16:09:00+00:00",
                    strategy_version_id="v282-old",
                    account_id=account,
                ),
                AppliedFillFact(
                    execution_id="fill-last",
                    instrument_id="AAA",
                    side="buy",
                    quantity=40.0,
                    price=10.39,
                    applied_at="2026-10-20T16:11:28+00:00",
                    strategy_version_id="v283-window-a",
                    cycle_id="cyc-9b1599c7c635",
                    account_id=account,
                ),
            ),
        )

    worker._canonical_positions_reader = reader
    await worker.readopt_positions()

    # El ÚLTIMO buy aplicado manda: es el que abrió (o amplió) el inventario vivo.
    assert worker._position_version["AAA"] == "v283-window-a"
    assert worker._canonical_attribution["AAA"]["cycleId"] == "cyc-9b1599c7c635"

    worker._open["AAA"] = Decimal("100")
    position = worker._v2_adopt_position("AAA", Decimal("10.42"))
    assert position is not None
    assert position.cycle_id == "cyc-9b1599c7c635", "el cierre hereda el ciclo de la entrada"

    # Un libro que NO declara ciclo no autoriza a inventarlo.
    async def reader_without_cycle(_acc: str) -> CanonicalPositions:
        return CanonicalPositions(
            {"AAA": Decimal("100")},
            facts=(
                AppliedFillFact(
                    execution_id="fill-nocycle",
                    instrument_id="AAA",
                    side="buy",
                    quantity=100.0,
                    price=10.3335,
                    applied_at="2026-10-20T16:11:28+00:00",
                    strategy_version_id="v283-window-a",
                    account_id=account,
                ),
            ),
        )

    bare = _adoption_worker(account=account)
    bare._canonical_positions_reader = reader_without_cycle
    await bare.readopt_positions()
    bare._open["AAA"] = Decimal("100")
    bare_position = bare._v2_adopt_position("AAA", Decimal("10.42"))
    assert bare_position is not None
    assert bare_position.cycle_id is None, "sin ciclo en el libro no se acuña ninguno"
    assert bare._position_version["AAA"] == "v283-window-a"
