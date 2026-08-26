"""DEX-4 — Confirm = orquestador (ADR-035).

Ancla spine: ConfirmRecommendationIntent compone Identity / RiskGate /
OpeningGate / ExitGate / Execution / SubmitIntent / PositionSync.
Semántica OR-1…OR-4 / DEX-1…3 intacta (regresión en batería existente).
"""

from __future__ import annotations

from bolsa_application.confirm import (
    ExecutionCoordinator,
    ExitGateCoordinator,
    IdentityCoordinator,
    OpeningGateCoordinator,
    PositionSyncCoordinator,
    RiskGateCoordinator,
    SubmitIntentCoordinator,
)
from bolsa_application.confirm_recommendation import ConfirmRecommendationIntent


def test_dex4_confirm_composes_seven_coordinators() -> None:
    uc = ConfirmRecommendationIntent()
    assert isinstance(uc._identity, IdentityCoordinator)
    assert isinstance(uc._risk, RiskGateCoordinator)
    assert isinstance(uc._opening, OpeningGateCoordinator)
    assert isinstance(uc._exit, ExitGateCoordinator)
    assert isinstance(uc._execution, ExecutionCoordinator)
    assert isinstance(uc._submit, SubmitIntentCoordinator)
    assert isinstance(uc._positions, PositionSyncCoordinator)


def test_dex4_orchestrator_module_is_thin() -> None:
    """confirm_recommendation.py debe quedar como orquestador (~<1100 líneas)."""
    from pathlib import Path

    import bolsa_application.confirm_recommendation as mod

    path = Path(mod.__file__)
    lines = path.read_text(encoding="utf-8").count("\n") + 1
    assert lines < 1100, f"Confirm orquestador demasiado grueso: {lines} líneas"
    # God Use Case pre-DEX-4 ~1531; post-extracción debe caber con holgura.
    assert lines < 1531
