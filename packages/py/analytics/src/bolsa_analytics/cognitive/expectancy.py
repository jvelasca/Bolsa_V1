"""Expectancy advisory thin (ADR-031 Ciclo 8.0).

Pure aggregate over setup+R samples. Read-only; never a fill gate or permission.
Live propose uses a single proxy sample (entrySetup + mfeMae.currentR).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

ExpectancyStatus = Literal["none", "thin", "ready"]
ExpectancySampleQuality = Literal[
    "insufficient",
    "preliminary",
    "developing",
    "useful",
]
ExpectancyWhy = Literal[
    "missing_inputs",
    "thin_sample",
    "live_proxy",
    "aggregated",
    "not_permission",
]

EXPECTANCY_KEY = "expectancy"
# Thin-surface ready threshold. `status: ready` is NOT statistically useful (C5).
_READY_MIN_N = 5


def sample_quality_from_n(n: int) -> ExpectancySampleQuality:
    """Honesty bands (convention, not closed science).

    n<20 insufficient · 20–49 preliminary · 50–99 developing · 100+ useful.
    Independent of ``status`` (ready uses _READY_MIN_N=5).
    """
    if n < 20:
        return "insufficient"
    if n < 50:
        return "preliminary"
    if n < 100:
        return "developing"
    return "useful"


def map_expectancy(
    *,
    samples: Sequence[dict[str, Any] | Any] | None = None,
    focus_setup: str | None = None,
    current_r: float | None = None,
) -> dict[str, Any]:
    """Aggregate expectancy in R for a setup focus.

    expectancyR = mean(rMultiple) among matching samples
    (= winRate * avgWinR - lossRate * |avgLossR|).
    """
    focus = focus_setup.strip() if isinstance(focus_setup, str) and focus_setup.strip() else None
    if focus == "none":
        focus = None

    matched: list[float] = []
    if samples:
        for raw in samples:
            try:
                if isinstance(raw, dict):
                    setup = raw.get("entrySetup")
                    if not isinstance(setup, str):
                        setup = raw.get("entry_setup")
                    r_raw = raw.get("rMultiple")
                    if r_raw is None:
                        r_raw = raw.get("r_multiple")
                else:
                    setup = getattr(raw, "entrySetup", None) or getattr(
                        raw, "entry_setup", None
                    )
                    r_raw = getattr(raw, "rMultiple", None)
                    if r_raw is None:
                        r_raw = getattr(raw, "r_multiple", None)
                if not isinstance(setup, str) or not setup.strip() or setup.strip() == "none":
                    continue
                if focus is not None and setup.strip() != focus:
                    continue
                r = float(r_raw)
            except (TypeError, ValueError, AttributeError):
                continue
            matched.append(r)

    cur: float | None = None
    if current_r is not None:
        try:
            cur = float(current_r)
        except (TypeError, ValueError):
            cur = None

    if not matched:
        return {
            "status": "none",
            "entrySetup": focus,
            "n": 0,
            "expectancyR": None,
            "winRate": None,
            "avgWinR": None,
            "avgLossR": None,
            "currentR": cur,
            "why": ["missing_inputs"],
            "sampleQuality": sample_quality_from_n(0),
        }

    n = len(matched)
    wins = [r for r in matched if r > 0]
    losses = [r for r in matched if r < 0]
    expectancy_r = round(sum(matched) / n, 4)
    win_rate = round(len(wins) / n, 4)
    avg_win = round(sum(wins) / len(wins), 4) if wins else None
    avg_loss = round(sum(losses) / len(losses), 4) if losses else None

    why: list[str] = ["not_permission"]
    if n == 1 and cur is not None and abs(matched[0] - cur) < 1e-9:
        why.append("live_proxy")
    elif n >= 2:
        why.append("aggregated")
    if n < _READY_MIN_N:
        why.append("thin_sample")
        status: ExpectancyStatus = "thin"
    else:
        status = "ready"

    return {
        "status": status,
        "entrySetup": focus,
        "n": n,
        "expectancyR": expectancy_r,
        "winRate": win_rate,
        "avgWinR": avg_win,
        "avgLossR": avg_loss,
        "currentR": cur,
        "why": why,
        "sampleQuality": sample_quality_from_n(n),
    }


def build_expectancy_dict(
    *,
    samples: Sequence[dict[str, Any] | Any] | None = None,
    focus_setup: str | None = None,
    current_r: float | None = None,
) -> dict[str, Any]:
    return map_expectancy(
        samples=samples,
        focus_setup=focus_setup,
        current_r=current_r,
    )
