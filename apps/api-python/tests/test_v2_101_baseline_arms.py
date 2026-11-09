"""Tests del runner de líneas base (auditoría externa 2026-11-08).

Cubren lo que puede hacer circular la evidencia sin tocar la base de datos:
* el brazo AUTO se deriva del artefacto (curva + coste MEDIDO), no de un edge inventado;
* sin ``equityEvidence`` el brazo queda ``NOT_MEASURED``;
* ``v2_93`` sin ``--edge`` ya no arranca (el 0.9 de fábrica se eliminó).
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
    return _load("v2_101_baseline_arms.py")


def _artifact(*, cost: float | None = 32.0) -> dict[str, Any]:
    return {
        "meta": {"declaredEdge": 0.62, "phase": "V2.93 DIA-D AUTO MULTI ATTRIBUTION"},
        "equityEvidence": {
            "curve": [
                {"day": "2024-01-01", "equity": 100_000.0},
                {"day": "2024-01-02", "equity": 110_000.0},
            ],
            "netReturnPct": 10.0,
            "maxDrawdownPct": 0.0,
            "positiveWindowPct": 100.0,
            "positiveWindows": {"measuredWindows": 1},
            "buyHold": {"pct": 8.0, "excessPct": 2.0},
            "realizedCostBpsPerSide": 12.71,
            "realizedCostRoundTripBps": cost,
            "startDay": "2024-01-01",
            "endDay": "2024-01-02",
            "holdout": {
                "holdoutPct": 30.0,
                "cutDay": "2024-01-02",
                "inSampleDays": 1,
                "inSampleNetReturnPct": 0.0,
                "inSampleMaxDrawdownPct": 0.0,
                "outOfSampleDays": 1,
                "outOfSampleNetReturnPct": 10.0,
                "outOfSampleMaxDrawdownPct": 0.0,
            },
            "notMeasured": [],
        },
    }


class TestAutoArm:
    def test_uses_artifact_curve_cost_and_declared_edge(self, runner: Any) -> None:
        arm = runner._auto_arm(_artifact(), holdout_pct=30.0)
        assert arm["evaluation"]["verdict"] == "ACCREDITED"
        assert arm["declaredEdge"] == pytest.approx(0.62)
        assert arm["realizedCostBpsPerSide"] == pytest.approx(12.71)
        assert arm["holdout"]["outOfSampleNetReturnPct"] == pytest.approx(10.0)

    def test_unmeasured_cost_never_accredits(self, runner: Any) -> None:
        arm = runner._auto_arm(_artifact(cost=None), holdout_pct=30.0)
        assert arm["evaluation"]["verdict"] == "NOT_ACCREDITED"
        assert arm["evaluation"]["notMeasured"] == ["minRoundTripCostBps"]

    def test_missing_equity_evidence_is_declared_not_invented(self, runner: Any) -> None:
        arm = runner._auto_arm({"meta": {}}, holdout_pct=30.0)
        assert arm["verdict"] == "NOT_MEASURED"
        assert "equityEvidence" in arm["reason"]


class TestCliGuards:
    def test_auto_artifact_without_declared_edge_is_rejected(self, runner: Any) -> None:
        assert runner.main(["--auto-artifact", "no-existe.json"]) == 1

    def test_dia_d_multi_without_edge_does_not_start(self) -> None:
        module = _load("v2_93_dia_d_multi.py")
        assert module.main(["--from-year", "2024", "--to-year", "2024"]) == 1
