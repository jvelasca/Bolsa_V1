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
    "AccountReconciliationReport",
    "POSITION_PROJECTION_DIVERGENT",
    "POSITION_PROJECTION_OK",
    "POSITION_PROJECTION_REBUILT",
    "POSITION_PROJECTION_UNKNOWN",
    "ReconciliationVerdict",
    "expected_position_from_events",
    "reconcile_sim_account",
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


@dataclass(frozen=True, slots=True)
class AccountReconciliationReport:
    """V2.24.2 (P2-C) — veredicto GLOBAL de reconciliación de una cuenta/engine.

    ``reconcile_sim_position`` decide por símbolo; este reporte agrega TODOS los
    símbolos relevantes (unión de eventos, canónico y proyección) para que la
    vigilancia de la cuenta no dependa de mirar el watch uno a uno. ``blocks_openings``
    es fail-closed: si CUALQUIER símbolo está ``DIVERGENT`` o ``UNKNOWN``, no se
    autorizan nuevas aperturas en la cuenta.
    """

    account_id: str
    engine_id: str
    verdicts: tuple[ReconciliationVerdict, ...]

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(v.symbol for v in self.verdicts)

    @property
    def divergent(self) -> tuple[ReconciliationVerdict, ...]:
        return tuple(v for v in self.verdicts if v.status == POSITION_PROJECTION_DIVERGENT)

    @property
    def unknown(self) -> tuple[ReconciliationVerdict, ...]:
        return tuple(v for v in self.verdicts if v.status == POSITION_PROJECTION_UNKNOWN)

    @property
    def rebuilt(self) -> tuple[ReconciliationVerdict, ...]:
        return tuple(v for v in self.verdicts if v.status == POSITION_PROJECTION_REBUILT)

    @property
    def ok(self) -> bool:
        return not self.divergent and not self.unknown

    @property
    def blocks_openings(self) -> bool:
        """Fail-closed: cualquier DIVERGENT/UNKNOWN bloquea nuevas aperturas."""
        return not self.ok

    @property
    def status(self) -> str:
        if self.divergent:
            return POSITION_PROJECTION_DIVERGENT
        if self.unknown:
            return POSITION_PROJECTION_UNKNOWN
        if self.rebuilt:
            return POSITION_PROJECTION_REBUILT
        return POSITION_PROJECTION_OK


def reconcile_sim_account(
    *,
    account_id: str,
    engine_id: str,
    symbols: Sequence[str],
    execution_events: Sequence[object] | None,
    financial_positions: Mapping[str, object] | None,
    sim_auto_positions: Mapping[str, object] | None,
) -> AccountReconciliationReport:
    """Reconcilia TODOS los símbolos de una cuenta/engine (P2-C).

    Amplía el conjunto de símbolos con los que aparecen en el canónico o en la
    proyección (no solo el watch), de modo que una posición fantasma —presente en la
    proyección pero ausente del canónico— también se detecte como ``DIVERGENT`` en
    vez de quedar invisible. Fail-closed: cualquier símbolo no-OK bloquea aperturas.
    """
    seen: list[str] = []
    for source in (symbols, financial_positions or {}, sim_auto_positions or {}):
        for raw in source:
            symbol = str(raw)
            if symbol and symbol not in seen:
                seen.append(symbol)
    verdicts = tuple(
        reconcile_sim_position(
            symbol=symbol,
            execution_events=execution_events,
            financial_positions=financial_positions,
            sim_auto_positions=sim_auto_positions,
        )
        for symbol in seen
    )
    return AccountReconciliationReport(
        account_id=account_id,
        engine_id=engine_id,
        verdicts=verdicts,
    )
