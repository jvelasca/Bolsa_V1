"""Circuit breaker para el proveedor Yahoo Finance.

Complementa throttle + reintentos: tras N fallos consecutivos agotados,
abre el circuito un cooldown para no saturar Yahoo ni la cola de sync.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    """Estado del circuito Yahoo."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class YahooCircuitOpenError(RuntimeError):
    """El circuito Yahoo está abierto (cooldown tras fallos)."""


@dataclass
class YahooCircuitBreaker:
    """Breaker simple (proceso local) para llamadas Yahoo."""

    name: str = "yahoo"
    failure_threshold: int = field(
        default_factory=lambda: int(os.environ.get("YAHOO_CB_FAILURE_THRESHOLD", "5")),
    )
    cooldown_sec: float = field(
        default_factory=lambda: float(os.environ.get("YAHOO_CB_COOLDOWN_SEC", "60")),
    )
    success_threshold: int = field(
        default_factory=lambda: int(os.environ.get("YAHOO_CB_SUCCESS_THRESHOLD", "2")),
    )
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    opened_at: float | None = None
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0

    def before_call(self) -> None:
        """Rechaza si el circuito está abierto y el cooldown no ha expirado."""
        self.total_requests += 1
        now = time.monotonic()
        if self.state == CircuitState.OPEN:
            if self.opened_at is None or (now - self.opened_at) >= self.cooldown_sec:
                self.state = CircuitState.HALF_OPEN
                self.consecutive_successes = 0
            else:
                self.total_rejected += 1
                remaining = self.cooldown_sec - (now - (self.opened_at or now))
                raise YahooCircuitOpenError(
                    f"Yahoo circuit OPEN ({self.name}); retry in ~{remaining:.0f}s",
                )

    def record_success(self) -> None:
        """Cierra el circuito tras éxitos consecutivos en half-open."""
        self.total_successes += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        if self.state == CircuitState.HALF_OPEN:
            if self.consecutive_successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.opened_at = None
                self.consecutive_successes = 0
        else:
            self.state = CircuitState.CLOSED
            self.opened_at = None

    def record_failure(self) -> None:
        """Abre el circuito si se supera el umbral de fallos consecutivos."""
        self.total_failures += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        if self.state == CircuitState.HALF_OPEN or (
            self.consecutive_failures >= self.failure_threshold
        ):
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()

    def reset(self) -> None:
        """Reset manual (tests / ops)."""
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.opened_at = None

    def snapshot(self) -> dict[str, Any]:
        """Métricas para health / observabilidad."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejected": self.total_rejected,
            "failure_threshold": self.failure_threshold,
            "cooldown_sec": self.cooldown_sec,
        }
