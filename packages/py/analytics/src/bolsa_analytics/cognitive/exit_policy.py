"""ExitPolicy — fracciones T1/T2 por plantilla (V1.27). No es un motor de salida."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExitTrailWidth = Literal["tight", "medium", "wide"]
ExitSuggestedAction = Literal["hold", "protect", "reduce", "full_exit"]


def _round4(value: float) -> float:
    return round(value * 10000) / 10000


def clamp_exit_fraction(value: float) -> float:
    if value != value:
        return 0.0
    return min(1.0, max(0.0, float(value)))


def qty_from_exit_fraction(remaining: float, fraction: float) -> float:
    if remaining <= 0:
        return 0.0
    f = clamp_exit_fraction(fraction)
    if f <= 1e-12:
        return 0.0
    if f >= 1.0 - 1e-12:
        return _round4(remaining)
    return _round4(remaining * f)


@dataclass(frozen=True, slots=True)
class ExitPolicy:
    t1_reduce_fraction: float
    t2_reduce_fraction: float
    trail_width: ExitTrailWidth

    def to_dict(self) -> dict[str, Any]:
        return {
            "t1ReduceFraction": self.t1_reduce_fraction,
            "t2ReduceFraction": self.t2_reduce_fraction,
            "trailWidth": self.trail_width,
        }


CONSERVATIVE_EXIT_POLICY = ExitPolicy(0.5, 1.0, "tight")
MODERATE_EXIT_POLICY = ExitPolicy(0.3, 0.3, "medium")
AGGRESSIVE_SWING_EXIT_POLICY = ExitPolicy(0.0, 0.3, "wide")

EXIT_POLICY_BY_TEMPLATE: dict[str, ExitPolicy] = {
    "conservative": CONSERVATIVE_EXIT_POLICY,
    "moderate": MODERATE_EXIT_POLICY,
    "aggressive_swing": AGGRESSIVE_SWING_EXIT_POLICY,
}


def resolve_exit_policy(template_id: str | None) -> ExitPolicy:
    if template_id == "conservative":
        return CONSERVATIVE_EXIT_POLICY
    if template_id == "aggressive_swing":
        return AGGRESSIVE_SWING_EXIT_POLICY
    return MODERATE_EXIT_POLICY


def suggestion_from_exit_policy(
    primary: str | None,
    remaining: float,
    policy: ExitPolicy | None,
    trail_stop: float | None = None,
) -> tuple[ExitSuggestedAction, float | None, float | None]:
    if not primary:
        return "hold", None, None
    if primary == "TRAIL":
        stop = _round4(trail_stop) if trail_stop is not None and trail_stop > 0 else None
        return "protect", None, stop
    if primary == "TARGET_1":
        fraction = policy.t1_reduce_fraction if policy is not None else 0.5
        qty = qty_from_exit_fraction(remaining, fraction)
        if qty <= 0:
            return "hold", None, None
        if qty >= remaining - 1e-9:
            return "full_exit", _round4(remaining), None
        return "reduce", qty, None
    if primary == "TARGET_2":
        fraction = policy.t2_reduce_fraction if policy is not None else 1.0
        qty = qty_from_exit_fraction(remaining, fraction)
        if qty <= 0:
            return "hold", None, None
        if qty >= remaining - 1e-9:
            return "full_exit", _round4(remaining), None
        return "reduce", qty, None
    return "full_exit", _round4(remaining), None
