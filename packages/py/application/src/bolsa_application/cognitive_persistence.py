"""Casos de uso — persistencia cognitiva RFC-008 (application orquesta analytics + infra)."""

from __future__ import annotations

from datetime import UTC
from typing import Any, Protocol

from bolsa_analytics.cognitive import (
    DecisionMemoryEntry,
    EdgeReport,
    StatisticalSuiteResult,
    TrialsLog,
    build_effectiveness_summary,
    build_memory_entry,
)
from bolsa_analytics.cognitive.edge_report import build_edge_report
from bolsa_analytics.cognitive.trials_log import TrialRecord
from bolsa_domain.entities.cognitive_artifacts import (
    ConfidenceStateRecord,
    DecisionMemoryRecord,
    DecisionSessionRecord,
    EdgeReportRecord,
    TrialRecordPersist,
)


class CognitiveStore(Protocol):
    """Puerto / almacén de Cognitive."""
    async def append_decision_memory(self, record: DecisionMemoryRecord) -> DecisionMemoryRecord: ...
    async def list_decision_memory(
        self,
        *,
        limit: int = 100,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionMemoryRecord]: ...
    async def append_decision_session(self, record: DecisionSessionRecord) -> DecisionSessionRecord: ...
    async def get_decision_session(self, session_id: str) -> DecisionSessionRecord | None: ...
    async def list_decision_sessions(
        self,
        *,
        limit: int = 50,
        account_id: str | None = None,
        instrument_id: str | None = None,
    ) -> list[DecisionSessionRecord]: ...
    async def update_decision_session(
        self, record: DecisionSessionRecord
    ) -> DecisionSessionRecord: ...
    async def append_trial(self, record: TrialRecordPersist) -> TrialRecordPersist: ...
    async def count_trials(
        self,
        *,
        strategy_family_ref: str | None = None,
        log_id: str | None = None,
        account_id: str | None = None,
    ) -> int: ...
    async def list_trials(
        self,
        *,
        strategy_family_ref: str | None = None,
        log_id: str | None = None,
        account_id: str | None = None,
        limit: int = 500,
    ) -> list[TrialRecordPersist]: ...
    async def upsert_confidence_state(
        self, record: ConfidenceStateRecord
    ) -> ConfidenceStateRecord: ...
    async def append_edge_report(self, record: EdgeReportRecord) -> EdgeReportRecord: ...
    async def latest_edge_report(
        self,
        *,
        strategy_or_signal_ref: str | None = None,
        account_id: str | None = None,
    ) -> EdgeReportRecord | None: ...
    async def persistence_stats(self, *, account_id: str | None = None) -> dict[str, Any]: ...


def memory_entry_to_record(
    entry: DecisionMemoryEntry,
    *,
    account_id: str | None = None,
) -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        id=entry.memory_id,
        decision_id=entry.decision_id,
        instrument_id=entry.instrument_id,
        outcome=entry.outcome,
        reasons=entry.reasons,
        policy_rule_ids=entry.policy_rule_ids,
        reevaluate_when=entry.reevaluate_when,
        opportunity_intact=entry.opportunity_intact,
        created_at=entry.created_at,
        account_id=account_id,
        policy_id=entry.policy_id,
        policy_version=entry.policy_version,
        payload=entry.to_dict(),
    )


def decision_session_to_record(session: Any) -> DecisionSessionRecord:
    """Convierte DecisionSession (analytics) → DecisionSessionRecord (domain)."""
    payload = session.to_dict() if hasattr(session, "to_dict") else dict(session)
    return DecisionSessionRecord(
        id=str(payload.get("sessionId") or getattr(session, "session_id", "")),
        kind=str(payload.get("kind") or getattr(session, "kind", "propose")),
        status=str(payload.get("status") or getattr(session, "status", "open")),
        instrument_id=str(
            payload.get("instrumentId") or getattr(session, "instrument_id", "")
        ),
        created_at=str(payload.get("createdAt") or getattr(session, "created_at", "")),
        account_id=payload.get("accountId") or getattr(session, "account_id", None),
        symbol=payload.get("symbol") or getattr(session, "symbol", None),
        recommendation_id=payload.get("recommendationId")
        or getattr(session, "recommendation_id", None),
        decision_id=payload.get("decisionId") or getattr(session, "decision_id", None),
        payload=payload,
    )


def record_to_memory_entry(record: DecisionMemoryRecord) -> DecisionMemoryEntry:
    return DecisionMemoryEntry(
        memory_id=record.id,
        decision_id=record.decision_id,
        instrument_id=record.instrument_id,
        outcome=record.outcome,  # type: ignore[arg-type]
        reasons=record.reasons,
        policy_rule_ids=record.policy_rule_ids,
        reevaluate_when=record.reevaluate_when,
        opportunity_intact=record.opportunity_intact,
        created_at=record.created_at,
        policy_id=record.policy_id,
        policy_version=record.policy_version,
    )


def edge_report_to_record(
    report: EdgeReport,
    *,
    account_id: str | None = None,
) -> EdgeReportRecord:
    return EdgeReportRecord(
        id=report.edge_report_id,
        version=report.version,
        strategy_or_signal_ref=report.strategy_or_signal_ref,
        credibility=report.credibility,
        edge_score=report.edge_score,
        band=report.band,
        suite={
            "walkForwardEfficiency": report.suite.walk_forward_efficiency,
            "wfeSource": report.suite.wfe_source,
            "monteCarloPValue": report.suite.monte_carlo_p_value,
            "psr": report.suite.psr,
            "dsr": report.suite.dsr,
            "bootstrapAlphaCiLower": report.suite.bootstrap_alpha_ci_lower,
            "bootstrapAlphaCiUpper": report.suite.bootstrap_alpha_ci_upper,
            "stressSurvivalRate": report.suite.stress_survival_rate,
            "historicalWinRate": report.suite.historical_win_rate,
            "sampleTradesCount": report.suite.sample_trades_count,
            "trialsN": report.suite.trials_n,
        },
        notes=report.notes,
        created_at=report.created_at,
        instrument_universe_ref=report.instrument_universe_ref,
        account_id=account_id,
        payload=report.to_dict(),
    )


def record_to_edge_report(record: EdgeReportRecord) -> EdgeReport:
    s = record.suite
    wfe_source = s.get("wfeSource")
    if wfe_source not in ("lab_score", "sharpe", None):
        wfe_source = None
    suite = StatisticalSuiteResult(
        trials_n=int(s.get("trialsN") or 0),
        walk_forward_efficiency=s.get("walkForwardEfficiency"),
        wfe_source=wfe_source,
        monte_carlo_p_value=s.get("monteCarloPValue"),
        psr=s.get("psr"),
        dsr=s.get("dsr"),
        bootstrap_alpha_ci_lower=s.get("bootstrapAlphaCiLower"),
        bootstrap_alpha_ci_upper=s.get("bootstrapAlphaCiUpper"),
        stress_survival_rate=s.get("stressSurvivalRate"),
        historical_win_rate=s.get("historicalWinRate"),
        sample_trades_count=s.get("sampleTradesCount"),
    )
    return EdgeReport(
        edge_report_id=record.id,
        version=record.version,
        strategy_or_signal_ref=record.strategy_or_signal_ref,
        created_at=record.created_at,
        suite=suite,
        credibility=record.credibility,
        edge_score=record.edge_score,
        band=record.band,  # type: ignore[arg-type]
        instrument_universe_ref=record.instrument_universe_ref,
        notes=record.notes,
    )


class PersistDecisionMemory:
    """Persiste Decision Memory."""
    def __init__(self, store: CognitiveStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        decision_id: str,
        instrument_id: str,
        outcome: str,
        reasons: list[str],
        policy_rule_ids: list[str] | None = None,
        reevaluate_when: list[str] | None = None,
        opportunity_intact: bool = True,
        policy_id: str | None = None,
        policy_version: str | None = None,
        account_id: str | None = None,
    ) -> DecisionMemoryRecord:
        entry = build_memory_entry(
            decision_id=decision_id,
            instrument_id=instrument_id,
            outcome=outcome,  # type: ignore[arg-type]
            reasons=reasons,
            policy_rule_ids=policy_rule_ids or (),
            reevaluate_when=reevaluate_when or (),
            opportunity_intact=opportunity_intact,
            policy_id=policy_id,
            policy_version=policy_version,
        )
        return await self._store.append_decision_memory(
            memory_entry_to_record(entry, account_id=account_id)
        )


class PersistTrial:
    """Persiste Trial."""
    def __init__(self, store: CognitiveStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        log_id: str,
        strategy_family_ref: str,
        hypothesis_ref: str,
        params_hash: str,
        sharpe_is: float | None = None,
        notes: str | None = None,
        account_id: str | None = None,
    ) -> TrialRecordPersist:
        from datetime import datetime
        from uuid import uuid4

        rec = TrialRecord(
            trial_id=f"T-{uuid4().hex[:10]}",
            hypothesis_ref=hypothesis_ref,
            params_hash=params_hash,
            sharpe_is=sharpe_is,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            notes=notes,
        )
        return await self._store.append_trial(
            TrialRecordPersist(
                id=rec.trial_id,
                log_id=log_id,
                strategy_family_ref=strategy_family_ref,
                hypothesis_ref=rec.hypothesis_ref,
                params_hash=rec.params_hash,
                created_at=rec.created_at,
                sharpe_is=rec.sharpe_is,
                notes=rec.notes,
                account_id=account_id,
                payload=rec.to_dict(),
            )
        )


class PersistEdgeReport:
    """Persiste Edge Report."""
    def __init__(self, store: CognitiveStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        strategy_or_signal_ref: str,
        suite: StatisticalSuiteResult,
        version: str = "1.0.0",
        notes: tuple[str, ...] = (),
        account_id: str | None = None,
        auto_trial: bool = True,
    ) -> EdgeReportRecord:
        report = build_edge_report(strategy_or_signal_ref, suite, version=version, notes=notes)
        rec = await self._store.append_edge_report(
            edge_report_to_record(report, account_id=account_id)
        )
        # Auto-persist trial para que TrialsLog / Efectividad no queden vacíos.
        if auto_trial:
            from datetime import datetime
            from uuid import uuid4

            await self._store.append_trial(
                TrialRecordPersist(
                    id=f"T-{uuid4().hex[:10]}",
                    log_id=f"LOG-{strategy_or_signal_ref}"[:64],
                    strategy_family_ref=strategy_or_signal_ref,
                    hypothesis_ref=f"edge:{rec.id}",
                    params_hash=rec.id,
                    created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    sharpe_is=suite.psr,
                    notes="auto from PersistEdgeReport",
                    account_id=account_id,
                    payload={"source": "edge_report", "edgeReportId": rec.id},
                )
            )
        return rec


class LoadEffectivenessFromStore:
    """Lee PG → EffectivenessSummary (sin demo)."""

    def __init__(self, store: CognitiveStore, profile_store: Any | None = None) -> None:
        self._store = store
        self._profile_store = profile_store

    async def execute(
        self,
        *,
        account_id: str | None = None,
        strategy_family_ref: str | None = None,
        refresh_observed: bool = True,
    ) -> dict[str, Any]:
        from bolsa_analytics.cognitive.investor_profile import ObservedInvestorProfile
        from bolsa_application.investor_profiles import RefreshObservedProfile

        stats = await self._store.persistence_stats(account_id=account_id)
        edge_rec = await self._store.latest_edge_report(account_id=account_id)
        mem_recs = await self._store.list_decision_memory(limit=200, account_id=account_id)

        edge = None if edge_rec is None else record_to_edge_report(edge_rec)
        memories = [record_to_memory_entry(m) for m in mem_recs]

        trials = await self._store.list_trials(
            strategy_family_ref=strategy_family_ref,
            account_id=account_id,
            limit=500,
        )
        trials_log: TrialsLog | None = None
        if trials:
            family = strategy_family_ref or trials[0].strategy_family_ref
            trials_log = TrialsLog(log_id=trials[0].log_id, strategy_family_ref=family)
            for t in trials:
                trials_log.trials.append(
                    TrialRecord(
                        trial_id=t.id,
                        hypothesis_ref=t.hypothesis_ref,
                        params_hash=t.params_hash,
                        sharpe_is=t.sharpe_is,
                        created_at=t.created_at,
                        notes=t.notes,
                    )
                )

        observed: ObservedInvestorProfile | None = None
        if self._profile_store is not None and account_id:
            profile = await self._profile_store.get_for_account(account_id)
            if profile is not None:
                if refresh_observed and memories:
                    payloads = [m.to_dict() for m in memories]
                    refreshed = await RefreshObservedProfile(self._profile_store).execute(
                        profile.id,
                        memory_payloads=payloads,
                    )
                    if refreshed is not None and refreshed.observed:
                        profile = refreshed
                if profile.observed:
                    o = profile.observed
                    observed = ObservedInvestorProfile(
                        sample_trade_count=int(o.get("sampleTradeCount") or 0),
                        diverges_from_declared=bool(o.get("divergesFromDeclared")),
                        diverges_from_policy=bool(o.get("divergesFromPolicy")),
                        impulsivity_score=o.get("impulsivityScore"),
                        overtrading_score=o.get("overtradingScore"),
                        discipline_score=o.get("disciplineScore"),
                        last_observed_at=o.get("lastObservedAt"),
                        notes=tuple(o.get("notes") or ()),
                    )

        summary = build_effectiveness_summary(
            edge_report=edge,
            trials_log=trials_log,
            memory_entries=memories,
            observed=observed,
            status="ready"
            if (edge or memories or trials or observed)
            else "insufficient_data",
        )
        data = summary.to_dict()
        data["persistence"] = stats
        data["source"] = "postgres"
        # Learning v1 (Session Outcomes) — distinto de Memory Gate
        try:
            from bolsa_analytics.cognitive.decision_outcome import summarize_session_outcomes

            session_rows = await self._store.list_decision_sessions(
                limit=200, account_id=account_id
            )
            payloads = [r.payload for r in session_rows if r.payload]
            data["sessionLearning"] = summarize_session_outcomes(payloads)
            notes = list(data.get("notes") or [])
            notes.append(
                "sessionLearning = hit-rate Outcomes (Propose); memory = Gate accepted/rejected."
            )
            data["notes"] = notes
        except Exception:  # noqa: BLE001
            data["sessionLearning"] = None
        return data
