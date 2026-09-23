"""AUTO-13 — la costura del CABLEADO del Data Gate en el plan Adaptive (paso 3).

Lo que se prueba es la COSTURA, no la tabla pura del gate (esa vive en
``packages/py/analytics/tests/test_auto_adaptive_data_gate.py``): que el gate se componga de los
hechos que el tick YA midió sin pagar I/O nuevo, que con ``OK`` los argumentos del plan sean los
históricos (el plan es byte-idéntico a ``v2.53``), que ``DEGRADED`` deje de repartir con la
confianza **conservando la protección**, que ``STALE`` no admita reactivaciones nuevas y que
``BLOCKED`` declare el tick sin plan (y sin fila de journal).

Con el flag Adaptive OFF ``_v2_plan_tick`` no llama a este método (worker 2912), así que el gate
—que vive DENTRO de él— tampoco se evalúa: es la misma garantía de cero I/O que ya cubre la
costura de ``AUTO-12`` y el byte-idéntico del payload de ``AUTO-8`` con el flag OFF.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_simulation_worker as worker_mod
from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_STRATEGY_COOLDOWN,
    ADAPTIVE_STRATEGY_UNHEALTHY,
    AdaptivePolicy,
)
from bolsa_analytics.cognitive.auto_adaptive_data_gate import assess_data_gate
from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.sim_durable_store import SimFillFinanceContext

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"
_FLOOR = 0.35
#: ``AdaptivePolicy.min_pause_cycles`` por defecto: el techo de la retención en ``STALE`` es 2.
_MIN_PAUSE = AdaptivePolicy().min_pause_cycles


def _fill(version: str, index: int, *, side: str, price: str) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=f"{version}-{index}-{side}",
        instrument_id="AAA",
        side=side,
        quantity=Decimal("10"),
        price=Decimal(price),
        account_id=_ACCOUNT,
        venue="SIM",
        strategy_version_id=version,
        cycle_id=f"cyc-{version}-{index}",
        created_at=datetime(2026, 9, 1, 9 if side == "buy" else 15, 0, tzinfo=UTC),
    )


def _cycles(version: str, count: int, *, entry: str, exit_: str) -> list[SimFillFinanceContext]:
    """``count`` ciclos cerrados con el mismo recorrido de precio (ganadores o perdedores)."""
    return [
        _fill(version, index, side=side, price=price)
        for index in range(count)
        for side, price in (("buy", entry), ("sell", exit_))
    ]


def _profitable(version: str, count: int) -> list[SimFillFinanceContext]:
    return _cycles(version, count, entry="100", exit_="110")


def _losing(version: str, count: int) -> list[SimFillFinanceContext]:
    """Ciclos decisorios y PROBADAMENTE negativos: la salud manda pausar, no los datos."""
    return _cycles(version, count, entry="100", exit_="90")


class _FillStore:
    """Store de fills que CUENTA las lecturas: el gate no puede añadir I/O."""

    def __init__(self, by_version: dict[str, list[SimFillFinanceContext]]) -> None:
        self._by_version = by_version
        self.calls: list[str] = []

    async def list_for_strategy_version(
        self, version: str, *, account_id: str | None = None, limit: int | None = None
    ) -> list[SimFillFinanceContext]:
        self.calls.append(version)
        return list(self._by_version.get(version, ()))


class _Reservations:
    """Reservas de mentira: una entrada con riesgo medido por ciclo (el denominador de R)."""

    async def list_by_cycle_ids(
        self, _account_id: str | None, cycle_ids: Any, *, limit: int = 500
    ) -> list[Any]:
        return [
            SimpleNamespace(
                cycle_id=cycle_id,
                reservation_id=f"RES-{cycle_id}",
                is_buy=True,
                reserved_risk="5",
                cost=None,
                created_at="2026-09-01T09:00:00+00:00",
            )
            for cycle_id in cycle_ids
        ]


class _Journal:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def sink(self, entry: Any) -> None:
        self.entries.append(entry)


def _worker(
    *,
    store: Any | None = None,
    paused: dict[str, int] | None = None,
    failures: int = 0,
    anchor: int | None = None,
) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = "auto-sim"
    worker._context_store = store
    worker._reservation_store = _Reservations()
    worker._cycle_regime_reader = None
    worker._v2_adaptive_paused_cycles = dict(paused or {})
    worker._v2_adaptive_paused_cycles_entered = {}
    worker._v2_adaptive_sink_failures = failures
    worker._v2_adaptive_journal_anchor_age = anchor
    worker._v2_tunables = SimpleNamespace(
        adaptive_enabled=True,
        adaptive_win_rate_floor=_FLOOR,
        regime_override=None,
    )
    worker._time = SimpleNamespace(strftime=lambda _fmt: _AS_OF)
    return worker


def _health_of(plan: Any, version: str) -> Any:
    return next(row for row in plan.health if row.strategy_version == version)


def _spy_gate(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura los HECHOS con los que se compone el gate (sin cambiar su resultado)."""
    captured: list[dict[str, Any]] = []
    original = worker_mod.assess_data_gate

    def spy(**kwargs: Any) -> Any:
        captured.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(worker_mod, "assess_data_gate", spy)
    return captured


def _spy_plan(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Captura los ARGUMENTOS con los que se construye el plan (y lo construye igual)."""
    captured: list[dict[str, Any]] = []
    original = worker_mod.build_adaptive_plan

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(worker_mod, "build_adaptive_plan", spy)
    return captured


# ── La composición del gate: hechos ya medidos, cero I/O ────────────────────────────


@pytest.mark.asyncio
async def test_the_gate_is_composed_from_already_measured_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El gate no inventa insumos ni lee: une la completitud de los ejes que Adaptive exige."""
    store = _FillStore({"orb-1": _profitable("orb-1", 12)})
    captured = _spy_gate(monkeypatch)
    worker = _worker(store=store)

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert store.calls == ["orb-1"], "el gate no puede pagar una lectura nueva"
    facts = captured[0]
    assert facts["regime_available"] is True
    # La completitud entra por los ejes que Adaptive EXIGE (resultados y riesgo), no por el
    # net-R opcional: su hueco cae por diseño al eje moneda y NO es una deuda de datos.
    assert facts["measurement_completeness"] == "COMPLETE"
    assert facts["recent_available"] is True
    assert facts["read_ok"] is True
    assert facts["sink_failures"] == 0


@pytest.mark.asyncio
async def test_the_gate_adds_no_read_even_when_it_limits_or_blocks() -> None:
    """``DEGRADED``/``STALE``/``BLOCKED`` no cuestan una lectura más: siguen siendo una por versión."""
    for failures, anchor in ((1, None), (_MIN_PAUSE, None), (1, 20)):
        store = _FillStore({"orb-1": _profitable("orb-1", 12)})
        worker = _worker(store=store, failures=failures, anchor=anchor)

        await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

        assert store.calls == ["orb-1"]


@pytest.mark.asyncio
async def test_an_unknown_regime_is_declared_absent_and_limits_the_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§20: sin régimen juzgable el gate lo declara incompleto (``regime_available=False``)."""
    captured = _spy_gate(monkeypatch)
    worker = _worker(store=_FillStore({"orb-1": _profitable("orb-1", 12)}))

    await worker._v2_build_adaptive_plan({"orb-1"}, None)

    assert captured[0]["regime_available"] is False


# ── ``OK``: los argumentos del plan son los históricos ──────────────────────────────


@pytest.mark.asyncio
async def test_with_a_healthy_gate_the_plan_arguments_are_the_historical_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``OK`` ⇒ mismos argumentos que ``v2.53``: la confianza se pasa y las pausas son las reales."""
    store = _FillStore({"orb-1": _profitable("orb-1", 12)})
    captured = _spy_plan(monkeypatch)
    worker = _worker(store=store, paused={"orb-1": 5})

    plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is not None
    assert captured[0]["confidence"] is not None, "OK no puede apagar la confianza de AUTO-12"
    assert captured[0]["paused_cycles"] == {"orb-1": 5}, "las pausas entran sin recortar"
    assert _health_of(plan, "orb-1").confidence is not None


@pytest.mark.asyncio
async def test_with_a_healthy_gate_the_plan_is_byte_identical() -> None:
    """Dos ticks con el mismo material y gate ``OK`` producen el MISMO plan publicado."""
    store_a = _FillStore({"thin": _profitable("thin", 12), "broad": _profitable("broad", 180)})
    store_b = _FillStore({"thin": _profitable("thin", 12), "broad": _profitable("broad", 180)})

    first = await _worker(store=store_a)._v2_build_adaptive_plan({"thin", "broad"}, "TREND_UP")
    second = await _worker(store=store_b)._v2_build_adaptive_plan({"thin", "broad"}, "TREND_UP")

    assert first is not None and second is not None
    assert first.as_dict() == second.as_dict()


@pytest.mark.asyncio
async def test_an_explicit_healthy_gate_is_equivalent_to_the_composed_one() -> None:
    """``gate=None`` compone la lectura; aportar una ``OK`` da el MISMO plan (no cambia nada)."""
    fills = {"thin": _profitable("thin", 12), "broad": _profitable("broad", 180)}

    composed = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad"}, "TREND_UP"
    )
    explicit = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad"}, "TREND_UP", gate=assess_data_gate()
    )

    assert composed is not None and explicit is not None
    assert composed.as_dict() == explicit.as_dict()


# ── ``DEGRADED``: deja de repartir con la confianza, conserva la protección ─────────


@pytest.mark.asyncio
async def test_degraded_stops_using_the_confidence_but_keeps_the_protection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un fallo del sink apaga el encogimiento por confianza; la pausa por salud sigue."""
    fills = {
        "thin": _profitable("thin", 12),
        "broad": _profitable("broad", 180),
        "bad": _losing("bad", 12),
    }
    healthy = await _worker(store=_FillStore(fills))._v2_build_adaptive_plan(
        {"thin", "broad", "bad"}, "TREND_UP"
    )
    captured = _spy_plan(monkeypatch)
    degraded = await _worker(store=_FillStore(fills), failures=1)._v2_build_adaptive_plan(
        {"thin", "broad", "bad"}, "TREND_UP"
    )

    assert healthy is not None and degraded is not None
    # OK: la confianza viaja como evidencia.
    assert _health_of(healthy, "thin").confidence is not None
    # DEGRADED: no se reparte con ella (``confidence=None`` entrante) y no se publica.
    assert captured[0]["confidence"] is None
    assert all(row.confidence is None for row in degraded.health)
    # …pero la PROTECCIÓN no se toca: la versión probadamente negativa sigue pausada.
    assert healthy.rotation.is_paused("bad") and degraded.rotation.is_paused("bad")
    assert degraded.rotation.reason_for("bad") == ADAPTIVE_STRATEGY_UNHEALTHY


# ── ``STALE``: ninguna reactivación nueva ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_stale_holds_a_live_pause_that_would_otherwise_reactivate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La evidencia ilegible no puede CONFIRMAR que el cooldown ya se cumplió: la pausa sigue."""
    store = _FillStore({"orb-1": _profitable("orb-1", 12)})
    # Con el gate OK, una pausa que ya cumplió su mínimo se reactiva (la métrica es sana).
    healthy = await _worker(store=store, paused={"orb-1": 5})._v2_build_adaptive_plan(
        {"orb-1"}, "TREND_UP"
    )
    assert healthy is not None and not healthy.rotation.is_paused("orb-1")

    captured = _spy_plan(monkeypatch)
    worker = _worker(store=store, paused={"orb-1": 5}, failures=_MIN_PAUSE)
    stale = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert stale is not None
    assert stale.rotation.is_paused("orb-1"), "STALE no admite reactivaciones nuevas"
    assert stale.rotation.reason_for("orb-1") == ADAPTIVE_STRATEGY_COOLDOWN
    # El techo de la retención es ``min_pause_cycles - 1``: por debajo del mínimo, no cumplido.
    assert captured[0]["paused_cycles"] == {"orb-1": _MIN_PAUSE - 1}
    # El contador REAL sigue creciendo: al volver la evidencia se juzga con la antigüedad verdadera.
    assert worker._v2_adaptive_paused_cycles == {"orb-1": 6}


@pytest.mark.asyncio
async def test_stale_does_not_freeze_a_new_health_pause() -> None:
    """``STALE`` congela reactivaciones, no la protección: una pausa NUEVA por salud sí entra."""
    fills = {"ok": _profitable("ok", 12), "bad": _losing("bad", 12)}
    worker = _worker(store=_FillStore(fills), failures=_MIN_PAUSE)

    plan = await worker._v2_build_adaptive_plan({"ok", "bad"}, "TREND_UP")

    assert plan is not None
    assert plan.rotation.is_paused("bad")
    assert plan.rotation.reason_for("bad") == ADAPTIVE_STRATEGY_UNHEALTHY
    assert not plan.rotation.is_paused("ok")


# ── ``BLOCKED``: el tick se declara sin plan ────────────────────────────────────────


@pytest.mark.asyncio
async def test_blocked_declares_the_tick_without_a_plan(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Journal muerto (ancla corroborada por encima del gap) ⇒ ``adaptive = None`` declarado."""
    journal = _Journal()
    worker = _worker(
        store=_FillStore({"orb-1": _profitable("orb-1", 12)}), failures=1, anchor=20
    )
    worker._adaptive_sink = journal.sink

    with caplog.at_level(logging.WARNING):
        plan = await worker._v2_build_adaptive_plan({"orb-1"}, "TREND_UP")

    assert plan is None
    assert "BLOCKED" in caplog.text
    # Sin plan no hay fila: el journal no finge una recomendación vacía (fail-open declarado).
    await worker._v2_journal_adaptive_recommendation(plan)
    assert journal.entries == []
