"""V2.24 / A9.1 (P1-01 + P2-02) — reconciliación de la posición SIM.

El motor AUTO mantiene tres vistas de la misma verdad:

* ``expected`` — lo que dicen los ``ExecutionEvent`` aplicados (fills BUY − SELL del
  día, fuente de auditoría financiera).
* ``actual``   — la posición del estado financiero CANÓNICO (ledger/portfolio).
* ``projection`` — el espejo de recuperación ``sim_auto_positions`` (V2.23 · P2-01).

V2.23 solo comprobaba que la proyección se hubiera escrito; **no** que coincidiera
con el estado real. Este módulo exige ``expected == actual == projection`` y decide
qué hacer cuando no:

* ``OK``        — las tres coinciden; la proyección es fiable.
* ``REBUILT``   — la proyección divergía y se reconstruyó desde el canónico.
* ``DIVERGENT`` — ``expected != actual`` (inconsistencia financiera seria): NO se
  autorizan nuevas aperturas hasta reconciliar; se reporta.
* ``UNKNOWN``   — no hay datos suficientes (p. ej. sin lector canónico): fail-closed,
  tampoco autoriza aperturas.

Regla de oro (P1-01): **una proyección no puede autorizar por sí sola una compra**.
Ante ``DIVERGENT``/``UNKNOWN`` el motor debe bloquear aperturas y avisar.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "POSITION_PROJECTION_DIVERGENT",
    "POSITION_PROJECTION_OK",
    "POSITION_PROJECTION_REBUILT",
    "POSITION_PROJECTION_UNKNOWN",
    "ReconciliationVerdict",
    "expected_position_from_events",
    "reconcile_sim_position",
]

POSITION_PROJECTION_OK = "OK"
POSITION_PROJECTION_REBUILT = "REBUILT"
POSITION_PROJECTION_DIVERGENT = "DIVERGENT"
POSITION_PROJECTION_UNKNOWN = "UNKNOWN"

_TOL = Decimal("0.000001")


def _dec(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError):
        return Decimal("0")


def expected_position_from_events(
    events: Sequence[object],
    *,
    symbol: str,
) -> Decimal:
    """Posición esperada por el símbolo desde los ``ExecutionEvent`` (BUY − SELL).

    Acepta objetos con ``instrument_id``/``symbol`` y ``side``/``qty``/``quantity``
    (tolerante a los distintos mapeos del dominio). Las trazas con venue LIVE se
    ignoran (AUTO jamás las produce; defensa redundante).
    """
    live = {"live", "broker_live", "xtb", "real", "live_bridge"}
    net = Decimal("0")
    for ev in events:
        ev_symbol = getattr(ev, "instrument_id", None) or getattr(ev, "symbol", None)
        if str(ev_symbol or "") != symbol:
            continue
        venue = str(getattr(ev, "venue", "") or "").strip().lower()
        if venue in live:
            continue
        side = str(getattr(ev, "side", "") or "").strip().lower()
        qty = getattr(ev, "qty", None)
        if qty is None:
            qty = getattr(ev, "quantity", None)
        magnitude = abs(_dec(qty))
        if side in {"buy", "b", "compra"}:
            net += magnitude
        elif side in {"sell", "s", "venta"}:
            net -= magnitude
    return net


@dataclass(frozen=True, slots=True)
class ReconciliationVerdict:
    """Resultado de reconciliar una posición SIM (por símbolo)."""

    symbol: str
    status: str
    expected: Decimal
    actual: Decimal | None
    projection: Decimal | None
    rebuilt: bool = False
    detail: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.status in {POSITION_PROJECTION_OK, POSITION_PROJECTION_REBUILT}

    @property
    def allows_new_openings(self) -> bool:
        """Solo ``OK``/``REBUILT`` autorizan nuevas aperturas (fail-closed)."""
        return self.ok


def _close(a: Decimal, b: Decimal, tol: Decimal = _TOL) -> bool:
    return abs(a - b) <= tol


def reconcile_sim_position(
    *,
    symbol: str,
    execution_events: Sequence[object] | None,
    financial_positions: Mapping[str, object] | None,
    sim_auto_positions: Mapping[str, object] | None,
) -> ReconciliationVerdict:
    """Reconcilia ``ExecutionEvents`` ↔ posición canónica ↔ proyección SIM.

    Fail-closed: sin datos canónicos (``financial_positions is None``) o sin eventos
    (``execution_events is None``) el veredicto es ``UNKNOWN`` y NO autoriza abrir.
    """
    events = execution_events
    canonical_raw = financial_positions.get(symbol) if financial_positions is not None else None
    projection_raw = sim_auto_positions.get(symbol) if sim_auto_positions is not None else None

    projection = _dec(projection_raw) if projection_raw is not None else None
    actual = _dec(canonical_raw) if canonical_raw is not None else None

    if events is None or financial_positions is None or actual is None:
        return ReconciliationVerdict(
            symbol=symbol,
            status=POSITION_PROJECTION_UNKNOWN,
            expected=expected_position_from_events(events or (), symbol=symbol),
            actual=actual,
            projection=projection,
            detail=("missing_canonical_or_events",),
        )

    expected = expected_position_from_events(events, symbol=symbol)
    if not _close(expected, actual):
        return ReconciliationVerdict(
            symbol=symbol,
            status=POSITION_PROJECTION_DIVERGENT,
            expected=expected,
            actual=actual,
            projection=projection,
            detail=("events_vs_canonical_mismatch",),
        )

    if projection is None or not _close(projection, actual):
        return ReconciliationVerdict(
            symbol=symbol,
            status=POSITION_PROJECTION_REBUILT,
            expected=expected,
            actual=actual,
            projection=projection,
            rebuilt=True,
            detail=("projection_rebuilt_from_canonical",),
        )

    return ReconciliationVerdict(
        symbol=symbol,
        status=POSITION_PROJECTION_OK,
        expected=expected,
        actual=actual,
        projection=projection,
    )
