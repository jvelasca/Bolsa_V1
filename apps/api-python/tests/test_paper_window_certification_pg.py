"""V2.98 · PAPER WINDOW CERTIFICATION sobre PostgreSQL real (certificador no fabrica).

Qué certifica este fichero, y por qué es PG-gated:

1. **El certificador LEE el material PAPER real** por el camino canónico (``v2_80._collect``, el
   mismo instrumento que publica la ventana) y lo certifica: días de calendario / regímenes /
   ciclos medibles.
2. **NO fabrica.** Si la ventana ``≥4 días`` / ``≥2 episodios`` / ``≥32 ciclos`` NO se alcanza, el
   certificador DECLARA ``INCONCLUSIVE`` con su criterio faltante y el test PASA (declarar el hueco
   no es un fallo). Si se alcanza, todos los criterios están cumplidos: nunca un ``READY`` a medias.
3. **``UNKNOWN ≠ 0``.** Un conteo sólo es ``>= 0`` si se MIDIÓ; jamás un ``0`` de relleno.

GOBIERNO DE HONESTIDAD y ALCANCE
--------------------------------
* Gate PROPIO ``PAPER_WINDOW_CERT_PG_REQUIRED``: sin PostgreSQL hace ``pytest.skip``; con el env a
  ``1`` un skip silencioso es un FALLO duro. Se cablea en el paso DEDICADO del job ``lifecycle-pg``
  (PG presente ⇒ corre; en CI no hay ventana real, así que ejercita la rama honesta ``INCONCLUSIVE``).
  La corrida real de ``≥4`` días de CALENDARIO (reloj de pared) sigue siendo **OPERACIÓN**, no CI.
* Read-only y **NUNCA** abre el bridge LIVE. ``BROKER_VENUE=paper`` sólo habilita LECTURA del
  material durable PAPER (fills + reservas + régimen), jamás una orden real.
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
_CLI = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_98_paper_window_certification.py"

#: Gate propio (fail-if-skipped SÓLO si se pide explícitamente). NO requerido por defecto.
_REQUIRED_ENV = "PAPER_WINDOW_CERT_PG_REQUIRED"
#: Ámbito opcional por env (si no se aporta, se DESCUBRE una cuenta con material).
_ACCOUNT_ENV = "PAPER_WINDOW_CERT_ACCOUNT"
_VERSIONS_ENV = "PAPER_WINDOW_CERT_VERSIONS"


def _load_cli() -> Any:
    """Carga el CLI hermano por ruta (mismo patrón que ``v2_90``/``v2_97``)."""
    name = "v2_98_paper_window_certification_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest_asyncio.fixture
async def paper_window_pg_factory() -> Any:
    from tests._estudio_pg_helpers import make_pg_session_factory, require_or_skip

    try:
        factory, engine = await make_pg_session_factory()
    except Exception as exc:  # noqa: BLE001 — skip/fail gate honesto por env.
        require_or_skip(exc, required_env=_REQUIRED_ENV, what="certificación ventana PAPER")
        raise
    try:
        yield factory
    finally:
        await engine.dispose()


async def _resolve_scope(factory: Any) -> tuple[str | None, list[str]]:
    """Cuenta y versiones del material durable: las pide por env o las DESCUBRE (read-only).

    Se declara lo leído: una cuenta con material y sus versiones observadas; sin material no se
    inventa un ámbito (el test lo trata como lectura real y vacía).
    """
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
            account = str(row[0]) if row and row[0] is not None else None
        if account and not versions:
            counts = await store.count_by_strategy_version(account_id=account)
            versions = sorted(str(key) for key in counts if key is not None and str(key).strip())
    return account, versions


@pytest.mark.asyncio
async def test_certifier_reads_real_material_and_never_fabricates(
    paper_window_pg_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bolsa_application.operability_window import (
        MARKET_WINDOW_INCONCLUSIVE,
        MARKET_WINDOW_MIN_CYCLES,
        MARKET_WINDOW_MIN_DAYS,
        MARKET_WINDOW_MIN_EPISODES,
        MARKET_WINDOW_READY,
    )
    from bolsa_application.paper_window_certification import (
        PaperWindowMaterial,
        certify_paper_window,
    )

    account, versions = await _resolve_scope(paper_window_pg_factory)

    # Lectura CANÓNICA del material real (mismo instrumento que la ventana). Sólo lectura PAPER:
    # el guard de venue de ``v2_80`` exige PAPER; NUNCA se abre el bridge LIVE.
    monkeypatch.setenv("BROKER_VENUE", "paper")
    if account and versions:
        args = argparse.Namespace(
            account_id=account,
            strategy_version=versions,
            days=None,
            since=None,
            limit=2000,
            forward=None,
        )
        rows, _meta = await _load_cli().collect_window_rows(args)
    else:
        # Lectura real y VACÍA: la cuenta no tiene material durable. Es un cero MEDIDO, no un hueco.
        rows = []
    material = PaperWindowMaterial(measured=True, rows=rows, account_id=account)
    cert = certify_paper_window(material)

    # (1) El veredicto sólo puede ser uno de los dos honestos.
    assert cert.verdict in {MARKET_WINDOW_READY, MARKET_WINDOW_INCONCLUSIVE}
    # (2) Un criterio sólo está ``met`` con un conteo MEDIDO que alcanza su umbral.
    for criterion in cert.criteria:
        if criterion.met:
            assert criterion.actual is not None
            assert criterion.actual >= criterion.required
    # (3) READY ⇒ TODOS los criterios cumplidos y los umbrales alcanzados (nada a medias).
    if cert.verdict == MARKET_WINDOW_READY:
        assert cert.ready is True
        assert cert.missing == ()
        assert cert.days is not None and cert.days >= MARKET_WINDOW_MIN_DAYS
        assert cert.episodes is not None and cert.episodes >= MARKET_WINDOW_MIN_EPISODES
        assert cert.measurable_cycles is not None
        assert cert.measurable_cycles >= MARKET_WINDOW_MIN_CYCLES
    else:
        # (4) INCONCLUSIVE ⇒ DECLARA al menos un criterio faltante (no un ``0`` disfrazado).
        assert cert.ready is False
        assert cert.missing
    # (5) ``UNKNOWN ≠ 0``: medido ⇒ ``>= 0``; no medido ⇒ ``None`` (jamás un cero de relleno).
    for value in (cert.days, cert.episodes, cert.measurable_cycles):
        assert value is None or value >= 0
