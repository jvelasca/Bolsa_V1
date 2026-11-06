"""Cableado de la sonda de proveedores en el ``lifespan`` de la API.

Lo que se prueba es el ARRANQUE (que la sonda exista y se dispare sola), no la sonda en
sí: ``packages/py/application/tests/test_market_providers.py`` cubre la medición. Aquí se
sustituyen engine, migraciones y monitor por dobles para no tocar BD ni red.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

import bolsa_api.main as main_module

pytestmark = pytest.mark.asyncio


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


class _FakeMonitor:
    instances: list[_FakeMonitor] = []

    def __init__(self, session_factory: Any, *, xtb_bridge_url: str | None = None) -> None:
        self.session_factory = session_factory
        self.xtb_bridge_url = xtb_bridge_url
        self.probes = 0
        self.started = 0
        self.closed = False
        _FakeMonitor.instances.append(self)

    async def probe_if_due(self, *, force: bool = False) -> None:
        _ = force
        self.probes += 1

    def start(self) -> None:
        self.started += 1

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """``lifespan`` sin BD, sin red y con el monitor sustituido."""
    import bolsa_application.market_providers as providers_module
    from bolsa_infrastructure.config import Settings

    _FakeMonitor.instances = []
    engine = _FakeEngine()
    captured: dict[str, Any] = {"engine": engine}

    async def _bootstrap(*, engine: Any, session_factory: Any) -> None:
        captured["session_factory"] = session_factory

    def _session_factory(_engine: Any) -> Any:
        def factory() -> None:
            return None

        return factory

    monkeypatch.setattr(main_module, "install_log_redact", lambda: None)
    monkeypatch.setattr(main_module, "configure_ai_governance_proxy", lambda: None)
    monkeypatch.setattr(main_module, "teardown_ai_governance_proxy", lambda: None)
    monkeypatch.setattr(main_module, "dispose_llm_call_audit_engine", lambda: None)
    monkeypatch.setattr(main_module, "database_bootstrap", _bootstrap)
    monkeypatch.setattr(main_module, "create_engine", lambda _settings: engine)
    monkeypatch.setattr(main_module, "create_session_factory", _session_factory)
    monkeypatch.setattr(providers_module, "ProviderHealthMonitor", _FakeMonitor)

    def _settings(**_kwargs: Any) -> Settings:
        # ``Settings`` declara alias en mayúsculas: se pasan como alias para que la
        # inicialización gane al entorno y al ``.env`` (pytest inyecta el flag en OFF
        # para toda la suite; este doble decide su propio valor).
        return Settings(
            XTB_BRIDGE_URL=None,
            PROVIDER_HEALTH_PROBE_ON_STARTUP=(
                "1" if captured.get("probe_on_startup", True) else "0"
            ),
        )

    monkeypatch.setattr(main_module, "get_settings", _settings)
    return captured


async def test_lifespan_installs_monitor_and_probes_on_startup(wired: dict[str, Any]) -> None:
    app = FastAPI()

    async with main_module.lifespan(app):
        monitor = app.state.provider_health
        assert isinstance(monitor, _FakeMonitor)
        assert monitor.probes == 1
        # El bucle arranca siempre; si la política está OFF no medirá, pero un cambio a ON
        # surte efecto sin reiniciar.
        assert monitor.started == 1
        assert monitor.xtb_bridge_url is None
        assert monitor.session_factory is not None

    # Al apagar, la sonda en vuelo se cancela: no quedan tareas huérfanas.
    assert monitor.closed is True
    assert wired["engine"].disposed is True


async def test_lifespan_can_declare_no_startup_probe(wired: dict[str, Any]) -> None:
    """Sin sonda al arrancar el monitor sigue instalado: el endpoint sondea bajo demanda."""
    wired["probe_on_startup"] = False
    app = FastAPI()

    async with main_module.lifespan(app):
        monitor = app.state.provider_health
        assert isinstance(monitor, _FakeMonitor)
        assert monitor.probes == 0
        # El bucle sí arranca: apagar la cadencia no apaga la posibilidad de encenderla.
        assert monitor.started == 1
