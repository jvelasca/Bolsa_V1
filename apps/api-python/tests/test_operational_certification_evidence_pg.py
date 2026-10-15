"""V2.100 · bundle de evidencia operativa P1-P4 sobre PostgreSQL real (read-only).

Qué certifica este fichero, y por qué es PG-gated:

1. El bundle LEE el material durable real (certificador ``v2_98`` + cadena ESTUDIO) y produce un
   paquete por día con los cuatro pendientes resueltos.
2. **NO fabrica**: un pendiente sólo se declara ``closed`` con evidencia medida que alcanza su
   umbral; un dato ausente viaja ``None`` (hueco), jamás un ``0`` de relleno (``UNKNOWN != 0``).
3. **Read-only**: sólo ``SELECT``; NUNCA abre el bridge LIVE.

GOBIERNO DE HONESTIDAD y ALCANCE
--------------------------------
* Gate PROPIO ``OPERATIONAL_CERT_PG_REQUIRED``: sin PostgreSQL hace ``pytest.skip``; con el env a
  ``1`` un skip silencioso es un FALLO duro.
* La operación real (≥4 días de mercado operables) sigue siendo OPERACIÓN, no CI: en CI el bundle
  ejercita la rama honesta (pendientes ABIERTOS).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_100_operational_certification_evidence.py"

_REQUIRED_ENV = "OPERATIONAL_CERT_PG_REQUIRED"
_ACCOUNT_ENV = "OPERATIONAL_CERT_ACCOUNT"
_VERSIONS_ENV = "OPERATIONAL_CERT_VERSIONS"


def _load_cli() -> Any:
    name = "v2_100_operational_certification_pg_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest_asyncio.fixture
async def operational_cert_pg_factory() -> Any:
    from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="bundle de certificación operativa")
        raise
    try:
        yield factory
    finally:
        await engine.dispose()


async def _resolve_scope(factory: Any) -> tuple[str, list[str]]:
    """Cuenta y versiones del material durable: por env o DESCUBIERTAS (read-only)."""
    from sqlalchemy import text

    from bolsa_application.sim_durable_store import PostgresSimFillFinanceContextStore

    account = os.environ.get(_ACCOUNT_ENV, "").strip()
    versions = [v.strip() for v in os.environ.get(_VERSIONS_ENV, "").split(",") if v.strip()]
    async with factory() as session:
        store = PostgresSimFillFinanceContextStore(session)
        if not account:
            result = await session.execute(
                text(
                    "SELECT DISTINCT account_id FROM sim_fill_finance_context "
                    "WHERE account_id IS NOT NULL ORDER BY account_id LIMIT 1"
                )
            )
            row = result.first()
            account = str(row[0]) if row and row[0] is not None else ""
        if account and not versions:
            counts = await store.count_by_strategy_version(account_id=account)
            versions = sorted(str(key) for key in counts if key is not None and str(key).strip())
    # Sin material se declara una cuenta centinela: la lectura es real y VACÍA (cero MEDIDO).
    # Las versiones son obligatorias para leer la ventana: si el descubrimiento no aporta
    # ninguna, se usan las del pin (las mismas que inyecta el runner de la ventana).
    if not versions:
        versions = ["v283-window-a", "v283-window-b"]
    return account or "operational-cert-sentinel", versions


@pytest.mark.asyncio
async def test_bundle_reads_real_material_and_never_fabricates(
    operational_cert_pg_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account, versions = await _resolve_scope(operational_cert_pg_factory)

    # Sólo lectura PAPER: el guard de venue de ``v2_80`` exige PAPER; NUNCA se abre el bridge LIVE.
    monkeypatch.setenv("BROKER_VENUE", "paper")
    monkeypatch.delenv("LIVE_EXECUTION_UNLOCKED", raising=False)
    monkeypatch.delenv("LIVE_EXECUTION_AUTHORIZED", raising=False)

    args = argparse.Namespace(
        account_id=account,
        strategy_version=versions,
        engine_id="auto-sim",
        days=None,
        since=None,
        limit=2000,
        limit_cycles=100,
        forward=None,
    )
    bundle = await _load_cli()._collect(args)

    # (1) Estructura: los cuatro pendientes, sin excepción.
    assert bundle["kind"] == "OPERATIONAL_CERTIFICATION_EVIDENCE"
    assert bundle["readOnly"] is True
    assert set(bundle["pendings"]) == {"P1", "P2", "P3", "P4"}
    # ``closed`` y ``open`` son complementarios y exhaustivos.
    assert set(bundle["closedPendings"]) | set(bundle["openPendings"]) == {"P1", "P2", "P3", "P4"}
    assert not (set(bundle["closedPendings"]) & set(bundle["openPendings"]))

    pend = bundle["pendings"]

    # (2) P1: cierra sólo con umbrales MEDIDOS y missing vacío.
    p1 = pend["P1"]
    if p1["closed"]:
        assert p1["verdict"] == "READY"
        assert p1["days"] is not None and p1["days"] >= 4
        assert p1["episodes"] is not None and p1["episodes"] >= 2
        assert p1["measurableCycles"] is not None and p1["measurableCycles"] >= 32
        assert p1["missingCriterionIds"] == []
    # ``UNKNOWN != 0``: un conteo es hueco (None) o un entero >= 0.
    for value in (p1["days"], p1["episodes"], p1["measurableCycles"]):
        assert value is None or value >= 0

    # (3) P2: cierra sólo con ≥1 valor medido y una cadena completa.
    p2 = pend["P2"]
    if p2["closed"]:
        assert p2["measured"] is not None and p2["measured"] > 0
        assert p2["completeChains"] is not None and p2["completeChains"] > 0
    for value in (p2["measured"], p2["completeChains"], p2["cycles"]):
        assert value is None or value >= 0

    # (4) P3: cierra sólo con ``matches`` distinto de None (no fabricado con una sola fuente).
    p3 = pend["P3"]
    if p3["closed"]:
        assert p3["matchesTrue"] + p3["matchesFalse"] > 0
    assert p3["matchesNull"] >= 0

    # (5) P4: invariante de aislamiento con los defaults.
    p4 = pend["P4"]
    assert p4["brokerVenue"] != "live"
    assert p4["liveExecutionEnvsAbsent"] is True
    if p4["closed"]:
        assert p4["liveVenueEvents"] == 0
