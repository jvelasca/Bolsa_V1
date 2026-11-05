"""Evidencia MONETARIA del DÍA-D: curva de equity y veredicto contra la política por cuenta.

Qué cierra: el barrido ``v2_93`` mide la evidencia en **R por ciclo** (una unidad de riesgo), y
la política de evidencia ([``account_evidence_policy``](./account_evidence_policy.py)) está
escrita en **porcentaje de la cuenta**: retorno neto, drawdown máximo, ventanas positivas,
exceso sobre comprar y mantener y reserva fuera de muestra. Sin una curva de equity no se puede
pasar de una a otra, y el hueco se declaraba ``NOT_MEASURED``.

Este módulo hace esa conversión con **flujos de caja reales de los fills** (lado, cantidad y
precio), no con una regla de tres sobre R: el motor dimsensiona por riesgo con un tope del
1 % por operación ([``auto_v2_entry``](./auto_v2_entry.py) ``max_risk_per_trade_pct``), así que
una operación no arriesga exactamente lo mismo que otra y ``R × constante`` **no** es un
porcentaje.

Contrato de medición (fail-closed, misma disciplina que el resto del repo):

* Un dato que falta es ``None`` y se **declara**; nunca se convierte en ``0``.
* Una ventana **sin flujo** no es «ventana plana»: es una ventana ``NOT_MEASURED`` y no entra en
  el denominador de «% de ventanas positivas».
* El veredicto solo es ``ACCREDITED`` si **todos** los umbrales están medidos y se cumplen. Un
  umbral no medido deja el veredicto en ``NOT_ACCREDITED`` (nunca en un aprobado parcial).
* Este módulo **no** toca el motor, ni umbrales, ni allocation. Es un lector.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bolsa_application.closed_bars import bar_day

__all__ = [
    "BUY_HOLD",
    "EVIDENCE_ACCREDITED",
    "EVIDENCE_NOT_ACCREDITED",
    "EVIDENCE_REFUTED",
    "CashFlow",
    "PolicyCheck",
    "build_equity_evidence",
    "buy_and_hold_pct",
    "evaluate_evidence_policy",
    "flows_from_fill_rows",
    "holdout_split",
    "max_drawdown_pct",
    "net_return_pct",
    "realized_cost_bps",
    "window_returns",
]

EVIDENCE_ACCREDITED = "ACCREDITED"
EVIDENCE_REFUTED = "REFUTED"
EVIDENCE_NOT_ACCREDITED = "NOT_ACCREDITED"

BUY_HOLD = "buy_and_hold"

#: Notch de coste: por debajo se declara que la fricción no es comparable con la política.
_BPS = 10_000.0


def _finite(value: Any) -> float | None:
    """``float`` finito, o ``None``. ``bool`` no es un número (convención del repo)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _day(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if text else ""


def _bar_close(bar: Any) -> Any:
    """Cierre de una barra (``OhlcvBar`` o ``Mapping``); ``None`` si no lo declara."""
    if isinstance(bar, Mapping):
        return bar.get("close")
    return getattr(bar, "close", None)


@dataclass(frozen=True, slots=True)
class CashFlow:
    """Movimiento de caja de UN fill, en el día en que se liquida.

    ``amount`` lleva el signo del dinero: una compra **sale** caja (negativo) y una venta
    **entra** (positivo). ``cycle_id`` permite atribuir el flujo a su ciclo sin inventarlo:
    ``None`` cuando el fill no lo declara.
    """

    day: str
    amount: float
    cycle_id: str | None = None
    symbol: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "amount": self.amount,
            "cycleId": self.cycle_id,
            "symbol": self.symbol,
        }


def flows_from_fill_rows(
    rows: Sequence[Any],
    *,
    day_by_cycle: Mapping[str, str] | None = None,
) -> tuple[list[CashFlow], int]:
    """Flujos de caja desde filas de fill (``SimFillFinanceContext`` o ``Mapping``).

    Devuelve ``(flujos, noMedidos)``. Una fila no cuenta como ingreso ni como gasto si le
    falta el lado, la cantidad, el precio o el día: incrementa ``noMedidos`` y **no** entra en
    la curva (un cero afirmaría «esta operación no movió dinero», que es lo que no se sabe).

    ``day_by_cycle`` es el respaldo cuando el fill no trae instante (dobles herméticos): se
    usa el día de ENTRADA del ciclo. Sin instante y sin ciclo, el flujo no es medible.
    """

    fallback = {str(k): _day(v) for k, v in (day_by_cycle or {}).items() if _day(v)}
    flows: list[CashFlow] = []
    unmeasured = 0
    for row in rows or ():
        if isinstance(row, Mapping):
            side = str(row.get("side") or "").strip().lower()
            quantity = _finite(row.get("quantity"))
            price = _finite(row.get("price"))
            instant = row.get("createdAt") or row.get("created_at")
            cycle_id = row.get("cycleId") or row.get("cycle_id")
            symbol = row.get("instrumentId") or row.get("instrument_id")
        else:
            side = str(getattr(row, "side", "") or "").strip().lower()
            quantity = _finite(getattr(row, "quantity", None))
            price = _finite(getattr(row, "price", None))
            instant = getattr(row, "created_at", None)
            cycle_id = getattr(row, "cycle_id", None)
            symbol = getattr(row, "instrument_id", None)
        cycle_key = str(cycle_id or "").strip() or None
        day = _day(instant) or (fallback.get(cycle_key or "") or "")
        if side not in {"buy", "sell"} or quantity is None or price is None or quantity <= 0 or price <= 0 or not day:
            unmeasured += 1
            continue
        gross = quantity * price
        flows.append(
            CashFlow(
                day=day,
                amount=-gross if side == "buy" else gross,
                cycle_id=cycle_key,
                symbol=str(symbol) if symbol else None,
            )
        )
    flows.sort(key=lambda flow: (flow.day, flow.amount, flow.cycle_id or "", flow.symbol or ""))
    return flows, unmeasured


def _curve(flows: Sequence[CashFlow], initial_equity: float) -> list[tuple[str, float]]:
    """``[(día, equity)]`` acumulada por día, en orden determinista. Sin flujos ⇒ vacía."""
    seed = _finite(initial_equity)
    if seed is None or seed <= 0:
        return []
    by_day: dict[str, float] = {}
    for flow in flows:
        by_day[flow.day] = by_day.get(flow.day, 0.0) + flow.amount
    if not by_day:
        return []
    equity = seed
    points: list[tuple[str, float]] = [(min(by_day), seed)]
    for day in sorted(by_day):
        equity += by_day[day]
        points.append((day, equity))
    return points


def net_return_pct(curve: Sequence[tuple[str, float]]) -> float | None:
    """Retorno neto % del tramo medido: ``(último/primero - 1) × 100``. ``None`` si no se mide."""
    if len(curve) < 2:
        return None
    first = _finite(curve[0][1])
    last = _finite(curve[-1][1])
    if first is None or last is None or first <= 0:
        return None
    return (last / first - 1.0) * 100.0


def max_drawdown_pct(curve: Sequence[tuple[str, float]]) -> float | None:
    """Caída máxima % desde el pico (high-water-mark) del tramo medido.

    ``None`` si la curva no tiene al menos dos puntos o si un punto no es finito: una caída
    ``0 %`` afirmaría que no hubo ninguna, y eso no es lo mismo que no poder medirla.
    """
    if len(curve) < 2:
        return None
    peak: float | None = None
    worst = 0.0
    for _day, equity in curve:
        value = _finite(equity)
        if value is None:
            return None
        peak = value if peak is None else max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak * 100.0)
    return worst


def window_returns(
    curve: Sequence[tuple[str, float]],
    *,
    granularity: str = "day",
) -> dict[str, Any]:
    """Retornos por ventana (``day`` o ``year``) y % de ventanas positivas.

    Una ventana **sin cambio de equity** es ``NOT_MEASURED``: no hubo operación cerrada que la
    mida, así que no se cuenta ni como positiva ni como negativa. Las ventanas sin flujo de un
    día a otro (fin de semana, festivo) no existen en la curva y tampoco entran.

    Devuelve ``positivePct = None`` cuando no hay ninguna ventana medida.
    """
    if granularity not in {"day", "year"}:
        raise ValueError(f"granularidad desconocida: {granularity!r}")
    if len(curve) < 2:
        return {
            "granularity": granularity,
            "measuredWindows": 0,
            "positiveWindows": 0,
            "negativeWindows": 0,
            "positivePct": None,
        }

    positive = 0
    negative = 0
    if granularity == "day":
        # Una ventana es el SALTO de un punto al siguiente: el día sin movimiento no es una
        # ventana medida (no hubo operación cerrada que la mida).
        for (_day_a, before), (_day_b, after) in zip(curve, curve[1:]):
            if before <= 0:
                continue
            change = after - before
            if change > 0:
                positive += 1
            elif change < 0:
                negative += 1
    else:
        first_equity: dict[str, float] = {}
        last_equity: dict[str, float] = {}
        for day, equity in curve:
            bucket = day[:4]
            first_equity.setdefault(bucket, equity)
            last_equity[bucket] = equity
        for bucket in sorted(first_equity):
            start = first_equity[bucket]
            end = last_equity[bucket]
            if start <= 0:
                continue
            change = end - start
            if change > 0:
                positive += 1
            elif change < 0:
                negative += 1
    measured = positive + negative
    return {
        "granularity": granularity,
        "measuredWindows": measured,
        "positiveWindows": positive,
        "negativeWindows": negative,
        "positivePct": (positive / measured * 100.0) if measured else None,
    }


def buy_and_hold_pct(
    *,
    bars_by_symbol: Mapping[str, Sequence[Any]],
    watch: Sequence[str],
    start_day: str,
    end_day: str,
) -> dict[str, Any]:
    """Retorno % de **comprar y mantener** a partes iguales el watch entre dos días.

    Es el benchmark de la política: sin él, «exceso sobre comprar y mantener» no es medible.
    Un símbolo entra solo si tiene una barra legible el ``start_day`` **y** el ``end_day``
    (mismo criterio en todos: un símbolo a medio camino no se promedia). Sin ningún símbolo
    medible devuelve ``pct=None`` y lo declara.
    """
    start = _day(start_day)
    end = _day(end_day)
    if not start or not end or start > end:
        return {"pct": None, "symbolsMeasured": 0, "symbolsRequested": len(list(watch or ())), "reason": "ventana_invalida"}
    closes: list[float] = []
    for symbol in watch or ():
        table: dict[str, float] = {}
        for bar in bars_by_symbol.get(str(symbol), ()) or ():
            day = bar_day(bar)
            close = _finite(_bar_close(bar))
            if day and close is not None and close > 0:
                table[day] = close
        first = table.get(start)
        last = table.get(end)
        if first is None or last is None or first <= 0:
            continue
        closes.append((last / first - 1.0) * 100.0)
    if not closes:
        return {"pct": None, "symbolsMeasured": 0, "symbolsRequested": len(list(watch or ())), "reason": "sin_barras_en_los_extremos"}
    return {
        "pct": sum(closes) / len(closes),
        "symbolsMeasured": len(closes),
        "symbolsRequested": len(list(watch or ())),
        "reason": None,
    }


def holdout_split(days: Sequence[str], *, holdout_pct: float) -> dict[str, Any]:
    """Corte fuera de muestra: los últimos ``holdout_pct`` % de los días, en orden.

    El corte se fija por **días de calendario medidos**, no por operaciones: elegirlo por
    operaciones permitiría mover la frontera mirando el resultado.
    """
    ordered = sorted({_day(day) for day in days or () if _day(day)})
    pct = _finite(holdout_pct)
    if not ordered or pct is None or not 0 < pct < 100:
        return {"inSampleDays": 0, "outOfSampleDays": 0, "cutDay": None}
    out_count = int(round(len(ordered) * pct / 100.0))
    out_count = max(0, min(len(ordered), out_count))
    cut_index = len(ordered) - out_count
    return {
        "inSampleDays": cut_index,
        "outOfSampleDays": out_count,
        "cutDay": ordered[cut_index] if cut_index < len(ordered) else None,
    }


@dataclass(frozen=True, slots=True)
class PolicyCheck:
    """Un umbral de la política con su medición y su veredicto explícito."""

    name: str
    threshold: float | None
    measured: float | None
    verdict: str  # PASS | FAIL | NOT_MEASURED

    @property
    def passed(self) -> bool:
        return self.verdict == "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "measured": self.measured,
            "verdict": self.verdict,
        }


def _at_least(name: str, threshold: float | None, measured: float | None) -> PolicyCheck:
    limit = _finite(threshold)
    value = _finite(measured)
    if limit is None or value is None:
        return PolicyCheck(name=name, threshold=limit, measured=value, verdict="NOT_MEASURED")
    return PolicyCheck(name=name, threshold=limit, measured=value, verdict="PASS" if value >= limit else "FAIL")


def _at_most(name: str, threshold: float | None, measured: float | None) -> PolicyCheck:
    check = _at_least(name, threshold, measured)
    if check.verdict == "NOT_MEASURED":
        return check
    return PolicyCheck(
        name=name,
        threshold=check.threshold,
        measured=check.measured,
        verdict="PASS" if check.measured <= check.threshold else "FAIL",
    )


def evaluate_evidence_policy(
    *,
    measured_windows: int | None,
    measured_trades: int | None,
    positive_window_pct: float | None,
    net_return: float | None,
    drawdown: float | None,
    excess_vs_buy_hold: float | None,
    realized_cost_bps: float | None,
    policy: Any,
) -> dict[str, Any]:
    """Veredicto explícito de CADA umbral de la política, y el global.

    ``policy`` es un ``AccountEvidencePolicy`` (o cualquier objeto con los mismos atributos).
    El global es ``ACCREDITED`` solo con todos los checks en ``PASS``; ``REFUTED`` si alguno
    medido falla; y ``NOT_ACCREDITED`` cuando no falla ninguno pero queda alguno sin medir.
    """
    checks = [
        _at_least("minWindows", getattr(policy, "min_windows", None), measured_windows),
        _at_least("minTradesTotal", getattr(policy, "min_trades_total", None), measured_trades),
        _at_least(
            "minPositiveWindowPct", getattr(policy, "min_positive_window_pct", None), positive_window_pct
        ),
        _at_least("minNetReturnPct", getattr(policy, "min_net_return_pct", None), net_return),
        _at_most("maxDrawdownPct", getattr(policy, "max_drawdown_pct", None), drawdown),
        _at_least(
            "minExcessVsBuyHoldPct",
            getattr(policy, "min_excess_vs_buy_hold_pct", None),
            excess_vs_buy_hold,
        ),
        _at_least(
            "minRoundTripCostBps",
            getattr(policy, "min_round_trip_cost_bps", None),
            realized_cost_bps,
        ),
    ]
    failed = [check.name for check in checks if check.verdict == "FAIL"]
    unmeasured = [check.name for check in checks if check.verdict == "NOT_MEASURED"]
    if failed:
        verdict, reason = EVIDENCE_REFUTED, f"failed:{','.join(failed)}"
    elif unmeasured:
        verdict, reason = EVIDENCE_NOT_ACCREDITED, f"not_measured:{','.join(unmeasured)}"
    else:
        verdict, reason = EVIDENCE_ACCREDITED, "all_thresholds_met"
    return {
        "verdict": verdict,
        "verdictReason": reason,
        "failed": failed,
        "notMeasured": unmeasured,
        "checks": [check.to_dict() for check in checks],
        "policy": policy.to_dict() if hasattr(policy, "to_dict") else None,
    }


def realized_cost_bps(rows: Sequence[Any]) -> float | None:
    """Fricción APLICADA media, en bps por lado, ``|price/mid - 1| × 10000``.

    Es la medición de lo que costó operar, distinta del modelo configurado: si un fill no
    declara ``reference_mid`` no se puede afirmar su fricción y queda fuera. Sin ningún fill
    medible devuelve ``None`` (nunca ``0 bps``, que afirmaría «gratis»).
    """
    samples: list[float] = []
    for row in rows or ():
        if isinstance(row, Mapping):
            price = _finite(row.get("price"))
            mid = _finite(row.get("referenceMid") or row.get("reference_mid"))
        else:
            price = _finite(getattr(row, "price", None))
            mid = _finite(getattr(row, "reference_mid", None))
        if price is None or mid is None or price <= 0 or mid <= 0:
            continue
        samples.append(abs(price / mid - 1.0) * _BPS)
    if not samples:
        return None
    return sum(samples) / len(samples)


def build_equity_evidence(
    *,
    fill_rows: Sequence[Any],
    round_trips: Sequence[Mapping[str, Any]],
    bars_by_symbol: Mapping[str, Sequence[Any]],
    watch: Sequence[str],
    initial_equity: float,
    day_by_cycle: Mapping[str, str] | None = None,
    holdout_pct: float | None = None,
    policy: Any = None,
) -> dict[str, Any]:
    """Bloque completo de evidencia monetaria del barrido (aditivo, read-only).

    Devuelve un artefacto autocontenido con la curva, las métricas en % y —si se pasa
    ``policy``— el veredicto umbral a umbral. Todo dato que no se pueda medir viaja ``None``.
    """
    flows, unmeasured_rows = flows_from_fill_rows(fill_rows, day_by_cycle=day_by_cycle)
    curve = _curve(flows, initial_equity)
    days = [day for day, _equity in curve]
    start_day = days[0] if days else ""
    end_day = days[-1] if days else ""

    net = net_return_pct(curve)
    drawdown = max_drawdown_pct(curve)
    daily = window_returns(curve, granularity="day")
    yearly = window_returns(curve, granularity="year")

    benchmark = (
        buy_and_hold_pct(
            bars_by_symbol=bars_by_symbol, watch=watch, start_day=start_day, end_day=end_day
        )
        if start_day and end_day
        else {"pct": None, "symbolsMeasured": 0, "symbolsRequested": len(list(watch or ())), "reason": "sin_curva"}
    )
    bench_pct = _finite(benchmark.get("pct"))
    excess = None if bench_pct is None or net is None else net - bench_pct

    # Holdout: se declara el corte y se miden AMBOS tramos por separado (nunca se mezclan).
    split = holdout_split(days, holdout_pct=holdout_pct if holdout_pct is not None else 0.0)
    out_start = split.get("cutDay") or ""
    in_curve = [(day, equity) for day, equity in curve if out_start and day < out_start]
    out_curve = [(day, equity) for day, equity in curve if out_start and day >= out_start]

    cost = realized_cost_bps(fill_rows)

    evidence: dict[str, Any] = {
        "kind": "dia-d-equity-evidence-v1",
        "initialEquity": _finite(initial_equity),
        "currencyNote": "una sola divisa de la cuenta declarada; la mezcla de divisas NO se convierte",
        "curvePoints": len(curve),
        "startDay": start_day or None,
        "endDay": end_day or None,
        "curve": [{"day": day, "equity": equity} for day, equity in curve],
        "netReturnPct": net,
        "maxDrawdownPct": drawdown,
        "positiveWindowPct": daily.get("positivePct"),
        "positiveWindows": daily,
        "positiveYears": yearly,
        "buyHold": {**benchmark, "excessPct": excess},
        "realizedCostBps": cost,
        "holdout": {
            "holdoutPct": holdout_pct,
            **split,
            "inSampleNetReturnPct": net_return_pct(in_curve),
            "inSampleDrawdownPct": max_drawdown_pct(in_curve),
            "outOfSampleNetReturnPct": net_return_pct(out_curve),
            "outOfSampleDrawdownPct": max_drawdown_pct(out_curve),
        },
        "flowsMeasured": len(flows),
        "flowsUnmeasured": unmeasured_rows,
        "measuredTrades": len(list(round_trips or ())),
        "notMeasured": [],
    }

    if unmeasured_rows:
        evidence["notMeasured"].append(
            f"{unmeasured_rows} fills sin lado/cantidad/precio/día: fuera de la curva (no son un 0)"
        )
    if net is None:
        evidence["notMeasured"].append("netReturnPct: sin curva de al menos dos puntos")
    if drawdown is None:
        evidence["notMeasured"].append("maxDrawdownPct: sin curva de al menos dos puntos")
    if daily.get("positivePct") is None:
        evidence["notMeasured"].append("positiveWindowPct: ninguna ventana medida")
    if bench_pct is None:
        evidence["notMeasured"].append(
            f"buyAndHold: {benchmark.get('reason') or 'no medible'} "
            f"({benchmark.get('symbolsMeasured')}/{benchmark.get('symbolsRequested')} símbolos)"
        )
    if cost is None:
        evidence["notMeasured"].append("realizedCostBps: ningún fill declara reference_mid")
    if not split.get("outOfSampleDays"):
        evidence["notMeasured"].append("holdout: sin días suficientes para reservar fuera de muestra")

    if policy is not None:
        evidence["policyEvaluation"] = evaluate_evidence_policy(
            measured_windows=daily.get("measuredWindows"),
            measured_trades=len(list(round_trips or ())),
            positive_window_pct=daily.get("positivePct"),
            net_return=net,
            drawdown=drawdown,
            excess_vs_buy_hold=excess,
            realized_cost_bps=cost,
            policy=policy,
        )
    return evidence
