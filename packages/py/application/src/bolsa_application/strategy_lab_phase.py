"""V2.25 / A10 — fases ESTUDIO y LABORATORIO del Strategy Lifecycle.

Glue puro/orquestable que reutiliza la infraestructura ya existente:

* **ESTUDIO** (``build_estudio_candidates``): convierte el universo resuelto por
  ``resolve_estudio_universe`` en ``StrategyCandidate`` reproducibles, sellando un
  ``data_snapshot_id`` (``bolsa_analytics.research.data_snapshot``). Distingue
  ``EMPTY`` (universo vacío, no es error) de ``UNAVAILABLE`` (no se pudo resolver ⇒
  no se inventan candidatas). No ejecuta nada: decide qué investigar.
* **LABORATORIO** (``evaluate_optimize_result``): traduce el resultado REAL de
  ``RunSmaGridOptimize`` (champion IS/OOS + walk-forward + CPCV + PBO + edge report)
  a los seis gates del Promotion Gate y a una ``StrategyEvaluation`` con score.

Sin IA, sin red y sin DB en estas funciones: son transformaciones deterministas que
la orquestación (V2.26) encadena. Fail-closed: si falta evidencia de un gate, ese
gate queda ``NOT_EVALUATED`` (que NO es PASS).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bolsa_domain.entities.strategy_lifecycle import (
    GateResult,
    GateStatus,
    StrategyCandidate,
    StrategyEvaluation,
)

__all__ = [
    "EstudioCandidatePlan",
    "build_estudio_candidates",
    "evaluate_optimize_result",
    "gate_from_metrics",
]


@dataclass(frozen=True, slots=True)
class EstudioCandidatePlan:
    """Resultado de la fase ESTUDIO: candidatas a investigar + estado del universo."""

    status: str
    candidates: tuple[StrategyCandidate, ...] = ()
    data_snapshot_id: str | None = None
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok" and bool(self.candidates)


def _family_for(family: str) -> str:
    """Normaliza una familia de estrategia conocida (best-effort, sin lanzar)."""
    try:
        from bolsa_application.optimize import normalize_strategy_family

        return normalize_strategy_family(family)
    except Exception:  # noqa: BLE001 — familia libre en ESTUDIO (se valida en LAB).
        return (family or "sma").strip().lower()


def build_estudio_candidates(
    *,
    resolution: Any,
    strategy_family: str,
    params: dict[str, Any],
    data_snapshot_id: str | None = None,
    candidate_id_factory: Any | None = None,
    preset_key: str | None = None,
    max_candidates: int | None = None,
) -> EstudioCandidatePlan:
    """Fase ESTUDIO: universo resuelto ⇒ candidatas reproducibles.

    ``resolution`` es el objeto de ``resolve_estudio_universe`` (con ``status`` e
    ``instrument_ids``). ``EMPTY``/``UNAVAILABLE`` se propagan sin inventar trabajo;
    ``OK`` produce una candidata por instrumento, con ``data_snapshot_id`` común para
    que el LABORATORIO sea reproducible.
    """
    status = str(getattr(resolution, "status", "") or "")
    if status != "ok":
        return EstudioCandidatePlan(status=status or "unavailable")

    raw_ids = getattr(resolution, "instrument_ids", None) or []
    instrument_ids = [str(i) for i in raw_ids if i]
    if not instrument_ids:
        return EstudioCandidatePlan(status="empty")
    if max_candidates is not None and max_candidates > 0:
        instrument_ids = instrument_ids[:max_candidates]

    family = _family_for(strategy_family)
    candidates: list[StrategyCandidate] = []
    for index, instrument_id in enumerate(instrument_ids):
        cid = (
            candidate_id_factory(instrument_id, index)
            if candidate_id_factory is not None
            else f"cand-{instrument_id}-{family}-{index}"
        )
        candidates.append(
            StrategyCandidate(
                id=str(cid),
                instrument_id=instrument_id,
                strategy_family=family,
                params=dict(params),
                origin="estudio",
                data_snapshot_id=data_snapshot_id,
                preset_key=preset_key,
            )
        )
    return EstudioCandidatePlan(
        status="ok",
        candidates=tuple(candidates),
        data_snapshot_id=data_snapshot_id,
    )


def _gate(
    name: str,
    passed: bool | None,
    *,
    metrics: dict[str, Any] | None = None,
    detail: str | None = None,
) -> GateResult:
    """Construye un gate: ``None`` ⇒ NOT_EVALUATED (fail-closed)."""
    if passed is None:
        return GateResult(gate=name, status=GateStatus.NOT_EVALUATED, detail=detail)
    status = GateStatus.PASS if passed else GateStatus.FAIL
    return GateResult(gate=name, status=status, detail=detail, metrics=dict(metrics or {}))


def gate_from_metrics(
    name: str,
    metrics: Mapping[str, Any] | None,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
    key: str = "score",
) -> GateResult:
    """Gate cuantitativo simple sobre una métrica (p. ej. ``oos.score >= umbral``).

    Falta de métrica ⇒ ``NOT_EVALUATED`` (no PASS). Fuera de rango ⇒ FAIL.
    """
    if not isinstance(metrics, Mapping):
        return GateResult(gate=name, status=GateStatus.NOT_EVALUATED, detail="sin_metricas")
    raw = metrics.get(key)
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return GateResult(
            gate=name, status=GateStatus.NOT_EVALUATED, detail=f"{key}_ausente"
        )
    value = float(raw)
    ok = True
    if min_value is not None and value < min_value:
        ok = False
    if max_value is not None and value > max_value:
        ok = False
    return GateResult(
        gate=name,
        status=GateStatus.PASS if ok else GateStatus.FAIL,
        detail=f"{key}={value}",
        metrics={key: value},
    )


@dataclass(frozen=True, slots=True)
class LabThresholds:
    """Umbrales cuantitativos del LAB (defaults honestos, ajustables por env/doc)."""

    min_oos_score: float = 0.0
    min_wfe: float = 0.0
    max_pbo: float = 1.0
    min_dsr: float = 0.0
    zero_tolerance: float = 1e-9
    extra: dict[str, Any] = field(default_factory=dict)


def _best_trial(result: Any) -> Any | None:
    trials = list(getattr(result, "trials", None) or [])
    if not trials:
        return None
    return max(trials, key=lambda t: float(getattr(t, "score", 0.0) or 0.0))


def evaluate_optimize_result(
    *,
    candidate: StrategyCandidate,
    result: Any,
    thresholds: LabThresholds | None = None,
    extra_gates: Sequence[GateResult] = (),
) -> StrategyEvaluation:
    """Fase LABORATORIO: resultado real de optimización ⇒ ``StrategyEvaluation``.

    Los gates se derivan de datos REALES del resultado (no de opiniones):

    * ``backtest``     — el campeón IS existe y su score > 0.
    * ``robustness``   — PBO por debajo del umbral (menos overfit) y hay CPCV.
    * ``walk_forward`` — WFE presente y por encima del umbral.
    * ``oos``          — score OOS del campeón por encima del umbral.
    * ``risk``         — hay métricas de riesgo (drawdown) y es finito.
    * ``coach``        — NO se decide aquí (lo aporta la fase COACH; NOT_EVALUATED).
    """
    th = thresholds or LabThresholds()
    champion = _best_trial(result)
    gates: list[GateResult] = []

    is_score = float(getattr(champion, "score", 0.0) or 0.0) if champion is not None else None
    gates.append(
        _gate(
            "backtest",
            (is_score is not None and is_score > th.zero_tolerance),
            metrics={"is_score": is_score} if is_score is not None else None,
            detail="campeon_is" if champion is not None else "sin_trials",
        )
    )

    cpcv = getattr(result, "cpcv", None)
    pbo = getattr(result, "pbo", None)
    pbo_value = None
    if isinstance(pbo, dict):
        pbo_value = pbo.get("pbo")
    elif isinstance(cpcv, dict):
        pbo_value = cpcv.get("pbo")
    has_cpcv = isinstance(cpcv, dict) and bool(cpcv)
    if pbo_value is None:
        gates.append(_gate("robustness", None, detail="pbo_ausente"))
    else:
        passes = float(pbo_value) <= th.max_pbo and has_cpcv
        gates.append(
            _gate(
                "robustness",
                passes,
                metrics={"pbo": float(pbo_value)},
                detail="pbo_ok" if passes else "pbo_alto_o_sin_cpcv",
            )
        )

    walk_forward = getattr(result, "walk_forward", None)
    wfe = None
    if isinstance(walk_forward, dict):
        wfe = walk_forward.get("walkForwardEfficiency") or walk_forward.get("wfe")
    edge_report = getattr(result, "edge_report", None)
    if wfe is None and isinstance(edge_report, dict):
        wfe = edge_report.get("labWalkForwardEfficiency") or edge_report.get("wfe")
    if wfe is None:
        gates.append(_gate("walk_forward", None, detail="wfe_ausente"))
    else:
        gates.append(
            _gate(
                "walk_forward",
                float(wfe) >= th.min_wfe,
                metrics={"wfe": float(wfe)},
            )
        )

    oos_metrics = getattr(champion, "oos_metrics", None) if champion is not None else None
    oos_score = oos_metrics.get("score") if isinstance(oos_metrics, dict) else None
    if oos_score is not None:
        gates.append(
            gate_from_metrics(
                "oos",
                oos_metrics,
                min_value=th.min_oos_score,
            )
        )
    else:
        gates.append(_gate("oos", None, detail="oos_ausente"))

    dd = getattr(champion, "max_drawdown_pct", None) if champion is not None else None
    gates.append(
        _gate(
            "risk",
            (dd is not None and float(dd) >= 0.0),
            metrics={"max_drawdown_pct": float(dd)} if dd is not None else None,
            detail="drawdown_ok" if dd is not None else "risk_ausente",
        )
    )

    dsr = None
    if isinstance(edge_report, dict):
        dsr = edge_report.get("dsr") or edge_report.get("deflatedSharpe")
    gates.append(
        _gate("dsr", None if dsr is None else float(dsr) >= th.min_dsr, metrics={"dsr": dsr})
    )

    # El COACH no se decide en el LAB: queda NOT_EVALUATED hasta la fase COACH.
    gates.append(_gate("coach", None, detail="fase_coach"))

    gates.extend(extra_gates)

    metrics: dict[str, Any] = {"instrument_id": candidate.instrument_id}
    if is_score is not None:
        metrics["is_score"] = is_score
    if oos_score is not None:
        metrics["oos_score"] = float(oos_score)
    if wfe is not None:
        metrics["wfe"] = float(wfe)
    if pbo_value is not None:
        metrics["pbo"] = float(pbo_value)
    if dsr is not None:
        metrics["dsr"] = float(dsr)

    score = is_score if is_score is not None else 0.0
    return StrategyEvaluation(
        candidate_id=candidate.id,
        score=score,
        gates=tuple(gates),
        optimization_run_id=getattr(result, "optimization_run_id", None),
        edge_report_id=getattr(result, "edge_report_id", None),
        metrics=metrics,
    )
