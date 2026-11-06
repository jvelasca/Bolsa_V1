"""Pruebas de la guarda de sesión que protege los latidos del repo.

La guarda existe porque ``operability_runs/`` **no está trackeado**: ``git status`` no ve que
un test reescribió ``day-watch.json`` o añadió líneas a ``day-watch.jsonl``. Se prueba aquí
la lógica de atribución, que es la parte que decide entre «la suite ensució el árbol» y «lo
escribió el stack de desarrollo».

Se prueba sobre directorios temporales: estos tests **no** tocan los artefactos reales.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import ModuleType

import _day_watch_guard as guard
import pytest

_OUR_RUN = "pytest-run-de-esta-suite"


def _write_journal(base: Path, rows: list[dict]) -> None:
    base.mkdir(parents=True, exist_ok=True)
    (base / "day-watch.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_fingerprint_detects_a_rewrite_with_identical_content(tmp_path: Path) -> None:
    """Reescribir el mismo contenido NO es inocuo: cambia ``mtime_ns``.

    Es exactamente el caso que ``git status`` no distingue y que la guarda debe ver.
    """
    base = tmp_path
    _write_journal(base, [{"day": "20261026", "verdict": "NOT_DUE"}])
    latido = base / "day-watch.json"
    latido.write_text('{"day": "20261026"}\n', encoding="utf-8")

    before = guard.fingerprint(base)
    time.sleep(0.01)
    latido.write_text('{"day": "20261026"}\n', encoding="utf-8")
    after = guard.fingerprint(base)

    assert before["day-watch.json"][:2] == after["day-watch.json"][:2]  # hash y tamaño
    assert before["day-watch.json"] != after["day-watch.json"]  # mtime_ns distinto
    assert before["day-watch.jsonl"] == after["day-watch.jsonl"]


def test_fingerprint_marks_absent_artifacts(tmp_path: Path) -> None:
    before = guard.fingerprint(tmp_path)
    assert before["day-watch.json"] == ("<ausente>", 0, 0, 0)
    assert before["day-watch.jsonl"] == ("<ausente>", 0, 0, 0)


def test_writers_reads_only_the_new_lines(tmp_path: Path) -> None:
    """Las líneas anteriores a la sesión no cuentan como escritores de la suite."""
    old = [{"day": "20261025", "verdict": "NOT_DUE", "runId": "proceso-anterior"}]
    _write_journal(tmp_path, old)
    before = guard.fingerprint(tmp_path)

    _write_journal(
        tmp_path,
        [
            *old,
            {"day": "20261026", "verdict": "NOT_DUE", "runId": _OUR_RUN},
        ],
    )
    (tmp_path / "day-watch.json").write_text(
        json.dumps({"day": "20261026", "runId": _OUR_RUN}), encoding="utf-8"
    )

    found = guard.writers(before, tmp_path)
    assert found == {_OUR_RUN}
    assert guard.polluted_by(_OUR_RUN, found) is True


def test_writers_flags_a_foreign_heartbeat_without_run_id(tmp_path: Path) -> None:
    """El latido del stack de desarrollo no lleva ``runId``: se distingue del nuestro."""
    _write_journal(tmp_path, [])
    before = guard.fingerprint(tmp_path)
    _write_journal(tmp_path, [{"day": "20261026", "verdict": "NOT_DUE", "source": "worker"}])

    found = guard.writers(before, tmp_path)
    assert found == {guard.NO_RUN_ID}
    assert guard.polluted_by(_OUR_RUN, found) is False


def test_polluted_by_ignores_a_different_pytest_run(tmp_path: Path) -> None:
    """Otra corrida de pytest sí es atribuible… pero no a esta: avisa, no falla."""
    _write_journal(tmp_path, [])
    before = guard.fingerprint(tmp_path)
    _write_journal(tmp_path, [{"day": "20261026", "verdict": "NOT_DUE", "runId": "otra"}])

    found = guard.writers(before, tmp_path)
    assert guard.polluted_by(_OUR_RUN, found) is False


def test_the_suite_injects_the_run_id_in_the_environment() -> None:
    """El contrato mínimo con el ``conftest``: la variable está y es la misma para todos."""
    run_id = os.environ.get("BOLSA_DAY_WATCH_RUN_ID")
    assert run_id, "la fixture autouse debe inyectar BOLSA_DAY_WATCH_RUN_ID"
    assert run_id.startswith("pytest-")


def _app_conftest() -> ModuleType:
    """Localiza el ``conftest`` de ``apps/api-python/tests`` por ruta, no por nombre.

    ``import conftest`` es ambiguo en cuanto conviven varias raíces de test en una misma
    invocación: pytest registra cada ``conftest.py`` bajo un nombre propio y el bare
    ``conftest`` puede resolver a otra copia. Se busca el módulo ya cargado cuya ``__file__``
    sea exactamente el de este directorio; si no está, se carga por ruta (nunca se adivina).
    """
    expected = (Path(__file__).resolve().parent / "conftest.py").resolve()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path is not None and Path(path).resolve() == expected:
            return module
    spec = importlib.util.spec_from_file_location("_app_conftest_for_guard", expected)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def _drive_guard(monkeypatch, base: Path):
    """Ejecuta el cuerpo real de la fixture de sesión sobre ``base`` (sin tocar el repo).

    Devuelve ``(generador, run_id)``. El ``run_id`` se toma del **mismo** módulo que ejecuta
    la guarda: es el que compara.
    """
    app_conftest = _app_conftest()

    monkeypatch.setattr(app_conftest, "_DAY_WATCH_REPO_DIR", base)
    return (
        app_conftest._guard_window_day_watch_artifacts.__wrapped__(),
        app_conftest._PYTEST_RUN_ID,
    )


def test_session_guard_fails_when_this_run_wrote_the_latido(monkeypatch, tmp_path: Path) -> None:
    """Camino rojo: una escritura con **nuestro** ``runId`` rompe la sesión."""
    import pytest as _pytest

    base = tmp_path
    _write_journal(base, [{"day": "20261025", "verdict": "NOT_DUE"}])
    gen, run_id = _drive_guard(monkeypatch, base)
    next(gen)

    _write_journal(
        base,
        [
            {"day": "20261025", "verdict": "NOT_DUE"},
            {"day": "20261026", "verdict": "NOT_DUE", "runId": run_id},
        ],
    )
    (base / "day-watch.json").write_text(
        json.dumps({"day": "20261026", "runId": run_id}), encoding="utf-8"
    )

    with _pytest.raises(_pytest.fail.Exception, match="escribió estado del repo"):
        next(gen)


def test_session_guard_only_warns_for_a_foreign_writer(monkeypatch, tmp_path: Path) -> None:
    """Camino ámbar: el latido del stack dev no puede convertir la suite en rojo."""
    import pytest as _pytest

    base = tmp_path
    _write_journal(base, [{"day": "20261025", "verdict": "NOT_DUE"}])
    gen, _run_id = _drive_guard(monkeypatch, base)
    next(gen)

    _write_journal(
        base,
        [
            {"day": "20261025", "verdict": "NOT_DUE"},
            {"day": "20261026", "verdict": "NOT_DUE", "source": "worker"},
        ],
    )
    (base / "day-watch.json").write_text(
        json.dumps({"day": "20261026", "source": "worker"}), encoding="utf-8"
    )

    with _pytest.warns(UserWarning, match="NO puede concluir"):
        with _pytest.raises(StopIteration):
            next(gen)


def test_session_guard_passes_when_nothing_changed(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path
    _write_journal(base, [{"day": "20261026", "verdict": "NOT_DUE"}])
    gen, _run_id = _drive_guard(monkeypatch, base)
    next(gen)
    with pytest.raises(StopIteration):
        next(gen)

