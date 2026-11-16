"""V2.103 — contrato del CLI de reemisión: clasificación pura y forma del artefacto.

Lo que se certifica aquí es la DECISIÓN del CLI, no la escritura (esa se mide en el nodo
PostgreSQL gemelo, donde ``ON CONFLICT DO NOTHING`` es un hecho y no una lectura del código):

1. **Clasificación honesta.** Un ciclo con un hecho de la política vigente es ``vigente``
   (no-op); con solo el histórico es ``solo_legacy``; sin ninguno es ``sin_settlement``. Un
   hecho SIN ``pnlPolicy`` es histórico —lo que de verdad se publicó—, no un hueco.
2. **La referencia del delta es el HISTÓRICO.** Cuando coexisten los dos hechos, la cifra
   contra la que se mide la reemisión es la que se va a superar. Compararse contra el hecho
   nuevo daría siempre delta cero y escondería justo el cambio que hay que declarar.
3. **Nada se inventa.** Un ciclo sin ``cycleId`` se cuenta como ``unmeasurable``; un PnL
   ausente deja el delta en ``None`` (nunca en ``0``, que sería una afirmación de igualdad).
4. **Dry-run por defecto.** Sin ``--apply`` el parser no escribe: es la garantía de que el
   artefacto de evidencia se puede producir contra la BD sin mutarla.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from decimal import Decimal
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
def cli() -> Any:
    return _load("v2_103_reenvio_settlements_politica.py")


def _settlement(
    *, cycle: str, pnl: Any, policy: str | None, settlement_id: str = "settle-x"
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": "auto_cycle_settlement",
        "settlementId": settlement_id,
        "cycleId": cycle,
        "pnl": pnl,
        "settledAt": "2026-11-01T10:00:00Z",
    }
    if policy is not None:
        payload["pnlPolicy"] = policy
    return payload


# ── Clasificación ────────────────────────────────────────────────────────────────────


def test_a_cycle_without_settlement_is_declared_not_guessed(cli: Any) -> None:
    """Sin hecho durable no hay referencia: ``sin_settlement``, nunca ``delta = 0``."""
    state = cli.classify_cycle("cyc-1", [])
    assert state["classification"] == cli.CLASS_SIN_SETTLEMENT
    assert state["previous"] is None
    assert state["previousPolicy"] is None


def test_only_the_historical_fact_is_a_reemission_candidate(cli: Any) -> None:
    """Un hecho sin ``pnlPolicy`` es el histórico: ``solo_legacy`` y su PnL es la referencia."""
    legacy = _settlement(cycle="cyc-1", pnl=-29.24890072, policy=None)
    state = cli.classify_cycle("cyc-1", [legacy])
    assert state["classification"] == cli.CLASS_SOLO_LEGACY
    assert state["previous"] is legacy
    assert state["previousPolicy"] == "fifo_exact_v0"
    assert state["duplicateLegacy"] is False


def test_a_current_fact_is_a_no_op(cli: Any) -> None:
    """Con hecho de la política vigente no se reemite: la corrida es un no-op."""
    current = _settlement(cycle="cyc-1", pnl="-29.248900", policy="applied_per_fill_v1")
    state = cli.classify_cycle("cyc-1", [current])
    assert state["classification"] == cli.CLASS_VIGENTE
    assert state["legacy"] == []


def test_two_policies_coexisting_are_not_a_duplicate(cli: Any) -> None:
    """Legacy + vigente conviviendo: vigente manda y el histórico es la REFERENCIA del delta."""
    legacy = _settlement(cycle="cyc-1", pnl=-29.24890072, policy=None, settlement_id="settle-old")
    current = _settlement(
        cycle="cyc-1", pnl="-29.248900", policy="applied_per_fill_v1", settlement_id="settle-new"
    )
    state = cli.classify_cycle("cyc-1", [legacy, current])
    assert state["classification"] == cli.CLASS_VIGENTE
    assert state["previous"] is legacy, "la referencia es la cifra que se va a superar"
    assert state["duplicateCurrent"] is False


def test_duplicates_within_a_policy_are_flagged(cli: Any) -> None:
    """Dos hechos de la MISMA política sí son un duplicado: no se normaliza en silencio."""
    one = _settlement(cycle="cyc-1", pnl="-29.248900", policy="applied_per_fill_v1")
    two = _settlement(cycle="cyc-1", pnl="-29.248900", policy="applied_per_fill_v1")
    state = cli.classify_cycle("cyc-1", [one, two])
    assert state["classification"] == cli.CLASS_VIGENTE
    assert state["duplicateCurrent"] is True


def test_facts_of_another_cycle_do_not_leak(cli: Any) -> None:
    """El filtro es por ``cycleId``: un hecho de otro ciclo no cambia la clasificación."""
    other = _settlement(cycle="cyc-2", pnl="1.0", policy="applied_per_fill_v1")
    state = cli.classify_cycle("cyc-1", [other])
    assert state["classification"] == cli.CLASS_SIN_SETTLEMENT


# ── Plan ────────────────────────────────────────────────────────────────────────────


def _cycle(cycle_id: str | None, pnl: str, exact: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "cycleId": cycle_id,
        "pnl": Decimal(pnl),
        "pnlPolicy": "applied_per_fill_v1",
    }
    if exact is not None:
        row["pnlExact"] = Decimal(exact)
    return row


def test_the_plan_publishes_the_delta_against_the_superseded_figure(cli: Any) -> None:
    """El delta declarado es ``nuevo − histórico``: la cifra nueva frente a la sellada."""
    legacy = _settlement(cycle="cyc-1", pnl="-29.24890072", policy=None)
    plan = cli.build_plan(
        cycles=[_cycle("cyc-1", "-29.248900", "-29.24890072")],
        settlements=[legacy],
    )
    row = plan["rows"][0]
    assert row["classification"] == cli.CLASS_SOLO_LEGACY
    assert row["needsReemission"] is True
    assert row["previousPnl"] == "-29.24890072"
    assert row["newPnl"] == "-29.248900"
    assert row["newPnlExact"] == "-29.24890072"
    assert row["delta"] == "0.00000072"
    assert plan["counts"][cli.CLASS_SOLO_LEGACY] == 1
    assert plan["counts"]["toReemit"] == 1
    assert plan["counts"]["maxAbsDelta"] == "0.00000072"


def test_a_vigente_cycle_is_not_scheduled_and_its_delta_is_zero(cli: Any) -> None:
    """Con el hecho vigente ya presente no hay reemisión: delta cero, no un hueco."""
    current = _settlement(cycle="cyc-1", pnl="-29.248900", policy="applied_per_fill_v1")
    plan = cli.build_plan(cycles=[_cycle("cyc-1", "-29.248900")], settlements=[current])
    row = plan["rows"][0]
    assert row["classification"] == cli.CLASS_VIGENTE
    assert row["needsReemission"] is False
    assert row["delta"] == "0.000000"
    assert plan["counts"]["toReemit"] == 0


def test_a_cycle_without_identity_is_declared_unmeasurable(cli: Any) -> None:
    """Sin ``cycleId`` no hay hecho que reemitir: se cuenta el hueco en vez de adivinar."""
    plan = cli.build_plan(cycles=[_cycle(None, "1.0")], settlements=[])
    assert plan["counts"]["unmeasurable"] == 1
    assert plan["counts"]["total"] == 0
    assert plan["rows"] == []


def test_a_missing_pnl_leaves_the_delta_absent(cli: Any) -> None:
    """Sin cifra nueva el delta es ``None``: no se afirma igualdad que nadie midió."""
    plan = cli.build_plan(
        cycles=[{"cycleId": "cyc-1", "pnl": None}],
        settlements=[_settlement(cycle="cyc-1", pnl="1.0", policy=None)],
    )
    assert plan["rows"][0]["delta"] is None
    assert plan["rows"][0]["previousPnl"] == "1.0"
    assert plan["rows"][0]["newPnl"] is None


def test_the_max_abs_delta_ignores_absent_values(cli: Any) -> None:
    """La cota agregada no convierte un ``None`` en cero: solo mide lo medido."""
    plan = cli.build_plan(
        cycles=[_cycle("cyc-1", "1.0"), {"cycleId": "cyc-2", "pnl": None}],
        settlements=[
            _settlement(cycle="cyc-1", pnl="0.5", policy=None),
            _settlement(cycle="cyc-2", pnl="9.0", policy=None),
        ],
    )
    assert plan["counts"]["maxAbsDelta"] == "0.5"


def test_the_decimal_reader_never_invents_a_zero(cli: Any) -> None:
    """``bool`` y basura no son dinero; un ausente no se convierte en ``0``."""
    assert cli._dec(None) is None
    assert cli._dec(True) is None
    assert cli._dec("no-es-un-numero") is None
    assert cli._dec("1.25") == Decimal("1.25")


# ── CLI ─────────────────────────────────────────────────────────────────────────────


def test_dry_run_is_the_default_mode(cli: Any) -> None:
    """Sin ``--apply`` el CLI no escribe: evidencia contra la BD sin mutarla."""
    args = cli._parse_args(["--account-id", "acc-1"])
    assert args.apply is False
    assert args.limit == 500
    assert args.account_id == "acc-1"


def test_apply_must_be_requested_explicitly(cli: Any) -> None:
    args = cli._parse_args(["--account-id", "acc-1", "--apply", "--cycle-id", "cyc-1"])
    assert args.apply is True
    assert args.cycle_id == "cyc-1"
