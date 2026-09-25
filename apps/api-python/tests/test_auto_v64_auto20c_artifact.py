"""AUTO-20C (V2.64) — artefacto reproducible, render e invariante PAPER VIRTUAL (PURO).

Tres contratos que NO necesitan PostgreSQL:

* **Artefacto + render.** El battery, con ``--out``/``--render``, guarda el ``AUTO EVIDENCE
  REPORT`` reproducible sin cambiar una coma de lo que ya emitía por stdout.
* **Procedencia virtual.** El artefacto declara que el material es PAPER con **dinero VIRTUAL**:
  nunca se ejecuta sobre XTB ni ninguna plataforma real.
* **Venue.** El exportador se BLOQUEA (``exit 2``) si la venue no es ``paper``: un artefacto PAPER
  no se sella con material de otro carril.

Hermético: sin PG, sin red, sin broker. El E2E contra PostgreSQL real vive en
``test_auto_v63_auto20b_export_e2e_pg.py`` (job PG con gate fail-if-skipped).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_cycles_export.py"
_BATTERY = Path(__file__).resolve().parents[3] / "scripts" / "research" / "auto_replay_battery.py"


def _load_battery() -> Any:
    spec = importlib.util.spec_from_file_location("auto20c_replay_battery", _BATTERY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_exporter() -> Any:
    spec = importlib.util.spec_from_file_location("auto20c_paper_cycles_export", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cycles() -> list[dict[str, Any]]:
    return [
        {
            "cycleId": f"cyc-a20c-{index}",
            "strategyVersion": "orb-a20c",
            "pnl": "1.0",
            "closedAt": f"2026-09-2{index}T10:00:00Z",
            "riskAmount": "0.5",
        }
        for index in range(1, 7)
    ]


def _manifest(cycles: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "account": "acc-a20c",
        "requestedStrategyVersions": ["orb-a20c"],
        "observedStrategyVersions": ["orb-a20c"],
        "versionsRequestedWithoutMaterial": [],
        "versionsObservedNotRequested": [],
        "materialOrigin": "paper_real",
        "executionReality": "virtual_paper_only",
        "brokerVenue": "paper",
        "fillsRead": len(cycles),
        "fillsTotalForAccount": 20,
        "fillsSelected": len(cycles),
        "fillsExcludedNoVersion": 8,
        "fillsExcludedOtherVersion": 0,
        "closedCycles": len(cycles),
        "cyclesWithRisk": len(cycles),
        "cyclesWithoutRisk": 0,
        "regimesPresent": ["TREND_UP"],
        "reservationsRead": len(cycles),
        "riskReadSaturated": False,
        "riskBasis": "reservation_reserved_risk",
        "fingerprint": "sha256:a20c-material",
        "fingerprintMethod": "material_fingerprint_v1",
    }


def _material_file(tmp_path: Path) -> Path:
    cycles = _cycles()
    path = tmp_path / "material.json"
    path.write_text(
        json.dumps(
            {
                "note": "material PAPER REAL sobre cuenta PAPER VIRTUAL",
                "material_manifest": _manifest(cycles),
                "cycles": cycles,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_the_battery_writes_the_artifact_and_render_without_changing_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--out``/``--render`` añaden el artefacto; stdout queda byte-idéntico al de sin flags."""
    battery = _load_battery()
    material = _material_file(tmp_path)
    out = tmp_path / "AUTO20C_REAL_PAPER_REPORT.json"
    render = tmp_path / "AUTO20C_REAL_PAPER_REPORT.txt"
    base = ["--walk-forward", "--cycles", str(material), "--resamples", "20"]

    assert battery.main([*base]) == 0
    stdout_without = capsys.readouterr().out

    assert battery.main([*base, "--out", str(out), "--render", str(render)]) == 0
    captured = capsys.readouterr()
    assert captured.out == stdout_without, "el artefacto no puede cambiar lo que ya se imprimía"

    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["schema"] == "auto20c_evidence_artifact_v1"
    assert artifact["report"]["method"] == "walk_forward_calibration_v2"
    assert artifact["material"] == _manifest(_cycles())

    text = render.read_text(encoding="utf-8")
    assert "AUTO EVIDENCE REPORT" in text
    assert "excluded (no version):8" in text
    assert "AUTO-21 (fuera de alcance)" in text


def test_the_artifact_declares_virtual_paper_and_no_real_money(tmp_path: Path) -> None:
    """El invariante de la fase: PAPER VIRTUAL, venue paper, y el aviso viaja en el artefacto."""
    from bolsa_analytics.cognitive.auto_evidence_report import (
        EXECUTION_REALITY_VIRTUAL_PAPER,
        MATERIAL_ORIGIN_PAPER_REAL,
    )

    battery = _load_battery()
    out = tmp_path / "artifact.json"
    battery.main(
        [
            "--walk-forward",
            "--cycles",
            str(_material_file(tmp_path)),
            "--resamples",
            "20",
            "--out",
            str(out),
        ]
    )

    artifact = json.loads(out.read_text(encoding="utf-8"))
    assert artifact["executionReality"] == EXECUTION_REALITY_VIRTUAL_PAPER
    assert artifact["realMoneyAtRisk"] is False
    assert artifact["brokerVenue"] == "paper"
    assert artifact["materialOrigin"] == MATERIAL_ORIGIN_PAPER_REAL
    assert "VIRTUAL" in artifact["note"]


def test_the_exporter_blocks_a_venue_that_is_not_paper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un artefacto PAPER no se sella con material de otra venue: se DECLARA y se sale con 2."""
    from bolsa_infrastructure.config import get_settings

    module = _load_exporter()
    monkeypatch.setenv("BROKER_VENUE", "live")
    get_settings.cache_clear()
    try:
        code = module.main(["--account-id", "acc-a20c", "--strategy-version", "orb-a20c"])
    finally:
        get_settings.cache_clear()
    captured = capsys.readouterr()

    assert code == 2
    assert captured.out == "", "sin venue PAPER no se publica ningún JSON"
    assert "BLOQUEADO" in captured.err
