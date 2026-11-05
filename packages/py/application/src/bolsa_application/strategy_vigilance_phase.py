"""V2.25 / A10 — vigilancia de la estrategia ACTIVA (StrategyHealth).

Evalúa la salud de una estrategia ACTIVE a partir de sus métricas de edge/robustez
(``edge``, ``walk_forward_efficiency``, ``dsr``, ``credibility``) contra umbrales y
decide:

* **healthy** → la estrategia sigue en AUTO.
* **degraded** → se dispara re-LABORATORIO; **nunca** un swap directo de la activa
  por otra del LAB (regla anti strategy-chasing, auditoría V2.24 §20).

Determinista y sin DB/red: el orquestador (V2.26) persiste los snapshots y arranca
el re-LAB cuando esta fase lo pide.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    StrategyHealth,
    StrategyLifecycleState,
)

__all__ = [
    "DECISION_CONTINUE",
    "DECISION_RELAB",
    "EVIDENCE_FOREIGN_VERSION",
    "EVIDENCE_STALE",
    "EVIDENCE_UNDATED",
    "HealthThresholds",
    "VigilanceDecision",
    "evaluate_active_health",
]


DECISION_CONTINUE = "continue"
DECISION_RELAB = "relab"


@dataclass(frozen=True, slots=True)
class HealthThresholds:
    """Umbrales de degradación de la estrategia activa (fail-safe: conservadores).

    Los cuatro primeros son *predictivos* (del LAB). Los cuatro últimos son *observados*
    (ejecución SIM real; V2.28 / A10): su semántica es distinta y **nunca** degradan por
    debajo de ``min_observed_trades`` round-trips cerrados (guarda de muestra mínima).

    V2.32.1 (auditoría): los umbrales *predictivos* usan ``None`` = "sin configurar",
    igual que los observados. Un ``0.0`` real fingiría una decisión que nadie tomó
    (una estrategia con ``credibility=0.02`` no debería pasar como sana por defecto);
    con ``None`` ese indicador no degrada por su ausencia, pero tampoco inventa un cero.

    Nota sobre el drawdown observado: se expresa en magnitud positiva (p. ej. ``20`` = 20%
    de caída) y su umbral es un TECHO. La comparación con signo correcto la resuelve
    ``StrategyHealth._observed_degraded``; aquí solo se declara el valor.
    """

    min_edge: float | None = None
    min_wfe: float | None = None
    min_dsr: float | None = None
    min_credibility: float | None = None
    # --- Umbrales observados (V2.28 / A10) ---
    min_observed_trades: int = 10
    min_observed_return_pct: float | None = None
    max_observed_drawdown_pct: float | None = None
    min_observed_win_rate: float | None = None
    min_observed_profit_factor: float | None = None
    # S7: con ``True`` un indicador con umbral configurado pero SIN medición degrada
    # (``<metric>_unmeasured``). Default ``True`` (fail-closed): una métrica ausente no
    # es salud. Se puede apagar explícitamente (``fail_on_unmeasured=False``) para
    # reproducir la ruta histórica, y la decisión declara ``unmeasured`` en ambos casos.
    fail_on_unmeasured: bool = True
    # S7: TTL de frescura de la evidencia *predictiva* (la del LAB que sostiene la
    # activa). ``None`` = TTL sin configurar: la edad se mide y se declara, pero no
    # degrada. Con TTL, una evidencia más vieja degrada (re-LAB), porque una métrica
    # caducada no describe la estrategia que está operando hoy.
    max_metric_age_days: float | None = None
    # Con ``True`` (default) la evidencia caducada degrada; con ``False`` solo se declara
    # (``stale``) y la decisión sigue siendo ``continue``.
    fail_on_stale: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, float]:
        """Umbrales persistibles en el snapshot de salud.

        Los ``None`` se omiten: un umbral no configurado no debe viajar como 0 (que
        activaría una degradación por defecto no intencionada). Aplica a predictivos y
        observados por igual (V2.32.1: misma filosofía en ambos bloques).
        """
        out: dict[str, float] = {
            "min_observed_trades": float(self.min_observed_trades),
        }
        if self.min_edge is not None:
            out["edge"] = self.min_edge
        if self.min_wfe is not None:
            out["walk_forward_efficiency"] = self.min_wfe
        if self.min_dsr is not None:
            out["dsr"] = self.min_dsr
        if self.min_credibility is not None:
            out["credibility"] = self.min_credibility
        if self.min_observed_return_pct is not None:
            out["observed_return_pct"] = self.min_observed_return_pct
        if self.max_observed_drawdown_pct is not None:
            out["observed_max_drawdown_pct"] = self.max_observed_drawdown_pct
        if self.min_observed_win_rate is not None:
            out["observed_win_rate"] = self.min_observed_win_rate
        if self.min_observed_profit_factor is not None:
            out["observed_profit_factor"] = self.min_observed_profit_factor
        if self.max_metric_age_days is not None:
            out["max_metric_age_days"] = self.max_metric_age_days
        return out


@dataclass(frozen=True, slots=True)
class VigilanceDecision:
    """Decisión de vigilancia: seguir en AUTO o disparar re-LAB (nunca swap directo).

    S7: distingue cuatro estados de evidencia. La precedencia de ``health_state`` es
    ``degraded`` > ``stale`` > ``unmeasured`` > ``healthy``: una métrica ausente o
    caducada **nunca** se reporta como salud.
    """

    version_id: str
    decision: str
    degraded: bool
    breaches: tuple[str, ...] = ()
    health: StrategyHealth | None = None
    unmeasured: tuple[str, ...] = ()
    # S7: códigos de evidencia no fresca (``evidencia_caducada``,
    # ``evidencia_sin_fecha``, ``evidencia_de_otra_version``).
    stale: tuple[str, ...] = ()
    # S7: edad (en días) de la evidencia predictiva declarada; ``None`` si no se puede
    # medir (sin fecha) o si no hay TTL configurado ni evidencia predictiva.
    metrics_age_days: float | None = None

    @property
    def health_state(self) -> str:
        """``degraded`` / ``stale`` / ``unmeasured`` / ``healthy``: falta o vejez no es salud."""
        if self.degraded:
            return "degraded"
        if self.stale:
            return "stale"
        return "unmeasured" if self.unmeasured else "healthy"

    @property
    def relab(self) -> bool:
        return self.decision == DECISION_RELAB

    @property
    def target_state(self) -> StrategyLifecycleState | None:
        """Estado al que transiciona la estrategia activa (DEGRADED ⇒ vuelve al LAB)."""
        return StrategyLifecycleState.DEGRADED if self.degraded else None


def evaluate_active_health(
    *,
    version_id: str,
    as_of: str,
    metrics: Mapping[str, Any],
    thresholds: HealthThresholds | None = None,
    metrics_as_of: str | None = None,
    metrics_version_id: str | None = None,
    now: datetime | None = None,
) -> VigilanceDecision:
    """Evalúa la salud de la activa y decide continuar o re-LAB.

    Cualquier indicador conocido por debajo de su umbral ⇒ ``degraded`` ⇒ re-LAB.
    Falta de un indicador NO se inventa: se declara en ``unmeasured`` y, con
    ``fail_on_unmeasured`` (default), degrada.

    S7 — frescura. La evidencia *predictiva* (``edge``/``wfe``/``dsr``/``credibility``)
    es del LAB: no se re-mide cada ciclo, así que lo que caduca es la evidencia que
    sostiene la activa. Con ``thresholds.max_metric_age_days`` se exige:

    * una fecha de medición (``metrics_as_of`` o ``metrics["metrics_as_of"]``): sin ella
      la evidencia es ``evidencia_sin_fecha`` — no se asume fresca;
    * que esa fecha sea de ESTA versión (``metrics_version_id``): una métrica de otra
      versión es ``evidencia_de_otra_version``; y
    * que su edad no supere el TTL: ``evidencia_caducada``.

    ``now`` se inyecta en tests; sin él se usa el reloj UTC solo cuando hay TTL. El
    bloque *observado* no caduca por este TTL: se re-calcula de los fills de la versión
    en cada pasada y su decisividad la gobierna ``min_observed_trades``; la frescura del
    *dato* que alimenta la ejecución la guardan ``signal_stale``/``data_stale`` aguas
    arriba, no este módulo.
    """
    th = thresholds or HealthThresholds()
    edge = _num(metrics.get("edge"))
    if edge is None:
        # El LAB publica el edge del campeón como ``robust_score`` (= ``oos_score`` o
        # ``is_score`` si no hay OOS). Sin este alias, ``min_edge`` nunca se aplicaría:
        # el indicador estaría siempre "sin medir" aunque el LAB sí lo midió.
        edge = _num(metrics.get("robust_score"))
    wfe = _num(metrics.get("walk_forward_efficiency") or metrics.get("wfe"))
    dsr = _num(metrics.get("dsr"))
    credibility = _num(metrics.get("credibility"))
    observed_trades = _int(metrics.get("observed_trades"))

    health = StrategyHealth(
        version_id=version_id,
        as_of=as_of,
        edge=edge,
        walk_forward_efficiency=wfe,
        dsr=dsr,
        credibility=credibility,
        thresholds=th.as_dict(),
        # V2.28 / A10: bloque observado (ejecución SIM real atribuida a la versión).
        observed_return_pct=_num(metrics.get("observed_return_pct")),
        observed_max_drawdown_pct=_num(metrics.get("observed_max_drawdown_pct")),
        observed_win_rate=_num(metrics.get("observed_win_rate")),
        observed_profit_factor=_num(metrics.get("observed_profit_factor")),
        observed_trades=observed_trades,
    )

    breaches: list[str] = []
    if th.min_edge is not None and edge is not None and edge < th.min_edge:
        breaches.append("edge")
    if th.min_wfe is not None and wfe is not None and wfe < th.min_wfe:
        breaches.append("walk_forward_efficiency")
    if th.min_dsr is not None and dsr is not None and dsr < th.min_dsr:
        breaches.append("dsr")
    if (
        th.min_credibility is not None
        and credibility is not None
        and credibility < th.min_credibility
    ):
        breaches.append("credibility")
    # Degradación observada: se delega en la entidad, que aplica la guarda de muestra
    # mínima y la semántica de techo del drawdown. Si degrada por observado, se registran
    # los motivos concretos para que el snapshot sea auditable.
    if health.observed_degraded:
        breaches.extend(_observed_breaches(health, th))

    unmeasured = _unmeasured_metrics(health, th)
    if th.fail_on_unmeasured:
        # Solo los *predictivos* degradan por ausencia. En el bloque observado la
        # ausencia es legítima (aún no hay round-trips cerrados) y su decisividad la
        # gobierna ``min_observed_trades``: degradar ahí sería castigar a una estrategia
        # joven por no haber operado todavía.
        breaches.extend(f"{name}_unmeasured" for name in _unmeasured_predictive(th, health))

    stale, metrics_age_days = _evidence_freshness(
        version_id=version_id,
        health=health,
        th=th,
        metrics_as_of=metrics_as_of or _text(metrics.get("metrics_as_of")),
        metrics_version_id=metrics_version_id or _text(metrics.get("metrics_version_id")),
        now=now,
    )
    if th.fail_on_stale:
        breaches.extend(stale)

    degraded = bool(breaches)
    return VigilanceDecision(
        version_id=version_id,
        decision=DECISION_RELAB if degraded else DECISION_CONTINUE,
        degraded=degraded,
        breaches=tuple(breaches),
        health=health,
        unmeasured=unmeasured,
        stale=stale,
        metrics_age_days=metrics_age_days,
    )


EVIDENCE_STALE = "evidencia_caducada"
EVIDENCE_UNDATED = "evidencia_sin_fecha"
EVIDENCE_FOREIGN_VERSION = "evidencia_de_otra_version"

# Formatos compactos que produce la traza del AUTO (``_new_cycle_id``):
# ``20261105T091200Z-abcd1234`` / ``20261105T091200``.
_COMPACT_INSTANTS = (("%Y%m%dT%H%M%SZ", 16), ("%Y%m%dT%H%M%S", 15))


def _evidence_freshness(
    *,
    version_id: str,
    health: StrategyHealth,
    th: HealthThresholds,
    metrics_as_of: str | None,
    metrics_version_id: str | None,
    now: datetime | None,
) -> tuple[tuple[str, ...], float | None]:
    """Motivos de evidencia no fresca y edad (días) de la evidencia predictiva (S7).

    ``metricas_de_otra_version`` no depende del TTL: una métrica de otra versión no
    describe esta activa, se configure o no la caducidad. La edad solo se mide cuando
    hay TTL configurado — sin TTL no hay política que comparar, pero la fecha sigue
    siendo exigible en cuanto el operador la configura.
    """
    if metrics_version_id is not None and metrics_version_id != version_id:
        return (EVIDENCE_FOREIGN_VERSION,), None
    if th.max_metric_age_days is None:
        return (), None
    has_evidence = any(
        value is not None
        for value in (
            health.edge,
            health.walk_forward_efficiency,
            health.dsr,
            health.credibility,
            health.observed_trades,
            health.observed_return_pct,
            health.observed_max_drawdown_pct,
            health.observed_win_rate,
            health.observed_profit_factor,
        )
    )
    if not has_evidence:
        # Sin nada que medir no hay caducidad: la falta de medida la declara
        # ``unmeasured``. Inventar un ``sin_fecha`` aquí duplicaría el motivo.
        return (), None
    instant = _parse_instant(metrics_as_of)
    if instant is None:
        # Con TTL configurado, una evidencia sin fecha NO se asume fresca.
        return (EVIDENCE_UNDATED,), None
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    age_days = round((clock - instant).total_seconds() / 86400.0, 3)
    if age_days > th.max_metric_age_days:
        return (EVIDENCE_STALE,), age_days
    return (), age_days


def _parse_instant(raw: str | None) -> datetime | None:
    """Parsea una marca temporal de la traza (ISO o ``YYYYMMDDTHHMMSSZ``); ``None`` si no."""
    text = (raw or "").strip()
    if not text:
        return None
    iso = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        parsed = None
    if parsed is not None:
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    for fmt, size in _COMPACT_INSTANTS:
        try:
            return datetime.strptime(text[:size], fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _text(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _unmeasured_predictive(th: HealthThresholds, health: StrategyHealth) -> tuple[str, ...]:
    """Indicadores predictivos con umbral configurado y valor ausente (S7).

    Es el subconjunto que **degrada** con ``fail_on_unmeasured``. El bloque observado
    queda fuera a propósito: su ausencia significa «aún no hay muestra», no «feed roto»,
    y ya está gobernado por ``min_observed_trades``.
    """
    checks = (
        ("edge", th.min_edge, health.edge),
        ("walk_forward_efficiency", th.min_wfe, health.walk_forward_efficiency),
        ("dsr", th.min_dsr, health.dsr),
        ("credibility", th.min_credibility, health.credibility),
    )
    return tuple(
        name for name, threshold, value in checks if threshold is not None and value is None
    )


def _unmeasured_metrics(health: StrategyHealth, th: HealthThresholds) -> tuple[str, ...]:
    """Indicadores DECLARADOS como no medidos (umbral configurado y valor ausente).

    Cubre las dos familias: es información para el snapshot/decisión, no el conjunto que
    degrada (ese es ``_unmeasured_predictive``).
    """
    checks = (
        ("edge", th.min_edge, health.edge),
        ("walk_forward_efficiency", th.min_wfe, health.walk_forward_efficiency),
        ("dsr", th.min_dsr, health.dsr),
        ("credibility", th.min_credibility, health.credibility),
        ("observed_return_pct", th.min_observed_return_pct, health.observed_return_pct),
        (
            "observed_max_drawdown_pct",
            th.max_observed_drawdown_pct,
            health.observed_max_drawdown_pct,
        ),
        ("observed_win_rate", th.min_observed_win_rate, health.observed_win_rate),
        ("observed_profit_factor", th.min_observed_profit_factor, health.observed_profit_factor),
    )
    return tuple(name for name, threshold, value in checks if threshold is not None and value is None)


def _observed_breaches(health: StrategyHealth, th: HealthThresholds) -> list[str]:
    """Motivos concretos de la degradación observada (auditoría del snapshot)."""
    out: list[str] = []
    if (
        th.min_observed_return_pct is not None
        and health.observed_return_pct is not None
        and health.observed_return_pct < th.min_observed_return_pct
    ):
        out.append("observed_return_pct")
    if (
        th.max_observed_drawdown_pct is not None
        and health.observed_max_drawdown_pct is not None
        and health.observed_max_drawdown_pct > th.max_observed_drawdown_pct
    ):
        out.append("observed_max_drawdown_pct")
    if (
        th.min_observed_win_rate is not None
        and health.observed_win_rate is not None
        and health.observed_win_rate < th.min_observed_win_rate
    ):
        out.append("observed_win_rate")
    if (
        th.min_observed_profit_factor is not None
        and health.observed_profit_factor is not None
        and health.observed_profit_factor < th.min_observed_profit_factor
    ):
        out.append("observed_profit_factor")
    return out


def _num(raw: Any) -> float | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _int(raw: Any) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    return None
