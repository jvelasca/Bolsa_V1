"""AUTO-22 — RUN de evidencia: un comando, un bundle reproducible o un BLOQUEO. Sin bundle parcial.

Certifica el contrato del script ``auto_evidence_run.py``:

* **Bundle completo o nada.** La corrida escribe ``cycles.json``/``artifact.json``/``render.txt``/
  ``run.json`` de una vez; si algo la bloquea, NO se crea ni el directorio.
* **``exit 2`` con motivo declarado.** Sin fichero de ciclos, sin ciclos con R medible, o sobre una
  corrida que ya existe (una medición es inmutable) se declara por stderr y se sale con ``2``.
* **Una sola lectura de material.** El exportador (``paper_cycles_export.py``) y el run comparten el
  paginador de ``bolsa_application``: no hay una copia que pueda divergir en el denominador de R.
* **Procedencia declarada, jamás adivinada.** El modo fixture declara ``synthetic_fixture``; con un
  ``material_manifest`` que declara PAPER real, la procedencia es la del material.

Los casos puros (composición) viven en ``packages/py/analytics/tests/test_auto_evidence_run.py``. La
sonda PG real (material sembrado en PostgreSQL) reutiliza el fixture del E2E de ``AUTO-20B``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime as real_datetime
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from tests import test_auto_v63_auto20b_export_e2e_pg as e2e  # noqa: E402 — fixture PG reutilizada.

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "auto_evidence_run.py"
_CALIBRATION_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "py"
    / "analytics"
    / "tests"
    / "fixtures"
    / "auto_calibration_cycles.json"
)


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("auto22_evidence_run", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(argv: list[str]) -> tuple[int, str, str]:
    module = _load_runner()
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def _bundle_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []


# ── Bundle completo (modo fixture declarado) ────────────────────────────────────────


def test_the_run_writes_a_complete_bundle_and_prints_the_three_levels(tmp_path: Path) -> None:
    """Una corrida con material medible escribe los CUATRO ficheros y publica los 3 niveles."""
    root = tmp_path / "runs"
    code, _out, err = _run(
        [
            "--cycles",
            str(_CALIBRATION_FIXTURE),
            "--resamples",
            "50",
            "--out-root",
            str(root),
        ]
    )
    assert code == 0, err
    dirs = _bundle_dirs(root)
    assert len(dirs) == 1, "una corrida escribe exactamente un bundle"
    for name in ("cycles.json", "artifact.json", "render.txt", "run.json"):
        assert (dirs[0] / name).is_file(), f"falta {name}"

    run = json.loads((dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert run["schema"] == "auto22_evidence_run_bundle_v1"
    assert run["source"] == "fixture"
    assert run["materialOrigin"] == "synthetic_fixture"
    assert run["files"]["artifact"] == "artifact.json"
    assert tuple(run["levels"]) == ("material", "statistics", "context")
    assert run["cyclesClosed"] == len(
        json.loads(_CALIBRATION_FIXTURE.read_text(encoding="utf-8"))["cycles"]
    )

    artifact = json.loads((dirs[0] / "artifact.json").read_text(encoding="utf-8"))
    assert "report" in artifact and "correlation" in artifact
    assert (dirs[0] / "render.txt").read_text(encoding="utf-8").startswith(
        "AUTO EVIDENCE REPORT"
    )

    # Los TRES niveles se declaran por stderr, con lo medido y lo no medido.
    for expected in ("NIVEL 1 — MATERIAL", "NIVEL 2 — STATISTICS", "NIVEL 3 — CONTEXT"):
        assert expected in err
    assert "P(R>0)" in err


def test_the_run_accepts_the_declared_out_dir_alias(tmp_path: Path) -> None:
    """El plan nombra `--out-dir`: el alias existe y apunta al MISMO destino que `--out-root`."""
    root = tmp_path / "runs"
    code, _out, err = _run(
        [
            "--cycles",
            str(_CALIBRATION_FIXTURE),
            "--resamples",
            "50",
            "--out-dir",
            str(root),
        ]
    )
    assert code == 0, err
    assert len(_bundle_dirs(root)) == 1, "una corrida escribe exactamente un bundle"


def test_the_run_declares_the_origin_of_a_manifest_instead_of_inventing_it(
    tmp_path: Path,
) -> None:
    """Con un ``material_manifest`` que declara PAPER real, la procedencia es la del material."""
    payload = json.loads(_CALIBRATION_FIXTURE.read_text(encoding="utf-8"))
    payload["material_manifest"] = {
        "materialOrigin": "paper_real",
        "brokerVenue": "paper",
        "fingerprint": "sha256:auto22-fixture",
        "closedCycles": len(payload["cycles"]),
    }
    source = tmp_path / "material.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    root = tmp_path / "runs"
    code, _out, err = _run(
        ["--cycles", str(source), "--resamples", "50", "--out-root", str(root)]
    )
    assert code == 0, err
    run = json.loads(
        (_bundle_dirs(root)[0] / "run.json").read_text(encoding="utf-8")
    )
    assert run["materialOrigin"] == "paper_real"
    assert run["brokerVenue"] == "paper"
    assert run["fingerprint"] == "sha256:auto22-fixture"
    # El origen se declara, pero la CORRIDA no se disfraza de lectura de PostgreSQL.
    assert run["source"] == "fixture"


# ── BLOQUEADO: nunca un bundle parcial ─────────────────────────────────────────────


def test_the_run_is_blocked_without_writing_anything_when_the_cycles_file_is_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runs"
    code, out, err = _run(
        ["--cycles", str(tmp_path / "no_existe.json"), "--out-root", str(root)]
    )
    assert code == 2
    assert out == ""
    assert "BLOQUEADO" in err
    assert _bundle_dirs(root) == [], "un BLOQUEO no deja carpeta ni fichero"


def test_the_run_is_blocked_when_no_cycle_has_a_measurable_r(tmp_path: Path) -> None:
    """Ciclos sin denominador de R: no hay medición, así que no hay bundle."""
    cycles = [
        {
            "cycleId": f"cyc-{index}",
            "strategyVersion": "orb-a",
            "pnl": "3",
            "closedAt": f"2026-01-{index + 1:02d}T10:00:00Z",
        }
        for index in range(6)
    ]
    source = tmp_path / "sin-r.json"
    source.write_text(json.dumps({"cycles": cycles}), encoding="utf-8")

    root = tmp_path / "runs"
    code, out, _err = _run(["--cycles", str(source), "--out-root", str(root)])
    assert code == 2
    assert out == ""
    assert _bundle_dirs(root) == []


def test_an_evidence_run_is_immutable_and_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repetir la misma corrida (mismo instante y huella) BLOQUEA: no se pisa una medición."""
    module = _load_runner()

    class _FrozenDatetime:
        @classmethod
        def now(cls, tz: Any = None) -> real_datetime:
            return real_datetime(2026, 9, 25, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(module, "datetime", _FrozenDatetime)
    root = tmp_path / "runs"
    argv = ["--cycles", str(_CALIBRATION_FIXTURE), "--resamples", "50", "--out-root", str(root)]

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        first = module.main(argv)
        second = module.main(argv)
    assert first == 0, err.getvalue()
    assert second == 2
    assert "BLOQUEADO" in err.getvalue()
    assert len(_bundle_dirs(root)) == 1


# ── Una sola lectura de material (sin copia divergente) ─────────────────────────────


def test_the_exporter_and_the_run_share_the_only_pagination_reader() -> None:
    """El paginador del exportador ES el de la aplicación: no hay una segunda implementación."""
    from bolsa_application.auto_paper_material import read_all_reservations

    spec = importlib.util.spec_from_file_location(
        "auto22_export_single_reader",
        Path(__file__).resolve().parents[1] / "scripts" / "paper_cycles_export.py",
    )
    assert spec is not None and spec.loader is not None
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)

    assert exporter._read_all_reservations is read_all_reservations
    assert exporter.read_paper_material is not None


# ── Sonda PG real: el paso operativo del propietario, ejercitado ────────────────────


def test_the_run_reads_real_postgres_material_and_seals_it(tmp_path: Path) -> None:
    """El comando del propietario, de punta a punta, sobre PostgreSQL real (material sembrado).

    No es evidencia de mercado: es material de fixture con cardinalidad conocida. Lo que certifica
    es que el RUN —lectura única, composición y bundle— funciona entero contra PostgreSQL de verdad
    y declara la procedencia PAPER de lo leído. Gate honesto: sin PostgreSQL real se salta (o falla
    duro con ``AUTO20B_EXPORT_PG_REQUIRED=1``), el mismo gobierno que el E2E del exportador.
    """
    import uuid

    try:
        asyncio.run(e2e._probe())
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        e2e._require_or_skip(exc)
        raise

    account_id = f"acc-a22-{uuid.uuid4().hex[:10]}"
    root = tmp_path / "runs"
    try:
        asyncio.run(e2e._seed(account_id))
        argv = ["--account-id", account_id, "--resamples", "50", "--out-root", str(root)]
        for version in e2e._VERSIONS:
            argv += ["--strategy-version", version]
        code, _out, err = _run(argv)
        assert code == 0, err
        dirs = _bundle_dirs(root)
        assert len(dirs) == 1
        run = json.loads((dirs[0] / "run.json").read_text(encoding="utf-8"))
        assert run["source"] == "paper_real"
        assert run["materialOrigin"] == "paper_real"
        assert run["brokerVenue"] == "paper"
        assert run["cyclesClosed"] == len(e2e._SPECS)
        assert run["fingerprint"]
        # El material leído es el MISMO que el exportador certifica (misma huella).
        artifact = json.loads((dirs[0] / "artifact.json").read_text(encoding="utf-8"))
        assert artifact["material"]["closedCycles"] == len(e2e._SPECS)
        assert artifact["material"]["materialOrigin"] == "paper_real"
        assert artifact["executionReality"] == "virtual_paper_only"
    finally:
        asyncio.run(e2e._cleanup(account_id))
