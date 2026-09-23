"""AUTO-7 — alimentación del informe de autoevaluación desde los fills durables (READ-ONLY).

Une el cálculo puro (``bolsa_analytics.cognitive.auto_self_evaluation``) con el almacén
durable de fills SIM (``SimFillFinanceContext``), que es la fuente que YA existe para la
vigilancia real (V2.28/A10) y que desde V2.47 lleva ``cycle_id`` (migración 044).

Qué hace, exactamente:

* **Reconstruye el ciclo** (``signal → decisión → ejecución → resultado``) agrupando los
  fills por ``cycle_id`` y realizando FIFO dentro del grupo. Un grupo con salida abierta
  NO se emite: todavía no tiene resultado que medir (no es un hueco de medición, es que no
  hay resultado). Un grupo cuyas ventas no casan con ninguna compra tampoco: sin
  contrapartida no hay PnL, y fabricarlo sería mentir.
* **Legacy sin ``cycle_id``**: los fills anteriores a la 044 se emparejan FIFO por versión
  de estrategia, emitiendo un ciclo por emparejamiento (anónimos, declarados como tales por
  el módulo puro: ``cycle_without_identity``).
* **Lo que NO se puede medir aquí se declara, no se inventa**: el R realizado exige un
  denominador de riesgo que los fills NO llevan, así que se calcula solo si el llamante
  aporta la evidencia por ciclo (``cycle_risk``, productor de ``AUTO-9``); el MAE/MFE, el
  slippage y el embudo exigen otros productores que viven en el worker. Sin esos aportes se
  pasan como ``None`` y el módulo los publica como ``UNKNOWN``/``PARTIAL`` con su nota. Este
  adaptador nunca rellena un 0.
* Un ciclo que declare DOS versiones de estrategia distintas es un defecto de atribución:
  se emite SIN versión (el módulo lo declara en el cajón ``unattributed``) en vez de
  repartirlo entre las dos.

Read-only: este módulo no escribe ni modifica nada; solo lee y agrega.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_analytics.cognitive.auto_adaptive_confidence import (
    ADAPTIVE_LONG_WINDOW_DEFAULT,
    ADAPTIVE_RECENT_WINDOW_DEFAULT,
    AdaptiveConfidence,
    build_adaptive_confidence,
)
from bolsa_analytics.cognitive.auto_self_evaluation import (
    SELF_EVAL_MIN_TRADES_DEFAULT,
    AutoSelfEvaluation,
    evaluate_auto_self_evaluation,
)
from bolsa_application.cycle_risk import CycleRisk, apply_cycle_risk
from bolsa_application.sim_durable_store import (
    PostgresSimFillFinanceContextStore,
    SimFillFinanceContextStore,
)

__all__ = [
    "build_adaptive_confidence_from_fills",
    "build_auto_self_evaluation",
    "cycles_from_fills",
    "make_auto_self_evaluation_provider",
]

logger = logging.getLogger(__name__)


def _version_of(fill: Any) -> str:
    value = getattr(fill, "strategy_version_id", None)
    return str(value).strip() if isinstance(value, str) and value.strip() else ""


def _fill_instant(fill: Any) -> datetime | None:
    """Instante durable del fill (``created_at``), o ``None`` si no lo declara."""
    value = getattr(fill, "created_at", None)
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def _closed_at(rows: Sequence[Any]) -> str | None:
    """``closedAt`` del ciclo: el instante del ÚLTIMO fill del grupo, o ``None``.

    Es lo que permite la ventana RECIENTE del Adaptive (``AUTO-12``) ordenar por instante
    real en vez de por posición de lista. Sin instante legible NO se inventa uno: la clave se
    OMITE y el lector de confianza declara la ausencia (``recent_unavailable``).
    """
    instants = [value for value in (_fill_instant(fill) for fill in rows) if value is not None]
    if not instants:
        return None
    return max(instants).isoformat()


def _realize(rows: Sequence[Any]) -> tuple[Decimal, Decimal, int]:
    """FIFO del grupo: ``(pnl_realizado, cantidad_abierta, nº emparejamientos)``.

    Una venta que excede lo comprado se ignora (no se fabrica un corto): igual criterio que
    la contabilidad observada de la vigilancia.
    """
    lots: deque[list[Decimal]] = deque()
    realized = Decimal("0")
    matches = 0
    for fill in rows:
        qty = abs(Decimal(str(getattr(fill, "quantity", 0) or 0)))
        price = Decimal(str(getattr(fill, "price", 0) or 0))
        if qty <= 0:
            continue
        if str(getattr(fill, "side", "") or "").strip().lower() == "buy":
            lots.append([qty, price])
            continue
        remaining = qty
        while remaining > 0 and lots:
            lot_qty, lot_price = lots[0]
            matched = min(remaining, lot_qty)
            realized += (price - lot_price) * matched
            matches += 1
            remaining -= matched
            if matched == lot_qty:
                lots.popleft()
            else:
                lots[0] = [lot_qty - matched, lot_price]
    open_qty = sum((lot[0] for lot in lots), Decimal("0"))
    return realized, open_qty, matches


def _realize_pairs(rows: Sequence[Any]) -> tuple[Decimal, ...]:
    """PnL de cada emparejamiento FIFO (un ciclo por par) para los fills sin ``cycle_id``."""
    lots: deque[list[Decimal]] = deque()
    pairs: list[Decimal] = []
    for fill in rows:
        qty = abs(Decimal(str(getattr(fill, "quantity", 0) or 0)))
        price = Decimal(str(getattr(fill, "price", 0) or 0))
        if qty <= 0:
            continue
        if str(getattr(fill, "side", "") or "").strip().lower() == "buy":
            lots.append([qty, price])
            continue
        remaining = qty
        while remaining > 0 and lots:
            lot_qty, lot_price = lots[0]
            matched = min(remaining, lot_qty)
            pairs.append((price - lot_price) * matched)
            remaining -= matched
            if matched == lot_qty:
                lots.popleft()
            else:
                lots[0] = [lot_qty - matched, lot_price]
    return tuple(pairs)


def cycles_from_fills(fills: Iterable[Any]) -> tuple[dict[str, Any], ...]:
    """(PURA) ciclos financieros reconstruidos de los fills durables, en orden estable.

    Devuelve filas con ``cycleId``, ``strategyVersion``, ``pnl`` y —cuando se pudo medir— su
    ``closedAt`` (instante del último fill del grupo). Lo que no se puede derivar de los fills
    se queda ausente para que el informe lo declare; en particular, los ciclos **sin
    ``cycle_id``** (legacy) no reclaman un instante de cierre, porque sin identidad de ciclo
    tampoco hay una frontera de cierre que afirmar.
    """
    ordered: list[Any] = list(fills)
    grouped: dict[str, list[Any]] = {}
    anonymous: list[Any] = []
    for fill in ordered:
        cycle_id = getattr(fill, "cycle_id", None)
        key = str(cycle_id).strip() if isinstance(cycle_id, str) else ""
        if key:
            grouped.setdefault(key, []).append(fill)
        else:
            anonymous.append(fill)

    cycles: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        realized, open_qty, matches = _realize(rows)
        if matches == 0 or open_qty > 0:
            continue
        versions = {_version_of(fill) for fill in rows} - {""}
        # Un ciclo = una señal = una estrategia. Si el grupo declara dos, es un defecto de
        # atribución y el ciclo va SIN versión (lo declara el informe, no lo reparto).
        version = versions.pop() if len(versions) == 1 else ""
        row: dict[str, Any] = {"cycleId": key, "strategyVersion": version, "pnl": realized}
        closed_at = _closed_at(rows)
        if closed_at is not None:
            # Se AÑADE solo cuando se midió: sin fecha la clave se omite y el lector de
            # confianza declara el hueco. Así el informe de AUTO-7 no cambia de forma.
            row["closedAt"] = closed_at
        cycles.append(row)

    by_version: dict[str, list[Any]] = {}
    for fill in anonymous:
        by_version.setdefault(_version_of(fill), []).append(fill)
    for version, rows in by_version.items():
        for pnl in _realize_pairs(rows):
            cycles.append({"strategyVersion": version, "pnl": pnl})

    return tuple(cycles)


def build_auto_self_evaluation(
    *,
    fills: Iterable[Any] | None = None,
    opportunities: Iterable[Any] | None = None,
    seen: int | None = None,
    durable_seen: int | None = None,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
    cycle_risk: Mapping[str, CycleRisk] | None = None,
) -> AutoSelfEvaluation:
    """(PURA) informe AUTO-7 a partir de los fills durables (+ embudo si el llamante lo tiene).

    ``opportunities``/``seen``/``durable_seen`` son opcionales y se pasan TAL CUAL: si no
    se aportan, el embudo queda declarado ``UNKNOWN`` en vez de cerrarse con un cero.

    ``cycle_risk`` es la evidencia de riesgo por ciclo del productor ``AUTO-9`` (denominador
    y coste estimado, atados por ``cycle_id``). Sin ella el informe es **byte-idéntico** al
    de ``AUTO-7``: los ciclos quedan sin R, que es el hueco que el módulo ya declaraba.
    """
    return evaluate_auto_self_evaluation(
        cycles=apply_cycle_risk(cycles_from_fills(fills or ()), cycle_risk),
        opportunities=opportunities,
        seen=seen,
        durable_seen=durable_seen,
        min_trades=min_trades,
    )


def build_adaptive_confidence_from_fills(
    *,
    fills: Iterable[Any] | None = None,
    cycle_risk: Mapping[str, CycleRisk] | None = None,
    recent_window: int = ADAPTIVE_RECENT_WINDOW_DEFAULT,
    long_window: int = ADAPTIVE_LONG_WINDOW_DEFAULT,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
) -> AdaptiveConfidence:
    """(PURA) confianza estadística de ``AUTO-12`` desde los MISMOS fills que el informe.

    Reutiliza las dos piezas ya existentes —``cycles_from_fills`` (con su ``closedAt``) y
    ``apply_cycle_risk``— para que la confianza y el informe de ``AUTO-7``/``AUTO-9`` hablen
    exactamente del mismo material: sin un segundo productor que pueda divergir en silencio.
    """
    return build_adaptive_confidence(
        apply_cycle_risk(cycles_from_fills(fills or ()), cycle_risk),
        recent_window=recent_window,
        long_window=long_window,
        min_trades=min_trades,
    )


def make_auto_self_evaluation_provider(
    session_factory: Any,
    *,
    account_id: str | None = None,
    store_factory: Callable[[Any], SimFillFinanceContextStore] | None = None,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
) -> Any:
    """Devuelve ``self_evaluation(version_id) -> dict`` para composición del worker/API.

    Mismo patrón que ``make_observed_metrics_provider``: abre su propia sesión por
    invocación y, ante un fallo de lectura, devuelve un informe con el motivo declarado
    (nunca métricas fabricadas).
    """
    build_store = store_factory or (lambda session: PostgresSimFillFinanceContextStore(session))

    async def _self_evaluation(version_id: str) -> dict[str, Any]:
        vid = str(version_id or "").strip()
        if not vid:
            return _failed_report("strategy_version_required")
        try:
            async with session_factory() as session:
                fills = await build_store(session).list_for_strategy_version(
                    vid, account_id=account_id
                )
        except Exception:  # noqa: BLE001 — sin lectura no hay informe; no se inventa.
            logger.exception("self evaluation read failed version=%s", vid)
            return _failed_report("read_failed")
        return build_auto_self_evaluation(fills=fills, min_trades=min_trades).as_dict()

    return _self_evaluation


def _failed_report(reason: str) -> dict[str, Any]:
    """Informe vacío con el motivo declarado (sin datos NO es un informe de ceros)."""
    report = evaluate_auto_self_evaluation(min_trades=SELF_EVAL_MIN_TRADES_DEFAULT).as_dict()
    report["errors"] = [reason]
    report["decisive"] = False
    return report
