"""Dictamen diario on-demand: medición en SERVIDOR y caché por cuenta (migración 067).

Falsables cubiertos:
- el servidor mide posición y scores (el cliente ya no manda hints);
- ``position_open=None`` ⇒ dictamen transitorio, ``position_unmeasured`` y NO se cachea;
- la posición intra-día invalida la caché (misma cuenta);
- dos cuentas no comparten postura el mismo día;
- ``has_eod_bar`` se valida barra a barra (no se acepta del cliente);
- los hints internos (jobs de servidor) siguen siendo confiables.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_application.daily_opinion_hints import (
    COMPOSITE_CHUNK,
    FUNDAMENTALS_CHUNK,
    OpinionHint,
    measure_opinion_hints,
)
from bolsa_application.daily_opinion_service import SOURCE_ON_DEMAND, DailyOpinionService
from bolsa_infrastructure.database.repositories.instrument_daily_opinion_repository import (
    InstrumentDailyOpinionRecord,
    account_scope_for,
)

AS_OF = date(2026, 11, 10)
NOW = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
ACCOUNT = "acc-1"


class FakeOpinionRepo:
    """Caché en memoria con el mismo contrato que el repo SQL (scope por cuenta)."""

    def __init__(self) -> None:
        self.upserts: list[dict[str, Any]] = []
        self.rows: dict[tuple[str, date, str, str], InstrumentDailyOpinionRecord] = {}

    async def list_for_instruments(
        self,
        instrument_ids: list[str],
        as_of: date,
        source: str = "on_demand",
        *,
        account_scope: str = "__global__",
    ) -> list[InstrumentDailyOpinionRecord]:
        scope = account_scope_for(account_scope)
        wanted = set(instrument_ids)
        return [
            row
            for (iid, day, src, sc), row in self.rows.items()
            if iid in wanted and day == as_of and src == source and sc == scope
        ]

    async def list_history(
        self,
        instrument_id: str,
        *,
        date_from: date,
        date_to: date,
        source: str = "on_demand",
        account_scope: str = "__global__",
    ) -> list[InstrumentDailyOpinionRecord]:
        scope = account_scope_for(account_scope)
        rows = [
            (day, row)
            for (iid, day, src, sc), row in self.rows.items()
            if iid == instrument_id
            and src == source
            and sc == scope
            and date_from <= day <= date_to
        ]
        return [row for _, row in sorted(rows, key=lambda item: item[0])]

    async def upsert(self, payload: dict[str, Any]) -> InstrumentDailyOpinionRecord:
        self.upserts.append(dict(payload))
        scope = str(payload.get("account_scope") or account_scope_for(payload.get("account_id")))
        record = InstrumentDailyOpinionRecord(
            id=f"ido_{len(self.upserts)}",
            instrument_id=str(payload["instrument_id"]),
            account_id=payload.get("account_id"),
            as_of_bar_date=payload["as_of_bar_date"],
            stance=str(payload["stance"]),
            dictamen_stars=int(payload["dictamen_stars"]),
            strategy_stars=payload.get("strategy_stars"),
            io_score=payload.get("io_score"),
            fa_score=payload.get("fa_score"),
            ta_score=payload.get("ta_score"),
            distress=bool(payload.get("distress") or False),
            reasons=list(payload.get("reasons") or []),
            gate_status=payload.get("gate_status"),
            top_id=payload.get("top_id"),
            top_version=payload.get("top_version"),
            source=str(payload.get("source") or "on_demand"),
            engine_version=str(payload.get("engine_version") or "opinion_v1"),
            idempotency_key=str(payload.get("idempotency_key") or ""),
            computed_at=payload.get("computed_at") or NOW,
            created_at=NOW,
            updated_at=NOW,
            position_open=payload.get("position_open"),
        )
        key = (record.instrument_id, record.as_of_bar_date, record.source, scope)
        self.rows[key] = record
        return record


class FakeTopRepo:
    """TOP con un finalista de 4★ fresco (permite posturas de posición)."""

    def __init__(self, stars: float = 4.0) -> None:
        self._stars = stars

    async def get(self, instrument_id: str, timeframe: str) -> Any:
        return SimpleNamespace(
            id=f"top_{instrument_id}",
            version=1,
            updated_at=NOW,
            slots=[{"rank": 1, "stars": self._stars}],
        )


class FakeOhlcv:
    def __init__(self, bar_dates: list[date] | None = None) -> None:
        self._bar_dates = [AS_OF] if bar_dates is None else bar_dates

    async def get_bars(
        self,
        instrument_id: str,
        *,
        timeframe: Any,
        limit: int,
        date_to: str,
    ) -> list[Any]:
        return [
            SimpleNamespace(timestamp=day.isoformat())
            for day in self._bar_dates
            if day.isoformat() <= date_to
        ]


class FakeComposite:
    def __init__(self, io: float | None = 85.0) -> None:
        self.io = io
        self.calls: list[list[str]] = []

    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 40,
        horizon: str = "swing",
        regime: str = "neutral",
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(list(instrument_ids))
        return [
            {
                "instrumentId": iid,
                "indiceOperativo": self.io,
                "technicalDisplay100": 60.0,
            }
            for iid in instrument_ids
        ]


class FakeFundamentals:
    """Chips FA; ``calls`` fija QUE ids se piden (solo los ``miss_ids``)."""

    def __init__(self, distress: bool = False) -> None:
        self.distress = distress
        self.calls: list[list[str]] = []

    async def execute_chips(
        self,
        instrument_ids: list[str],
        *,
        max_ids: int = 80,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append(list(instrument_ids))
        return [
            {"instrumentId": iid, "scoreDisplay100": 70.0, "distress": self.distress}
            for iid in instrument_ids
        ]


class FakePositions:
    """Posiciones abiertas por cuenta; ``fail=True`` simula la lectura caída."""

    def __init__(
        self,
        by_account: dict[str, set[str]] | None = None,
        *,
        fail: bool = False,
    ) -> None:
        self.by_account = by_account or {}
        self.fail = fail
        self.calls: list[str] = []

    async def list_open_for_account(self, account_id: str) -> list[Any]:
        self.calls.append(account_id)
        if self.fail:
            raise RuntimeError("portfolio unavailable")
        return [
            SimpleNamespace(instrument_id=iid)
            for iid in sorted(self.by_account.get(account_id, set()))
        ]


def build_service(
    *,
    repo: FakeOpinionRepo | None = None,
    composite: Any | None = None,
    fundamentals: Any | None = None,
    positions: Any | None = None,
    ohlcv: Any | None = None,
) -> tuple[DailyOpinionService, FakeOpinionRepo]:
    opinion_repo = repo or FakeOpinionRepo()
    service = DailyOpinionService(
        opinion_repo,  # type: ignore[arg-type]
        FakeTopRepo(),  # type: ignore[arg-type]
        (ohlcv or FakeOhlcv()),  # type: ignore[arg-type]
        None,
        composite=composite,
        fundamentals=fundamentals,
        positions=positions,
    )
    return service, opinion_repo


@pytest.mark.asyncio
async def test_query_measures_scores_and_position_in_server() -> None:
    composite = FakeComposite(io=85.0)
    fundamentals = FakeFundamentals()
    positions = FakePositions({ACCOUNT: {"inst-1"}})
    service, repo = build_service(
        composite=composite,
        fundamentals=fundamentals,
        positions=positions,
    )

    rows = await service.query(
        instrument_ids=["inst-1", "inst-2"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    assert len(rows) == 2
    held, free = rows
    assert held.instrument_id == "inst-1"
    assert held.io_score == 85.0
    assert held.fa_score == 70.0
    assert held.position_open is True
    # Con posición y señal fuerte: mantener (el motor es long-only).
    assert held.stance == "hold_watch"
    # Misma señal sin posición: compra.
    assert free.position_open is False
    assert free.stance == "buy"
    assert composite.calls == [["inst-1", "inst-2"]]
    # (1) La cartera se mide UNA sola vez aunque la consulta lleve dos instrumentos.
    assert positions.calls == [ACCOUNT]
    # (2) Los chips FA se piden una vez por consulta y para TODOS los ids (todos son miss).
    assert fundamentals.calls == [["inst-1", "inst-2"]]
    # Persistido en el scope de la cuenta, no en el global.
    assert {u["account_scope"] for u in repo.upserts} == {account_scope_for(ACCOUNT)}
    assert repo.upserts[0]["idempotency_key"].endswith(f"|{ACCOUNT}")


@pytest.mark.asyncio
async def test_unmeasured_portfolio_is_transient_and_never_cached() -> None:
    service, repo = build_service(
        composite=FakeComposite(),
        fundamentals=FakeFundamentals(),
        positions=FakePositions(fail=True),
    )

    rows = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    assert rows[0].id.startswith("ido_tmp_")
    assert rows[0].position_open is None
    assert rows[0].stance == "no_trade"
    assert "position_unmeasured" in rows[0].reasons
    assert repo.upserts == []

    # Con la cartera ya medida, la siguiente llamada sí cachea.
    measured, measured_repo = build_service(
        composite=FakeComposite(),
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: set()}),
    )
    await measured.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert len(measured_repo.upserts) == 1
    assert measured_repo.upserts[0]["position_open"] is False


@pytest.mark.asyncio
async def test_position_change_intraday_recomputes_and_updates_cache() -> None:
    positions = FakePositions({ACCOUNT: {"inst-1"}})
    service, repo = build_service(
        composite=FakeComposite(io=20.0),
        fundamentals=FakeFundamentals(),
        positions=positions,
    )

    first = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert first[0].stance == "sell_exit"
    assert first[0].position_open is True
    assert len(repo.upserts) == 1

    # Misma posición ⇒ se sirve la caché (sin upsert extra).
    cached = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert cached[0].id == first[0].id
    assert len(repo.upserts) == 1

    # Posición cerrada intra-día ⇒ la caché no sirve: se recalcula.
    positions.by_account[ACCOUNT] = set()
    after_close = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert after_close[0].position_open is False
    assert after_close[0].stance != "sell_exit"
    assert len(repo.upserts) == 2


@pytest.mark.asyncio
async def test_accounts_do_not_share_the_same_day_row() -> None:
    positions = FakePositions({"acc-a": {"inst-1"}, "acc-b": set()})
    service, repo = build_service(
        composite=FakeComposite(io=20.0),
        fundamentals=FakeFundamentals(),
        positions=positions,
    )

    row_a = (
        await service.query(
            instrument_ids=["inst-1"],
            as_of_bar_date=AS_OF,
            account_id="acc-a",
            now=NOW,
        )
    )[0]
    row_b = (
        await service.query(
            instrument_ids=["inst-1"],
            as_of_bar_date=AS_OF,
            account_id="acc-b",
            now=NOW,
        )
    )[0]

    assert row_a.stance == "sell_exit"
    assert row_b.stance != "sell_exit"
    assert row_a.position_open is True
    assert row_b.position_open is False
    assert {u["account_scope"] for u in repo.upserts} == {"acc-a", "acc-b"}


@pytest.mark.asyncio
async def test_has_eod_bar_is_validated_per_bar_not_trusted_from_the_client() -> None:
    # Sin barra EOD ⇒ fail-closed incluso con señal fuerte.
    no_bar_service, _ = build_service(
        composite=FakeComposite(io=90.0),
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: {"inst-1"}}),
        ohlcv=FakeOhlcv(bar_dates=[]),
    )
    stale = await no_bar_service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert stale[0].stance == "no_trade"
    assert "eod_data_stale" in stale[0].reasons

    # Barra de hace 10 días ⇒ igualmente stale (no basta con que exista una barra).
    old_bar_service, _ = build_service(
        composite=FakeComposite(io=90.0),
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: {"inst-1"}}),
        ohlcv=FakeOhlcv(bar_dates=[date(2026, 10, 31)]),
    )
    too_old = await old_bar_service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert "eod_data_stale" in too_old[0].reasons


@pytest.mark.asyncio
async def test_internal_server_hints_are_trusted_and_skip_measurement() -> None:
    composite = FakeComposite(io=85.0)
    service, repo = build_service(
        composite=composite,
        fundamentals=FakeFundamentals(),
        positions=None,
    )

    rows = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
        hints=[
            OpinionHint(
                instrument_id="inst-1",
                io_score=20.0,
                position_open=True,
                has_eod_bar=True,
            )
        ],
    )

    assert composite.calls == []
    assert rows[0].io_score == 20.0
    assert rows[0].stance == "sell_exit"
    assert len(repo.upserts) == 1


@pytest.mark.asyncio
async def test_internal_hints_skip_position_read_even_when_port_is_injected() -> None:
    """(1) Con hints internos para TODOS los ids no se lee la cartera.

    Antes el escenario solo se cubría con ``positions=None`` (ausencia de adaptador), que
    no distingue «no hay puerto» de «hay puerto y no se consulta». Aquí el puerto EXISTE y
    el contador demuestra que el servicio no lo toca: la posición ya viene del job.
    """
    composite = FakeComposite(io=85.0)
    fundamentals = FakeFundamentals()
    positions = FakePositions({ACCOUNT: {"inst-1"}})
    service, repo = build_service(
        composite=composite,
        fundamentals=fundamentals,
        positions=positions,
    )

    rows = await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
        hints=[
            OpinionHint(
                instrument_id="inst-1",
                io_score=20.0,
                position_open=True,
                has_eod_bar=True,
            )
        ],
    )

    assert positions.calls == []
    assert composite.calls == []
    assert fundamentals.calls == []
    assert rows[0].position_open is True
    assert len(repo.upserts) == 1


@pytest.mark.asyncio
async def test_chunking_of_miss_ids_does_not_multiply_portfolio_reads() -> None:
    """(3) 81 miss ids ⇒ composite en 3 trozos (40+40+1) y FA en 2 (80+1).

    El troceo es de los CHIPS: la cartera se sigue midiendo una sola vez por consulta y
    cada id se pide exactamente una vez, sin duplicados entre trozos.
    """
    ids = [f"inst-{index:03d}" for index in range(81)]
    composite = FakeComposite(io=85.0)
    fundamentals = FakeFundamentals()
    positions = FakePositions({ACCOUNT: set()})
    service, repo = build_service(
        composite=composite,
        fundamentals=fundamentals,
        positions=positions,
    )

    rows = await service.query(
        instrument_ids=ids,
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    # Valores reales de los trozos declarados en daily_opinion_hints (no supuestos).
    assert COMPOSITE_CHUNK == 40
    assert FUNDAMENTALS_CHUNK == 80
    assert [len(call) for call in composite.calls] == [40, 40, 1]
    assert [len(call) for call in fundamentals.calls] == [80, 1]
    # Ningún id se repite ni se pierde al trocear.
    assert [iid for call in composite.calls for iid in call] == ids
    assert [iid for call in fundamentals.calls for iid in call] == ids
    assert positions.calls == [ACCOUNT]
    assert len(rows) == 81
    assert len(repo.upserts) == 81


@pytest.mark.asyncio
async def test_measure_hints_keeps_position_tristate() -> None:
    failed = await measure_opinion_hints(
        ["inst-1"],
        account_id=ACCOUNT,
        positions=FakePositions(fail=True),
        as_of=AS_OF.isoformat(),
    )
    assert failed.positions_measured is False
    hint = failed.hint_for("inst-1")
    assert hint.position_open is None
    assert hint.has_eod_bar is None
    assert hint.allow_trading is True
    assert "positions_unavailable" in failed.notes

    # Sin cuenta no hay cartera que medir: tampoco se inventa «sin posición».
    no_account = await measure_opinion_hints(
        ["inst-1"],
        account_id=None,
        positions=FakePositions({ACCOUNT: {"inst-1"}}),
        as_of=AS_OF.isoformat(),
    )
    assert no_account.positions_measured is False
    assert no_account.hint_for("inst-1").position_open is None

    measured = await measure_opinion_hints(
        ["inst-1"],
        account_id=ACCOUNT,
        composite=FakeComposite(io=72.0),
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: {"inst-1"}}),
        as_of=AS_OF.isoformat(),
    )
    assert measured.positions_measured is True
    assert measured.hint_for("inst-1").position_open is True
    assert measured.hint_for("inst-1").io_score == 72.0
    assert measured.notes == []


@pytest.mark.asyncio
async def test_cached_rows_do_not_measure_chips_again() -> None:
    """H-2: con la caché válida no se pagan composite/fundamentales."""
    composite = FakeComposite(io=85.0)
    positions = FakePositions({ACCOUNT: {"inst-1"}})
    service, repo = build_service(
        composite=composite,
        fundamentals=FakeFundamentals(),
        positions=positions,
    )

    first = await service.query(
        instrument_ids=["inst-1", "inst-2"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert composite.calls == [["inst-1", "inst-2"]]
    assert len(repo.upserts) == 2

    second = await service.query(
        instrument_ids=["inst-1", "inst-2"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    # Sin chips nuevos y sin upserts: ambas filas se sirven de la caché.
    assert composite.calls == [["inst-1", "inst-2"]]
    assert len(repo.upserts) == 2
    assert [row.id for row in second] == [row.id for row in first]
    # La cartera se mide una vez por consulta, no una por instrumento.
    assert positions.calls == [ACCOUNT, ACCOUNT]


@pytest.mark.asyncio
async def test_only_miss_ids_are_measured_for_chips() -> None:
    composite = FakeComposite(io=85.0)
    fundamentals = FakeFundamentals()
    positions = FakePositions({ACCOUNT: set()})
    service, repo = build_service(
        composite=composite,
        fundamentals=fundamentals,
        positions=positions,
    )

    await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert len(repo.upserts) == 1

    # inst-1 sigue cacheado con la misma posición; inst-2 es nuevo.
    await service.query(
        instrument_ids=["inst-1", "inst-2"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    assert composite.calls == [["inst-1"], ["inst-2"]]
    # (2) Composite y FA reciben SOLO el miss de cada consulta, nunca el id cacheado.
    assert fundamentals.calls == [["inst-1"], ["inst-2"]]
    # (1) Dos consultas ⇒ dos lecturas de cartera (una por consulta, no una por id).
    assert positions.calls == [ACCOUNT, ACCOUNT]
    assert len(repo.upserts) == 2


@pytest.mark.asyncio
async def test_force_refresh_measures_every_id_again() -> None:
    composite = FakeComposite(io=85.0)
    service, repo = build_service(
        composite=composite,
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: set()}),
    )

    await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    await service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
        force_refresh=True,
    )

    assert composite.calls == [["inst-1"], ["inst-1"]]
    assert len(repo.upserts) == 2


@pytest.mark.asyncio
async def test_unmeasured_portfolio_is_never_served_from_cache() -> None:
    """Una fila cacheada con posición medida NO se sirve si la cartera no se puede leer."""
    repo = FakeOpinionRepo()
    cached_service, _ = build_service(
        repo=repo,
        composite=FakeComposite(io=85.0),
        fundamentals=FakeFundamentals(),
        positions=FakePositions({ACCOUNT: set()}),
    )
    await cached_service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )
    assert repo.upserts[0]["position_open"] is False

    blind_service, _ = build_service(
        repo=repo,
        composite=FakeComposite(io=85.0),
        fundamentals=FakeFundamentals(),
        positions=FakePositions(fail=True),
    )
    rows = await blind_service.query(
        instrument_ids=["inst-1"],
        as_of_bar_date=AS_OF,
        account_id=ACCOUNT,
        now=NOW,
    )

    assert rows[0].id.startswith("ido_tmp_")
    assert rows[0].position_open is None
    assert "position_unmeasured" in rows[0].reasons
    # No se sobrescribe la caché con una medición no verificable.
    assert len(repo.upserts) == 1


@pytest.mark.asyncio
async def test_history_ensure_days_does_not_invent_unmeasured_days() -> None:
    service, repo = build_service(
        composite=FakeComposite(),
        fundamentals=FakeFundamentals(),
        positions=FakePositions(fail=True),
    )

    rows = await service.history("inst-1", days=5, ensure_days=3, account_id=ACCOUNT)

    assert rows == []
    assert repo.upserts == []
    assert SOURCE_ON_DEMAND == "on_demand"
