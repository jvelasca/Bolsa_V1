"""V2.103 — la reemisión contra PostgreSQL real: un hecho NUEVO, el anterior intacto.

El nodo puro certifica la decisión; este certifica el único hecho que la decisión necesita y
que no se puede leer del código: que ``--apply`` **inserta** y no reescribe, que la clave
policy-aware hace que reejecutar sea un no-op, y que el hecho histórico sigue en su sitio.

Secuencia medida sobre un ciclo cerrado por el camino PRODUCTIVO (mismo arnés que la batería
de identidad, para no sembrar hechos a mano):

1. el cierre productivo ya publicó el settlement de la política vigente ⇒ ``vigente``, no-op;
2. se sustituye ese hecho por el HISTÓRICO (sin ``pnlPolicy`` y con el PnL exacto del FIFO,
   que es la cifra que el contrato anterior publicaba) ⇒ ``solo_legacy`` con delta medible;
3. ``--apply`` ⇒ exactamente UN hecho nuevo, el histórico sigue presente;
4. ``--apply`` otra vez ⇒ CERO hechos nuevos (``ON CONFLICT DO NOTHING`` sobre la clave
   versionada), que es lo que impide que un reintento duplique la historia.

GOBIERNO DE HONESTIDAD: sin PostgreSQL real hace ``pytest.skip``; con
``AUTO_IDENTITY_CHAIN_PG_REQUIRED=1`` el skip es FALLO. Nunca abre el bridge LIVE.
"""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY

# El arnés es el MISMO de la batería de identidad: si cambia el camino productivo, este nodo
# mide el cambio en vez de congelar una copia que pueda divergir en silencio.
from tests.test_auto_identity_chain_battery_pg import (
    _IDENTITY_SOURCE,
    _drive_cycle,
    _teardown,
    identity_pg_factory,  # noqa: F401 — fixture: se solicita por su NOMBRE
)

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_CLI = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "v2_103_reenvio_settlements_politica.py"
)

_EVENT = "auto_cycle_settlement"


def _load_cli() -> Any:
    name = "v2_103_reenvio_settlements_politica_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ── Lecturas/escrituras de apoyo (SQL directo: el nodo mira la TABLA, no el repositorio) ─


async def _facts(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, cycle_id: str
) -> list[dict[str, Any]]:
    """Hechos de settlement del ciclo, tal y como están en la tabla (id + payload + clave)."""
    async with factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, payload, dedupe_key FROM decision_journal_entries "
                    "WHERE event_type = :e AND account_id = :a AND payload->>'cycleId' = :c "
                    "ORDER BY id"
                ),
                {"e": _EVENT, "a": account_id, "c": cycle_id},
            )
        ).all()
    return [
        {"id": str(row[0]), "payload": dict(row[1] or {}), "dedupeKey": row[2]}
        for row in rows
    ]


async def _delete_facts(
    factory: async_sessionmaker[AsyncSession], *, account_id: str, cycle_id: str
) -> None:
    """Borra los hechos del ciclo SOLO para dejar el escenario histórico: no es el CLI."""
    async with factory() as session:
        await session.execute(
            text(
                "DELETE FROM decision_journal_entries "
                "WHERE event_type = :e AND account_id = :a AND payload->>'cycleId' = :c"
            ),
            {"e": _EVENT, "a": account_id, "c": cycle_id},
        )
        await session.commit()


async def _insert_historical_fact(
    factory: async_sessionmaker[AsyncSession],
    *,
    account_id: str,
    engine_id: str,
    cycle_id: str,
    payload: dict[str, Any],
    pnl_exact: Decimal,
) -> None:
    """Reinserta el hecho con la FORMA HISTÓRICA: sin ``pnlPolicy`` y con el PnL exacto.

    Se construye con el MISMO builder de producción (con ``pnl_policy=None``), de modo que el
    escenario legacy es el que el contrato anterior producía, no un JSON inventado a mano.
    """
    from bolsa_application.auto_operational_audit import (
        build_cycle_settlement_entry,
        durable_fact_dedupe_key,
    )
    from bolsa_infrastructure.database.repositories.journal_repository import (
        SqlAlchemyJournalRepository,
    )

    entry = build_cycle_settlement_entry(
        settlement_id=payload.get("settlementId") or f"settle-{cycle_id}",
        instrument_id=payload.get("instrumentId"),
        side=payload.get("side"),
        closed_qty=payload.get("closedQty"),
        pnl=pnl_exact,
        settled_at=payload.get("settledAt"),
        exit_reason=payload.get("exitReason"),
        price_source=payload.get("priceSource"),
        cycle_id=cycle_id,
        actor=engine_id,
        as_of=payload.get("settledAt"),
        account_id=account_id,
        structural=bool(payload.get("structural")),
        # SIN política: es el hecho histórico, byte a byte el del contrato anterior.
        pnl_policy=None,
    )
    assert entry is not None
    legacy_payload = dict(entry.payload)
    legacy_payload["engineId"] = engine_id
    key = durable_fact_dedupe_key(
        event_type=entry.event_type,
        account_id=account_id,
        engine_id=engine_id,
        cycle_id=cycle_id,
    )
    assert key is not None
    from dataclasses import replace

    entry = replace(entry, payload=legacy_payload, dedupe_key=key)
    async with factory() as session:
        await SqlAlchemyJournalRepository(session).append(entry)
        await session.commit()


async def _run_cli(account_id: str, *, apply: bool, cycle_id: str) -> dict[str, Any]:
    """Ejecuta el CLI REAL (su propio engine) contra la BD configurada."""
    cli = _load_cli()
    argv = ["--account-id", account_id, "--cycle-id", cycle_id, "--json"]
    if apply:
        argv.append("--apply")
    return await cli._run(cli._parse_args(argv))


# ── El nodo ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_apply_inserts_one_new_fact_and_keeps_the_historical_one_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],  # noqa: F811 — fixture del arnés
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reemisión append-only e idempotente sobre un ciclo cerrado real."""

    state = await _drive_cycle(identity_pg_factory, monkeypatch, source=_IDENTITY_SOURCE, prefix="inst-v2103-")
    cli = _load_cli()
    try:
        account_id = state["accountId"]
        engine_id = state["engineId"]
        cycle_id = state["cycleId"]

        # (1) El cierre productivo ya dejó el hecho de la política vigente: no se reemite.
        facts = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(facts) == 1, f"el cierre productivo publica UN settlement: {facts}"
        assert facts[0]["payload"].get("pnlPolicy") == CYCLE_PNL_POLICY
        dry = await _run_cli(account_id, apply=False, cycle_id=cycle_id)
        assert dry["counts"][cli.CLASS_VIGENTE] == 1, dry["counts"]
        assert dry["counts"]["toReemit"] == 0, dry["counts"]
        assert dry["applied"] is None, "sin --apply no se escribe nada"

        # (2) Escenario histórico: el hecho de la política vigente se sustituye por el
        #     histórico (PnL exacto del FIFO). Las cifras salen del MISMO productor.
        from bolsa_application.auto_self_evaluation_feed import cycles_from_fills as _cycles

        async with identity_pg_factory() as session:
            fills = await cli._load_cycle_fills(
                session, account_id=account_id, cycle_id=cycle_id
            )
            cycle = next(
                row for row in _cycles(fills) if str(row.get("cycleId")) == cycle_id
            )
        applied_pnl = Decimal(str(cycle["pnl"]))
        exact_pnl = Decimal(str(cycle["pnlExact"]))
        # El residuo PUEDE ser cero en un ciclo cuyos precios ya caen en el quantum (medido en
        # la batería): la reemisión no depende de la diferencia de dinero, sino de que la
        # POLÍTICA del hecho esté declarada. El nodo mide el delta; no lo exige distinto de 0.
        delta_expected = applied_pnl - exact_pnl
        base = facts[0]["payload"]
        await _delete_facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        await _insert_historical_fact(
            identity_pg_factory,
            account_id=account_id,
            engine_id=engine_id,
            cycle_id=cycle_id,
            payload=base,
            pnl_exact=exact_pnl,
        )
        legacy = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(legacy) == 1 and "pnlPolicy" not in legacy[0]["payload"]
        legacy_id = legacy[0]["id"]

        # (3) Dry-run: el ciclo es candidato y el delta se mide contra la cifra superada.
        dry = await _run_cli(account_id, apply=False, cycle_id=cycle_id)
        assert dry["counts"][cli.CLASS_SOLO_LEGACY] == 1, dry["counts"]
        row = next(item for item in dry["rows"] if item["cycleId"] == cycle_id)
        assert Decimal(row["previousPnl"]) == exact_pnl, row
        assert Decimal(row["newPnl"]) == applied_pnl, row
        assert Decimal(row["delta"]) == delta_expected, row
        assert dry["applied"] is None

        # (4) --apply: UN hecho nuevo, y el histórico sigue exactamente donde estaba.
        first = await _run_cli(account_id, apply=True, cycle_id=cycle_id)
        assert first["applied"]["inserted"] == 1, first["applied"]
        after = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(after) == 2, f"el hecho histórico NO se sustituye: {after}"
        historical = [fact for fact in after if "pnlPolicy" not in fact["payload"]]
        current = [fact for fact in after if fact["payload"].get("pnlPolicy") == CYCLE_PNL_POLICY]
        assert len(historical) == 1, after
        assert len(current) == 1, after
        assert historical[0]["id"] == legacy_id, "el histórico sigue siendo la MISMA fila"
        assert current[0]["id"] != legacy_id, "el hecho reemitido es NUEVO, no el anterior reescrito"
        assert Decimal(str(historical[0]["payload"]["pnl"])) == exact_pnl, historical[0]
        assert current[0]["dedupeKey"] is not None
        assert current[0]["dedupeKey"].endswith(f":{CYCLE_PNL_POLICY}"), current[0]["dedupeKey"]
        assert f":{engine_id}:{cycle_id}:" in current[0]["dedupeKey"], (
            "el motor se hereda del histórico: cambiarlo cambiaría la identidad del hecho"
        )
        assert current[0]["payload"].get("engineId") == engine_id, current[0]
        assert Decimal(str(current[0]["payload"]["pnl"])) == applied_pnl, current[0]

        # (5) Reejecutar es un no-op: misma clave ⇒ ``ON CONFLICT DO NOTHING``.
        second = await _run_cli(account_id, apply=True, cycle_id=cycle_id)
        assert second["applied"]["inserted"] == 0, second["applied"]
        assert second["counts"][cli.CLASS_VIGENTE] == 1, second["counts"]
        stable = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(stable) == 2, f"la segunda corrida no duplica: {stable}"
    finally:
        await _teardown(identity_pg_factory, state)


@pytest.mark.asyncio
async def test_the_historical_fact_alone_is_not_a_vigente_cycle_pg(
    identity_pg_factory: async_sessionmaker[AsyncSession],  # noqa: F811 — fixture del arnés
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un ciclo solo con el hecho histórico se declara ``solo_legacy``, nunca ``vigente``.

    Es el criterio que hace útil el CLI: si un hecho sin política contara como vigente, la
    reemisión no tendría nada que hacer y la diferencia de aritmética quedaría invisible.
    """
    state = await _drive_cycle(
        identity_pg_factory, monkeypatch, source=_IDENTITY_SOURCE, prefix="inst-v2103b-"
    )
    cli = _load_cli()
    try:
        account_id = state["accountId"]
        cycle_id = state["cycleId"]
        facts = await _facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        assert len(facts) == 1
        await _delete_facts(identity_pg_factory, account_id=account_id, cycle_id=cycle_id)
        await _insert_historical_fact(
            identity_pg_factory,
            account_id=account_id,
            engine_id=state["engineId"],
            cycle_id=cycle_id,
            payload=facts[0]["payload"],
            pnl_exact=Decimal(str(facts[0]["payload"]["pnl"])),
        )
        dry = await _run_cli(account_id, apply=False, cycle_id=cycle_id)
        assert dry["counts"][cli.CLASS_SOLO_LEGACY] == 1, dry["counts"]
        assert dry["counts"][cli.CLASS_VIGENTE] == 0, dry["counts"]
        row = next(item for item in dry["rows"] if item["cycleId"] == cycle_id)
        assert row["previousPolicy"] == "fifo_exact_v0", row
        assert row["needsReemission"] is True, row
        # Sin delta medible (misma cifra) sigue siendo candidato: la POLÍTICA es lo que
        # falta, no la diferencia de dinero.
        assert row["delta"] == "0.000000", row
    finally:
        await _teardown(identity_pg_factory, state)
