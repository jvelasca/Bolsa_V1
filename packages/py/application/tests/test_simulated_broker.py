"""V2.21 / A8 (M3) — SimulatedBroker determinista (semántica delta_per_fill_seq).

Invariantes del contrato P2-03:
* cantidad del evento = DELTA de ESE fill_seq (40+30+30=100), nunca acumulado.
* ``execution_id`` = f"{venue_order_id}#{fill_seq}" (idempotencia financiera).
* Determinismo: misma seed → idéntico resultado (free RNG global).
* Fail-safe: la suma de deltas nunca supera la cantidad pedida.
"""

from __future__ import annotations

from decimal import Decimal

from bolsa_application.simulated_broker import (
    SimulatedOrderResult,
    simulated_fill_schedule,
)

_Q = Decimal("100.000000")


def _run(seed: int, *, qty: str = "100", venue_order_id: str = "sim-a") -> SimulatedOrderResult:
    return simulated_fill_schedule(
        instrument_id="AAA",
        side="buy",
        quantity=Decimal(qty),
        venue_order_id=venue_order_id,
        seed=seed,
        fill_chunks=3,
    )


def test_deterministic_same_seed_identical() -> None:
    a = _run(1234)
    b = _run(1234)
    assert a == b
    # seed distinto → normalmente distinto (no exigimos garantía, solo no-excepción).
    _ = _run(9999)


def test_partial_delta_semantics_40_30_30() -> None:
    """Caso de libro: deltas por fill_seq que reconstruyen por SUMA al total."""
    res = _run(7)
    qsum = sum((f.qty_delta for f in res.fills), Decimal("0"))
    assert qsum <= _Q
    ids = [(f.fill_seq, f.execution_id) for f in res.fills]
    seqs = [s for s, _i in ids]
    assert seqs == sorted(seqs)
    if res.status == "filled":
        # full fill: suma de deltas == quantity y cumulative == quantity.
        assert qsum == _Q
        assert res.cumulative_filled_quantity == _Q
        assert len(res.fills) == 3
        for i, f in enumerate(res.fills, start=1):
            assert f.execution_id == "sim-a#" + str(i)
            assert f.fill_seq == i
    else:
        # partial: menos del total llenado, nunca más.
        assert qsum < _Q
        assert res.status == "partial"
    assert res.cumulative_filled_quantity == qsum


def test_sweep_never_overfilled_and_deterministic() -> None:
    """Property sweep: para una batería de seeds nunca se sobre-llena; deltas > 0;
    q por SEQ no acumula; cumulative == suma de deltas."""
    for seed in range(50, 150, 3):
        res = simulated_fill_schedule(
            instrument_id="AAA",
            side="buy",
            quantity=_Q,
            venue_order_id="sim-sweep",
            seed=seed,
            fill_chunks=3,
        )
        # Determinismo intrapaso: recomputamos la misma seed y debe ser idéntico.
        again = simulated_fill_schedule(
            instrument_id="AAA",
            side="buy",
            quantity=_Q,
            venue_order_id="sim-sweep",
            seed=seed,
            fill_chunks=3,
        )
        assert again == res
        total_filled = sum((f.qty_delta for f in res.fills), Decimal("0"))
        if res.fills:
            assert all(f.qty_delta > 0 for f in res.fills)
            assert total_filled <= _Q
            assert total_filled > 0
            if res.status == "filled":
                assert total_filled == _Q
            assert len({f.fill_seq for f in res.fills}) == len(res.fills)  # únicos.
        assert res.cumulative_filled_quantity == total_filled


def test_finds_full_fill_and_partial_and_terminal_noise_in_deterministic_sweep() -> None:
    """En la batería determinista deben convivir: un full fill, un partial y un
    terminal noisy (reject/timeout/unknown) con cero delta."""
    saw_full = saw_partial = saw_noisy = False
    qty = Decimal("100")
    for seed in range(1, 400):
        res = simulated_fill_schedule(
            instrument_id="AAA",
            side="sell" if seed % 2 else "buy",
            quantity=qty,
            venue_order_id=f"sim-sweep-{seed}",
            seed=seed,
            fill_chunks=3,
        )
        if res.status == "filled":
            saw_full = True
            assert res.cumulative_filled_quantity == qty
            assert len(res.fills) == 3
        elif res.status == "partial":
            saw_partial = True
            assert 0 < res.cumulative_filled_quantity < qty
        elif res.status in {"rejected", "unknown"}:
            saw_noisy = True
            assert res.fills == ()
            assert res.cumulative_filled_quantity == 0
    # Propiedades que la simulación con este espectro de seeds SÍ debe reunir.
    assert saw_full, "ningún seed llenó completo en sweep"
    assert saw_partial, "ningún seed quedó en partial en sweep"
    assert saw_noisy, "ningún seed disparó cola noisy en sweep"
