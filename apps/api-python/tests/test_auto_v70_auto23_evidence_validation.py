"""AUTO-23 — VALIDACIÓN de evidencia: un comando, un informe inmutable o un BLOQUEO.

Certifica el contrato del script ``auto_evidence_validate.py``:

* **Informe completo o nada.** La validación escribe ``sweep.json``/``regime_stability.json``/
  ``correlation_validation.json``/``validation.json`` de una vez; si algo la bloquea, NO se crea ni
  el directorio.
* **``exit 2`` con motivo declarado.** Sin fichero de ciclos, sin ciclos con R medible, o sobre una
  validación que ya existe (una medición es inmutable) se declara por stderr y se sale con ``2``.
* **Una sola lectura de material.** El validador y el RUN comparten el paginador de
  ``bolsa_application``: no hay una copia que pueda divergir en el denominador de R.
* **Procedencia declarada, jamás adivinada.** El modo fixture declara ``synthetic_fixture``; con un
  ``material_manifest`` que declara PAPER real, la procedencia es la del material.

La sonda PG real (material sembrado en PostgreSQL) reutiliza el fixture del E2E de ``AUTO-20B``.
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

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "auto_evidence_validate.py"
_CALIBRATION_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "py"
    / "analytics"
    / "tests"
    / "fixtures"
    / "auto_calibration_cycles.json"
)


def _load_validator() -> Any:
    spec = importlib.util.spec_from_file_location("auto23_evidence_validate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(argv: list[str]) -> tuple[int, str, str]:
    module = _load_validator()
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def _run_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir()) if root.exists() else []


_SMALL = ["--sizes", "16,64", "--buckets", "day,week", "--resamples", "50"]


# ── Informe completo (modo fixture declarado) ───────────────────────────────────────


def test_the_validation_writes_a_complete_report(tmp_path: Path) -> None:
    """Una validación con material medible escribe los CUATRO ficheros y declara la procedencia."""
    root = tmp_path / "validations"
    code, _out, err = _run(
        ["--cycles", str(_CALIBRATION_FIXTURE), *_SMALL, "--out-root", str(root)]
    )
    assert code == 0, err
    dirs = _run_dirs(root)
    assert len(dirs) == 1, "una validación escribe exactamente un informe"
    for name in (
        "sweep.json",
        "regime_stability.json",
        "correlation_validation.json",
        "validation.json",
    ):
        assert (dirs[0] / name).is_file(), f"falta {name}"

    document = json.loads((dirs[0] / "validation.json").read_text(encoding="utf-8"))
    assert document["schema"] == "auto23_evidence_validation_v2"
    assert document["materialOrigin"] == "synthetic_fixture"
    assert document["measuredCycles"] == 126
    assert document["run"]["source"] == "fixture"
    assert document["run"]["files"]["sweep"] == "sweep.json"
    assert document["sweep"]["schema"] == "auto23_sample_size_sweep_v2"
    assert document["regimeStability"]["schema"] == "auto23_regime_stability_v2"
    assert document["correlationValidation"]["schema"] == "auto23_correlation_validation_v1"
    # El cubo proyectado en run.json es el pedido, no el defecto silencioso.
    assert document["run"]["buckets"] == ["day", "week"]
    assert "BLOQUEADO" not in err


def test_the_validation_declares_the_origin_of_a_manifest_instead_of_inventing_it(
    tmp_path: Path,
) -> None:
    """Con un ``material_manifest`` que declara PAPER real, la procedencia es la del material."""
    payload = json.loads(_CALIBRATION_FIXTURE.read_text(encoding="utf-8"))
    payload["material_manifest"] = {
        "materialOrigin": "paper_real",
        "brokerVenue": "paper",
        "fingerprint": "sha256:auto23-fixture",
        "closedCycles": len(payload["cycles"]),
    }
    source = tmp_path / "material.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    root = tmp_path / "validations"
    code, _out, err = _run(
        ["--cycles", str(source), *_SMALL, "--out-root", str(root)]
    )
    assert code == 0, err
    document = json.loads(
        (_run_dirs(root)[0] / "validation.json").read_text(encoding="utf-8")
    )
    assert document["materialOrigin"] == "paper_real"
    assert document["brokerVenue"] == "paper"
    assert document["fingerprint"] == "sha256:auto23-fixture"
    # El origen se declara, pero la corrida no se disfraza de lectura de PostgreSQL.
    assert document["run"]["source"] == "fixture"


# ── BLOQUEADO: nunca un informe parcial ─────────────────────────────────────────────


def test_the_validation_is_blocked_without_writing_anything_when_the_cycles_file_is_missing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "validations"
    code, out, err = _run(
        ["--cycles", str(tmp_path / "no_existe.json"), "--out-root", str(root)]
    )
    assert code == 2
    assert out == ""
    assert "BLOQUEADO" in err
    assert _run_dirs(root) == [], "un BLOQUEO no deja carpeta ni fichero"


def test_the_validation_is_blocked_when_no_cycle_has_a_measurable_r(tmp_path: Path) -> None:
    """Ciclos sin denominador de R: no hay medición, así que no hay informe."""
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

    root = tmp_path / "validations"
    code, out, _err = _run(["--cycles", str(source), "--out-root", str(root)])
    assert code == 2
    assert out == ""
    assert _run_dirs(root) == []


def test_a_validation_is_immutable_and_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Repetir la misma validación (mismo instante y huella) BLOQUEA: no se pisa una medición."""
    module = _load_validator()

    class _FrozenDatetime:
        @classmethod
        def now(cls, tz: Any = None) -> real_datetime:
            return real_datetime(2026, 9, 25, 12, 0, 0, tzinfo=tz)

    monkeypatch.setattr(module, "datetime", _FrozenDatetime)
    root = tmp_path / "validations"
    argv = ["--cycles", str(_CALIBRATION_FIXTURE), *_SMALL, "--out-root", str(root)]

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        first = module.main(argv)
        second = module.main(argv)
    assert first == 0, err.getvalue()
    assert second == 2
    assert "BLOQUEADO" in err.getvalue()
    assert len(_run_dirs(root)) == 1


# ── Una sola lectura de material (sin copia divergente) ─────────────────────────────


def test_the_validator_and_the_run_share_the_only_material_reader() -> None:
    """El lector del validador ES el de la aplicación: no hay una segunda implementación."""
    from bolsa_application.auto_paper_material import read_paper_material

    validator = _load_validator()
    assert validator.read_paper_material is read_paper_material


# ── Sonda PG real: el paso operativo del propietario, ejercitado ────────────────────


def test_the_validation_reads_real_postgres_material_and_seals_it(tmp_path: Path) -> None:
    """El comando del propietario, de punta a punta, sobre PostgreSQL real (material sembrado)."""
    import uuid

    try:
        asyncio.run(e2e._probe())
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        e2e._require_or_skip(exc)
        raise

    account_id = f"acc-a23-{uuid.uuid4().hex[:10]}"
    root = tmp_path / "validations"
    try:
        asyncio.run(e2e._seed(account_id))
        argv = [
            "--account-id",
            account_id,
            *_SMALL,
            "--out-root",
            str(root),
        ]
        for version in e2e._VERSIONS:
            argv += ["--strategy-version", version]
        code, _out, err = _run(argv)
        assert code == 0, err
        dirs = _run_dirs(root)
        assert len(dirs) == 1
        document = json.loads(
            (dirs[0] / "validation.json").read_text(encoding="utf-8")
        )
        assert document["run"]["source"] == "paper_real"
        assert document["materialOrigin"] == "paper_real"
        assert document["brokerVenue"] == "paper"
        assert document["measuredCycles"] == len(e2e._SPECS)
        assert document["fingerprint"]
    finally:
        asyncio.run(e2e._cleanup(account_id))
