"""El bloque ``autoRuntime`` declara lo que AUTO tiene encendido, no lo que se supone.

La auditoría externa de 2026-11-08 encontró el gobernador y el veto por ATR apagados y el
precio real OFF sin que nada lo dijera. Estos tests fijan el contrato de la declaración:
un interruptor ausente se reporta con su default real y genera un aviso legible.
"""

from __future__ import annotations

import pytest

from bolsa_api import auto_runtime
from bolsa_api.auto_runtime import auto_runtime_snapshot

_ENV_NAMES = (
    auto_runtime.ENV_WORKER,
    auto_runtime.ENV_V2,
    auto_runtime.ENV_REAL_PRICE,
    auto_runtime.ENV_GOVERNOR,
    auto_runtime.ENV_ATR_REQUIRED,
    auto_runtime.ENV_ACCOUNT_MAX_DD,
    auto_runtime.ENV_ENGINE_ID,
    auto_runtime.ENV_EQUITY,
    "AUTO_ENGINE_SIM_V2_COST_MODEL",
    "AUTO_ENGINE_SIM_V2_COMMISSION_BPS",
    "AUTO_ENGINE_SIM_V2_SPREAD_BPS",
    "AUTO_ENGINE_SIM_V2_SLIPPAGE_BPS",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_default_auto_is_declared_off_not_silent() -> None:
    snap = auto_runtime_snapshot()

    assert snap["workerEnabled"] is False
    assert snap["syntheticFlatPrice"] is False
    assert snap["accountMaxDrawdownPct"] is None
    assert any("AUTO apagado" in warning for warning in snap["warnings"])


def test_worker_on_without_real_price_declares_the_synthetic_100(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(auto_runtime.ENV_WORKER, "1")

    snap = auto_runtime_snapshot()

    assert snap["workerEnabled"] is True
    assert snap["v2Enabled"] is False
    assert snap["syntheticFlatPrice"] is True
    assert any("fabrica 100.0" in warning for warning in snap["warnings"])
    assert any("SIN motor V2" in warning for warning in snap["warnings"])
    assert any("GOBERNADOR" in warning.upper() for warning in snap["warnings"])


def test_full_dev_profile_has_no_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auto_runtime.ENV_WORKER, "1")
    monkeypatch.setenv(auto_runtime.ENV_V2, "1")
    monkeypatch.setenv(auto_runtime.ENV_REAL_PRICE, "1")
    monkeypatch.setenv(auto_runtime.ENV_GOVERNOR, "1")
    monkeypatch.setenv(auto_runtime.ENV_ATR_REQUIRED, "1")
    monkeypatch.setenv(auto_runtime.ENV_ACCOUNT_MAX_DD, "15")
    monkeypatch.setenv(auto_runtime.ENV_ENGINE_ID, "auto-dev-local")
    monkeypatch.setenv(auto_runtime.ENV_EQUITY, "100000")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_COST_MODEL", "1")

    snap = auto_runtime_snapshot()

    assert snap["workerEnabled"] is True
    assert snap["v2Enabled"] is True
    assert snap["realPrice"] is True
    assert snap["syntheticFlatPrice"] is False
    assert snap["governorEnabled"] is True
    assert snap["atrRequired"] is True
    assert snap["accountMaxDrawdownPct"] == pytest.approx(15.0)
    assert snap["engineId"] == "auto-dev-local"
    assert snap["costModel"] is not None
    assert snap["warnings"] == []


def test_a_non_numeric_drawdown_cap_is_not_silently_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(auto_runtime.ENV_WORKER, "1")
    monkeypatch.setenv(auto_runtime.ENV_ACCOUNT_MAX_DD, "quince")

    snap = auto_runtime_snapshot()

    assert snap["accountMaxDrawdownPct"] is None
    assert any("drawdown de cuenta" in warning for warning in snap["warnings"])


def test_cost_model_off_is_declared(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(auto_runtime.ENV_WORKER, "1")
    monkeypatch.setenv("AUTO_ENGINE_SIM_V2_COST_MODEL", "0")

    snap = auto_runtime_snapshot()

    assert snap["costModel"] is None
    assert any("Modelo de coste" in warning for warning in snap["warnings"])
