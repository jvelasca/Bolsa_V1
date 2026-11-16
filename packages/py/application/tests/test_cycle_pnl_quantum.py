"""El dinero del ciclo: cuantización POR FILL, publicada y verificable (ADR-051).

Diagnóstico del fallo que no tenía causa raíz declarada (``test_auto_identity_chain_battery_pg``:
``ciclo=-29.248900720000`` frente a ``libro=-29.248900``). La causa medida fue que el libro aplicado
mueve ``round6(q × p)`` **fill a fill** (todas las columnas monetarias son ``NUMERIC(18, 6)``)
mientras el FIFO del ciclo sumaba exacto y solo se cuantizaba al publicar::

    libro − ciclo_exacto = Σ signo_i · ( round6(q_i·p_i) − q_i·p_i )

El contrato que este fichero fija (``applied_per_fill_v1``) elige la magnitud que el dinero mueve:
``cycles_from_fills`` publica en ``pnl`` la suma de los movimientos YA cuantizados y conserva el
FIFO exacto en ``pnlExact`` para atribución. La igualdad sigue siendo exacta —no hay tolerancia—,
solo cambia el punto donde se aplica el quantum.

Qué demuestra, caso a caso:

* **A (control negativo).** Con ``q·p`` exacto a 6 decimales las dos magnitudes coinciden y el
  libro las reproduce: el hueco no nace de la acumulación.
* **B (el defecto).** La diferencia entre ``pnlExact`` y el libro es EXACTAMENTE la suma de los
  residuos por fill; la diferencia entre ``pnl`` y el libro es CERO.
* **C (el reparto).** Dos troceados de la misma cantidad y precio dan el mismo ``pnlExact`` y
  distinto ``pnl``: el quantum es del movimiento, no de la operación.
* **D (la mitad exacta).** Un producto que cae justo en ``…5e-7`` distingue ``ROUND_HALF_UP``
  (PostgreSQL) de ``ROUND_HALF_EVEN``: se fija el redondeo, no se hereda del intérprete.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from bolsa_application.auto_self_evaluation_feed import cycles_from_fills
from bolsa_application.cycle_pnl_policy import CYCLE_PNL_POLICY
from bolsa_application.sim_durable_store import SimFillFinanceContext

#: Quantum del DINERO: ``NUMERIC(18, 6)`` en todas las columnas monetarias del ledger.
_MONEY = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    """Redondeo del dinero a su quantum, como PostgreSQL ``NUMERIC(18, 6)``."""
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


def _fill(side: str, qty: str, price: str, *, execution_id: str, cycle_id: str) -> SimFillFinanceContext:
    return SimFillFinanceContext(
        execution_id=execution_id,
        instrument_id="AAA",
        side=side,
        quantity=Decimal(qty),
        price=Decimal(price),
        strategy_version_id="orb-1",
        cycle_id=cycle_id,
        created_at=None,
    )


def _cycle(fills: list[SimFillFinanceContext]) -> dict:
    cycles = cycles_from_fills(fills)
    assert len(cycles) == 1, f"el escenario debe dejar UN ciclo cerrado, hay {len(cycles)}"
    return cycles[0]


def _ledger_pnl(fills: list[SimFillFinanceContext]) -> Decimal:
    """Réplica del libro aplicado: ``Σ ± round6(q·p)``, fill a fill.

    Es la MISMA aritmética que ``realized_notional_from_applied_fills``
    (``apps/api-python/tests/applied_fill_equity.py``) usa como fuente independiente: cada
    fill mueve su notional redondeado porque la columna del ledger tiene 6 decimales.
    """
    total = Decimal("0")
    for fill in fills:
        notional = _money(fill.quantity * fill.price)
        total += notional if fill.side == "sell" else -notional
    return total


def _signed_residuals(fills: list[SimFillFinanceContext]) -> list[Decimal]:
    """``signo_i · (round6(q_i·p_i) − q_i·p_i)`` por fill, en el orden del libro."""
    rows: list[Decimal] = []
    for fill in fills:
        product = fill.quantity * fill.price
        residual = _money(product) - product
        rows.append(residual if fill.side == "sell" else -residual)
    return rows


# ── Caso A — control negativo: si el producto es exacto al quantum, no hay hueco ─────


def test_a_product_exact_at_six_decimals_leaves_no_residual() -> None:
    """Con productos exactos a 6 decimales las dos magnitudes y el libro coinciden EXACTO."""
    fills = [
        _fill("buy", "100", "10.005", execution_id="e1", cycle_id="cyc-1"),
        _fill("sell", "100", "10.095", execution_id="e2", cycle_id="cyc-1"),
    ]

    cycle = _cycle(fills)

    assert all(residual == 0 for residual in _signed_residuals(fills))
    assert cycle["pnl"] == cycle["pnlExact"] == _ledger_pnl(fills) == Decimal("9.000000")
    assert cycle["pnlPolicy"] == CYCLE_PNL_POLICY


# ── Caso B — el defecto: el quantum del movimiento, no del agregado ──────────────────


def test_the_published_pnl_is_the_ledger_and_the_exact_pnl_keeps_the_residual() -> None:
    """El ``pnl`` publicado REPRODUCE el libro; el hueco queda aislado en ``pnlExact``.

    Escenario: dos compras troceadas (cuanto mayor, peor) y una venta que cierra la
    posición. Ni la distribución de fills ni la acumulación del FIFO entran en la
    diferencia: los dos números son exactos y su distancia es, literalmente, la suma de
    los redondeos que el ledger aplicó fill a fill.
    """
    fills = [
        _fill("buy", "1.111111", "10.000003", execution_id="e1", cycle_id="cyc-1"),
        _fill("buy", "1.111111", "10.123457", execution_id="e2", cycle_id="cyc-1"),
        _fill("sell", "2.222222", "9.876541", execution_id="e3", cycle_id="cyc-1"),
    ]

    cycle = _cycle(fills)
    exact = cycle["pnlExact"]
    published = cycle["pnl"]
    ledger = _ledger_pnl(fills)
    residuals = _signed_residuals(fills)

    # La cantidad está ENTERAMENTE emparejada: sin esto la identidad no sería algebraica
    # (una posición abierta aportaría coste sin venta y el ciclo ni se publicaría).
    bought = sum((fill.quantity for fill in fills if fill.side == "buy"), Decimal("0"))
    sold = sum((fill.quantity for fill in fills if fill.side == "sell"), Decimal("0"))
    assert bought == sold == Decimal("2.222222")

    assert published == ledger, "el dinero publicado es exactamente lo que movió el libro"
    assert exact == Decimal("-0.411531069958")
    assert ledger == Decimal("-0.411530")
    assert ledger - exact == sum(residuals, Decimal("0")) == Decimal("0.000001069958")
    assert published != exact, "el residuo sigue siendo medible: no se ha perdido"


def test_quantizing_inputs_is_not_the_same_as_quantizing_the_fill() -> None:
    """El quantum se aplica al MOVIMIENTO: redondear el producto no es redondear el total.

    Se fija la diferencia que el fallo real mostró (``round6(-29.248900720000) = -29.248901``
    frente a ``libro = -29.248900``): el redondeo del agregado no reconstruye el libro, porque
    el libro redondea ANTES de sumar.
    """
    fills = [
        _fill("buy", "1.111111", "10.000003", execution_id="e1", cycle_id="cyc-1"),
        _fill("buy", "1.111111", "10.123457", execution_id="e2", cycle_id="cyc-1"),
        _fill("sell", "2.222222", "9.876541", execution_id="e3", cycle_id="cyc-1"),
    ]

    cycle = _cycle(fills)

    assert _money(cycle["pnlExact"]) == Decimal("-0.411531")
    assert cycle["pnl"] == Decimal("-0.411530")
    assert _money(cycle["pnlExact"]) != _money(cycle["pnl"]), (
        "cuantizar el total del ciclo NO reconstruye el libro: el redondeo es por fill. "
        f"round6(exacto)={_money(cycle['pnlExact'])} aplicado={cycle['pnl']}"
    )
    # Y el hueco ya supera UN quantum: la tolerancia de un quantum sobre los totales no
    # sería un criterio (crece con el número de fills, ≤ n × 5e-7).
    assert abs(cycle["pnl"] - cycle["pnlExact"]) > _MONEY


# ── Caso C — el residuo es del FILL, no del reparto ni del agregado ─────────────────


def test_the_residual_is_a_property_of_the_fill_not_of_the_operation_total() -> None:
    """El quantum es del MOVIMIENTO (el fill), no del importe de la operación.

    Dos repartos de la MISMA cantidad y el MISMO precio no tienen por qué dar el mismo
    resultado, porque cada tramo redondea su propio producto. El FIFO exacto es cero en los
    dos casos —no hay beneficio—, así que cualquier diferencia es cuantización pura.
    """
    one_lot = [
        _fill("buy", "3.000001", "10.000003", execution_id="e1", cycle_id="cyc-1"),
        _fill("sell", "3.000001", "10.000003", execution_id="e2", cycle_id="cyc-1"),
    ]
    uneven = [
        _fill("buy", "0.500000", "10.000003", execution_id="e1", cycle_id="cyc-1"),
        _fill("buy", "0.500001", "10.000003", execution_id="e2", cycle_id="cyc-1"),
        _fill("sell", "1.000001", "10.000003", execution_id="e3", cycle_id="cyc-1"),
    ]

    assert _cycle(one_lot)["pnlExact"] == Decimal("0")
    assert _cycle(uneven)["pnlExact"] == Decimal("0")

    # Sin producto no hay beneficio: el FIFO exacto es cero en AMBOS repartos. El DINERO
    # publicado, en cambio, no tiene por qué devolver cero cuando los tramos redondean distinto.
    assert _cycle(one_lot)["pnl"] == Decimal("0")
    assert _cycle(uneven)["pnl"] != Decimal("0"), (
        "el libro redondea movimientos: repartir la misma cantidad en tramos con residuos "
        "que no se cancelan separa el dinero publicado del FIFO exacto, aunque no haya beneficio"
    )


# ── Caso D — la mitad exacta: el redondeo se fija, no se hereda ─────────────────────


def test_a_product_exactly_half_a_quantum_rounds_away_from_zero() -> None:
    """``…5e-7`` se redondea hacia fuera de cero (``ROUND_HALF_UP``), como PostgreSQL.

    Con ``ROUND_HALF_EVEN`` (el modo por defecto de ``Decimal``) el mismo producto bajaría,
    y el libro aplicado dejaría de reproducirse. Este nodo fija el modo del dinero.
    """
    # 1.0000005 tiene un séptimo decimal exacto de 5 ⇒ mitad del quantum.
    fills = [
        _fill("buy", "1", "10", execution_id="e1", cycle_id="cyc-1"),
        _fill("sell", "1", "10.0000005", execution_id="e2", cycle_id="cyc-1"),
    ]

    cycle = _cycle(fills)

    # ledgers: venta 10.000001 (HALF_UP), compra 10.000000.
    assert cycle["pnl"] == Decimal("0.000001")
    assert cycle["pnlExact"] == Decimal("0.0000005")
