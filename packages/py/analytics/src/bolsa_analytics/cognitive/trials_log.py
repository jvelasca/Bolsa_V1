"""Registro de trials / hipótesis — obligatorio para DSR válido (RFC-008 D3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class TrialRecord:
    trial_id: str
    hypothesis_ref: str
    params_hash: str
    sharpe_is: float | None
    created_at: str
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trialId": self.trial_id,
            "hypothesisRef": self.hypothesis_ref,
            "paramsHash": self.params_hash,
            "sharpeIs": self.sharpe_is,
            "createdAt": self.created_at,
            "notes": self.notes,
        }


@dataclass
class TrialsLog:
    """Log mutable de hipótesis exploradas (N = len(trials))."""

    log_id: str = field(default_factory=lambda: f"TRL-{uuid4().hex[:12]}")
    strategy_family_ref: str = ""
    trials: list[TrialRecord] = field(default_factory=list)

    @property
    def trials_n(self) -> int:
        return len(self.trials)

    def record(
        self,
        hypothesis_ref: str,
        params_hash: str,
        *,
        sharpe_is: float | None = None,
        notes: str | None = None,
    ) -> TrialRecord:
        rec = TrialRecord(
            trial_id=f"T-{uuid4().hex[:10]}",
            hypothesis_ref=hypothesis_ref,
            params_hash=params_hash,
            sharpe_is=sharpe_is,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            notes=notes,
        )
        self.trials.append(rec)
        return rec

    def variance_of_trial_sharpes(self) -> float | None:
        vals = [t.sharpe_is for t in self.trials if t.sharpe_is is not None]
        if len(vals) < 2:
            return None
        return float(np_var(vals))

    def to_dict(self) -> dict[str, Any]:
        return {
            "logId": self.log_id,
            "strategyFamilyRef": self.strategy_family_ref,
            "trialsN": self.trials_n,
            "trials": [t.to_dict() for t in self.trials],
        }


def np_var(vals: list[float]) -> float:
    import numpy as np

    return float(np.var(vals, ddof=1))
