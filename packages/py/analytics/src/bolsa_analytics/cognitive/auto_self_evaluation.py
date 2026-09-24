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
* **embudo**: ``traded``/``rejected``/``expired``/``missed`` con sus motivos;
* **régimen** (``AUTO-9``): el mismo material cruzado por estado de mercado
  (``by_regime``), porque una esperanza agregada mezcla regímenes que no se parecen. El
  régimen **ausente** es un cubo propio (``UNKNOWN``): no se reparte ni se hereda.

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
from enum import StrEnum
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
from bolsa_analytics.cognitive.portfolio_reservation import coerce_trading_cost

__all__ = [
    "AUTO_SELF_EVALUATION_KEY",
    "SELF_EVAL_FUNNEL_NOT_DIMENSIONED",
    "SELF_EVAL_MIN_TRADES_DEFAULT",
    "SELF_EVAL_OPPORTUNITY_STATUSES",
    "SELF_EVAL_COST_BASIS_APPLIED",
    "SELF_EVAL_COST_BASIS_ESTIMATED",
    "SELF_EVAL_COST_BASIS_MIXED",
    "SELF_EVAL_COST_BASIS_UNDECLARED",
    "SELF_EVAL_COST_MODEL_MIXED",
    "SELF_EVAL_COST_MODEL_UNDECLARED",
    "SELF_EVAL_REGIME_UNDETERMINED",
    "SELF_EVAL_REGIME_UNKNOWN",
    "AutoSelfEvaluation",
    "CycleR",
    "NetRBasis",
    "NetRBasisSeries",
    "StrategyRegimeEvaluation",
    "StrategySelfEvaluation",
    "aggregate_by_regime",
    "affirms_declared_net_r_basis",
    "cycle_r",
    "declared_regime",
    "evaluate_auto_self_evaluation",
    "single_decisive_regime",
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
SELF_EVAL_PNL_UNMEASURED = "pnl_unmeasured"
SELF_EVAL_COST_UNMEASURED = "cost_unmeasured"
# AUTO-16 — la BASE del coste con la que se calculó el R neto. El neto es un cociente contra un
# coste, y ese coste puede venir de DOS modelos distintos (el aplicado por el simulador y el
# supuesto por el decisor): sin declarar la base, dos netos con el mismo aspecto podrían no ser
# comparables. ``MIXED`` no es un error: es la declaración de que un agregado mezcla las dos.
class NetRBasis(StrEnum):
    """(AUTO-18, §16) vocabulario CERRADO de las bases declarables del R neto.

    El enum cierra el conjunto sin mover un byte del JSON: sus valores son EXACTAMENTE los
    strings que ya viajan en ``netRBasis``/``net_r_basis`` (y ``str`` ⇒ ``json.dumps`` los
    serializa idénticos). Las constantes ``SELF_EVAL_COST_BASIS_*`` siguen siendo la casa del
    literal para los consumidores; el enum existe para que un agregado no pueda declarar una base
    que no esté en el conjunto.

    * :attr:`APPLIED` — el neto descontó la fricción que el simulador **aplicó** (más la comisión
      del modelo; el schedule no la cobra, así que dejarla fuera lo haría parecer mejor).
    * :attr:`ESTIMATED` — el neto descontó el coste que el decisor **supuso**.
    * :attr:`MIXED` — el agregado mezcla bases (heterogeneidad INTERNA de una población).
    * :attr:`UNDECLARED` — hay netos pero las filas no declaran de dónde salió el coste.
    """

    ESTIMATED = "estimated"
    APPLIED = "applied_friction+modelled_commission"
    MIXED = "mixed"
    UNDECLARED = "undeclared"


SELF_EVAL_COST_BASIS_APPLIED = NetRBasis.APPLIED.value
SELF_EVAL_COST_BASIS_ESTIMATED = NetRBasis.ESTIMATED.value
SELF_EVAL_COST_BASIS_MIXED = NetRBasis.MIXED.value
#: El agregado tiene netos pero sus filas no declaran de dónde salió el coste (p.ej. un informe
#: AUTO-7 cuyos ciclos ya traían el R neto calculado fuera). Se declara, no se supone.
SELF_EVAL_COST_BASIS_UNDECLARED = NetRBasis.UNDECLARED.value
# AUTO-18 — la VERSIÓN del modelo de coste (``cm:<preset|bps>:c/s/l/g``). Es el METRO del neto:
# dos netos medidos con modelos distintos no son comparables aunque los dos se llamen "coste".
#: Distintas versiones de modelo conviven en un agregado: no se promedian como si fueran una.
SELF_EVAL_COST_MODEL_MIXED = "mixed"
#: Hay netos pero sus filas no declaran la versión del modelo (histórico anterior a la fase):
#: el metro NO se puede reconstruir, así que se declara en vez de afirmarlo.
SELF_EVAL_COST_MODEL_UNDECLARED = "undeclared"
# AUTO-9 — el cruce ``strategy × regime``. El régimen **ausente** no se reparte ni se suma al
# de otro ciclo: tiene cubo PROPIO. ``UNKNOWN`` es aquí un valor de agrupación, no un hueco
# por rellenar.
SELF_EVAL_REGIME_UNKNOWN = "UNKNOWN"
SELF_EVAL_REGIME_UNDETERMINED = "regime_undetermined"
SELF_EVAL_FUNNEL_NOT_DIMENSIONED = "funnel_not_dimensioned_by_regime"

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


def _modelled_commission(cost: Any) -> Decimal | None:
    """(PURA, AUTO-16) la comisión del MODELO que completa el neto aplicado, o ``None``.

    El schedule del simulador **no cobra comisión** (en SIM la comisión realizada es ``0``:
    ``lifecycle_from_auto`` la declara así en los fills con ``fill_id``), así que un neto que
    descontara solo la fricción aplicada saldría más alto que el estimado por un motivo que no
    es una mejor ejecución, sino una parte del coste que se dejó fuera. Se completa con la
    comisión **estimada** del decisor —la única que existe— y la base lo declara.

    ``None`` cuando no se puede cuantificar: sin comisión no se puede componer el número y el
    neto vuelve al estimado completo (declarado), en vez de publicar un neto al que le falta
    una parte del coste.
    """
    return None if cost is None else _dec(_field(cost, "commission"))


def _applied_friction(applied: Any) -> Decimal | None:
    """(PURA, AUTO-16) la fricción aplicada **COMPLETA** de un ciclo, o ``None``.

    Lee el contrato de ``applied_cost.AppliedCost`` por sus dos hechos —``measurement`` y
    ``friction``—, sin acoplarse al dataclass (el mismo módulo sirve al worker, al journal y a
    un test). Regla dura: un aplicado ``PARTIAL`` es un SUELO (le faltan patas o referencias),
    así que **no** entra al cociente —restarlo sobrestimaría el neto—; y sin ``friction`` no hay
    número que restar. En los dos casos el hueco lo declara quien lee la base, no este helper.
    """
    if applied is None:
        return None
    if _field(applied, "measurement") != MEASUREMENT_COMPLETE:
        return None
    return _dec(_field(applied, "friction"))


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
    net_r_multiple: float | None
    regime: str
    mfe_r: float | None
    mae_r: float | None
    slippage: Decimal | None
    closed_at: str | None
    #: AUTO-16: la base del coste con la que salió ``net_r_multiple`` (``applied``/``estimated``).
    #: ``None`` cuando el neto no se calculó aquí o su fila no declara de dónde salió el coste:
    #: la ausencia de base NO se hereda de otro ciclo ni se supone.
    cost_basis: str | None = None
    #: AUTO-18: la VERSIÓN del modelo de coste del ciclo (``cm:<preset|bps>:...``), o ``None`` si
    #: su fila no la declara. La ausencia del metro NO se reconstruye ni se hereda: se declara.
    cost_model_version: str | None = None


def _regime(value: Any) -> str:
    """Régimen de mercado declarado por el ciclo, o el cubo ``UNKNOWN``.

    ``UNKNOWN`` **es un cubo propio** del cruce ``strategy × regime``: un ciclo sin régimen
    declarado —o que se declara literalmente ``unknown``, en cualquier caja— se agrupa con
    los demás sin régimen. Nunca se le atribuye el régimen de otro ciclo ni se suma a otro
    cubo, porque eso sería afirmar un cruce que nadie midió.
    """
    text = _explicit(value)
    if text is None or text.upper() == SELF_EVAL_REGIME_UNKNOWN:
        return SELF_EVAL_REGIME_UNKNOWN
    return text


def _read_cycle(raw: Any) -> _Cycle:
    """Normaliza una fila de ciclo (dict u objeto) sin inventar ningún campo ausente.

    El R se **lee** cuando la fila ya lo declara —es una medida hecha por su productor, y
    sobrescribirla sería desconfiar de un dato que sí se midió— y, si no, se **calcula** con
    el riesgo y el coste que la fila declare (``AUTO-9``). Así el mismo módulo sirve al
    informe AUTO-7, que recibe el R ya medido, y al productor por ciclo del ``v2.50``, que
    solo tiene el material en crudo.
    """
    nested_mfe = _field(raw, "mfe_mae", "mfeMae")
    mfe = _num(_field(raw, "mfe_r", "mfeR"))
    mae = _num(_field(raw, "mae_r", "maeR"))
    if nested_mfe is not None:
        mfe = mfe if mfe is not None else _num(_field(nested_mfe, "mfeR", "mfe_r"))
        mae = mae if mae is not None else _num(_field(nested_mfe, "maeR", "mae_r"))
    cycle_id = _explicit(_field(raw, "cycle_id", "cycleId"))
    signal_id = _explicit(_field(raw, "signal_id", "signalId"))
    pnl = _dec(_field(raw, "pnl", "realized_pnl", "realizedPnl", "pnl_currency"))
    declared_r = _num(_field(raw, "r_multiple", "rMultiple", "r"))
    declared_net = _num(_field(raw, "net_r_multiple", "netRMultiple", "netR"))
    computed: CycleR | None = None
    if declared_r is None or declared_net is None:
        computed = cycle_r(
            pnl=pnl,
            risk_amount=_field(raw, "risk_amount", "riskAmount", "reserved_risk", "reservedRisk"),
            cost=_field(raw, "cost", "trading_cost", "tradingCost"),
            # AUTO-16: la fricción que el simulador APLICÓ (``costApplied``), si el productor
            # la midió. Entra al cociente SOLO si está COMPLETE; el estimado queda de respaldo.
            cost_applied=_field(raw, "cost_applied", "costApplied"),
            # AUTO-18: la versión del modelo de coste, si la fila la declara (o el propio coste).
            cost_model_version=_field(raw, "cost_model_version", "costModelVersion"),
        )
    # La base se DECLARA, no se hereda: si el neto vino calculado de fuera, solo se cree si la
    # fila la declara; si no, queda sin base (``None``) y el agregado lo dirá.
    declared_basis = _explicit(_field(raw, "cost_basis", "costBasis"))
    basis = computed.cost_basis if computed is not None else None
    basis = basis or declared_basis
    # AUTO-18: el metro se declara o se lee del coste; nunca se reconstruye desde los bps de hoy.
    declared_version = _explicit(_field(raw, "cost_model_version", "costModelVersion"))
    version = computed.cost_model_version if computed is not None else None
    version = version or declared_version
    measured_r = declared_r if declared_r is not None else _computed_r(computed, net=False)
    measured_net = declared_net if declared_net is not None else _computed_r(computed, net=True)
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
        pnl=pnl,
        r_multiple=measured_r,
        net_r_multiple=measured_net,
        regime=_regime(_field(raw, "regime", "marketRegime", "market_regime")),
        mfe_r=mfe,
        mae_r=mae,
        slippage=_dec(_field(raw, "slippage", "slippage_currency", "slippageCurrency")),
        closed_at=_explicit(_field(raw, "closed_at", "closedAt")),
        cost_basis=basis,
        cost_model_version=version,
    )


def _computed_r(computed: CycleR | None, *, net: bool) -> float | None:
    """El R calculado (o el neto) de un ``CycleR``; ``None`` si no se pudo calcular."""
    if computed is None:
        return None
    return computed.net_r_multiple if net else computed.r_multiple


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


# ── AUTO-9 — el R de un ciclo (adimensional: medido, o declarado ausente) ───────────


def _ratio(numerator: Decimal, denominator: Decimal) -> float | None:
    """Cociente adimensional a 4 decimales; ``None`` si no es un número utilizable.

    El denominador es un RIESGO: ``0`` o negativo **no divide**, y no se sustituye por
    ``0`` — un R de cero afirmaría "no pasó nada", que es una conclusión que nadie ha
    medido. Tampoco se deja escapar un ``inf``: "riesgo gratis" no es un resultado.
    """
    if denominator <= 0:
        return None
    try:
        quotient = numerator / denominator
    except (InvalidOperation, ZeroDivisionError):
        return None
    value = _num(quotient)
    return None if value is None else _round4(value)


@dataclass(frozen=True, slots=True)
class CycleR:
    """AUTO-9 — el R de UN ciclo: lo medido y lo que no se pudo medir, con su motivo.

    ``r_multiple`` es ``pnl / risk_amount`` y ``net_r_multiple`` es
    ``(pnl − coste) / risk_amount``. ``risk_amount`` y el coste usado se publican junto al
    resultado porque son el **rastro de la división**: sin ellos, un R no es auditable.

    # AUTO-16 — el neto declara su BASE. El coste que descuenta el neto puede venir de dos
    # modelos distintos, y los dos se publican por separado para que la resta sea auditable:
    # ``cost_estimate`` es el que el **decisor supuso** (``TradingCost``) y ``cost_applied`` el
    # que el **simulador aplicó** (fricción medida contra el mid de referencia, sin comisión:
    # el schedule no la cobra). ``cost_basis`` dice qué entró en el cociente —nunca se adivina—
    # y, cuando el aplicado manda, **nombra su composición**: la fricción medida más la comisión
    # del modelo, porque un neto al que le falta esa parte parecería mejor sin serlo. Una base
    # sin número o un número sin base no se publican: son el mismo hueco declarado.
    """

    r_multiple: float | None
    net_r_multiple: float | None
    risk_amount: Decimal | None
    cost_estimate: Decimal | None
    measurement: MeasurementStatus
    notes: tuple[str, ...]
    #: AUTO-16: la fricción que el simulador APLICÓ, medida contra su mid de referencia. ``None``
    #: cuando no se midió (fila anterior a 2.57, o una pata sin referencia): nunca un ``0``. NO
    #: lleva la comisión dentro (el schedule no la cobra); la composición la declara ``cost_basis``.
    cost_applied: Decimal | None = None
    #: AUTO-16: la BASE del cociente —``applied_friction+modelled_commission`` / ``estimated``—,
    #: o ``None`` si no hubo neto. Es la mitad que impide que dos netos no comparables se lean
    #: como uno solo.
    cost_basis: str | None = None
    #: AUTO-18: la VERSIÓN del modelo de coste con que se midió el neto (``cm:<preset|bps>:...``),
    #: o ``None`` si la fila no la declara (histórico anterior a la fase). Es la otra mitad: con
    #: la base sola, dos netos ``estimated`` calculados con bps distintos seguirían pareciendo
    #: comparables y no lo son.
    cost_model_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "rMultiple": self.r_multiple,
            "netRMultiple": self.net_r_multiple,
            "riskAmount": None if self.risk_amount is None else str(self.risk_amount),
            "costEstimate": None if self.cost_estimate is None else str(self.cost_estimate),
            "costApplied": None if self.cost_applied is None else str(self.cost_applied),
            "costBasis": self.cost_basis,
            "costModelVersion": self.cost_model_version,
            "measurement": self.measurement,
            "notes": list(self.notes),
        }


def cycle_r(
    *,
    pnl: Any,
    risk_amount: Any,
    cost: Any = None,
    cost_applied: Any = None,
    cost_model_version: Any = None,
) -> CycleR:
    """(PURA) el R de un ciclo desde su PnL, su riesgo comprometido y su coste.

    ``pnl`` es el PnL **realizado** del ciclo, ``risk_amount`` el riesgo que se comprometió
    en la reserva (``reserved_risk``: el denominador que hace adimensional la medida) y
    ``cost`` el ``TradingCost`` estimado en la decisión, en su forma serializada
    (``to_dict()``) o ya reconstruido. Sin I/O, sin reloj, sin estado.

    Reglas duras — ninguna es negociable:

    * ``risk_amount`` ausente, ``0`` o negativo ⇒ **los dos** R son ``None`` y se declara
      ``risk_unmeasured``. Nunca ``0`` (diría "no pasó nada") ni ``inf`` (diría "riesgo
      gratis").
    * ``pnl`` ausente ⇒ ``None`` y ``pnl_unmeasured``: sin numerador no hay cociente.
    * ``cost`` ausente —o presente pero **incompleto**, con ``total`` sin cuantificar— ⇒
      ``net_r_multiple`` es ``None`` y se declara ``cost_unmeasured``. Un coste que no se
      pudo cerrar no se lee como coste cero: eso sería **regalar R**.
    * ``pnl == 0`` **sí** es una medida (``r_multiple = 0.0``, ``COMPLETE``): un resultado
      plano medido no es un hueco, y confundirlos es la mitad de este módulo.

    **AUTO-16 — dos costes, y la BASE declarada.** ``cost`` es el que el decisor **supuso**
    (estimado en el instante de la decisión); ``cost_applied`` es la fricción que el simulador
    **aplicó** (medida contra su mid de referencia, ``applied_cost``). Cuando el aplicado entra
    ``COMPLETE``, el cociente se hace contra ÉL **más la comisión del modelo** —el schedule no
    cobra comisión, y dejarla fuera sobrestimaría el neto— y
    ``cost_basis = "applied_friction+modelled_commission"``; si no, se hace contra el estimado
    y ``cost_basis = "estimated"``. Un aplicado ``PARTIAL`` **no** se usa: es un suelo, y restar
    un suelo sobrestimaría el neto. Los dos números se publican por separado para que la resta
    sea auditable, y la base evita que dos netos no comparables se lean como uno.

    **AUTO-18 — la VERSIÓN del modelo.** ``cost_model_version`` es el METRO del neto: la firma
    determinista del modelo de coste (``cm:<preset|bps>:c/s/l/g``). Se toma de la fila si la
    declara y, si no, del propio coste (``TradingCost.cost_model_version``); nunca se reconstruye
    desde los bps actuales, que podrían no ser los que midieron esta operación. Sin ella, dos
    netos ``estimated`` calculados con modelos distintos seguirían pareciendo comparables.
    """
    amount = _dec(pnl)
    risk = _dec(risk_amount)
    cost_row = coerce_trading_cost(cost)
    friction = None if cost_row is None else _dec(cost_row.total)
    applied = _applied_friction(cost_applied)
    commission = _modelled_commission(cost_row)

    notes: list[str] = []
    if risk is None or risk <= 0:
        notes.append(SELF_EVAL_RISK_UNMEASURED)
    if amount is None:
        notes.append(SELF_EVAL_PNL_UNMEASURED)

    r_multiple: float | None = None
    net_r_multiple: float | None = None
    cost_basis: str | None = None
    if amount is not None and risk is not None and risk > 0:
        r_multiple = _ratio(amount, risk)
        deducted: Decimal | None = None
        if applied is not None and commission is not None:
            # El aplicado entra CON la comisión del modelo, y la base lo declara en su nombre.
            deducted, cost_basis = applied + commission, SELF_EVAL_COST_BASIS_APPLIED
        elif friction is not None:
            deducted, cost_basis = friction, SELF_EVAL_COST_BASIS_ESTIMATED
        if deducted is None:
            notes.append(SELF_EVAL_COST_UNMEASURED)
        else:
            net_r_multiple = _ratio(amount - deducted, risk)

    valued = sum(1 for value in (r_multiple, net_r_multiple) if value is not None)
    # AUTO-18: la versión del modelo se DECLARA (fila) o se LEE del coste; nunca se inventa.
    version = _explicit(cost_model_version)
    if version is None and cost_row is not None:
        version = _explicit(cost_row.cost_model_version)
    return CycleR(
        r_multiple=r_multiple,
        net_r_multiple=net_r_multiple,
        risk_amount=risk,
        cost_estimate=friction,
        cost_applied=applied,
        cost_basis=cost_basis,
        cost_model_version=version,
        measurement=measurement_from_counts(valued=valued, unvalued=2 - valued),
        notes=tuple(notes),
    )


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
        counts[status] for status in (SELF_EVAL_REJECTED, SELF_EVAL_EXPIRED, SELF_EVAL_MISSED)
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
class NetRBasisSeries:
    """(AUTO-17) el R neto de UNA base de coste: su número y su muestra, SIN promediar con otra.

    La base del R neto es una dimensión estadística, no una etiqueta: dos netos medidos contra
    modelos de coste distintos (``estimated`` vs ``applied``) no son comparables. Cuando un
    agregado convive con las dos, el pooled **no se publica** (``net_expectancy_r = None``,
    ``net_r_basis = mixed``) y los números viven aquí, cada uno con su muestra y su base. Es la
    regla que impide que un cambio de base se lea como un cambio de rendimiento.

    ``n`` es el número de ciclos con R neto medido de esa base (el denominador de su media): sin
    él, la media de una serie no es auditable.
    """

    basis: str
    n: int
    expectancy_r: float | None
    #: AUTO-18: la VERSIÓN del modelo de coste de esta serie (``cm:<preset|bps>:...``), o
    #: ``undeclared`` si sus filas no la declaran. La agrupación es por ``(basis,
    #: cost_model_version)``, así que cada serie tiene **una sola** versión: un cambio de modelo
    #: **separa** series en vez de promediarlas, y por eso aquí ya no aparece ``mixed``.
    cost_model_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "basis": self.basis,
            "n": self.n,
            "expectancyR": self.expectancy_r,
            "costModelVersion": self.cost_model_version,
        }


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
    net_expectancy_r: float | None
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
    net_r_measurement: MeasurementStatus
    cycles_without_cost: int
    excursions_measurement: MeasurementStatus
    slippage_measurement: MeasurementStatus
    rejection_cost_measurement: MeasurementStatus
    drawdown_measurement: MeasurementStatus
    decisive: bool
    notes: tuple[str, ...]
    #: AUTO-16: la base del coste del R neto declarada por sus ciclos (``applied``/``estimated``),
    #: ``mixed`` si conviven las dos y ``undeclared`` si ninguna fila lo dice. ``None`` cuando no
    #: hay ningún neto que declarar, y también por defecto: una fila construida sin declararla NO
    #: afirma una base (el mismo trato que ``sinkFailuresDurable``: sin declaración, no se afirma).
    net_r_basis: str | None = None
    #: AUTO-17: el desglose del R neto POR POBLACIÓN (``NetRBasisSeries``), hoy ``(base,
    #: versión del modelo)``. Con una sola población tiene una entrada (idéntica al pooled); con
    #: bases distintas —o con metros distintos dentro de la misma base— una por población y el
    #: pooled queda ``None``. Defecto ``()``: una fila construida sin el campo NO afirma series.
    net_r_series: tuple[NetRBasisSeries, ...] = ()
    #: AUTO-18: la VERSIÓN del modelo de coste del neto agregado (``cm:<preset|bps>:...``),
    #: ``mixed`` si conviven metros distintos y ``undeclared`` si ninguna fila la declara. ``None``
    #: sin netos que declarar. Defecto ``None``: sin declaración no se afirma un metro.
    cost_model_version: str | None = None

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
            "netExpectancyR": self.net_expectancy_r,
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
            "netRMeasurement": self.net_r_measurement,
            "netRBasis": self.net_r_basis,
            "netRBasisSeries": [series.as_dict() for series in self.net_r_series],
            "costModelVersion": self.cost_model_version,
            "cyclesWithoutCost": self.cycles_without_cost,
            "excursionsMeasurement": self.excursions_measurement,
            "slippageMeasurement": self.slippage_measurement,
            "rejectionCostMeasurement": self.rejection_cost_measurement,
            "drawdownMeasurement": self.drawdown_measurement,
            "decisive": self.decisive,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class StrategyRegimeEvaluation:
    """AUTO-9 — una celda ``strategyVersion × régime`` del informe.

    El cruce existe para que la esperanza de una estrategia se **condicione** al estado de
    mercado en que se midió: una esperanza agregada mezcla regímenes que no se parecen, y
    decidir con ella es decidir con un promedio que nadie vivió.

    Dos cosas que esta celda **no** hace, y las declara en vez de disimularlas:

    * El embudo (``traded``/``rejected``/...) **no tiene dimensión de régimen** en el dato
      durable: por eso el informe publica ``funnel_not_dimensioned_by_regime``. El embudo
      sigue viviendo en ``byStrategy``, donde sí está medido.
    * ``regime == UNKNOWN`` es un cubo **propio**, no un comodín: agrupa los ciclos que no
      declaran régimen, y nadie hereda el régimen de otro ciclo.

    ``decisive`` exige que el R **bruto** esté medido en TODOS los ciclos de la celda y que
    la celda alcance ``min_trades``. **No** cubre el R neto: ``net_expectancy_r`` se publica
    con su propia medida (``net_r_measurement``) y su propia **base** (``net_r_basis``:
    ``applied``/``estimated``), así que quien decida con el neto **tiene que exigir**
    ``net_r_measurement == COMPLETE``. Mirar solo ``decisive`` leería como comparable un neto
    medido sobre la mitad de la celda. Es una bandera de lectura, nunca un permiso.
    """

    strategy_version: str
    regime: str
    cycles: int
    wins: int
    losses: int
    realized_pnl: Decimal
    expectancy_r: float | None
    net_expectancy_r: float | None
    win_rate: float | None
    cycles_without_risk: int
    cycles_without_cost: int
    r_measurement: MeasurementStatus
    net_r_measurement: MeasurementStatus
    sample_quality: str
    decisive: bool
    notes: tuple[str, ...]
    #: AUTO-16: la base del coste del neto de ESTA celda (``applied``/``estimated``/``mixed``/
    #: ``undeclared``), o ``None`` sin netos —y por defecto: sin declaración no se afirma base—.
    #: Es la mitad que impide leer como comparables dos netos medidos contra modelos distintos.
    net_r_basis: str | None = None
    #: AUTO-17: el desglose del R neto POR POBLACIÓN de la celda (mismo contrato que
    #: ``StrategySelfEvaluation.net_r_series``).
    net_r_series: tuple[NetRBasisSeries, ...] = ()
    #: AUTO-18: la VERSIÓN del modelo de coste del neto de la celda (mismo contrato que
    #: ``StrategySelfEvaluation.cost_model_version``: ``mixed``/``undeclared``/``None``).
    cost_model_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategyVersion": self.strategy_version,
            "regime": self.regime,
            "cycles": self.cycles,
            "wins": self.wins,
            "losses": self.losses,
            "realizedPnl": str(self.realized_pnl),
            "expectancyR": self.expectancy_r,
            "netExpectancyR": self.net_expectancy_r,
            "winRate": self.win_rate,
            "cyclesWithoutRisk": self.cycles_without_risk,
            "cyclesWithoutCost": self.cycles_without_cost,
            "rMeasurement": self.r_measurement,
            "netRMeasurement": self.net_r_measurement,
            "netRBasis": self.net_r_basis,
            "netRBasisSeries": [series.as_dict() for series in self.net_r_series],
            "costModelVersion": self.cost_model_version,
            "sampleQuality": self.sample_quality,
            "decisive": self.decisive,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class AutoSelfEvaluation:
    """Informe AUTO-7 completo: por estrategia + embudo + huecos de medición declarados."""

    by_strategy: tuple[StrategySelfEvaluation, ...]
    by_regime: tuple[StrategyRegimeEvaluation, ...]
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
    cycles_without_regime: int
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
            "byRegime": [row.as_dict() for row in self.by_regime],
            "cyclesWithoutRegime": self.cycles_without_regime,
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
        rows.append(_strategy_row(version, groups.get(version, ()), funnel, min_trades=min_trades))

    # AUTO-9 — el mismo material, cruzado por régimen. Las celdas se construyen sobre los
    # ciclos ATRIBUIBLES que ya pasaron por la deduplicación: el cruce no inventa filas ni
    # reparte las anónimas.
    regime_rows = _aggregate_by_regime(attributed, min_trades=min_trades)
    cycles_without_regime = sum(
        1 for cycle in attributed if cycle.regime == SELF_EVAL_REGIME_UNKNOWN
    )
    if regime_rows:
        notes.append(SELF_EVAL_FUNNEL_NOT_DIMENSIONED)

    total_dd = sum((row.drawdown_currency for row in rows), Decimal("0"))
    if total_dd > 0:
        # Cuota de drawdown sobre la SUMA de los drawdowns por estrategia: es un proxy
        # ADITIVO (los drawdowns de dos estrategias pueden solaparse en el tiempo), nunca
        # una atribución temporal. Se declara como tal.
        rows = [
            _with_share(row, share=_round4(float(row.drawdown_currency / total_dd))) for row in rows
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
        cycle for cycle in attributed if cycle.mfe_r is not None and cycle.mae_r is not None
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
        by_regime=regime_rows,
        cycles=len(unique_cycles),
        trades=total_trades,
        realized_pnl=total_pnl.quantize(_MONEY),
        expectancy_currency=((total_pnl / total_trades).quantize(_MONEY) if total_trades else None),
        expectancy_r=(_round4(sum(agg_r_values) / len(agg_r_values)) if agg_r_values else None),
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
        cycles_without_regime=cycles_without_regime,
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


def _net_r_series(cycles: Sequence[_Cycle]) -> tuple[NetRBasisSeries, ...]:
    """(PURA, AUTO-17/18) el R neto desglosado por POBLACIÓN, sin promediar entre poblaciones.

    Agrupa los ciclos con R neto medido por ``(base del coste, versión del modelo)`` —la base es
    ``estimated``/``applied``/``undeclared``— y devuelve, por población, su muestra ``n`` y su
    expectativa. El orden es determinista (por ``(base, versión)``) para que el desglose no
    dependa del orden de llegada de los ciclos.

    ``AUTO-18`` hizo la clave ``(basis, cost_model_version)``: la población es homogénea en los
    DOS ejes, así que un cambio de modelo **separa series** en vez de fundirlas en una media que
    ningún metro midió. Con un solo modelo por base —el caso normal— la partición es exactamente
    la de ``AUTO-17`` (mismo número, mismas series), y por eso las filas que no declaran el metro
    se agrupan en su propia serie ``undeclared``.

    La **suma publicada** (``_pooled_net_expectancy``) solo existe cuando hay UNA población: con
    dos metros conviviendo, promediar sus expectativas sería comparar peras con manzanas.
    """
    grouped: dict[tuple[str, str], list[_Cycle]] = {}
    for cycle in cycles:
        if cycle.net_r_multiple is None:
            continue
        basis = cycle.cost_basis or SELF_EVAL_COST_BASIS_UNDECLARED
        grouped.setdefault((basis, _cost_model_key(cycle)), []).append(cycle)
    return tuple(
        NetRBasisSeries(
            basis=basis,
            n=len(values),
            expectancy_r=_round4(
                sum(cycle.net_r_multiple for cycle in values if cycle.net_r_multiple is not None)
                / len(values)
            ),
            cost_model_version=model,
        )
        for (basis, model), values in sorted(grouped.items())
    )


def _cost_model_key(cycle: _Cycle) -> str:
    """(PURA, AUTO-18) la versión del modelo de un ciclo, con ``undeclared`` por ausencia."""
    return cycle.cost_model_version or SELF_EVAL_COST_MODEL_UNDECLARED


def _cost_model_of(versions: Sequence[str]) -> str | None:
    """(PURA, AUTO-18) la versión DECLARADA de un agregado a partir de sus versiones.

    ``None`` = no hay ningún neto que declarar. Una sola versión ⇒ esa; varias ⇒ ``mixed``
    (conviven metros distintos y promediarlos sería comparar peras con manzanas).
    """
    if not versions:
        return None
    unique = set(versions)
    if len(unique) == 1:
        return next(iter(unique))
    return SELF_EVAL_COST_MODEL_MIXED


def _basis_of(series: Sequence[NetRBasisSeries]) -> str | None:
    """(PURA) la base DECLARADA de un agregado a partir de su desglose.

    ``None`` = no hay ningún neto que declarar. Una sola base ⇒ esa; varias ⇒ ``mixed``.

    ``AUTO-18``: la cuenta es sobre las **bases distintas**, no sobre el número de series. Desde
    que la clave de agrupación es ``(basis, cost_model_version)``, varias series pueden compartir
    base y diferir en el modelo: la base sigue siendo única (no es ``mixed``) y lo que se declara
    como heterogéneo es la VERSIÓN del modelo (``costModelVersion = mixed`` en la fila).
    """
    if not series:
        return None
    bases = {row.basis for row in series}
    if len(bases) > 1:
        return SELF_EVAL_COST_BASIS_MIXED
    return series[0].basis


def affirms_declared_net_r_basis(
    *,
    net_r_measurement: MeasurementStatus,
    net_expectancy_r: float | None,
    net_r_basis: str | None,
) -> bool:
    """(PURA, ``AUTO-18``) invariante de dominio: un neto PUBLICADO declara su base (§18).

    ``net_r_measurement == COMPLETE`` con un ``net_expectancy_r`` no nulo solo es legible si la
    fila dice contra qué modelo de coste se midió. Un neto sin base es un número sin metro: si el
    predicado es ``False``, la confianza lo lee como ``DATA_DEGRADED`` (baja confianza declarada),
    NUNCA como estabilidad.

    Es vacuously ``True`` cuando no aplica (medición no completa, o sin neto publicado): el
    invariante habla de lo que se AFIRMA, no de lo que se calla. Construcciones manuales sin base
    no afirman base — este predicado es la forma en que un consumidor lo comprueba.
    """
    if net_r_measurement != MEASUREMENT_COMPLETE:
        return True
    if net_expectancy_r is None:
        return True
    return net_r_basis is not None


def _pooled_net_expectancy(
    series: Sequence[NetRBasisSeries], basis: str | None
) -> float | None:
    """(PURA, AUTO-17/18) la expectativa pooled del R neto, o ``None`` si la población no es una.

    Con UNA población (o ninguna) el número es el de siempre —la fila es byte a byte la de
    ``v2.56``—. Con bases distintas, o con **metros distintos dentro de la misma base**, el pooled
    **no se publica**: promediar dos modelos de coste como si fueran uno es exactamente el sesgo
    que ``AUTO-17``/``AUTO-18`` existen para impedir. Los números siguen disponibles, uno por
    población, en ``net_r_series``.
    """
    if basis == SELF_EVAL_COST_BASIS_MIXED:
        return None
    if len(series) != 1:
        # AUTO-18: dos series con la MISMA base pero distinto metro. La base no es mixta, la
        # población sí: no hay un número único que publicar (y no se elige uno de los dos).
        return None
    return series[0].expectancy_r


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
    net_values = [cycle.net_r_multiple for cycle in cycles if cycle.net_r_multiple is not None]
    excursions = [cycle for cycle in cycles if cycle.mfe_r is not None and cycle.mae_r is not None]
    mfe_values = [cycle.mfe_r for cycle in excursions if cycle.mfe_r is not None]
    mae_values = [cycle.mae_r for cycle in excursions if cycle.mae_r is not None]
    slippages = [cycle.slippage for cycle in cycles if cycle.slippage is not None]

    trades = len(cycles)
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    realized = sum(pnls, Decimal("0"))
    gross_profit = sum((pnl for pnl in pnls if pnl > 0), Decimal("0"))
    gross_loss = -sum((pnl for pnl in pnls if pnl < 0), Decimal("0"))

    results_measurement = (
        measurement_from_counts(valued=len(with_pnl), unvalued=trades - len(with_pnl))
        if cycles
        else MEASUREMENT_UNKNOWN
    )
    risk_measurement = measurement_from_counts(
        valued=len(r_values), unvalued=trades - len(r_values)
    )
    net_r_measurement = measurement_from_counts(
        valued=len(net_values), unvalued=trades - len(net_values)
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
    net_r_series = _net_r_series(cycles)
    net_r_basis = _basis_of(net_r_series)
    pooled_net_expectancy_r = _pooled_net_expectancy(net_r_series, net_r_basis)
    if pooled_net_expectancy_r is not None and net_r_basis is None:
        # Guarda del invariante (§18): un neto PUBLICADO no sale sin base. La base NO se
        # reconstruye desde los ciclos (no la declararon): se declara ``undeclared``, que es la
        # verdad, en vez de afirmar estabilidad que nadie firmó.
        net_r_basis = SELF_EVAL_COST_BASIS_UNDECLARED
    if cycles:
        # Los huecos se declaran SOLO cuando hay resultado que medir: en una versión sin
        # ningún ciclo, "R no medido" no aporta nada que "0 ciclos" no diga ya.
        if risk_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_RISK_UNMEASURED)
        if net_r_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_COST_UNMEASURED)
        if excursions_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_EXCURSIONS_UNMEASURED)
        if slippage_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_SLIPPAGE_UNMEASURED)
        if drawdown_measurement != MEASUREMENT_COMPLETE:
            notes.append(SELF_EVAL_DRAWDOWN_FLOOR)
        if net_r_basis == SELF_EVAL_COST_BASIS_MIXED:
            # El neto promedia bases distintas: el número sigue siendo útil, pero declararlo es
            # lo que evita que se lea como si viniera de un solo modelo de coste.
            notes.append(SELF_EVAL_COST_BASIS_MIXED)
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
        expectancy_currency=((realized / len(with_pnl)).quantize(_MONEY) if with_pnl else None),
        expectancy_r=(_round4(sum(r_values) / len(r_values)) if r_values else None),
        net_expectancy_r=pooled_net_expectancy_r,
        win_rate=_round4(wins / len(with_pnl)) if with_pnl else None,
        profit_factor=_profit_factor(pnls),
        avg_win_currency=((gross_profit / wins).quantize(_MONEY) if wins else None),
        avg_loss_currency=((gross_loss / losses).quantize(_MONEY) if losses else None),
        mfe_r=(_round4(sum(mfe_values) / len(mfe_values)) if mfe_values else None),
        mae_r=(_round4(sum(mae_values) / len(mae_values)) if mae_values else None),
        slippage_currency=(sum(slippages, Decimal("0")).quantize(_MONEY) if slippages else None),
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
        net_r_measurement=net_r_measurement,
        net_r_basis=net_r_basis,
        net_r_series=net_r_series,
        cost_model_version=_cost_model_of(
            [row.cost_model_version for row in net_r_series if row.cost_model_version is not None]
        ),
        cycles_without_cost=trades - len(net_values),
        excursions_measurement=excursions_measurement,
        slippage_measurement=slippage_measurement,
        rejection_cost_measurement=rejection_cost_measurement,
        drawdown_measurement=drawdown_measurement,
        decisive=(trades >= max(1, min_trades) and results_measurement == MEASUREMENT_COMPLETE),
        notes=tuple(dict.fromkeys(notes)),
    )


# ── AUTO-9 — el cruce strategy × regime ─────────────────────────────────────────────


def _aggregate_by_regime(
    cycles: Sequence[_Cycle],
    *,
    min_trades: int,
) -> tuple[StrategyRegimeEvaluation, ...]:
    """Celdas ``(strategyVersion, régime)`` de ciclos ya deduplicados y atribuibles."""
    cells: dict[tuple[str, str], list[_Cycle]] = {}
    for cycle in cycles:
        if not cycle.strategy_version:
            continue  # el cajón ``unattributed`` ya lo declara el informe entero
        cells.setdefault((cycle.strategy_version, cycle.regime), []).append(cycle)
    # Orden canónico: el cruce no depende del orden en que lleguen las filas.
    return tuple(
        _regime_row(version, regime, group, min_trades=min_trades)
        for (version, regime), group in sorted(cells.items())
    )


def aggregate_by_regime(
    cycles: Iterable[Any],
    *,
    min_trades: int = SELF_EVAL_MIN_TRADES_DEFAULT,
) -> tuple[StrategyRegimeEvaluation, ...]:
    """(PURA) el cruce ``strategyVersion × régime`` desde ciclos crudos.

    Es el mismo cruce que publica ``evaluate_auto_self_evaluation``, pero desde ciclos
    sueltos: lo usa el productor por ciclo del ``v2.50``, que no arma el informe entero. La
    deduplicación es la misma que la del informe, así que un ciclo **repetido** no infla
    ninguna celda, y los ciclos **sin versión** no se reparten. Sin I/O, sin reloj, sin
    estado.

    El tamaño de celda importa: una estrategia con 90 ciclos repartidos en 3 regímenes tiene
    celdas de 30, no una muestra de 90. Por eso ``min_trades`` se aplica **por celda**.
    """
    unique, _duplicates, _anonymous = _dedupe_cycles([_read_cycle(row) for row in cycles])
    return _aggregate_by_regime(unique, min_trades=min_trades)


def single_decisive_regime(
    cells: Sequence[StrategyRegimeEvaluation],
    version: str,
) -> str | None:
    """El régimen de ``version`` **si y solo si** hay exactamente una celda decisiva.

    Devuelve ``None`` si no hay ninguna celda decisiva, si hay más de una, o si la única
    decisiva es ``UNKNOWN``: en los tres casos el régimen **no está determinado**, y quien lo
    publique debe declararlo (``SELF_EVAL_REGIME_UNDETERMINED``) en vez de elegir uno. Una
    celda ``UNKNOWN`` decisiva no asciende a régimen: sigue significando "no se midió".
    """
    decisive = [
        cell
        for cell in cells
        if cell.strategy_version == version
        and cell.decisive
        and cell.regime != SELF_EVAL_REGIME_UNKNOWN
    ]
    if len(decisive) != 1:
        return None
    return decisive[0].regime


def declared_regime(
    cells: Sequence[StrategyRegimeEvaluation],
    version: str,
) -> tuple[str | None, str | None]:
    """El régimen de ``version`` **y la declaración de su hueco**, como un solo par.

    Devuelve ``(régimen, None)`` cuando hay exactamente una celda decisiva con régimen, y
    ``(None, SELF_EVAL_REGIME_UNDETERMINED)`` en cualquier otro caso. Quien publique el
    régimen de una estrategia publica **el par**: o el régimen, o el motivo por el que no
    hay. Nunca un régimen elegido entre varios candidatos.
    """
    regime = single_decisive_regime(cells, version)
    if regime is None:
        return None, SELF_EVAL_REGIME_UNDETERMINED
    return regime, None


def _regime_row(
    version: str,
    regime: str,
    cycles: Sequence[_Cycle],
    *,
    min_trades: int,
) -> StrategyRegimeEvaluation:
    """Agrega UNA celda y declara lo que no se pudo medir en ella, sin rellenarlo."""
    pnls = [cycle.pnl for cycle in cycles if cycle.pnl is not None]
    r_values = [cycle.r_multiple for cycle in cycles if cycle.r_multiple is not None]
    net_values = [cycle.net_r_multiple for cycle in cycles if cycle.net_r_multiple is not None]
    trades = len(cycles)
    wins = sum(1 for pnl in pnls if pnl > 0)
    losses = sum(1 for pnl in pnls if pnl < 0)
    r_measurement = measurement_from_counts(valued=len(r_values), unvalued=trades - len(r_values))
    net_measurement = measurement_from_counts(
        valued=len(net_values), unvalued=trades - len(net_values)
    )
    net_r_series = _net_r_series(cycles)
    net_r_basis = _basis_of(net_r_series)
    return StrategyRegimeEvaluation(
        strategy_version=version,
        regime=regime,
        cycles=trades,
        wins=wins,
        losses=losses,
        realized_pnl=sum(pnls, Decimal("0")).quantize(_MONEY),
        expectancy_r=(_round4(sum(r_values) / len(r_values)) if r_values else None),
        net_expectancy_r=_pooled_net_expectancy(net_r_series, net_r_basis),
        win_rate=_round4(wins / len(pnls)) if pnls else None,
        cycles_without_risk=trades - len(r_values),
        cycles_without_cost=trades - len(net_values),
        r_measurement=r_measurement,
        net_r_measurement=net_measurement,
        net_r_basis=net_r_basis,
        net_r_series=net_r_series,
        cost_model_version=_cost_model_of(
            [row.cost_model_version for row in net_r_series if row.cost_model_version is not None]
        ),
        sample_quality=sample_quality_from_n(trades),
        decisive=(trades >= max(1, min_trades) and r_measurement == MEASUREMENT_COMPLETE),
        notes=((SELF_EVAL_COST_UNMEASURED,) if net_measurement != MEASUREMENT_COMPLETE else ()),
    )
