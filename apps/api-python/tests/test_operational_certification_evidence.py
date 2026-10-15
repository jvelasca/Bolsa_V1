"""V2.100 · bundle de evidencia operativa P1-P4 — resúmenes falsables (puro, sin PG/BD).

Blinda la regla rectora ``UNKNOWN != 0``: un dato ausente se declara hueco (``None``) y NO cierra
el pendiente; un pendiente sólo se declara ``closed`` con evidencia medida que alcanza su umbral.

No ejerce PostgreSQL: prueba las funciones PURAS de resumen (``_p1_pending`` … ``_p4_pending``)
y el render/markdown del bundle.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_100_operational_certification_evidence.py"


def _load_cli() -> Any:
    name = "v2_100_operational_certification_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# P1 — ventana PAPER
# ---------------------------------------------------------------------------


def test_p1_ready_closes() -> None:
    cli = _load_cli()
    pending = cli._p1_pending(
        {
            "verdict": "READY",
            "days": 4,
            "episodes": 2,
            "measurableCycles": 32,
            "thresholds": {"days": 4, "episodes": 2, "measurableCycles": 32},
            "missingCriterionIds": [],
        }
    )
    assert pending["closed"] is True
    assert pending["days"] == 4


def test_p1_inconclusive_keeps_hueco_never_zero() -> None:
    cli = _load_cli()
    pending = cli._p1_pending(
        {
            "verdict": "INCONCLUSIVE",
            "days": None,
            "episodes": None,
            "measurableCycles": None,
            "missingCriterionIds": ["days", "episodes", "measurableCycles"],
        }
    )
    assert pending["closed"] is False
    assert pending["days"] is None
    assert pending["episodes"] is None
    assert pending["measurableCycles"] is None


def test_p1_ready_but_missing_is_not_closed() -> None:
    cli = _load_cli()
    pending = cli._p1_pending(
        {"verdict": "READY", "days": 4, "episodes": 2, "measurableCycles": 32,
         "missingCriterionIds": ["episodes"]}
    )
    assert pending["closed"] is False


# ---------------------------------------------------------------------------
# P2 — cadena durable por valor de ESTUDIO
# ---------------------------------------------------------------------------


def test_p2_closes_with_measured_value_and_complete_chain() -> None:
    cli = _load_cli()
    pending = cli._p2_pending(
        {"summary": {"values": 35, "measured": 3, "complete": 2, "cycles": 5, "cyclesComplete": 2}}
    )
    assert pending["closed"] is True


def test_p2_zero_measured_does_not_close() -> None:
    cli = _load_cli()
    pending = cli._p2_pending(
        {"summary": {"values": 35, "measured": 0, "complete": 0, "cycles": 0, "cyclesComplete": 0}}
    )
    assert pending["closed"] is False
    assert pending["measured"] == 0  # un cero MEDIDO es un cero, no un hueco


def test_p2_missing_summary_is_hueco() -> None:
    cli = _load_cli()
    pending = cli._p2_pending({})
    assert pending["closed"] is False
    assert pending["measured"] is None
    assert pending["values"] is None


# ---------------------------------------------------------------------------
# P3 — enlace DÍA-D ↔ ciclo
# ---------------------------------------------------------------------------


def test_p3_closes_when_matches_is_not_null() -> None:
    cli = _load_cli()
    chain = {
        "values": [
            {
                "cycles": [
                    {"diaD": {"x": 1}, "executedVsDiaD": {"matches": True}, "cycleId": "c1"},
                    {"diaD": {"y": 1}, "executedVsDiaD": {"matches": False}, "cycleId": "c2"},
                ]
            }
        ],
        "cyclesOutsideEstudio": [],
    }
    pending = cli._p3_pending(chain)
    assert pending["closed"] is True
    assert pending["matchesTrue"] == 1
    assert pending["matchesFalse"] == 1
    assert pending["cyclesWithDiaD"] == 2
    assert set(pending["linkedCycleIds"]) == {"c1", "c2"}


def test_p3_null_matches_does_not_close() -> None:
    cli = _load_cli()
    chain = {
        "values": [{"cycles": [{"diaD": None, "executedVsDiaD": {"matches": None}, "cycleId": "c"}]}],
        "cyclesOutsideEstudio": [],
    }
    pending = cli._p3_pending(chain)
    assert pending["closed"] is False
    assert pending["matchesNull"] == 1
    assert pending["cyclesWithDiaD"] == 0


# ---------------------------------------------------------------------------
# P4 — aislamiento fail-closed
# ---------------------------------------------------------------------------


def test_p4_isolated_closes() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "paper", "LIVE_EXECUTION_UNLOCKED": None, "LIVE_EXECUTION_AUTHORIZED": None},
        0,
    )
    assert pending["closed"] is True


def test_p4_live_venue_does_not_close() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "live", "LIVE_EXECUTION_UNLOCKED": "1", "LIVE_EXECUTION_AUTHORIZED": "1"},
        0,
    )
    assert pending["closed"] is False


def test_p4_unknown_count_is_hueco_not_zero() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "paper", "LIVE_EXECUTION_UNLOCKED": None, "LIVE_EXECUTION_AUTHORIZED": None},
        None,
    )
    assert pending["closed"] is False
    assert pending["liveVenueEvents"] is None


def test_p4_requires_explicit_paper_venue() -> None:
    """El contrato exige ``BROKER_VENUE == paper``: cualquier otro venue NO cierra P4."""
    cli = _load_cli()
    # Venue ausente/vacío/desconocido + envs LIVE ausentes + 0 trazas ⇒ ABIERTO (fail-closed).
    for venue in (None, "", "   ", "xtb", "binance", "unknown", "PAPERX"):
        pending = cli._p4_pending(
            {
                "BROKER_VENUE": venue,
                "LIVE_EXECUTION_UNLOCKED": None,
                "LIVE_EXECUTION_AUTHORIZED": None,
            },
            0,
        )
        assert pending["closed"] is False, f"venue={venue!r} no debe cerrar P4"


def test_p4_empty_venue_is_declared_hueco_not_fabricated() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "   ", "LIVE_EXECUTION_UNLOCKED": None, "LIVE_EXECUTION_AUTHORIZED": None},
        0,
    )
    assert pending["brokerVenue"] is None


def test_p4_paper_venue_canonicalises_case_and_space() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "  PAPER  ", "LIVE_EXECUTION_UNLOCKED": None, "LIVE_EXECUTION_AUTHORIZED": None},
        0,
    )
    assert pending["closed"] is True


def test_p4_live_venue_event_nonzero_does_not_close() -> None:
    cli = _load_cli()
    pending = cli._p4_pending(
        {"BROKER_VENUE": "paper", "LIVE_EXECUTION_UNLOCKED": None, "LIVE_EXECUTION_AUTHORIZED": None},
        3,
    )
    assert pending["closed"] is False
    assert pending["liveVenueEvents"] == 3


# ---------------------------------------------------------------------------
# Render del bundle
# ---------------------------------------------------------------------------


def _bundle(cli: Any) -> dict[str, Any]:
    pendings = {
        "P1": cli._p1_pending({"verdict": "INCONCLUSIVE", "days": None, "episodes": None,
                               "measurableCycles": None, "missingCriterionIds": ["days"]}),
        "P2": cli._p2_pending({"summary": {"values": 35, "measured": 0, "complete": 0}}),
        "P3": cli._p3_pending({"values": [], "cyclesOutsideEstudio": []}),
        "P4": cli._p4_pending(
            {"BROKER_VENUE": "paper", "LIVE_EXECUTION_UNLOCKED": None,
             "LIVE_EXECUTION_AUTHORIZED": None},
            0,
        ),
    }
    return {
        "meta": {"account": "acc", "capturedAt": "2026-10-15T00:00:00Z"},
        "pendings": pendings,
        "closedPendings": [k for k, v in pendings.items() if v["closed"]],
        "openPendings": [k for k, v in pendings.items() if not v["closed"]],
        "limits": ["read-only"],
    }


def test_render_markdown_declares_open_and_closed(capsys: Any) -> None:
    cli = _load_cli()
    bundle = _bundle(cli)
    md = cli._render_markdown(bundle)
    assert "P4 aislamiento | CERRADO" in md
    assert "P1 ventana PAPER | ABIERTO" in md
    cli._print_summary(bundle)
    out = capsys.readouterr().out
    assert "P4 aislamiento" in out
    assert "abiertos:" in out
