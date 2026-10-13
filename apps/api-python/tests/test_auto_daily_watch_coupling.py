"""Verificación hermética — ACOPLAMIENTO del watch diario ↔ ESTUDIO (V2.88.123 / S2).

Cierra (tras el hallazgo ``S2`` **declarado** en ``v2.88.122``) el hueco del
desacoplamiento: con el flag ``AUTO_ENGINE_SIMULATED_WATCH_FROM_ESTUDIO`` ON, la lane
de **operación diaria** (``paper_auto_engine_worker._watch_symbols`` /
``auto_simulation_worker.auto_sim_loop``) deriva su watch del universo **canónico**
ESTUDIO (``resolve_estudio_universe`` → ``SqlAlchemyListRepository.ESTUDIO_LIST_ID``)
y el CSV pasa a **allowlist que intersecta**.

Contrato (idéntico al orquestador ``_instruments_for_cycle``):

* ESTUDIO es el universo canónico; el CSV ``AUTO_ENGINE_SIMULATED_WATCH`` solo
  intersecta (vacío ⇒ universo completo; sin intersección ⇒ watch vacío).
* **Fail-closed**: ``empty``/``unavailable``/error/lista vacía ⇒ watch vacío (no se
  opera); la allowlist **nunca** sustituye al universo.
* Con el flag **OFF** (default) la conducta es byte-idéntica al CSV estático: no se
  consulta ESTUDIO ni se toca la BD.

Hermético (sin PostgreSQL): no abre bridge LIVE ni toca la BD.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from bolsa_api.background import paper_auto_engine_worker as worker

_WORKER_SRC = Path(worker.__file__)
_SIM_WATCH = "AUTO_ENGINE_SIMULATED_WATCH"
_DRY_WATCH = "AUTO_ENGINE_DRY_WATCH"
_SIM_FROM_ESTUDIO = worker._ENV_SIM_WATCH_FROM_ESTUDIO
_DRY_FROM_ESTUDIO = worker._ENV_WATCH_FROM_ESTUDIO


class _Port:
    """Puerto ESTUDIO doble: devuelve los ids dados (o ``None``/lanza según el doble)."""

    def __init__(self, instrument_ids: list[str] | None) -> None:
        self._ids = instrument_ids

    async def execute(self, list_id: str) -> Any:
        if self._ids is None:
            return None
        return type("_Detail", (), {"instrument_ids": list(self._ids)})()


class _BoomPort:
    async def execute(self, list_id: str) -> Any:
        raise RuntimeError("estudio down")


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (_SIM_WATCH, _DRY_WATCH, _SIM_FROM_ESTUDIO, _DRY_FROM_ESTUDIO):
        monkeypatch.delenv(name, raising=False)
    worker.reset_watch_memory_for_tests()
    yield
    worker.reset_watch_memory_for_tests()


# ---------------------------------------------------------------------------
# Flag OFF (default): byte-idéntico al CSV estático, sin tocar ESTUDIO.
# ---------------------------------------------------------------------------


def test_off_default_watch_is_the_static_csv() -> None:
    """Sin CSV y sin flag, el watch es el default estático ``AAA,IBEX``."""
    assert worker._watch_symbols() == ["AAA", "IBEX"]


def test_off_reads_the_sim_csv_and_prefers_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """El watch sale del CSV (SIM preferido sobre el alias DRY); recorta y vacía."""
    monkeypatch.setenv(_DRY_WATCH, "OLD,STALE")
    monkeypatch.setenv(_SIM_WATCH, " AAA , BBB ,, CCC ")
    assert worker._watch_symbols() == ["AAA", "BBB", "CCC"]

    monkeypatch.delenv(_SIM_WATCH, raising=False)
    assert worker._watch_symbols() == ["OLD", "STALE"]


def test_off_watch_does_not_resolve_estudio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falsable: con el flag OFF el resolver ESTUDIO NO se invoca (no-op byte-idéntico)."""
    import bolsa_api.background.paper_auto_engine_worker as w

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("el watch diario OFF no debe resolver ESTUDIO")

    monkeypatch.setattr(w, "resolve_daily_watch", _boom)
    monkeypatch.setenv(_SIM_WATCH, "ONLY,CSV")
    assert worker._watch_symbols() == ["ONLY", "CSV"]


def test_off_refresh_is_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con el flag OFF ``refresh_watch_from_estudio`` no consulta ESTUDIO ni cambia nada."""
    monkeypatch.setenv(_SIM_WATCH, "X,Y")

    async def _scenario() -> object:
        return await worker.refresh_watch_from_estudio(_Port(["A", "B"]))

    assert asyncio.run(_scenario()) is None
    assert worker._watch_symbols() == ["X", "Y"]


# ---------------------------------------------------------------------------
# Flag ON: el watch deriva de ESTUDIO (allowlist intersecta + fail-closed).
# ---------------------------------------------------------------------------


def test_on_watch_derives_from_estudio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    asyncio.run(worker.refresh_watch_from_estudio(_Port(["A", "B", "C"])))
    assert worker._watch_symbols() == ["A", "B", "C"]
    assert worker._watch_from_estudio_enabled() is True


def test_on_csv_becomes_an_allowlist_that_intersects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El CSV ya no es el watch: solo filtra (intersecta) el universo ESTUDIO."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "B, ZZZ")
    asyncio.run(worker.refresh_watch_from_estudio(_Port(["A", "B", "C"])))
    assert worker._watch_symbols() == ["B"]


def test_on_csv_without_intersection_is_empty_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "ZZZ,YYY")
    asyncio.run(worker.refresh_watch_from_estudio(_Port(["A", "B", "C"])))
    assert worker._watch_symbols() == []


def test_on_without_refresh_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Antes del primer refresco del tick, el watch ON está vacío (no cae al CSV)."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    assert worker._watch_symbols() == []


def test_on_empty_universe_fails_closed_even_with_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ESTUDIO ``empty`` ⇒ watch vacío: la allowlist NUNCA sustituye al universo."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "AAA")
    asyncio.run(worker.refresh_watch_from_estudio(_Port([])))
    assert worker._watch_symbols() == []


def test_on_unavailable_universe_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Puerto ausente (``None``) ⇒ ``unavailable`` ⇒ watch vacío."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "AAA")
    asyncio.run(worker.refresh_watch_from_estudio(_Port(None)))
    assert worker._watch_symbols() == []


def test_on_error_universe_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un puerto que lanza ⇒ ``unavailable`` ⇒ watch vacío (nunca CSV)."""
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")
    monkeypatch.setenv(_SIM_WATCH, "AAA")
    asyncio.run(worker.refresh_watch_from_estudio(_BoomPort()))
    assert worker._watch_symbols() == []


def test_on_dry_alias_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    """El alias retrocompat ``AUTO_ENGINE_DRY_WATCH_FROM_ESTUDIO`` también enciende."""
    monkeypatch.setenv(_DRY_FROM_ESTUDIO, "1")
    asyncio.run(worker.refresh_watch_from_estudio(_Port(["A"])))
    assert worker._watch_symbols() == ["A"]


def test_sync_decider_watch_updates_membership_without_recreating() -> None:
    """El spine determinista fija su watch al componerse; se realinea sin recrearlo."""

    class _Decider:
        watch: tuple[str, ...] = ("AAA",)

    d = _Decider()
    worker.sync_decider_watch(d, ["A", "B"])
    assert d.watch == ("A", "B")

    class _NoWatch:
        pass

    # Un decider sin atributo ``watch`` (p. ej. la estrategia ACTIVE) es no-op.
    worker.sync_decider_watch(_NoWatch(), ["A"])


def test_auto_sim_loop_refreshes_the_watch_before_each_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``auto_sim_loop`` refresca el watch ANTES de ``run_tick`` (orden del turno)."""
    from bolsa_api.background import auto_simulation_worker as sim

    monkeypatch.setenv(sim.AUTO_SIM_WORKER_ENABLED, "1")
    monkeypatch.setenv(_SIM_FROM_ESTUDIO, "1")

    async def _scenario() -> list[list[str]]:
        seen: list[list[str]] = []

        class _Runtime:
            async def run_tick(self) -> None:
                seen.append(list(worker._watch_symbols()))

        async def _watch_refresher() -> None:
            await worker.refresh_watch_from_estudio(_Port(["EST1", "EST2"]))

        task = asyncio.create_task(
            sim.auto_sim_loop(
                _Runtime(),
                interval_seconds=0.01,
                watch_refresher=_watch_refresher,
            )
        )
        try:
            for _ in range(200):
                await asyncio.sleep(0.01)
                if seen:
                    break
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        return seen

    seen = asyncio.run(_scenario())
    assert seen, "el loop debe haber ejecutado al menos un turno"
    assert seen[0] == ["EST1", "EST2"], "el turno debe ver el watch ESTUDIO vigente"


def test_daily_worker_wires_the_gated_estudio_coupling() -> None:
    """Guarda estática: el acoplamiento gated existe (inverso de la guarda de v2.88.122).

    En ``v2.88.122`` este fichero afirmaba que la lane diaria **no** importaba ESTUDIO.
    Ahora el hueco se cierra de forma **env-gated**: el módulo cablea el resolver
    (``resolve_daily_watch``), el gate (``_watch_from_estudio_enabled``) y el refresco
    (``refresh_watch_from_estudio``). La retirada del cableado pondría este test rojo.
    """
    source = _WORKER_SRC.read_text(encoding="utf-8")
    assert "_watch_from_estudio_enabled" in source, (
        "paper_auto_engine_worker debe exponer el gate del acoplamiento ESTUDIO"
    )
    assert "refresh_watch_from_estudio" in source, (
        "paper_auto_engine_worker debe poder refrescar el watch desde ESTUDIO"
    )
    assert "resolve_daily_watch" in source, (
        "paper_auto_engine_worker debe reutilizar el resolver ESTUDIO (no duplicarlo)"
    )
