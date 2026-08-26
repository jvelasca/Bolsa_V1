"""DEX-4 — Confirm coordinators package (Confirm = orquestador)."""

from __future__ import annotations

from bolsa_application.confirm.execution import ExecutionCoordinator
from bolsa_application.confirm.exit_gate import ExitGateCoordinator
from bolsa_application.confirm.identity import IdentityCoordinator
from bolsa_application.confirm.opening_gate import OpeningGateCoordinator
from bolsa_application.confirm.position_sync import PositionSyncCoordinator
from bolsa_application.confirm.risk_gate import RiskGateCoordinator
from bolsa_application.confirm.submit_intent import SubmitIntentCoordinator

__all__ = [
    "ExecutionCoordinator",
    "ExitGateCoordinator",
    "IdentityCoordinator",
    "OpeningGateCoordinator",
    "PositionSyncCoordinator",
    "RiskGateCoordinator",
    "SubmitIntentCoordinator",
]
