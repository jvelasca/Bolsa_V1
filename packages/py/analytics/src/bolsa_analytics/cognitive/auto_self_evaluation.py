"""AUTO-7 — autoevaluación del motor AUTO por ``strategyVersion`` (PURA y READ-ONLY).

Cierra la cadena de trazabilidad ``señal → decisión → ejecución → resultado`` en una única
agregación de lectura: qué le está pasando **de verdad** a cada versión de estrategia, con
el embudo de oportunidades cuadrado y los huecos de medición **declarados**.

Qué agrega por ``strategyVersion``:

* **resultado**: nº de ciclos (round-trips), PnL realizado, expectancy (en divisa y en R),
  win rate, profit factor y las medias de ganadoras/perdedoras;
* **excursiones**: MAE/MFE medios en R (recogidos, no calibrados);
* **costes**: ``slippage`` realizado y **coste de rechazo** (lo que dejaron pasar las
  oportunidades NO operadas con precio medido);
* **riesgo**: contribución al **drawdown** realizado de la estrategia y su cuota sobre la
  suma de drawdowns de las estrategias (proxy aditivo, declarado como tal);
* **embudo**: ``traded``/``rejected``/``expired``/``missed`` con sus motivos.

Disciplina de medición (la del repo, y aquí es el punto entero del módulo):

* Un agregado que **no** se pudo medir se declara ``UNKNOWN``/``PARTIAL`` con su nota.
  Nunca se publica un ``0`` que se leería como "no pasó nada" (que es una afirmación) ni un
  ``None`` disfrazado de cero.
* El embudo **solo cierra** (``funnel_closed``) cuando ``seen == traded + rejected + expired
  + missed`` y el estado de cada oportunidad está catalogado. Sin oportunidades aportadas el
  embudo queda ``UNKNOWN`` con ``seen = None``: el desconocido deja el embudo **abierto**,
  jamás se cierra con un cero inventado.
* Una fila **sin versión** de estrategia NO se reparte: cae en el cajón declarado
  ``unattributed`` (la ausencia se declara, no se atribuye).
* Un ciclo **repetido** (misma identidad) no se suma dos veces: se cuenta una vez y se
  declara ``duplicate_cycle`` — es el invariante *exactly-once* de AUTO-6 aplicado al
  informe, porque un doble conteo en la lectura miente igual que un doble fill.
* Un ciclo **sin identidad** (ni ``cycle_id`` ni ``signal_id``) se cuenta y se declara
  (``cycle_without_identity``): no se puede deduplicar lo que no se puede nombrar.

**Read-only por contrato**: este módulo no modifica pesos, ni sizing, ni estado alguno. Es
un informe; su campo ``read_only`` es ``True`` y su bandera ``decisive`` NO es un permiso.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from bolsa_analytics.cognitive.expectancy import sample_quality_from_n
from bolsa_analytics.cognitive.measurement import (
    MEASUREMENT_COMPLETE,
    MEASUREMENT_PARTIAL,
    MEASUREMENT_UNKNOWN,
    MeasurementStatus,
    combine_measurements,
    measurement_from_counts,
)

__all__ = [
    "AUTO_SELF_EVALUATION_KEY",
    "SELF_EVAL_MIN_TRADES_DEFAULT",
    "SELF_EVAL_OPPORTUNITY_STATUSES",
    "AutoSelfEvaluation",
    "StrategySelfEvaluation",
    "evaluate_auto_self_evaluation",
]

AUTO_SELF_EVALUATION_KEY = "autoSelfEvaluation"

#: Muestra mínima de ciclos cerrados para que la lectura sea *decisoria*. Por debajo, las
#: métricas se publican igual (son un informe) pero declaradas ``thin_sample`` y con
#: ``decisive = False``: una muestra anecdótica no autoriza a concluir.
SELF_EVAL_MIN_TRADES_DEFAULT = 10

#: Estados FINALES del embudo. La casa única del literal es
#: ``bolsa_application.auto_reason_codes`` (productor y agregador); aquí se re-declara para
#: que este módulo puro de ``bolsa_analytics`` no dependa de ``bolsa_application`` (la
#: dirección de dependencia del repo es application → analytics).
SELF_EVAL_TRADED = "traded"
SELF_EVAL_REJECTED = "rejected"
SELF_EVAL_EXPIRED = "expired"
SELF_EVAL_MISSED = "missed"
SELF_EVAL_OPPORTUNITY_STATUSES: frozenset[str] = frozenset(
    {SELF_EVAL_TRADED, SELF_EVAL_REJECTED, SELF_EVAL_EXPIRED, SELF_EVAL_MISSED}
)

# ── Notas y errores tipificados (vocabulario propio del informe) ─────────────────────
SELF_EVAL_FUNNEL_UNKNOWN = "funnel_unknown"
SELF_EVAL_FUNNEL_SEEN_MISMATCH = "funnel_seen_mismatch"
SELF_EVAL_FUNNEL_DURABLE_MISMATCH = "funnel_durable_mismatch"
SELF_EVAL_FUNNEL_UNBALANCED = "funnel_unbalanced"
SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN = "opportunity_status_unknown"
SELF_EVAL_REJECTION_WITHOUT_REASON = "rejection_without_reason"
SELF_EVAL_REJECTION_COST_UNMEASURED = "rejection_cost_unmeasured"
SELF_EVAL_RISK_UNMEASURED = "risk_unmeasured"
SELF_EVAL_EXCURSIONS_UNMEASURED = "excursions_unmeasured"
SELF_EVAL_SLIPPAGE_UNMEASURED = "slippage_unmeasured"
SELF_EVAL_DRAWDOWN_FLOOR = "drawdown_unmeasured_cycles"
SELF_EVAL_DRAWDOWN_SHARE_PROXY = "drawdown_share_additive_proxy"
SELF_EVAL_DUPLICATE_CYCLE = "duplicate_cycle"
SELF_EVAL_CYCLE_WITHOUT_IDENTITY = "cycle_without_identity"
SELF_EVAL_UNVERSIONED_CYCLE = "unversioned_cycle"
SELF_EVAL_THIN_SAMPLE = "thin_sample"
SELF_EVAL_MISSING_INPUTS = "missing_inputs"

_MONEY = Decimal("0.000001")


# ── Coerción tolerante (dict o atributo, snake_case o camelCase) ─────────────────────


def _field(raw: Any, *names: str) -> Any:
    """Primer campo presente de ``names`` en un ``Mapping`` o en un objeto; ``None`` si no.

    Acepta las dos convenciones del repo (``strategy_version_id`` del dominio,
    ``strategyVersion`` del payload JSONB) para que el mismo módulo puro sirva al worker,
    al journal durable y a los tests sin adaptadores intermedios.
    """
    if isinstance(raw, Mapping):
        for name in names:
            if name in raw:
                return raw[name]
        return None
    for name in names:
        if hasattr(raw, name):
            return getattr(raw, name)
    return None


def _dec(value: Any) -> Decimal | None:
    """Divisa/importe finito; ``None`` para ausente o ilegible (nunca un 0 silencioso)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _num(value: Any) -> float | None:
    """Número finito en coma flotante; ``None`` para ausente o ilegible."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / ±inf
        return None
    return number


def _round4(value: float) -> float:
    return round(value, 4)


def _explicit(value: Any) -> str | None:
    """Texto no vacío (y no ``"none"``) o ``None``: la ausencia no se rellena."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() == "none":
        return None
    return text


# ── Lectura de las filas de entrada ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Cycle:
    """Ciclo financiero (round-trip) ya normalizado: lo que el informe agrega."""

    strategy_version: str
    identity: str
    pnl: Decimal | None
    r_multiple: float | None
    mfe_r: float | None
    mae_r: float | None
    slippage: Decimal | None
    closed_at: str | None


def _read_cycle(raw: Any) -> _Cycle:
    """Normaliza una fila de ciclo (dict u objeto) sin inventar ningún campo ausente."""
    nested_mfe = _field(raw, "mfe_mae", "mfeMae")
    mfe = _num(_field(raw, "mfe_r", "mfeR"))
    mae = _num(_field(raw, "mae_r", "maeR"))
    if nested_mfe is not None:
        mfe = mfe if mfe is not None else _num(_field(nested_mfe, "mfeR", "mfe_r"))
        mae = mae if mae is not None else _num(_field(nested_mfe, "maeR", "mae_r"))
    cycle_id = _explicit(_field(raw, "cycle_id", "cycleId"))
    signal_id = _explicit(_field(raw, "signal_id", "signalId"))
    return _Cycle(
        strategy_version=(
            _explicit(
                _field(
                    raw,
                    "strategy_version",
                    "strategyVersion",
                    "strategy_version_id",
                    "strategyVersionId",
                )
            )
            or ""
        ),
        identity=cycle_id or signal_id or "",
        pnl=_dec(_field(raw, "pnl", "realized_pnl", "realizedPnl", "pnl_currency")),
        r_multiple=_num(_field(raw, "r_multiple", "rMultiple", "r")),
        mfe_r=mfe,
        mae_r=mae,
        slippage=_dec(_field(raw, "slippage", "slippage_currency", "slippageCurrency")),
        closed_at=_explicit(_field(raw, "closed_at", "closedAt")),
    )


def _dedupe_cycles(
    cycles: Sequence[_Cycle],
) -> tuple[tuple[_Cycle, ...], int, int]:
    """Quita ciclos con identidad REPETIDA (devuelve ``únicos, duplicados, sin_identidad``).

    La identidad ausente NO colapsa dos ciclos distintos: dos filas anónimas son dos
    ciclos (se cuentan y se declaran), nunca uno solo por parecerse.
    """
    unique: list[_Cycle] = []
    seen: set[str] = set()
    duplicates = 0
    anonymous = 0
    for cycle in cycles:
        if not cycle.identity:
            anonymous += 1
            unique.append(cycle)
            continue
        if cycle.identity in seen:
            duplicates += 1
            continue
        seen.add(cycle.identity)
        unique.append(cycle)
    return tuple(unique), duplicates, anonymous


# ── Embudo de oportunidades ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class _Funnel:
    """Resultado de la pasada por las oportunidades del periodo."""

    counts: dict[str, int]
    rejection_reasons: dict[str, int]
    by_strategy_counts: dict[str, dict[str, int]]
    by_strategy_rejection_cost: dict[str, float]
    by_strategy_rejection_valued: dict[str, int]
    rejection_cost: float | None
    rejection_cost_measurement: MeasurementStatus
    measurement: MeasurementStatus
    seen: int | None
    errors: tuple[str, ...]
    notes: tuple[str, ...]
    provided: bool


def _read_opportunities(
    opportunities: Sequence[Any],
    *,
    declared_seen: int | None,
    durable_seen: int | None,
) -> _Funnel:
    """Reconcilia el embudo: cuenta, tipifica motivos y MIDE el coste de lo no operado.

    Una oportunidad no operada **sin motivo** es una decisión en silencio
    (``rejection_without_reason``) y deja el embudo abierto; un estado no catalogado idem.
    El coste de rechazo de una fila sin los DOS precios (referencia y posterior) queda
    ``UNKNOWN`` con su nota: no se inventa un 0 de "no dejó pasar nada".
    """
    counts = {status: 0 for status in SELF_EVAL_OPPORTUNITY_STATUSES}
    rejection_reasons: dict[str, int] = {}
    by_strategy_counts: dict[str, dict[str, int]] = {}
    by_strategy_cost: dict[str, float] = {}
    by_strategy_valued: dict[str, int] = {}
    errors: list[str] = []
    notes: list[str] = []
    measured_rejection = 0
    measured_cost = 0.0

    for raw in opportunities:
        status = str(_field(raw, "status") or "").strip().lower()
        if status not in SELF_EVAL_OPPORTUNITY_STATUSES:
            errors.append(SELF_EVAL_OPPORTUNITY_STATUS_UNKNOWN)
            continue
        reason = _explicit(_field(raw, "reason")) or ""
        strategy = (
            _explicit(
                _field(
                    raw,
                    "strategy_version",
                    "strategyVersion",
                    "strategy_version_id",
                    "strategyVersionId",
                )
            )
            or ""
        )
        counts[status] += 1
        if strategy:
            bucket = by_strategy_counts.setdefault(strategy, {})
            bucket[status] = bucket.get(status, 0) + 1
        if status != SELF_EVAL_TRADED and not reason:
            errors.append(SELF_EVAL_REJECTION_WITHOUT_REASON)
        if status == SELF_EVAL_REJECTED and reason:
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        if status == SELF_EVAL_TRADED:
            continue
        # Coste de rechazo: solo con referencia y precio posterior MEDIDOS.
        reference = _dec(_field(raw, "reference_price", "referencePrice"))
        subsequent = _dec(_field(raw, "subsequent_price", "subsequentPrice"))
        if reference is None or subsequent is None or reference == 0:
            continue
        missed = _num((subsequent - reference) / reference)
        if missed is None:
            continue
        measured_rejection += 1
        measured_cost += missed
        if strategy:
            by_strategy_valued[strategy] = by_strategy_valued.get(strategy, 0) + 1
            by_strategy_cost[strategy] = by_strategy_cost.get(strategy, 0.0) + missed

    provided = bool(opportunities)
    if not provided:
        return _Funnel(
            counts=counts,
            rejection_reasons=rejection_reasons,
            by_strategy_counts=by_strategy_counts,
            by_strategy_rejection_cost=by_strategy_cost,
            by_strategy_rejection_valued=by_strategy_valued,
            rejection_cost=None,
            rejection_cost_measurement=MEASUREMENT_UNKNOWN,
            measurement=MEASUREMENT_UNKNOWN,
            seen=None,
            errors=(),
            notes=(SELF_EVAL_FUNNEL_UNKNOWN,),
            provided=False,
        )

    measured_states = sum(counts.values())
    seen = declared_seen if declared_seen is not None else len(opportunities)
    if declared_seen is not None and declared_seen != len(opportunities):
        # ``seen`` declarado por el productor ≠ filas observadas ⇒ hay oportunidades
        # vistas que no terminaron en un estado: es exactamente lo que el embudo caza.
        errors.append(SELF_EVAL_FUNNEL_SEEN_MISMATCH)
    if durable_seen is not None and durable_seen != seen:
        # La identidad durable (``sim_consumed_signals``) es el otro lado del embudo: si
        # no cuadra con lo journalizado, lo consumido y lo declarado divergen.
        errors.append(SELF_EVAL_FUNNEL_DURABLE_MISMATCH)
    if seen != measured_states:
        errors.append(SELF_EVAL_FUNNEL_UNBALANCED)

    rejected_like = sum(
        counts[status]
        for status in (SELF_EVAL_REJECTED, SELF_EVAL_EXPIRED, SELF_EVAL_MISSED)
    )
    if rejected_like == 0:
        cost_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
        cost: float | None = None
        notes.append(SELF_EVAL_REJECTION_COST_UNMEASURED)
    else:
        cost_measurement = measurement_from_counts(
            valued=measured_rejection, unvalued=rejected_like - measured_rejection
        )
        # Sin NINGUNA fila con precios el coste es DESCONOCIDO, no 0: publicar 0.0 aquí
        # afirmaría "no dejó pasar nada", que es exactamente lo contrario de "no se midió".
        cost = _round4(measured_cost) if measured_rejection else None
        if cost_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_REJECTION_COST_UNMEASURED)

    return _Funnel(
        counts=counts,
        rejection_reasons=rejection_reasons,
        by_strategy_counts=by_strategy_counts,
        by_strategy_rejection_cost=by_strategy_cost,
        by_strategy_rejection_valued=by_strategy_valued,
        rejection_cost=cost,
        rejection_cost_measurement=cost_measurement,
        measurement=(MEASUREMENT_COMPLETE if not errors else MEASUREMENT_PARTIAL),
        seen=seen,
        errors=tuple(errors),
        notes=tuple(notes),
        provided=True,
    )


# ── Curva de resultados y drawdown ──────────────────────────────────────────────────


def _max_drawdown(pnls: Sequence[Decimal]) -> Decimal:
    """Máxima caída (en divisa) de la curva de PnL realizado acumulado.

    La curva arranca en 0 y el drawdown se mide contra el pico alcanzado; una curva sin
    caída devuelve ``0`` (que aquí SÍ es una medida: la curva se conoce entera).
    """
    peak = Decimal("0")
    running = Decimal("0")
    worst = Decimal("0")
    for pnl in pnls:
        running += pnl
        if running > peak:
            peak = running
        drop = peak - running
        if drop > worst:
            worst = drop
    return worst.quantize(_MONEY)


# ── Agregados por estrategia ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StrategySelfEvaluation:
    """Lectura read-only de UNA ``strategyVersion`` sobre el periodo aportado."""

    strategy_version: str
    trades: int
    wins: int
    losses: int
    realized_pnl: Decimal
    expectancy_currency: Decimal | None
    expectancy_r: float | None
    win_rate: float | None
    profit_factor: float | None
    avg_win_currency: Decimal | None
    avg_loss_currency: Decimal | None
    mfe_r: float | None
    mae_r: float | None
    slippage_currency: Decimal | None
    rejection_cost_return: float | None
    drawdown_currency: Decimal
    drawdown_share: float | None
    traded: int
    rejected: int
    expired: int
    missed: int
    sample_quality: str
    results_measurement: MeasurementStatus
    risk_measurement: MeasurementStatus
    excursions_measurement: MeasurementStatus
    slippage_measurement: MeasurementStatus
    rejection_cost_measurement: MeasurementStatus
    drawdown_measurement: MeasurementStatus
    decisive: bool
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "trades": self.trades,
            "wins": self.wins,
            "losses": self.losses,
            "realizedPnl": str(self.realized_pnl),
            "expectancyCurrency": (
                None if self.expectancy_currency is None else str(self.expectancy_currency)
            ),
            "expectancyR": self.expectancy_r,
            "winRate": self.win_rate,
            "profitFactor": self.profit_factor,
            "avgWinCurrency": (
                None if self.avg_win_currency is None else str(self.avg_win_currency)
            ),
            "avgLossCurrency": (
                None if self.avg_loss_currency is None else str(self.avg_loss_currency)
            ),
            "mfeR": self.mfe_r,
            "maeR": self.mae_r,
            "slippageCurrency": (
                None if self.slippage_currency is None else str(self.slippage_currency)
            ),
            "rejectionCostReturn": self.rejection_cost_return,
            "drawdownCurrency": str(self.drawdown_currency),
            "drawdownShare": self.drawdown_share,
            "funnel": {
                "traded": self.traded,
                "rejected": self.rejected,
                "expired": self.expired,
                "missed": self.missed,
            },
            "sampleQuality": self.sample_quality,
            "resultsMeasurement": self.results_measurement,
            "riskMeasurement": self.risk_measurement,
            "excursionsMeasurement": self.excursions_measurement,
            "slippageMeasurement": self.slippage_measurement,
            "rejectionCostMeasurement": self.rejection_cost_measurement,
            "drawdownMeasurement": self.drawdown_measurement,
            "decisive": self.decisive,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AutoSelfEvaluation:
    """Informe AUTO-7 completo: por estrategia + embudo + huecos de medición declarados."""

    by_strategy: tuple[StrategySelfEvaluation, ...]
    cycles: int
    trades: int
    realized_pnl: Decimal
    expectancy_currency: Decimal | None
    expectancy_r: float | None
    win_rate: float | None
    profit_factor: float | None
    slippage_currency: Decimal | None
    opportunity_cost_return: float | None
    opportunity_cost_measurement: MeasurementStatus
    drawdown_currency: Decimal
    unattributed_cycles: int
    unattributed_pnl: Decimal
    cycles_without_identity: int
    duplicate_cycles: int
    seen: int | None
    traded: int | None
    rejected: int | None
    expired: int | None
    missed: int | None
    funnel_measurement: MeasurementStatus
    rejection_reasons: tuple[tuple[str, int], ...]
    results_measurement: MeasurementStatus
    measurement: MeasurementStatus
    decisive: bool
    errors: tuple[str, ...]
    notes: tuple[str, ...]
    read_only: bool = True

    @property
    def funnel_closed(self) -> bool:
        """El embudo cuadra y está MEDIDO (``seen == Σ estados``, sin motivos ausentes)."""
        return self.funnel_measurement == MEASUREMENT_COMPLETE

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": AUTO_SELF_EVALUATION_KEY,
            "readOnly": self.read_only,
            "cycles": self.cycles,
            "trades": self.trades,
            "realizedPnl": str(self.realized_pnl),
            "expectancyCurrency": (
                None if self.expectancy_currency is None else str(self.expectancy_currency)
            ),
            "expectancyR": self.expectancy_r,
            "winRate": self.win_rate,
            "profitFactor": self.profit_factor,
            "slippageCurrency": (
                None if self.slippage_currency is None else str(self.slippage_currency)
            ),
            "opportunityCostReturn": self.opportunity_cost_return,
            "opportunityCostMeasurement": self.opportunity_cost_measurement,
            "drawdownCurrency": str(self.drawdown_currency),
            "unattributedCycles": self.unattributed_cycles,
            "unattributedPnl": str(self.unattributed_pnl),
            "cyclesWithoutIdentity": self.cycles_without_identity,
            "duplicateCycles": self.duplicate_cycles,
            "funnel": {
                "seen": self.seen,
                "traded": self.traded,
                "rejected": self.rejected,
                "expired": self.expired,
                "missed": self.missed,
                "measurement": self.funnel_measurement,
                "closed": self.funnel_closed,
            },
            "rejectionReasons": dict(self.rejection_reasons),
            "byStrategy": [row.as_dict() for row in self.by_strategy],
            "resultsMeasurement": self.results_measurement,
            "measurement": self.measurement,
            "decisive": self.decisive,
            "errors": list(self.errors),
            "notes": list(self.notes),
        }


def evaluate_auto_self_evaluation(
    *,
    cycles: Iterable[Any] | None = None,
    opportunities: Iterable[Any] | None = None,
    seen: int | None = None,
    durable_seen: int | None = None,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
) -> AutoSelfEvaluation:
    """(PURA) autoevaluación AUTO-7 por ``strategyVersion`` sobre el periodo aportado.

    ``cycles`` son los ciclos financieros cerrados (``signal → decisión → ejecución →
    resultado``): cada uno aporta lo que declara — PnL, R realizado, MAE/MFE, slippage,
    ``cycle_id``/``signal_id`` y su versión de estrategia. ``opportunities`` son las filas
    del embudo del periodo. ``seen`` es el total declarado por el productor y
    ``durable_seen`` el número de señales consumidas **de la misma ventana** que el
    llamante lee de ``sim_consumed_signals`` (si la ventana no coincide, no se pasa: mejor
    un embudo declarado abierto que un cierre falso).

    No hay efectos: ni pesos, ni sizing, ni escritura. ``decisive`` es una bandera de
    lectura, NO un permiso.
    """
    raw_cycles = [_read_cycle(row) for row in (cycles or ())]
    unique_cycles, duplicates, anonymous = _dedupe_cycles(raw_cycles)

    funnel = _read_opportunities(
        list(opportunities or ()), declared_seen=seen, durable_seen=durable_seen
    )

    errors: list[str] = list(funnel.errors)
    notes: list[str] = []
    if duplicates:
        errors.append(SELF_EVAL_DUPLICATE_CYCLE)
    if anonymous:
        notes.append(SELF_EVAL_CYCLE_WITHOUT_IDENTITY)

    # Orden de la curva: por cierre cuando TODOS lo declaran (comparar órdenes mezclados
    # sería comparar peras con manzanas); si no, el orden de entrada, que es del llamante.
    ordered = unique_cycles
    if unique_cycles and all(cycle.closed_at for cycle in unique_cycles):
        ordered = tuple(sorted(unique_cycles, key=lambda c: str(c.closed_at)))

    groups: dict[str, list[_Cycle]] = {}
    unattributed: list[_Cycle] = []
    for cycle in ordered:
        if cycle.strategy_version:
            groups.setdefault(cycle.strategy_version, []).append(cycle)
        else:
            unattributed.append(cycle)
    if unattributed:
        # Una fila sin versión no se reparte: se declara el cajón entero.
        notes.append(SELF_EVAL_UNVERSIONED_CYCLE)
    # El roll-up de arriba cubre los ciclos ATRIBUIBLES: los sin versión no se reparten
    # entre estrategias (el cajón ``unattributed`` los declara aparte), y sumarlos aquí
    # daría un total que ninguna fila de estrategia explica.
    attributed = [cycle for cycle in ordered if cycle.strategy_version]
    pnls_measured = [cycle.pnl for cycle in attributed if cycle.pnl is not None]
    no_pnl = len(attributed) - len(pnls_measured)
    # Los bloques de RESULTADOS/DRAWDOWN solo están MEDIDOS si hay ciclos: un informe
    # vacío no es un informe completo.
    results_measurement: MeasurementStatus = (
        measurement_from_counts(valued=len(pnls_measured), unvalued=no_pnl)
        if attributed
        else MEASUREMENT_UNKNOWN
    )
    drawdown_measurement = results_measurement
    aggregate_dd = _max_drawdown(pnls_measured)
    if attributed and drawdown_measurement != MEASUREMENT_COMPLETE:
        notes.append(SELF_EVAL_DRAWDOWN_FLOOR)

    rows: list[StrategySelfEvaluation] = []
    # Una versión que solo aparece en el embudo (vista y jamás operada) TAMBIÉN es una
    # fila: sin ella, su coste de rechazo quedaría sin dueño. Con cero ciclos sus métricas
    # de resultado no existen y se declaran como tales.
    versions = sorted(set(groups) | set(funnel.by_strategy_counts))
    for version in versions:
        rows.append(
            _strategy_row(version, groups.get(version, ()), funnel, min_trades=min_trades)
        )

    total_dd = sum((row.drawdown_currency for row in rows), Decimal("0"))
    if total_dd > 0:
        # Cuota de drawdown sobre la SUMA de los drawdowns por estrategia: es un proxy
        # ADITIVO (los drawdowns de dos estrategias pueden solaparse en el tiempo), nunca
        # una atribución temporal. Se declara como tal.
        rows = [
            _with_share(row, share=_round4(float(row.drawdown_currency / total_dd)))
            for row in rows
        ]
        notes.append(SELF_EVAL_DRAWDOWN_SHARE_PROXY)

    total_trades = sum(row.trades for row in rows)
    total_pnl = sum((row.realized_pnl for row in rows), Decimal("0"))
    agg_r_values = [cycle.r_multiple for cycle in attributed if cycle.r_multiple is not None]
    agg_wins = sum(1 for cycle in attributed if cycle.pnl is not None and cycle.pnl > 0)
    agg_slippage = [cycle.slippage for cycle in attributed if cycle.slippage is not None]

    slippage_measurement = measurement_from_counts(
        valued=len(agg_slippage), unvalued=len(attributed) - len(agg_slippage)
    )
    risk_measurement = measurement_from_counts(
        valued=len(agg_r_values), unvalued=len(attributed) - len(agg_r_values)
    )
    excursions = [
        cycle
        for cycle in attributed
        if cycle.mfe_r is not None and cycle.mae_r is not None
    ]
    excursions_measurement = measurement_from_counts(
        valued=len(excursions), unvalued=len(attributed) - len(excursions)
    )

    aggregate = combine_measurements(
        funnel.measurement if funnel.provided else MEASUREMENT_UNKNOWN,
        results_measurement,
        risk_measurement,
        excursions_measurement,
        slippage_measurement,
        funnel.rejection_cost_measurement,
    )
    if not unique_cycles and not funnel.provided:
        notes.append(SELF_EVAL_MISSING_INPUTS)
    if total_trades < max(1, min_trades):
        notes.append(SELF_EVAL_THIN_SAMPLE)
    if attributed and risk_measurement != MEASUREMENT_COMPLETE:
        notes.append(SELF_EVAL_RISK_UNMEASURED)
    if attributed and excursions_measurement != MEASUREMENT_COMPLETE:
        notes.append(SELF_EVAL_EXCURSIONS_UNMEASURED)
    if attributed and slippage_measurement != MEASUREMENT_COMPLETE:
        notes.append(SELF_EVAL_SLIPPAGE_UNMEASURED)

    decisive = (
        results_measurement == MEASUREMENT_COMPLETE
        and total_trades >= max(1, min_trades)
        and not errors
    )

    return AutoSelfEvaluation(
        by_strategy=tuple(rows),
        cycles=len(unique_cycles),
        trades=total_trades,
        realized_pnl=total_pnl.quantize(_MONEY),
        expectancy_currency=(
            (total_pnl / total_trades).quantize(_MONEY) if total_trades else None
        ),
        expectancy_r=(
            _round4(sum(agg_r_values) / len(agg_r_values)) if agg_r_values else None
        ),
        win_rate=_round4(agg_wins / len(pnls_measured)) if pnls_measured else None,
        profit_factor=_profit_factor(pnls_measured),
        slippage_currency=(
            sum(agg_slippage, Decimal("0")).quantize(_MONEY) if agg_slippage else None
        ),
        opportunity_cost_return=funnel.rejection_cost,
        opportunity_cost_measurement=funnel.rejection_cost_measurement,
        drawdown_currency=aggregate_dd,
        unattributed_cycles=len(unattributed),
        unattributed_pnl=sum(
            (cycle.pnl for cycle in unattributed if cycle.pnl is not None), Decimal("0")
        ).quantize(_MONEY),
        cycles_without_identity=anonymous,
        duplicate_cycles=duplicates,
        seen=funnel.seen,
        traded=funnel.counts[SELF_EVAL_TRADED] if funnel.provided else None,
        rejected=funnel.counts[SELF_EVAL_REJECTED] if funnel.provided else None,
        expired=funnel.counts[SELF_EVAL_EXPIRED] if funnel.provided else None,
        missed=funnel.counts[SELF_EVAL_MISSED] if funnel.provided else None,
        funnel_measurement=funnel.measurement,
        rejection_reasons=tuple(sorted(funnel.rejection_reasons.items())),
        results_measurement=results_measurement,
        measurement=aggregate,
        decisive=decisive,
        errors=tuple(dict.fromkeys(errors)),
        notes=tuple(dict.fromkeys([*funnel.notes, *notes])),
    )


def _with_share(row: StrategySelfEvaluation, *, share: float) -> StrategySelfEvaluation:
    """Copia la fila añadiendo su cuota de drawdown (proxy aditivo declarado)."""
    return replace(row, drawdown_share=share)


def _profit_factor(pnls: Sequence[Decimal]) -> float | None:
    """Ganancias brutas / pérdidas brutas; ``None`` si no hay pérdidas (indefinido)."""
    gross_profit = sum((pnl for pnl in pnls if pnl > 0), Decimal("0"))
    gross_loss = -sum((pnl for pnl in pnls if pnl < 0), Decimal("0"))
    if gross_loss <= 0:
        return None
    return _round4(float(gross_profit / gross_loss))


def _strategy_row(
    version: str,
    cycles: Sequence[_Cycle],
    funnel: _Funnel,
    *,
    min_trades: int,
) -> StrategySelfEvaluation:
    """Agrega los ciclos de UNA versión y declara lo que no se pudo medir de ellos."""
    with_pnl = [cycle for cycle in cycles if cycle.pnl is not None]
    pnls = [cycle.pnl for cycle in with_pnl if cycle.pnl is not None]
    r_values = [cycle.r_multiple for cycle in cycles if cycle.r_multiple is not None]
    excursions = [
        cycle for cycle in cycles if cycle.mfe_r is not None and cycle.mae_r is not None
    ]
    mfe_values = [cycle.mfe_r for cycle in excursions if cycle.mfe_r is not None]
    mae_values = [cycle.mae_r for cycle in excursions if cycle.mae_r is not None]
    slippages = [cycle.slippage for cycle in cycles if cycle.slippage is not None]

    trades = len(cycles)
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    realized = sum(pnls, Decimal("0"))
    gross_profit = sum((pnl for pnl in pnls if pnl > 0), Decimal("0"))
    gross_loss = -sum((pnl for pnl in pnls if pnl < 0), Decimal("0"))

    results_measurement = measurement_from_counts(
        valued=len(with_pnl), unvalued=trades - len(with_pnl)
    ) if cycles else MEASUREMENT_UNKNOWN
    risk_measurement = measurement_from_counts(
        valued=len(r_values), unvalued=trades - len(r_values)
    )
    excursions_measurement = measurement_from_counts(
        valued=len(excursions), unvalued=trades - len(excursions)
    )
    slippage_measurement = measurement_from_counts(
        valued=len(slippages), unvalued=trades - len(slippages)
    )
    drawdown_measurement = measurement_from_counts(
        valued=len(with_pnl), unvalued=trades - len(with_pnl)
    )

    counts = funnel.by_strategy_counts.get(version, {})
    rejected_total = (
        counts.get(SELF_EVAL_REJECTED, 0)
        + counts.get(SELF_EVAL_EXPIRED, 0)
        + counts.get(SELF_EVAL_MISSED, 0)
    )
    rejection_valued = funnel.by_strategy_rejection_valued.get(version, 0)
    if rejected_total == 0:
        rejection_cost: float | None = None
        rejection_cost_measurement: MeasurementStatus = MEASUREMENT_UNKNOWN
    else:
        rejection_cost_measurement = measurement_from_counts(
            valued=rejection_valued, unvalued=rejected_total - rejection_valued
        )
        rejection_cost = (
            _round4(funnel.by_strategy_rejection_cost.get(version, 0.0))
            if rejection_valued
            else None
        )

    notes: list[str] = []
    if cycles:
        # Los huecos se declaran SOLO cuando hay resultado que medir: en una versión sin
        # ningún ciclo, "R no medido" no aporta nada que "0 ciclos" no diga ya.
        if risk_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_RISK_UNMEASURED)
        if excursions_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_EXCURSIONS_UNMEASURED)
        if slippage_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_SLIPPAGE_UNMEASURED)
        if drawdown_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_DRAWDOWN_FLOOR)
    if rejection_cost_measurement != MEASUREMENT_COMPLETE and rejected_total:
        notes.append(SELF_EVAL_REJECTION_COST_UNMEASURED)
    if trades < max(1, min_trades):
        notes.append(SELF_EVAL_THIN_SAMPLE)

    return StrategySelfEvaluation(
        strategy_version=version,
        trades=trades,
        wins=wins,
        losses=losses,
        realized_pnl=realized.quantize(_MONEY),
        expectancy_currency=(
            (realized / len(with_pnl)).quantize(_MONEY) if with_pnl else None
        ),
        expectancy_r=(
            _round4(sum(r_values) / len(r_values)) if r_values else None
        ),
        win_rate=_round4(wins / len(with_pnl)) if with_pnl else None,
        profit_factor=_profit_factor(pnls),
        avg_win_currency=(
            (gross_profit / wins).quantize(_MONEY) if wins else None
        ),
        avg_loss_currency=(
            (gross_loss / losses).quantize(_MONEY) if losses else None
        ),
        mfe_r=(
            _round4(sum(mfe_values) / len(mfe_values)) if mfe_values else None
        ),
        mae_r=(
            _round4(sum(mae_values) / len(mae_values)) if mae_values else None
        ),
        slippage_currency=(
            sum(slippages, Decimal("0")).quantize(_MONEY) if slippages else None
        ),
        rejection_cost_return=rejection_cost,
        drawdown_currency=_max_drawdown(pnls),
        drawdown_share=None,
        traded=counts.get(SELF_EVAL_TRADED, 0),
        rejected=counts.get(SELF_EVAL_REJECTED, 0),
        expired=counts.get(SELF_EVAL_EXPIRED, 0),
        missed=counts.get(SELF_EVAL_MISSED, 0),
        sample_quality=sample_quality_from_n(trades),
        results_measurement=results_measurement,
        risk_measurement=risk_measurement,
        excursions_measurement=excursions_measurement,
        slippage_measurement=slippage_measurement,
        rejection_cost_measurement=rejection_cost_measurement,
        drawdown_measurement=drawdown_measurement,
        decisive=(
            trades >= max(1, min_trades)
            and results_measurement == MEASUREMENT_COMPLETE
        ),
        notes=tuple(dict.fromkeys(notes)),
    )
