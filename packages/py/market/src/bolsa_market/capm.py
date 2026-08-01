"""FIE F2.6 — CAPM cost of equity (`fund_capm_v1`).

``k_e = r_f + beta * ERP``

- **beta** vivo desde Yahoo ``defaultKeyStatistics.beta``.
- **r_f / ERP** versionados (no fetch Treasury/día-1). Cambiar ⇒ bump versión.
- Si falta beta o es inválida → caller cae a WACC sector (F2.4).

Usado como tasa de descuento del DCF (misma simplificación equity que F2.4).
"""

from __future__ import annotations

from typing import Any

FUND_CAPM_VERSION = "fund_capm_v1"

# Constantes versionadas (bump FUND_CAPM_VERSION si cambian)
CAPM_RF = 0.04
CAPM_ERP = 0.05
CAPM_BETA_FLOOR = 0.3
CAPM_BETA_CAP = 2.5


def clamp_beta(beta: float | None) -> float | None:
    if beta is None:
        return None
    try:
        b = float(beta)
    except (TypeError, ValueError):
        return None
    if b <= 0 or b != b:  # NaN
        return None
    return max(CAPM_BETA_FLOOR, min(CAPM_BETA_CAP, b))


def compute_capm_cost_of_equity(
    beta: float | None,
    *,
    rf: float = CAPM_RF,
    erp: float = CAPM_ERP,
) -> tuple[float | None, str | None, dict[str, Any] | None]:
    """
    Returns ``(ke, method, meta)`` o ``(None, None, None)`` si no hay beta usable.
    """
    b = clamp_beta(beta)
    if b is None:
        return None, None, None
    if erp <= 0 or rf < 0:
        return None, None, None
    ke = float(rf) + b * float(erp)
    return (
        round(ke, 4),
        FUND_CAPM_VERSION,
        {"beta": round(b, 4), "rf": float(rf), "erp": float(erp)},
    )
