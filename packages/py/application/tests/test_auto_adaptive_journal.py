"""AUTO-11 — contrato de la recomendación Adaptive durable (paso 1: puro).

Lo que se prueba es la DISCIPLINA, no la aritmética: que sin plan **no** haya fila (una fila vacía
afirmaría "Adaptive evaluó y no recomendó nada"), que la identidad sea del TURNO —un reintento del
mismo tick no duplica evidencia— y que **no** sea alcanzable desde la derivación de ciclos de
AUTO-10 (dos historias distintas no pueden compartir clave), y que lo que no se midió (régimen
ausente, salud inexistente) viaje declarado en vez de rellenarse.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_analytics.cognitive.auto_adaptive import (
    ADAPTIVE_POLICY_VERSION,
    AdaptivePlan,
    AllocationPlan,
    RotationDecision,
    RotationPlan,
    build_adaptive_plan,
)
from bolsa_analytics.cognitive.auto_self_evaluation import StrategySelfEvaluation
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_UNKNOWN,
)
from bolsa_application.auto_adaptive_journal import (
    ADAPTIVE_RECOMMENDATION_DECISION_PREFIX,
    AUTO_ADAPTIVE_RECOMMENDATION_EVENT,
    adaptive_recommendation_decision_id,
    build_adaptive_recommendation_entry,
)
from bolsa_application.auto_cycle_journal import cycle_decision_id

_ACCOUNT = "acc-1"
_AS_OF = "2026-09-22T10:00:00Z"


def _row(
    version: str,
    *,
    decisive: bool = False,
    expectancy: str | None = None,
    win_rate: float | None = None,
) -> StrategySelfEvaluation:
    """Fila de self-evaluation mínima con SOLO lo que Adaptive lee (el resto, ausente)."""
    return StrategySelfEvaluation(
        strategy_version=version,
        trades=0,
        wins=0,
        losses=0,
        realized_pnl=Decimal("0"),
        expectancy_currency=Decimal(expectancy) if expectancy is not None else None,
        expectancy_r=None,
        net_expectancy_r=None,
        win_rate=win_rate,
        profit_factor=None,
        avg_win_currency=None,
        avg_loss_currency=None,
        mfe_r=None,
        mae_r=None,
        slippage_currency=None,
        rejection_cost_return=None,
        drawdown_currency=Decimal("0"),
        drawdown_share=None,
        traded=0,
        rejected=0,
        expired=0,
        missed=0,
        sample_quality="",
        results_measurement=MEASUREMENT_COMPLETE if decisive else MEASUREMENT_UNKNOWN,
        risk_measurement=MEASUREMENT_UNKNOWN,
        net_r_measurement=MEASUREMENT_UNKNOWN,
        cycles_without_cost=0,
        excursions_measurement=MEASUREMENT_UNKNOWN,
        slippage_measurement=MEASUREMENT_UNKNOWN,
        rejection_cost_measurement=MEASUREMENT_UNKNOWN,
        drawdown_measurement=MEASUREMENT_UNKNOWN,
        decisive=decisive,
        notes=(),
    )


def _plan(rows: tuple[StrategySelfEvaluation, ...] = ()) -> AdaptivePlan:
    return build_adaptive_plan(rows, "TREND_UP")


def _entry(**overrides: object):
    base: dict[str, object] = {
        "plan": _plan((_row("v42", decisive=True, expectancy="3"),)),
        "actor": "auto-sim",
        "as_of": _AS_OF,
        "account_id": _ACCOUNT,
    }
    base.update(overrides)
    built = build_adaptive_recommendation_entry(**base)  # type: ignore[arg-type]
    assert built is not None
    return built


# ── Sin plan no hay fila ────────────────────────────────────────────────────────────


def test_without_a_plan_there_is_no_entry() -> None:
    """Un plan ausente NO se escribe como fila vacía: sería afirmar una evaluación que no hubo."""
    assert build_adaptive_recommendation_entry(plan=None, actor="auto-sim", as_of=_AS_OF) is None


# ── La identidad es del TURNO, y no es la de un ciclo ───────────────────────────────


def test_the_decision_id_is_deterministic_for_the_turn() -> None:
    first = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of=_AS_OF)
    second = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of=_AS_OF)

    assert first == second
    assert first.startswith(ADAPTIVE_RECOMMENDATION_DECISION_PREFIX)
    assert len(first) == len(ADAPTIVE_RECOMMENDATION_DECISION_PREFIX) + 12


def test_a_different_turn_or_account_is_a_different_identity() -> None:
    base = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of=_AS_OF)

    assert base != adaptive_recommendation_decision_id(
        account_id=_ACCOUNT, as_of="2026-09-22T11:00:00Z"
    )
    assert base != adaptive_recommendation_decision_id(account_id="acc-2", as_of=_AS_OF)


def test_without_an_instant_the_identity_is_unique_instead_of_shared() -> None:
    """Sin sello de turno no hay clave que reclamar: una identidad propia, nunca una compartida."""
    first = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of="")
    second = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of="")

    assert first != second
    assert first.startswith(ADAPTIVE_RECOMMENDATION_DECISION_PREFIX)


def test_the_adaptive_identity_is_not_reachable_from_a_cycle() -> None:
    """Las dos derivaciones viven en mundos distintos: un ciclo no puede leer esta historia.

    Es la garantía de aislamiento entre la traza de régimen (AUTO-10) y la recomendación
    Adaptive (AUTO-11): si la identidad de una pudiera derivarse de la otra, una sola fila
    serviría a dos lectores con contratos distintos.
    """
    decision_id = adaptive_recommendation_decision_id(account_id=_ACCOUNT, as_of=_AS_OF)

    assert cycle_decision_id(decision_id) is None


def test_a_retry_of_the_same_turn_keeps_the_identity_but_not_the_row() -> None:
    first = _entry()
    second = _entry()

    assert first.decision_id == second.decision_id
    assert first.id != second.id, "el journal es append-only: dos escrituras son dos filas"


# ── El payload: estable, y con lo ausente declarado ─────────────────────────────────


def test_the_payload_declares_the_recommendation_is_read_only() -> None:
    payload = _entry().payload

    assert payload is not None
    assert payload["event"] == AUTO_ADAPTIVE_RECOMMENDATION_EVENT
    assert payload["asOf"] == _AS_OF
    assert payload["readOnly"] is True, "la autoridad de ejecución no es de Adaptive"
    assert payload["policyVersion"] == ADAPTIVE_POLICY_VERSION
    assert payload["regime"] == "TREND_UP"
    assert set(payload) == {
        "event",
        "asOf",
        "readOnly",
        "policyVersion",
        "regime",
        "rotation",
        "allocation",
        "pausedCycles",
        "healthByStrategy",
    }


def test_an_absent_regime_is_declared_not_disguised() -> None:
    """``regime = None`` viaja como ``None``: nunca un ``UNKNOWN`` de relleno."""
    plan = AdaptivePlan(
        rotation=RotationPlan((RotationDecision(strategy_version="v42", active=True),)),
        allocation=AllocationPlan({"v42": 1.0}),
    )
    entry = _entry(plan=plan)

    assert entry.payload is not None
    assert entry.payload["regime"] is None
    assert entry.payload["healthByStrategy"] == {}, "sin filas de salud no se inventa evidencia"


def test_the_rotation_and_allocation_are_projected_by_contract() -> None:
    rows = (
        _row("v42", decisive=True, expectancy="3"),
        _row("v99", decisive=True, expectancy="1"),
    )
    plan = _plan(rows)
    entry = _entry(plan=plan)

    assert entry.payload is not None
    assert entry.payload["rotation"] == {
        "paused": [],
        "byStrategy": [
            {"strategyVersion": "v42", "active": True, "reason": None},
            {"strategyVersion": "v99", "active": True, "reason": None},
        ],
    }
    assert entry.payload["allocation"]["riskMultipliers"] == {"v42": 1.0, "v99": 0.5}
    assert entry.payload["allocation"]["evidenceAxis"] == plan.allocation.evidence_axis
    assert "key" not in entry.payload, "solo lo declarado en el contrato viaja a la historia"


def test_a_paused_strategy_is_projected_in_the_rotation_and_not_assigned() -> None:
    """Pausada ⇒ aparece en ``paused`` y NO recibe multiplicador (no está activa que asignar)."""
    plan = _plan((_row("v42", decisive=True, expectancy="-2"),))
    entry = _entry(plan=plan)

    assert entry.payload is not None
    assert entry.payload["rotation"]["paused"] == ["v42"]
    assert entry.payload["allocation"]["riskMultipliers"] == {}


def test_the_health_is_the_same_evidence_the_decision_publishes() -> None:
    rows = (_row("v99", decisive=True, expectancy="1"),)
    plan = _plan(rows)
    entry = _entry(plan=plan)

    assert entry.payload is not None
    assert entry.payload["healthByStrategy"]["v99"] == plan.evidence_for("v99")
    assert entry.payload["healthByStrategy"]["v99"]["netExpectancyR"] is None
    assert entry.payload["healthByStrategy"]["v99"]["expectancyCurrency"] == "1"


def test_the_paused_counter_that_entered_the_decision_is_published_normalized() -> None:
    """Solo pausas vivas (``> 0``), ordenadas: un ``0`` no es una pausa y un ``bool`` no es cuenta."""
    entry = _entry(paused_cycles={"b": 2, "a": 1, "c": 0, "": 5, "d": -1, "e": True, 7: 3})

    assert entry.payload is not None
    assert entry.payload["pausedCycles"] == {"a": 1, "b": 2}


def test_blank_metadata_is_absent_not_empty() -> None:
    entry = _entry(account_id="   ")

    assert entry.account_id is None
    assert entry.instrument_id is None
