"""Verificación hermética — ACOPLAMIENTO (real: DESACOPLAMIENTO) del watch diario ↔ ESTUDIO.

HALLAZGO DECLARADO (plan ``verificación AUTO/DÍA-D``, slice ``S2``; NO se cierra aquí)

Las dos lanes AUTO no comparten fuente de instrumentos:

* Lane de **estrategia/orquestación** (``auto_orchestrator_worker``): el universo
  canónico es la lista **ESTUDIO** (``resolve_estudio_universe`` →
  ``SqlAlchemyListRepository.ESTUDIO_LIST_ID``); el CSV ``AUTO_ORCHESTRATOR_INSTRUMENTS``
  solo **intersecta**.
* Lane de **operación diaria** (``paper_auto_engine_worker._watch_symbols``, línea 104):
  el watch sale de un **CSV estático** (``AUTO_ENGINE_SIMULATED_WATCH`` /
  ``AUTO_ENGINE_DRY_WATCH``), con default ``AAA,IBEX``. **No consulta ESTUDIO.**

Consecuencia para el operador: mantener el CSV y la lista ESTUDIO **sincronizados a mano**;
un valor que entra en ESTUDIO no entra solo en el día AUTO. Este fichero FIJA la conducta
actual para que cualquier acoplamiento futuro sea VISIBLE (el test se pondría rojo y
obligaría a actualizar la declaración de evidencia), sin forzar el cierre del hueco.

Hermético (sin PostgreSQL): no abre bridge LIVE ni toca la BD.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_WORKER_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bolsa_api"
    / "background"
    / "paper_auto_engine_worker.py"
)
_SIM_WATCH = "AUTO_ENGINE_SIMULATED_WATCH"
_DRY_WATCH = "AUTO_ENGINE_DRY_WATCH"


def test_daily_watch_default_is_the_static_csv_not_estudio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin CSV, el watch diario es el default estático ``AAA,IBEX`` (nunca ESTUDIO)."""
    from bolsa_api.background import paper_auto_engine_worker as worker

    monkeypatch.delenv(_SIM_WATCH, raising=False)
    monkeypatch.delenv(_DRY_WATCH, raising=False)
    assert worker._watch_symbols() == ["AAA", "IBEX"]


def test_daily_watch_reads_the_sim_csv_and_prefers_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El watch sale del CSV (SIM preferido sobre el alias DRY); se recorta y se vacía."""
    from bolsa_api.background import paper_auto_engine_worker as worker

    monkeypatch.setenv(_DRY_WATCH, "OLD,STALE")
    monkeypatch.setenv(_SIM_WATCH, " AAA , BBB ,, CCC ")
    assert worker._watch_symbols() == ["AAA", "BBB", "CCC"]

    # Sin el canónico, cae al alias retrocompat (mismo contrato que el resto del worker).
    monkeypatch.delenv(_SIM_WATCH, raising=False)
    assert worker._watch_symbols() == ["OLD", "STALE"]


def test_daily_watch_never_consults_estudio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsable: booby-trap del resolver ESTUDIO ⇒ el watch diario NO se inmuta.

    Si la lane diaria llegara a derivar su watch de ESTUDIO, resolver el universo
    reventaría dentro de ``_watch_symbols``. Que devuelva el CSV pese al booby-trap es la
    prueba de que **no** existe tal dependencia hoy.
    """
    import bolsa_application.paper_desk_entry as entry
    from bolsa_api.background import paper_auto_engine_worker as worker

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("el watch diario NO debe resolver el universo ESTUDIO")

    monkeypatch.setattr(entry, "resolve_estudio_universe", _boom)
    monkeypatch.setenv(_SIM_WATCH, "ONLY,CSV")
    assert worker._watch_symbols() == ["ONLY", "CSV"]


def test_daily_worker_module_does_not_import_the_estudio_universe() -> None:
    """Guarda estática: el módulo de la lane diaria no cablea ESTUDIO (hueco declarado).

    Es un candado de VISIBILIDAD, no de corrección: si alguien acopla la lane diaria al
    universo, este test cae y hay que actualizar la declaración de evidencia del sello
    (y la matriz de cobertura) antes de volver a verde.
    """
    source = _WORKER_SRC.read_text(encoding="utf-8")
    assert "resolve_estudio_universe" not in source, (
        "paper_auto_engine_worker ha empezado a resolver ESTUDIO: el desacoplamiento "
        "declarado en la evidencia v2.88.122 ya no es cierto — actualiza la declaración"
    )
    assert "ESTUDIO_LIST_ID" not in source, (
        "paper_auto_engine_worker referencia ESTUDIO_LIST_ID: revisa el acoplamiento"
    )
