"""Probabilistic Sharpe Ratio (PSR) y Deflated Sharpe Ratio (DSR).

Bailey & López de Prado (2012/2014). Sin scipy — CDF/PPF vía erf / Acklam.
DSR requiere trials_n >= 1 (registro de hipótesis exploradas).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

EULER_MASCHERONI = 0.5772156649015329


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Aproximación Acklam de la inversa de la N(0,1) CDF."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    if abs(p - 0.5) < 1e-12:
        return 0.0

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )

    plow = 0.02425
    phigh = 1 - plow

    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )

    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


def observed_sharpe(returns: Sequence[float]) -> float:
    arr = np.asarray(list(returns), dtype=float)
    if arr.size < 2:
        return 0.0
    std = float(arr.std(ddof=1))
    if std < 1e-12:
        return 0.0
    return float(arr.mean() / std)


def skewness_kurtosis(returns: Sequence[float]) -> tuple[float, float]:
    """Skewness muestral y kurtosis de Pearson (normal ≈ 3)."""
    arr = np.asarray(list(returns), dtype=float)
    n = arr.size
    if n < 3:
        return 0.0, 3.0
    mean = float(arr.mean())
    std = float(arr.std(ddof=1))
    if std < 1e-12:
        return 0.0, 3.0
    z = (arr - mean) / std
    skew = float(np.mean(z**3))
    kurt = float(np.mean(z**4))  # Pearson
    return skew, kurt


def probabilistic_sharpe_ratio(
    sr_hat: float,
    *,
    n_obs: int,
    skew: float,
    kurtosis: float,
    sr_benchmark: float = 0.0,
) -> float:
    """
    PSR = Φ( (SR̂ - SR*) / σ̂(SR̂) )
    σ̂(SR̂) = sqrt( (1 - γ3 SR̂ + ((γ4-1)/4) SR̂²) / (n-1) )
    """
    if n_obs < 3:
        return 0.0
    denom_inside = 1.0 - skew * sr_hat + ((kurtosis - 1.0) / 4.0) * sr_hat**2
    if denom_inside <= 0:
        denom_inside = 1e-12
    sr_std = math.sqrt(denom_inside / (n_obs - 1))
    if sr_std < 1e-12:
        return 1.0 if sr_hat > sr_benchmark else 0.0
    return _norm_cdf((sr_hat - sr_benchmark) / sr_std)


def expected_max_sharpe_null(*, trials_n: int, sr_std: float) -> float:
    """E[max SR] bajo H0 con N trials independientes (EVT / Bailey–LdP)."""
    if trials_n < 1:
        raise ValueError("trials_n must be >= 1 for DSR")
    if trials_n == 1:
        return 0.0
    n = float(trials_n)
    return float(
        sr_std
        * (
            (1.0 - EULER_MASCHERONI) * _norm_ppf(1.0 - 1.0 / n)
            + EULER_MASCHERONI * _norm_ppf(1.0 - 1.0 / (n * math.e))
        )
    )


def deflated_sharpe_ratio(
    sr_hat: float,
    *,
    n_obs: int,
    skew: float,
    kurtosis: float,
    trials_n: int,
    trials_sr_std: float | None = None,
) -> float:
    """
    DSR ≡ PSR(SR* = E[max SR | N trials]).
    Si trials_n < 1 → ValueError (DSR inválido sin log de trials).
    """
    if trials_n < 1:
        raise ValueError("DSR inválido: trials_n < 1 — registrar hipótesis en TrialsLog")
    if n_obs < 3:
        return 0.0
    denom_inside = 1.0 - skew * sr_hat + ((kurtosis - 1.0) / 4.0) * sr_hat**2
    if denom_inside <= 0:
        denom_inside = 1e-12
    sr_std = math.sqrt(denom_inside / (n_obs - 1))
    null_std = trials_sr_std if trials_sr_std is not None else sr_std
    sr_star = expected_max_sharpe_null(trials_n=trials_n, sr_std=null_std)
    return probabilistic_sharpe_ratio(
        sr_hat,
        n_obs=n_obs,
        skew=skew,
        kurtosis=kurtosis,
        sr_benchmark=sr_star,
    )


def psr_dsr_from_returns(
    returns: Sequence[float],
    *,
    trials_n: int,
    sr_benchmark: float = 0.0,
) -> tuple[float, float, float]:
    """Return (sr_hat, psr, dsr)."""
    arr = list(returns)
    sr = observed_sharpe(arr)
    skew, kurt = skewness_kurtosis(arr)
    n = len(arr)
    psr = probabilistic_sharpe_ratio(
        sr, n_obs=n, skew=skew, kurtosis=kurt, sr_benchmark=sr_benchmark
    )
    dsr = deflated_sharpe_ratio(
        sr, n_obs=n, skew=skew, kurtosis=kurt, trials_n=trials_n
    )
    return sr, psr, dsr
