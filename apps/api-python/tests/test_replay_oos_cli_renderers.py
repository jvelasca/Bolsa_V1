"""V2.86 / V2.87 — regresión del RENDER del censo en modo TEXTO (hallazgo de Bugbot).

Por qué existe este fichero
---------------------------

``main`` de ``v2_86_replay_oos_viability.py`` vuelca ``evidence["census"] = census.to_dict()``
y **después** llama a ``_print_census(evidence["census"])``. El renderer estaba escrito contra el
objeto ``CensusReport`` (acceso por atributo: ``census.watch``, ``census.days``,
``census.operable_by_operational()``), así que el modo **texto** —sin ``--json``— reventaba con
``AttributeError: 'dict' object has no attribute 'watch'``.

El fallo era **silencioso por diseño del CLI**: el ``--out`` JSON se escribe *antes* del render, así
que el artefacto sobrevivía y el crash solo lo veía quien leyese la consola. Esta suite fija el
contrato que lo hace imposible: **lo que ``main`` pasa es un ``dict``**, y el renderer debe aceptarlo.

El guardarraíl es de contrato, no de formato: no afirma *cómo* se imprime, sino que **no se puede**
volver a leer atributos de un ``dict``.
"""

from __future__ import annotations

import importlib.util
import pathlib
from typing import Any

import pytest

from bolsa_application.replay_oos import CensusDay, CensusReport

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_V86_SCRIPT = _ROOT / "apps" / "api-python" / "scripts" / "v2_86_replay_oos_viability.py"
_V87_SCRIPT = _ROOT / "apps" / "api-python" / "scripts" / "v2_87_replay_oos_durable_cycle.py"


def _load(path: pathlib.Path, name: str) -> Any:
    """Carga un orquestador por ruta (no es un módulo instalable)."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def v86() -> Any:
    return _load(_V86_SCRIPT, "v2_86_replay_oos_viability")


@pytest.fixture(scope="module")
def v87() -> Any:
    return _load(_V87_SCRIPT, "v2_87_replay_oos_durable_cycle")


def _census_dict() -> dict[str, Any]:
    """El payload EXACTO que ``main`` entrega al renderer: ``CensusReport.to_dict()``."""
    days = (
        CensusDay(
            day="2022-02-22",
            regimes={"a": "trend_down"},
            counts={"trend_down": 11, "trend_up": 4},
            aggregate="trend_down",
            operational="HIGH_VOLATILITY",
            entries_allowed_long=True,
            operable_symbols=15,
            measured_symbols=20,
            watch=20,
        ),
        CensusDay(
            day="2022-02-23",
            regimes={"a": "trend_down"},
            counts={"trend_down": 10},
            aggregate="trend_down",
            operational="BEAR_TREND",
            entries_allowed_long=False,
            operable_symbols=0,
            measured_symbols=20,
            watch=20,
        ),
    )
    report = CensusReport(
        days=days,
        operable_days=1,
        max_operable_streak=1,
        aggregate_counts={"trend_down": 2},
        watch=20,
    )
    payload = report.to_dict()
    assert isinstance(payload, dict), "el contrato es el dict, no el dataclass"
    return payload


def test_v86_census_renderer_accepts_the_dict_that_main_passes(
    v86: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Con el ``dict`` de ``main`` el render debe funcionar (antes: ``AttributeError``)."""
    payload = _census_dict()

    v86._print_census(payload)  # noqa: SLF001 — se prueba el renderer por contrato.

    out = capsys.readouterr().out
    assert "días de historia          2" in out
    assert "días OPERABLES (long)     1" in out
    # El desglose por eje operativo es el que evita leer «318» como «318 días alcistas».
    assert "{'HIGH_VOLATILITY': 1}" in out
    # La muestra imprime SOLO los días operables y declara cuando no hay ninguno.
    assert "2022-02-22" in out
    assert "2022-02-23" not in out


def test_v86_census_renderer_declares_an_empty_sample(
    v86: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sin días operables el render DECLARA el hueco; no lo deja en blanco."""
    payload = _census_dict()
    payload["days"] = [
        {**payload["days"][1], "entriesAllowedLong": False},
    ]

    v86._print_census(payload)  # noqa: SLF001

    assert "(ninguno)" in capsys.readouterr().out


def test_both_renderers_agree_on_the_same_payload(
    v86: Any, v87: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """El render de ``v2.87`` reimplementó el de ``v2.86``: deben coincidir en el mismo payload.

    No es cosmético: el script de ``v2.87`` nació con la versión CORRECTA (dict) mientras el de
    ``v2.86`` arrastraba la de atributo, así que la divergencia era la huella del defecto.
    """
    payload = _census_dict()

    v86._print_census(payload)  # noqa: SLF001
    from_v86 = capsys.readouterr().out
    v87._print_census(payload)  # noqa: SLF001
    from_v87 = capsys.readouterr().out

    assert from_v86 == from_v87
