"""AUTO-20B — manifest del material: los conteos son del MISMO material que el instrumento.

El manifest no mide nada nuevo: cuenta y declara lo que entra al calibrador, para que se pueda
auditar que el universo es el que se cree. Estos tests certifican que los conteos se derivan de
las filas de ``adaptive_instrument_cycles`` (sin un segundo FIFO) y que los huecos se declaran
en vez de colapsarse en el total.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from bolsa_analytics.cognitive.auto_material_manifest import material_fingerprint
from bolsa_application.auto_material_manifest import (
    MATERIAL_RISK_BASIS,
    build_material_manifest,
)
from bolsa_application.auto_self_evaluation_feed import adaptive_instrument_cycles
from bolsa_application.cycle_risk import CycleRisk
from bolsa_application.sim_durable_store import SimFillFinanceContext

_AT = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)


def _fill(
    side: str,
    qty: str,
    price: str,
    *,
    execution_id: str,
    cycle_id: str,
    version: str = "orb-a",
    reference_mid: str | None = None,
) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        reference_mid=None if reference_mid is None else Decimal(reference_mid),
        strategy_version_id=version,
        cycle_id=cycle_id,
        created_at=_AT,
    )


def _round_trip(
    cycle_id: str,
    *,
    version: str = "orb-a",
    sell_version: str | None = None,
    reference: bool = False,
) -> list[SimFillFinanceContext]:
    reference_buy = "99.9" if reference else None
    reference_sell = "110.1" if reference else None
    return [
        _fill(
            "buy",
            "10",
            "100",
            execution_id=f"{cycle_id}-buy",
            cycle_id=cycle_id,
            version=version,
            reference_mid=reference_buy,
        ),
        _fill(
            "sell",
            "10",
            "110",
            execution_id=f"{cycle_id}-sell",
            cycle_id=cycle_id,
            version=sell_version or version,
            reference_mid=reference_sell,
        ),
    ]


def _fixture() -> tuple[list[SimFillFinanceContext], dict[str, CycleRisk]]:
    """A parcial (3/4 con riesgo), B completa (2/2), C sin riesgo (0/1), U sin versión."""
    fills = [
        *_round_trip("cyc-a1", reference=True),
        *_round_trip("cyc-a2"),
        *_round_trip("cyc-a3"),
        *_round_trip("cyc-a4"),
        *_round_trip("cyc-b1", version="orb-b", reference=True),
        *_round_trip("cyc-b2", version="orb-b"),
        *_round_trip("cyc-c1", version="orb-c"),
        # Ciclo con DOS versiones distintas en sus fills: queda SIN versión (atribución rota).
        *_round_trip("cyc-u1", version="orb-a", sell_version="orb-b"),
    ]
    risk = {
        cycle_id: CycleRisk(cycle_id=cycle_id, risk_amount=Decimal("10"))
        for cycle_id in ("cyc-a1", "cyc-a2", "cyc-a3", "cyc-b1", "cyc-b2")
    }
    return fills, risk


def test_the_manifest_counts_the_same_material_the_instrument_carries() -> None:
    fills, risk = _fixture()
    cycles = adaptive_instrument_cycles(fills, risk)

    manifest = build_material_manifest(
        account_id="acc-1",
        requested_versions=["orb-a", "orb-b", "orb-c"],
        fills=fills,
        cycles=cycles,
        reservations_read=10,
        risk_read_saturated=False,
        export_timestamp="2026-09-24T10:00:00Z",
        regime_confirmed=5,
        regime_absent=3,
    )

    assert manifest["closedCycles"] == len(cycles) == 8, "sin un segundo FIFO"
    assert manifest["fillsRead"] == len(fills) == 16
    assert manifest["cyclesWithRisk"] == 5
    assert manifest["cyclesWithoutRisk"] == 3
    assert manifest["cyclesWithoutVersion"] == 1, "el ciclo de dos versiones queda sin versión"
    assert manifest["cyclesWithVersion"] == 7
    assert manifest["costAppliedCycles"] == 2, "a1 y b1 tienen referencia en sus dos patas"
    assert manifest["reservationsRead"] == 10
    assert manifest["riskReadSaturated"] is False
    assert manifest["riskBasis"] == MATERIAL_RISK_BASIS
    assert manifest["regimeRead"] == {
        "confirmed": 5,
        "absent": 3,
        "unconfirmed": 0,
        "notDerivable": 0,
    }
    assert manifest["cyclesWithoutRegime"] == 3


def test_the_manifest_partitions_by_version_without_contaminating() -> None:
    """Cada versión declara sus propios ciclos: A parcial, B completa, C sin riesgo."""
    fills, risk = _fixture()
    manifest = build_material_manifest(
        account_id="acc-1",
        requested_versions=["orb-a", "orb-b", "orb-c"],
        fills=fills,
        cycles=adaptive_instrument_cycles(fills, risk),
        reservations_read=0,
        risk_read_saturated=False,
        export_timestamp="2026-09-24T10:00:00Z",
    )

    assert manifest["perVersion"]["orb-a"] == {"cycles": 4, "withRisk": 3, "withoutRisk": 1}
    assert manifest["perVersion"]["orb-b"] == {"cycles": 2, "withRisk": 2, "withoutRisk": 0}
    assert manifest["perVersion"]["orb-c"] == {"cycles": 1, "withRisk": 0, "withoutRisk": 1}
    assert "" not in manifest["perVersion"], "las filas sin versión no se reparten"


def test_the_manifest_fingerprint_is_the_instrument_material_fingerprint() -> None:
    """La huella del manifest es la del material que mide el instrumento (no una copia)."""
    fills, risk = _fixture()
    cycles = adaptive_instrument_cycles(fills, risk)

    manifest = build_material_manifest(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        cycles=cycles,
        reservations_read=0,
        risk_read_saturated=False,
        export_timestamp="2026-09-24T10:00:00Z",
    )

    assert manifest["fingerprint"] == material_fingerprint(cycles)
    assert manifest["fingerprintMethod"] == "material_fingerprint_v1"
    assert manifest["exportTimestamp"] == "2026-09-24T10:00:00Z"


def test_the_manifest_declares_the_identity_gap() -> None:
    """Un ciclo legado sin ``cycleId`` entra al total pero se cuenta como hueco de identidad."""
    fills = [
        _fill("buy", "10", "100", execution_id="f1", cycle_id="cyc-x"),
        _fill("sell", "10", "110", execution_id="f2", cycle_id="cyc-x"),
    ]
    cycles = adaptive_instrument_cycles(fills, None)
    # Simula una fila legada sin identidad (la produce el pareo FIFO de los fills pre-2.47).
    legacy = dict(cycles[0])
    legacy.pop("cycleId")

    manifest = build_material_manifest(
        account_id="acc-1",
        requested_versions=["orb-a"],
        fills=fills,
        cycles=[legacy],
        reservations_read=0,
        risk_read_saturated=False,
        export_timestamp="2026-09-24T10:00:00Z",
    )

    assert manifest["closedCycles"] == 1
    assert manifest["cyclesWithoutIdentity"] == 1
