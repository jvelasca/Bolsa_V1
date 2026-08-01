"""SC-6 — dispatch de alertas por canal."""

from bolsa_infrastructure.alerts.alert_channels import (
    AlertChannelDispatchResult,
    SignalAlertChannelDispatcher,
)

__all__ = ["AlertChannelDispatchResult", "SignalAlertChannelDispatcher"]
