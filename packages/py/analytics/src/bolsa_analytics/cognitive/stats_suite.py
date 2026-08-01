"""Suite estadística mínima Evidence Engine (RFC-008 D3 skeleton)."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np


def walk_forward_efficiency(in_sample_sharpe: float, out_of_sample_sharpe: float) -> float:
    """WFE = Sharpe_OOS / Sharpe_IS (protege división por cero)."""
    if abs(in_sample_sharpe) < 1e-12:
        return 0.0
    return float(out_of_sample_sharpe / in_sample_sharpe)


def _sharpe(returns: np.ndarray) -> float:
    if returns.size < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std < 1e-12:
        return 0.0
    return float(returns.mean() / std * math.sqrt(len(returns)))


def monte_carlo_permutation_p_value(
    trade_returns: Sequence[float],
    *,
    permutations: int = 2000,
    seed: int = 42,
) -> float:
    """
    p-value: P(Sharpe permutado >= Sharpe observado).
    Destruye el orden temporal; mantiene la distribución marginal.
    """
    arr = np.asarray(list(trade_returns), dtype=float)
    if arr.size < 3:
        return 1.0

    observed = _sharpe(arr)
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(permutations):
        perm = rng.permutation(arr)
        if _sharpe(perm) >= observed - 1e-15:
            count += 1
    return (count + 1) / (permutations + 1)
