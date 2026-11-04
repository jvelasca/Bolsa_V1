"""P2 (auditoría TRADING/AUTO .183) — el router resuelve lo que el gate exige.

El Policy Gate se cerró en P2: una regla activa sin dato veta con
``<Regla>_unmeasured``. Eso solo es útil si el camino ``paper_auto`` —el que decide
aperturas— le entrega de verdad las métricas. Hoy no lo hacía: ``check_opening`` se
llamaba sin ``market_cap_usd``, sin ``average_daily_volume_usd`` y sin ``sector``, así
que ``MinMarketCap``/``MinADV``/``MaxSectorExposure`` no se evaluaban nunca.

Este test fija las dos mitades:

* ``_resolve_policy_measurements`` saca market cap (``get_fundamentals.marketCap``),
  ADV y sector (``InstrumentTradeContext``) del catálogo, y NO inventa nada;
* el veredicto de ``check_opening`` cambia según el dato esté o falte, con el motivo de
  la regla en el veto.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bolsa_analytics.cognitive.portfolio_fit import BasketPosition
from bolsa_application.execution_router import ExecutionRouter
from bolsa_application.risk_engine import check_opening


@dataclass(frozen=True, slots=True)
class _Ctx:
    sector: str | None
    adv_usd: float | None
    observed_at: str | None = None


class _FakeInstrumentRepo:
    def __init__(
        self,
        *,
        contexts: dict[str, _Ctx] | None = None,
        fundamentals: dict[str, dict[str, float]] | None = None,
        raise_on_contexts: bool = False,
    ) -> None:
        self._contexts = contexts or {}
        self._fundamentals = fundamentals or {}
        self._raise = raise_on_contexts

    async def list_trade_context_by_ids(self, ids: list[str]) -> dict[str, _Ctx]:
        if self._raise:
            raise RuntimeError("catálogo ilegible")
        return {i: self._contexts[i] for i in ids if i in self._contexts}

    async def get_fundamentals(self, instrument_id: str) -> dict[str, float] | None:
        return self._fundamentals.get(instrument_id)


def _router_with(repo: object | None) -> ExecutionRouter:
    """Router sin composición completa: aquí solo se prueba la resolución de métricas."""
    router = object.__new__(ExecutionRouter)
    object.__setattr__(router, "_instrument_repo", repo)
    return router


@pytest.mark.asyncio
async def test_the_catalog_supplies_market_cap_adv_and_sector() -> None:
    repo = _FakeInstrumentRepo(
        contexts={"inst-aapl": _Ctx(sector="technology", adv_usd=1.5e9)},
        fundamentals={"inst-aapl": {"marketCap": 3e12}},
    )
    market_cap, adv, sector, denial = await _router_with(repo)._resolve_policy_measurements(
        "inst-aapl"
    )
    assert denial is None
    assert market_cap == 3e12
    assert adv == 1.5e9
    assert sector == "technology"


@pytest.mark.asyncio
async def test_absent_catalog_data_stays_absent() -> None:
    """Sin contexto ni fundamentales no se inventa: el gate decide con ``None``."""
    repo = _FakeInstrumentRepo()
    market_cap, adv, sector, denial = await _router_with(repo)._resolve_policy_measurements(
        "inst-aapl"
    )
    assert denial is None
    assert (market_cap, adv, sector) == (None, None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["nan", "inf", -1.0, 0.0, True, "abc"])
async def test_non_finite_or_non_positive_metrics_are_rejected(bad: object) -> None:
    """P9 se adelanta aquí: ``NaN``/``inf`` no son mediciones."""
    repo = _FakeInstrumentRepo(
        contexts={"inst-aapl": _Ctx(sector="technology", adv_usd=bad)},  # type: ignore[arg-type]
        fundamentals={"inst-aapl": {"marketCap": bad}},  # type: ignore[dict-item]
    )
    market_cap, adv, _, denial = await _router_with(repo)._resolve_policy_measurements(
        "inst-aapl"
    )
    assert denial is None
    assert market_cap is None
    assert adv is None


@pytest.mark.asyncio
async def test_a_broken_catalog_denies_instead_of_deciding_blind() -> None:
    repo = _FakeInstrumentRepo(raise_on_contexts=True)
    _, _, _, denial = await _router_with(repo)._resolve_policy_measurements("inst-aapl")
    assert denial == "policy_metrics:trade_context_lookup_failed"


@pytest.mark.asyncio
async def test_without_repository_the_denial_names_the_composition() -> None:
    _, _, _, denial = await _router_with(None)._resolve_policy_measurements("inst-aapl")
    assert denial == "policy_metrics:instrument_repo_missing"


def _opening_kwargs(**overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = dict(
        profile=None,  # ⇒ plantilla moderate
        instrument_id="inst-aapl",
        symbol="AAPL",
        trade_type="buy",
        quantity=10.0,
        price=150.0,
        signal_kind="entry_long",
        equity=100_000.0,
        open_positions_count=1,
        kill_switch=False,
        portfolio_positions=[
            BasketPosition(instrument_id="inst-msft", market_value=5_000.0, sector="technology")
        ],
        account_daily_drawdown_pct=0.0,
        account_weekly_drawdown_pct=0.0,
        account_max_drawdown_pct=0.0,
    )
    kwargs.update(overrides)
    return kwargs


def test_a_measured_opening_passes() -> None:
    decision = check_opening(
        **{
            **_opening_kwargs(),
            "market_cap_usd": 3e12,
            "average_daily_volume_usd": 1.5e9,
            "sector": "technology",
        },  # type: ignore[arg-type]
    )
    assert decision.verdict == "ALLOW", decision.reasons


def test_an_unmeasured_opening_is_denied_with_the_rule_name() -> None:
    decision = check_opening(
        **{
            **_opening_kwargs(),
            "market_cap_usd": 3e12,
            # ADV ausente: la plantilla moderate exige 5M USD y no hay medición.
            "average_daily_volume_usd": None,
            "sector": "technology",
        },  # type: ignore[arg-type]
    )
    assert decision.verdict == "DENY"
    assert "MinADV_unmeasured" in decision.reasons


def test_a_missing_sector_does_not_silently_skip_the_exposure_rule() -> None:
    """Sin sector el agregado por sector no es medible: veto, no ``SKIPPED``."""
    decision = check_opening(
        **{
            **_opening_kwargs(),
            "market_cap_usd": 3e12,
            "average_daily_volume_usd": 1.5e9,
            "sector": None,
            "portfolio_positions": None,  # sin cesta no hay encaje que medir
        },  # type: ignore[arg-type]
    )
    assert decision.verdict == "DENY"
    assert any("MaxSectorExposure" in reason for reason in decision.reasons)
