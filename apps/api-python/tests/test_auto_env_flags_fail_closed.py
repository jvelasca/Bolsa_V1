"""P1 (auditoría TRADING/AUTO .183) — los interruptores de entorno son fail-closed.

El patrón que había antes (``valor not in {"", "0", "false", "no", "off"}``) ENCENDÍA con
cualquier cosa no reconocida: ``disabled``, ``n``, ``of``, ``2``. Este test fija la regla
contraria para cada familia de interruptor del sistema:

* solo ``1/true/yes/on`` enciende;
* ``0/false/no/off/none`` apaga;
* cualquier otro valor deja el DEFAULT del interruptor y deja rastro en el log.

Los defaults difieren por worker (AUTO y precio real nacen OFF; los workers de
infraestructura nacen ON), así que cada caso declara el suyo: lo que se prueba es que un
valor basura NO cambia el default, no que todos tengan el mismo default.
"""

from __future__ import annotations

import logging

import pytest

from bolsa_api.background import (
    alert_delivery_worker,
    execution_event_reaper_worker,
    lifecycle_outbox_worker,
    live_order_recovery_worker,
    paper_auto_engine_worker,
    window_day_watch_worker,
)
from bolsa_api.background import auto_simulation_worker as auto_sim
from bolsa_application.flags import env_finite_float, env_flag, env_positive_int

TRUTHY_VALUES = ("1", "true", "TRUE", "yes", "Yes", "on", "ON", " 1 ")
FALSY_VALUES = ("0", "false", "False", "no", "off", "none", "OFF")
GARBAGE_VALUES = ("disabled", "n", "of", "2", "onn", "tru", "-", "activado")


@pytest.mark.parametrize("raw", TRUTHY_VALUES)
def test_the_on_family_turns_the_switch_on(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("AUDIT_FLAG", raw)
    assert env_flag("AUDIT_FLAG", default=False) is True
    assert env_flag("AUDIT_FLAG", default=True) is True


@pytest.mark.parametrize("raw", FALSY_VALUES)
def test_the_off_family_turns_the_switch_off(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("AUDIT_FLAG", raw)
    assert env_flag("AUDIT_FLAG", default=False) is False
    assert env_flag("AUDIT_FLAG", default=True) is False


@pytest.mark.parametrize("raw", GARBAGE_VALUES)
def test_a_garbage_value_keeps_the_declared_default(
    monkeypatch: pytest.MonkeyPatch, raw: str, caplog: pytest.LogCaptureFixture
) -> None:
    """El corazón de P1: ``disabled`` ya no enciende AUTO ni el precio real."""
    monkeypatch.setenv("AUDIT_FLAG", raw)
    with caplog.at_level(logging.WARNING, logger="bolsa_application.flags"):
        assert env_flag("AUDIT_FLAG", default=False) is False
        assert env_flag("AUDIT_FLAG", default=True) is True
    assert raw.strip() in caplog.text


def test_an_absent_or_empty_value_uses_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDIT_FLAG", raising=False)
    assert env_flag("AUDIT_FLAG", default=False) is False
    assert env_flag("AUDIT_FLAG", default=True) is True
    monkeypatch.setenv("AUDIT_FLAG", "   ")
    assert env_flag("AUDIT_FLAG", default=False) is False
    assert env_flag("AUDIT_FLAG", default=True) is True


# --------------------------------------------------------------------------------------
# Casos por módulo: cada uno fija la función REAL que enciende su worker.
# --------------------------------------------------------------------------------------


def test_auto_sim_worker_and_real_price_are_off_with_a_garbage_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(auto_sim.AUTO_SIM_WORKER_ENABLED, "disabled")
    monkeypatch.setenv(auto_sim.AUTO_REAL_PRICE_ENV, "n")
    assert auto_sim.sim_worker_enabled() is False
    assert auto_sim.real_price_enabled() is False


def test_auto_sim_worker_and_real_price_turn_on_explicitly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(auto_sim.AUTO_SIM_WORKER_ENABLED, "1")
    monkeypatch.setenv(auto_sim.AUTO_REAL_PRICE_ENV, "on")
    assert auto_sim.sim_worker_enabled() is True
    assert auto_sim.real_price_enabled() is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("true", True), ("on", True), ("0", False), ("off", False),
     ("disabled", False), ("n", False)],
)
def test_paper_auto_engine_switch(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv(paper_auto_engine_worker._ENV_SIM_ENABLED, raw)
    assert paper_auto_engine_worker._enabled() is expected


def test_paper_auto_engine_falls_back_to_the_dry_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(paper_auto_engine_worker._ENV_SIM_ENABLED, raising=False)
    monkeypatch.setenv(paper_auto_engine_worker._ENV_ENABLED, "disabled")
    assert paper_auto_engine_worker._enabled() is False
    monkeypatch.setenv(paper_auto_engine_worker._ENV_ENABLED, "yes")
    assert paper_auto_engine_worker._enabled() is True


@pytest.mark.parametrize(
    "module_and_env",
    [
        (alert_delivery_worker, "ALERT_DELIVERY_WORKER_ENABLED"),
        (execution_event_reaper_worker, "EXECUTION_EVENT_REAPER_ENABLED"),
        (lifecycle_outbox_worker, "LIFECYCLE_OUTBOX_WORKER_ENABLED"),
        (live_order_recovery_worker, "LIVE_RECOVERY_WORKER_ENABLED"),
        (window_day_watch_worker, "WINDOW_DAY_WATCH_ENABLED"),
    ],
)
def test_infrastructure_workers_keep_their_on_default(
    monkeypatch: pytest.MonkeyPatch, module_and_env: tuple[object, str]
) -> None:
    """Estos workers nacen ON: un valor basura NO debe apagarlos por accidente."""
    module, env_name = module_and_env
    monkeypatch.setenv(env_name, "disabled")
    assert module._worker_enabled() is True  # type: ignore[attr-defined]
    monkeypatch.setenv(env_name, "off")
    assert module._worker_enabled() is False  # type: ignore[attr-defined]


# --------------------------------------------------------------------------------------
# P9 (avance): los lectores numéricos que comparten el módulo ya rechazan NaN/inf.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ("nan", "NaN", "inf", "-inf", "Infinity", "abc", ""))
def test_env_finite_float_rejects_non_finite_or_text(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("AUDIT_FLOAT", raw)
    assert env_finite_float("AUDIT_FLOAT", default=60.0) == 60.0


def test_env_finite_float_honours_the_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_FLOAT", "0")
    assert env_finite_float("AUDIT_FLOAT", default=60.0, minimum=1.0) == 60.0
    monkeypatch.setenv("AUDIT_FLOAT", "30")
    assert env_finite_float("AUDIT_FLOAT", default=60.0, minimum=1.0) == 30.0


@pytest.mark.parametrize("raw", ("0", "-3", "abc", "3.5", ""))
def test_env_positive_int_rejects_non_positive_or_non_integer(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("AUDIT_INT", raw)
    assert env_positive_int("AUDIT_INT", default=3) == 3


def test_env_positive_int_accepts_a_positive_integer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_INT", "7")
    assert env_positive_int("AUDIT_INT", default=3) == 7
