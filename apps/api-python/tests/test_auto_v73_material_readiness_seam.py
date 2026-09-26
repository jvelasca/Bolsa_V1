"""AUTO-MATERIAL-1 (V2.73) — costura del gate ``paper_material_readiness.py``.

Hermético: sin PostgreSQL. El ``_read`` (I/O) se sustituye por un material ya compuesto para
fijar el contrato del CLI: veredicto → códigos de salida (``0`` READY / ``2`` BLOCKED), y la
forma del JSON que consumirá una futura pantalla. El diagnóstico contra la base real vive en la
evidencia de la fase (medición del propietario).
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bolsa_analytics.cognitive.portfolio_reservation import (
    RESERVATION_OPEN,
    SIDE_BUY,
    PortfolioReservation,
)
from bolsa_application.paper_material_readiness import (
    MATERIAL_READINESS_METHOD,
    PaperMaterialReadiness,
    build_paper_material_readiness,
)
from bolsa_application.sim_durable_store import SimFillFinanceContext

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_material_readiness.py"


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("v73_paper_material_readiness", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blocked() -> PaperMaterialReadiness:
    """Material tipo v2.72: 4 fills sin ciclo, sin reservas."""
    fills = [
        SimFillFinanceContext(
            execution_id=f"legacy-{i}",
            instrument_id="AAA",
            side="buy",
            quantity=Decimal("10"),
            price=Decimal("100"),
            account_id="acc-1",
            strategy_version_id="orb-a",
            cycle_id=None,
        )
        for i in range(4)
    ]
    return build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=[],
        min_cycles_per_strategy=3,
    )


def _ready() -> PaperMaterialReadiness:
    fills: list[SimFillFinanceContext] = []
    reservations: list[PortfolioReservation] = []
    for cycle in ("cyc-a", "cyc-b", "cyc-c"):
        for side, price, suffix in (("buy", "100", "buy"), ("sell", "110", "sell")):
            fills.append(
                SimFillFinanceContext(
                    execution_id=f"{cycle}-{suffix}",
                    instrument_id="AAA",
                    side=side,
                    quantity=Decimal("10"),
                    price=Decimal(price),
                    account_id="acc-1",
                    strategy_version_id="orb-a",
                    cycle_id=cycle,
                )
            )
        reservations.append(
            PortfolioReservation(
                reservation_id=f"RES-{cycle}",
                account_id="acc-1",
                instrument_id="AAA",
                side=SIDE_BUY,
                quantity=10.0,
                entry=100.0,
                stop=95.0,
                reserved_cash=1000.0,
                reserved_risk=250.0,
                status=RESERVATION_OPEN,
                created_at="2026-09-26T08:00:00+00:00",
                remaining_qty=10.0,
                cycle_id=cycle,
            )
        )
    return build_paper_material_readiness(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        reservations=reservations,
        min_cycles_per_strategy=3,
    )


def _patch_read(monkeypatch: pytest.MonkeyPatch, module: Any, readiness: PaperMaterialReadiness) -> None:
    async def _read(account_id: str, versions: list[str], *, limit: int, min_cycles: int) -> Any:
        assert account_id == "acc-1"
        assert versions == ["orb-a"]
        return readiness

    monkeypatch.setattr(module, "_read", _read)


def test_a_blocked_material_exits_two_and_names_its_blockers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_cli()
    _patch_read(monkeypatch, module, _blocked())

    code = module.main(["--account-id", "acc-1", "--strategy-version", "orb-a", "--min-cycles", "3"])

    assert code == 2


def test_a_ready_material_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli()
    _patch_read(monkeypatch, module, _ready())

    code = module.main(["--account-id", "acc-1", "--strategy-version", "orb-a", "--min-cycles", "3"])

    assert code == 0


def test_the_json_payload_carries_the_seal_and_the_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_cli()
    _patch_read(monkeypatch, module, _blocked())

    code = module.main(
        ["--account-id", "acc-1", "--strategy-version", "orb-a", "--min-cycles", "3", "--json"]
    )

    assert code == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema"] == MATERIAL_READINESS_METHOD
    assert payload["verdict"] == "BLOCKED"
    assert payload["ready"] is False
    assert "no cycle lineage" in payload["blockers"]


def test_an_empty_strategy_version_is_a_usage_error() -> None:
    module = _load_cli()
    assert module.main(["--account-id", "acc-1", "--strategy-version", " "]) == 1
