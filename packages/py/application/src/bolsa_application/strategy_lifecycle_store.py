"""V2.25 / A10 — store del Strategy Lifecycle (Protocol + InMemory + Postgres).

Persiste el embudo de estrategia del dominio ``bolsa_domain.entities.strategy_lifecycle``
sin acoplar la capa application al infra en import-time (imports de modelo diferidos por
método, como ``execution_event``/``auto_engine_state_store``).

Tablas (migración ``030_strategy_lifecycle``):
``strategy_candidates`` · ``strategy_versions`` · ``strategy_evaluations`` ·
``strategy_promotions`` · ``strategy_health_snapshots``.

La evidencia pesada (``research_trials``/``research_evidence``/``edge_reports``) se
REFERENCIA por id; aquí no se duplica. Este módulo no ejecuta backtests ni decide
promociones: solo persiste y lee el estado del ciclo.

Fail-closed: sin evidencia no hay promoción (la decisión vive en el dominio;
aquí solo se guarda el veredicto).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from bolsa_domain.entities.strategy_lifecycle import (
    ActiveStrategy,
    CoachAssessment,
    GateResult,
    GateStatus,
    ShadowValidationResult,
    StrategyCandidate,
    StrategyEvaluation,
    StrategyFinalist,
    StrategyHealth,
    StrategyPromotion,
)

__all__ = [
    "ActiveStrategyRecord",
    "InMemoryStrategyLifecycleStore",
    "PostgresStrategyLifecycleStore",
    "StrategyLifecycleStore",
    "StrategyPromotionRecord",
    "new_promotion_record",
]


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | str | None) -> str:
    if value is None:
        return _now().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@dataclass(frozen=True, slots=True)
class StrategyPromotionRecord:
    """Promoción persistida (unión del veredicto del dominio + identidad)."""

    promotion: StrategyPromotion
    candidate_id: str
    instrument_id: str
    version_id: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ActiveStrategyRecord:
    """Estrategia ACTIVE persistida (versión inmutable + metadatos de promoción)."""

    active: ActiveStrategy
    promoted_at: str


class StrategyLifecycleStore(Protocol):
    async def save_candidate(self, candidate: StrategyCandidate) -> None: ...
    async def get_candidate(self, candidate_id: str) -> StrategyCandidate | None: ...
    async def list_candidates(
        self, *, instrument_id: str | None = None
    ) -> list[StrategyCandidate]: ...
    async def save_evaluation(self, evaluation: StrategyEvaluation) -> None: ...
    async def list_evaluations(self, candidate_id: str) -> list[StrategyEvaluation]: ...
    async def save_finalist(self, finalist: StrategyFinalist) -> None: ...
    async def save_promotion(self, record: StrategyPromotionRecord) -> None: ...
    async def list_promotions(self, *, promoted: bool | None = None) -> list[StrategyPromotionRecord]: ...
    async def save_active(self, record: ActiveStrategyRecord) -> None: ...
    async def get_active(self, *, instrument_id: str) -> ActiveStrategyRecord | None: ...
    async def list_active(self) -> list[ActiveStrategyRecord]: ...
    async def save_health(self, version_id: str, health: StrategyHealth) -> None: ...
    async def list_health(self, version_id: str) -> list[StrategyHealth]: ...
    # V2.29 / A10: dictamen COACH comparativo del TOP3 (advisory, uno por candidato).
    async def save_coach_assessment(self, assessment: CoachAssessment) -> None: ...
    async def list_coach_assessments(self, candidate_id: str) -> list[CoachAssessment]: ...
    # V2.32 / A12: evidencia shadow ejecutada (autoridad del Promotion Gate).
    async def save_shadow_result(self, result: ShadowValidationResult) -> None: ...
    async def list_shadow_results(self, version_id: str) -> list[ShadowValidationResult]: ...


class InMemoryStrategyLifecycleStore:
    """Doble hermético del store del ciclo de vida (tests/reina)."""

    def __init__(self) -> None:
        self._candidates: dict[str, StrategyCandidate] = {}
        self._evaluations: dict[str, list[StrategyEvaluation]] = {}
        self._finalists: dict[str, StrategyFinalist] = {}
        self._promotions: list[StrategyPromotionRecord] = []
        self._active: dict[str, ActiveStrategyRecord] = {}
        self._health: dict[str, list[StrategyHealth]] = {}
        self._coach: dict[str, list[CoachAssessment]] = {}
        self._shadow: dict[str, list[ShadowValidationResult]] = {}

    async def save_candidate(self, candidate: StrategyCandidate) -> None:
        self._candidates[candidate.id] = candidate

    async def get_candidate(self, candidate_id: str) -> StrategyCandidate | None:
        return self._candidates.get(candidate_id)

    async def list_candidates(self, *, instrument_id: str | None = None) -> list[StrategyCandidate]:
        values = list(self._candidates.values())
        if instrument_id is not None:
            values = [c for c in values if c.instrument_id == instrument_id]
        return values

    async def save_evaluation(self, evaluation: StrategyEvaluation) -> None:
        self._evaluations.setdefault(evaluation.candidate_id, []).append(evaluation)

    async def list_evaluations(self, candidate_id: str) -> list[StrategyEvaluation]:
        return list(self._evaluations.get(candidate_id, []))

    async def save_finalist(self, finalist: StrategyFinalist) -> None:
        self._finalists[finalist.version_id] = finalist

    async def save_promotion(self, record: StrategyPromotionRecord) -> None:
        self._promotions.append(record)

    async def list_promotions(
        self, *, promoted: bool | None = None
    ) -> list[StrategyPromotionRecord]:
        if promoted is None:
            return list(self._promotions)
        return [r for r in self._promotions if r.promotion.promoted is promoted]

    async def save_active(self, record: ActiveStrategyRecord) -> None:
        self._active[record.active.instrument_id] = record

    async def get_active(self, *, instrument_id: str) -> ActiveStrategyRecord | None:
        return self._active.get(instrument_id)

    async def list_active(self) -> list[ActiveStrategyRecord]:
        return list(self._active.values())

    async def save_health(self, version_id: str, health: StrategyHealth) -> None:
        self._health.setdefault(version_id, []).append(health)

    async def list_health(self, version_id: str) -> list[StrategyHealth]:
        return list(self._health.get(version_id, []))

    async def save_coach_assessment(self, assessment: CoachAssessment) -> None:
        self._coach.setdefault(assessment.candidate_id, []).append(assessment)

    async def list_coach_assessments(self, candidate_id: str) -> list[CoachAssessment]:
        return list(self._coach.get(candidate_id, []))

    async def save_shadow_result(self, result: ShadowValidationResult) -> None:
        self._shadow.setdefault(result.version_id, []).append(result)

    async def list_shadow_results(self, version_id: str) -> list[ShadowValidationResult]:
        return list(self._shadow.get(version_id, []))


def _gates_to_json(gates: tuple[GateResult, ...]) -> dict[str, Any]:
    return {
        g.gate: {
            "status": g.status.value,
            "detail": g.detail,
            "metrics": dict(g.metrics),
            "passed": g.passed,
        }
        for g in gates
    }


def _gates_from_json(raw: Any) -> tuple[GateResult, ...]:
    if not isinstance(raw, dict):
        return ()
    gates: list[GateResult] = []
    for gate, payload in raw.items():
        data = payload if isinstance(payload, dict) else {}
        status_raw = str(data.get("status") or GateStatus.NOT_EVALUATED.value)
        try:
            status = GateStatus(status_raw)
        except ValueError:
            status = GateStatus.NOT_EVALUATED
        gates.append(
            GateResult(
                gate=str(gate),
                status=status,
                detail=data.get("detail"),
                metrics=dict(data.get("metrics") or {}),
            )
        )
    return tuple(gates)


# V2.29/A10: serialización del dictamen COACH (advisory) al JSON libre de la
# evaluación. Se guarda como evidencia auditable, no como gate.
def _coach_to_json(assessment: CoachAssessment) -> dict[str, Any]:
    return {
        "candidate_id": assessment.candidate_id,
        "approved": assessment.approved,
        "headline": assessment.headline,
        "coherence": assessment.coherence.value,
        "complementarity": assessment.complementarity.value,
        "regime_fit": assessment.regime_fit.value,
        "contradictions": list(assessment.contradictions),
        "facts": list(assessment.facts),
    }


def _coach_from_json(payload: Any) -> CoachAssessment:
    data = payload if isinstance(payload, dict) else {}

    def _status_of(key: str) -> GateStatus:
        try:
            return GateStatus(str(data.get(key) or GateStatus.NOT_EVALUATED.value))
        except ValueError:
            return GateStatus.NOT_EVALUATED

    return CoachAssessment(
        candidate_id=str(data.get("candidate_id") or ""),
        approved=bool(data.get("approved")),
        headline=data.get("headline"),
        coherence=_status_of("coherence"),
        complementarity=_status_of("complementarity"),
        regime_fit=_status_of("regime_fit"),
        contradictions=tuple(str(c) for c in (data.get("contradictions") or [])),
        facts=tuple(str(f) for f in (data.get("facts") or [])),
    )


class PostgresStrategyLifecycleStore:
    """Store durable del ciclo de vida (imports de modelo diferidos por método)."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def save_candidate(self, candidate: StrategyCandidate) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyCandidateRow

        now = _now()
        await self._session.execute(
            pg_insert(StrategyCandidateRow)
            .values(
                id=candidate.id,
                instrument_id=candidate.instrument_id,
                strategy_family=candidate.strategy_family,
                params=dict(candidate.params),
                origin=candidate.origin,
                data_snapshot_id=candidate.data_snapshot_id,
                preset_key=candidate.preset_key,
                strategy_definition_id=candidate.strategy_definition_id,
                state="estudio",
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "params": dict(candidate.params),
                    "data_snapshot_id": candidate.data_snapshot_id,
                    "preset_key": candidate.preset_key,
                    "strategy_definition_id": candidate.strategy_definition_id,
                    "updated_at": now,
                },
            )
        )
        await self._session.commit()

    async def get_candidate(self, candidate_id: str) -> StrategyCandidate | None:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyCandidateRow

        row = (
            await self._session.execute(
                select(StrategyCandidateRow).where(StrategyCandidateRow.id == candidate_id)
            )
        ).scalar_one_or_none()
        return _candidate_from_row(row) if row is not None else None

    async def list_candidates(self, *, instrument_id: str | None = None) -> list[StrategyCandidate]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyCandidateRow

        stmt = select(StrategyCandidateRow)
        if instrument_id is not None:
            stmt = stmt.where(StrategyCandidateRow.instrument_id == instrument_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_candidate_from_row(r) for r in rows]

    async def save_evaluation(self, evaluation: StrategyEvaluation) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyEvaluationRow
        from bolsa_infrastructure.ids import new_id

        await self._session.execute(
            pg_insert(StrategyEvaluationRow)
            .values(
                id=new_id(),
                candidate_id=evaluation.candidate_id,
                instrument_id=str(evaluation.metrics.get("instrument_id") or ""),
                score=float(evaluation.score),
                gates=_gates_to_json(evaluation.gates),
                metrics=dict(evaluation.metrics),
                trial_ids=list(evaluation.trial_ids),
                optimization_run_id=evaluation.optimization_run_id,
                edge_report_id=evaluation.edge_report_id,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()

    async def list_evaluations(self, candidate_id: str) -> list[StrategyEvaluation]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyEvaluationRow

        rows = (
            await self._session.execute(
                select(StrategyEvaluationRow)
                .where(StrategyEvaluationRow.candidate_id == candidate_id)
                .order_by(StrategyEvaluationRow.created_at.asc())
            )
        ).scalars().all()
        return [
            StrategyEvaluation(
                candidate_id=r.candidate_id,
                score=float(r.score),
                gates=_gates_from_json(r.gates),
                trial_ids=tuple(str(t) for t in (r.trial_ids or [])),
                optimization_run_id=r.optimization_run_id,
                edge_report_id=r.edge_report_id,
                metrics=dict(r.metrics or {}),
            )
            for r in rows
        ]

    async def save_finalist(self, finalist: StrategyFinalist) -> None:
        from sqlalchemy import update
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import (
            StrategyCandidateRow,
            StrategyVersionRow,
        )

        instrument_id = finalist.definition.get("instrument_id") or ""
        if not instrument_id:
            candidate = await self.get_candidate(finalist.candidate_id)
            instrument_id = candidate.instrument_id if candidate is not None else ""
        await self._session.execute(
            pg_insert(StrategyVersionRow)
            .values(
                id=finalist.version_id,
                candidate_id=finalist.candidate_id,
                instrument_id=str(instrument_id),
                name=finalist.name,
                definition_hash=finalist.definition_hash,
                definition=dict(finalist.definition),
                is_finalist=True,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        # El finalista avanza la candidata a estado finalista.
        await self._session.execute(
            update(StrategyCandidateRow)
            .where(StrategyCandidateRow.id == finalist.candidate_id)
            .values(state="finalista", updated_at=_now())
        )
        await self._session.commit()

    async def save_promotion(self, record: StrategyPromotionRecord) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyPromotionRow
        from bolsa_infrastructure.ids import new_id

        await self._session.execute(
            pg_insert(StrategyPromotionRow)
            .values(
                id=new_id(),
                finalist_id=record.promotion.finalist_id,
                candidate_id=record.candidate_id,
                instrument_id=record.instrument_id,
                promoted=record.promotion.promoted,
                reasons=list(record.promotion.reasons),
                shadow_validated=record.promotion.shadow_validated,
                shadow_validation_id=record.promotion.shadow_validation_id,
                promoted_at=_now() if record.promotion.promoted else None,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()

    async def list_promotions(
        self, *, promoted: bool | None = None
    ) -> list[StrategyPromotionRecord]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyPromotionRow

        stmt = select(StrategyPromotionRow)
        if promoted is not None:
            stmt = stmt.where(StrategyPromotionRow.promoted.is_(promoted))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            StrategyPromotionRecord(
                promotion=StrategyPromotion(
                    finalist_id=r.finalist_id,
                    promoted=bool(r.promoted),
                    reasons=tuple(str(x) for x in (r.reasons or [])),
                    shadow_validated=bool(r.shadow_validated),
                    shadow_validation_id=(
                        str(r.shadow_validation_id) if r.shadow_validation_id else None
                    ),
                    promoted_at=r.promoted_at.isoformat() if r.promoted_at else None,
                ),
                candidate_id=r.candidate_id,
                instrument_id=r.instrument_id,
                version_id=r.finalist_id,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]

    async def save_shadow_result(self, result: ShadowValidationResult) -> None:
        """V2.32 / A12: persiste la evidencia shadow ejecutada (autoridad del gate)."""
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyShadowValidationRow
        from bolsa_infrastructure.ids import new_id

        await self._session.execute(
            pg_insert(StrategyShadowValidationRow)
            .values(
                id=new_id(),
                version_id=result.version_id,
                instrument_id=result.instrument_id,
                trades=int(result.trades),
                return_pct=result.return_pct,
                max_drawdown_pct=result.max_drawdown_pct,
                win_rate=result.win_rate,
                bars_used=int(result.bars_used),
                passed=bool(result.passed),
                reasons=list(result.reasons),
                as_of=result.as_of,
                # V2.32.1: identidad reproducible del dataset (P2-03).
                round_trips=int(result.round_trips),
                data_snapshot_id=result.data_snapshot_id,
                shadow_start=result.shadow_start,
                shadow_end=result.shadow_end,
                bars_hash=result.bars_hash,
                strategy_definition_hash=result.strategy_definition_hash,
                engine_version=result.engine_version,
                config_hash=result.config_hash,
                lab_end=result.lab_end,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()

    async def list_shadow_results(self, version_id: str) -> list[ShadowValidationResult]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyShadowValidationRow

        rows = (
            await self._session.execute(
                select(StrategyShadowValidationRow)
                .where(StrategyShadowValidationRow.version_id == version_id)
                .order_by(StrategyShadowValidationRow.created_at.asc())
            )
        ).scalars().all()
        return [
            ShadowValidationResult(
                version_id=r.version_id,
                trades=int(r.trades or 0),
                passed=bool(r.passed),
                reasons=tuple(str(x) for x in (r.reasons or [])),
                return_pct=r.return_pct,
                max_drawdown_pct=r.max_drawdown_pct,
                win_rate=r.win_rate,
                bars_used=int(r.bars_used or 0),
                as_of=r.as_of,
                round_trips=int(getattr(r, "round_trips", 0) or 0),
                data_snapshot_id=r.data_snapshot_id,
                shadow_start=r.shadow_start,
                shadow_end=r.shadow_end,
                bars_hash=r.bars_hash,
                strategy_definition_hash=r.strategy_definition_hash,
                engine_version=r.engine_version,
                config_hash=r.config_hash,
                lab_end=r.lab_end,
            )
            for r in rows
        ]

    async def save_active(self, record: ActiveStrategyRecord) -> None:
        # La activa se materializa como una promoción "activa" leída por get_active;
        # se persiste el marcador en la tabla de promociones (fuente única) para no
        # duplicar estado. No hay tabla ``active_strategies`` separada.
        from sqlalchemy import select, update

        from bolsa_infrastructure.database.models.tables import (
            StrategyPromotionRow,
            StrategyVersionRow,
        )

        await self._session.execute(
            update(StrategyVersionRow)
            .where(StrategyVersionRow.id == record.active.version_id)
            .values(is_finalist=True)
        )
        exists = (
            await self._session.execute(
                select(StrategyPromotionRow.id).where(
                    StrategyPromotionRow.finalist_id == record.active.version_id,
                    StrategyPromotionRow.promoted.is_(True),
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            from bolsa_infrastructure.ids import new_id

            # V2.32/A12: la fila de localización NO certifica shadow. Solo se propaga
            # la evidencia real (``active.shadow_validation_id``/``shadow_validated``)
            # si el Promotion Gate la aportó; en otro caso queda en False/None y
            # ``get_active`` localiza la activa por ``promoted`` (no por el flag).
            await self._session.execute(
                pg_insert(StrategyPromotionRow)
                .values(
                    id=new_id(),
                    finalist_id=record.active.version_id,
                    candidate_id=record.active.candidate_id,
                    instrument_id=record.active.instrument_id,
                    promoted=True,
                    reasons=[],
                    shadow_validated=bool(record.active.shadow_validated),
                    shadow_validation_id=record.active.shadow_validation_id,
                    promoted_at=_now(),
                    created_at=_now(),
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
        await self._session.commit()

    async def get_active(self, *, instrument_id: str) -> ActiveStrategyRecord | None:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import (
            StrategyPromotionRow,
            StrategyVersionRow,
        )

        row = (
            await self._session.execute(
                select(StrategyPromotionRow)
                .where(
                    StrategyPromotionRow.instrument_id == instrument_id,
                    StrategyPromotionRow.promoted.is_(True),
                )
                .order_by(StrategyPromotionRow.promoted_at.desc())
            )
        ).scalars().first()
        if row is None:
            return None
        version = (
            await self._session.execute(
                select(StrategyVersionRow).where(StrategyVersionRow.id == row.finalist_id)
            )
        ).scalar_one_or_none()
        if version is None:
            return None
        active = ActiveStrategy(
            version_id=version.id,
            candidate_id=version.candidate_id,
            instrument_id=version.instrument_id,
            name=version.name,
            definition=dict(version.definition or {}),
            shadow_validated=bool(row.shadow_validated),
            shadow_validation_id=(
                str(row.shadow_validation_id) if row.shadow_validation_id else None
            ),
            promoted_at=row.promoted_at.isoformat() if row.promoted_at else None,
        )
        return ActiveStrategyRecord(
            active=active,
            promoted_at=row.promoted_at.isoformat() if row.promoted_at else _iso(None),
        )

    async def list_active(self) -> list[ActiveStrategyRecord]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyPromotionRow

        rows = (
            await self._session.execute(
                select(StrategyPromotionRow).where(StrategyPromotionRow.promoted.is_(True))
            )
        ).scalars().all()
        out: list[ActiveStrategyRecord] = []
        for row in rows:
            record = await self.get_active(instrument_id=row.instrument_id)
            if record is not None:
                out.append(record)
        return out

    async def save_health(self, version_id: str, health: StrategyHealth) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyHealthRow
        from bolsa_infrastructure.ids import new_id

        await self._session.execute(
            pg_insert(StrategyHealthRow)
            .values(
                id=new_id(),
                version_id=version_id,
                as_of=_now(),
                edge=health.edge,
                walk_forward_efficiency=health.walk_forward_efficiency,
                dsr=health.dsr,
                credibility=health.credibility,
                # El JSON ``thresholds`` es el único campo libre de la tabla; en él se
                # persisten TAMBIÉN los valores observados (V2.28/A10) bajo el prefijo
                # ``value_`` para no colisionar con sus umbrales homónimos. Así el snapshot
                # es auditable sin migrar la tabla.
                thresholds=_health_payload(health),
                degraded=health.degraded,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()

    async def list_health(self, version_id: str) -> list[StrategyHealth]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyHealthRow

        rows = (
            await self._session.execute(
                select(StrategyHealthRow)
                .where(StrategyHealthRow.version_id == version_id)
                .order_by(StrategyHealthRow.as_of.asc())
            )
        ).scalars().all()
        return [
            StrategyHealth(
                version_id=r.version_id,
                as_of=r.as_of.isoformat(),
                edge=r.edge,
                walk_forward_efficiency=r.walk_forward_efficiency,
                dsr=r.dsr,
                credibility=r.credibility,
                **_health_from_payload(dict(r.thresholds or {})),
            )
            for r in rows
        ]

    async def save_coach_assessment(self, assessment: CoachAssessment) -> None:
        # V2.29/A10: el dictamen COACH se persiste como evidencia advisory en
        # ``strategy_evaluations`` (tabla existente, sin migración): ``id`` determinista
        # por candidato (idempotente) y el dictamen serializado en ``metrics["coach"]``.
        # ``score`` no aplica a un dictamen ⇒ 0.0; los gates van vacíos (el COACH no
        # sustituye a los gates cuantitativos).
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from bolsa_infrastructure.database.models.tables import StrategyEvaluationRow

        await self._session.execute(
            pg_insert(StrategyEvaluationRow)
            .values(
                id=f"coach-{assessment.candidate_id}",
                candidate_id=assessment.candidate_id,
                instrument_id="",
                score=0.0,
                gates={},
                metrics={"coach": _coach_to_json(assessment)},
                trial_ids=[],
                optimization_run_id=None,
                edge_report_id=None,
                created_at=_now(),
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        await self._session.commit()

    async def list_coach_assessments(self, candidate_id: str) -> list[CoachAssessment]:
        from sqlalchemy import select

        from bolsa_infrastructure.database.models.tables import StrategyEvaluationRow

        rows = (
            await self._session.execute(
                select(StrategyEvaluationRow)
                .where(StrategyEvaluationRow.id == f"coach-{candidate_id}")
            )
        ).scalars().all()
        out: list[CoachAssessment] = []
        for row in rows:
            payload = dict(row.metrics or {}).get("coach")
            if isinstance(payload, dict):
                out.append(_coach_from_json(payload))
        return out


# V2.28 / A10: claves del payload de salud que NO son umbrales, sino VALORES observados.
# Se guardan en el JSON ``thresholds`` (único campo libre) con prefijo ``value_`` para no
# colisionar con los umbrales homónimos (``observed_return_pct``, etc.).
_OBSERVED_VALUE_KEYS = (
    "observed_return_pct",
    "observed_max_drawdown_pct",
    "observed_win_rate",
    "observed_profit_factor",
)
_OBSERVED_TRADES_KEY = "value_observed_trades"


def _health_payload(health: StrategyHealth) -> dict[str, Any]:
    """Serializa umbrales + valores observados al JSON libre del snapshot.

    Filtra valores no finitos (``inf``/``nan``): JSON no los admite y romperían el
    ``INSERT`` en PG. Un valor no finito es, a efectos de salud, no disponible.
    """
    payload: dict[str, Any] = dict(health.thresholds)
    for key in _OBSERVED_VALUE_KEYS:
        value = getattr(health, key, None)
        if value is not None and _is_finite(value):
            payload[f"value_{key}"] = value
    if health.observed_trades is not None:
        payload[_OBSERVED_TRADES_KEY] = health.observed_trades
    return payload


def _is_finite(value: Any) -> bool:
    import math

    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _health_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reconstruye los campos observados desde el JSON y deja solo umbrales en ``thresholds``."""
    observed: dict[str, Any] = {}
    for key in _OBSERVED_VALUE_KEYS:
        value = payload.get(f"value_{key}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            observed[key] = float(value)
    trades = payload.get(_OBSERVED_TRADES_KEY)
    if isinstance(trades, int) and not isinstance(trades, bool):
        observed["observed_trades"] = trades
    thresholds = {
        key: value
        for key, value in payload.items()
        if not key.startswith("value_")
    }
    observed["thresholds"] = thresholds
    return observed


def _candidate_from_row(row: Any) -> StrategyCandidate:
    from bolsa_domain.entities.strategy_lifecycle import StrategyLifecycleState

    try:
        state = StrategyLifecycleState(str(row.state))
    except ValueError:
        state = StrategyLifecycleState.ESTUDIO
    return StrategyCandidate(
        id=row.id,
        instrument_id=row.instrument_id,
        strategy_family=row.strategy_family,
        params=dict(row.params or {}),
        origin=row.origin,
        data_snapshot_id=row.data_snapshot_id,
        preset_key=row.preset_key,
        created_at=row.created_at.isoformat() if row.created_at else None,
        strategy_definition_id=row.strategy_definition_id,
        state=state,
    )


# Reexport de cortesía para quien construya registros desde el dominio.
def new_promotion_record(
    *,
    promotion: StrategyPromotion,
    candidate_id: str,
    instrument_id: str,
) -> StrategyPromotionRecord:
    return StrategyPromotionRecord(
        promotion=promotion,
        candidate_id=candidate_id,
        instrument_id=instrument_id,
        version_id=promotion.finalist_id,
        created_at=_iso(None),
    )
