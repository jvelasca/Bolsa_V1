"""v2.88.137 (AUDITORIA3) — worker periódico del OUTBOX de alertas.

Hermético (sin PostgreSQL): se sustituye el caso de uso ``ProcessAlertDeliveries`` por un doble y
se ejercita ``_process_once`` (recuento por desenlace + WARNING de ``DEAD_LETTER``) y el gate
``ALERT_DELIVERY_WORKER_ENABLED`` (ON por defecto, OFF con ``0/false/no/off``).
"""

from __future__ import annotations

import logging

import pytest

from bolsa_api.background import alert_delivery_worker as worker
from bolsa_infrastructure.alerts.alert_channels import AlertChannelDispatchResult


class _FakeSession:
    def __init__(self) -> None:
        self.rolled_back = False

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[_FakeSession] = []

    def __call__(self) -> _FakeSessionFactory:
        return self

    async def __aenter__(self) -> _FakeSession:
        session = _FakeSession()
        self.sessions.append(session)
        return session

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeUseCase:
    def __init__(self, results: list[AlertChannelDispatchResult]) -> None:
        self._results = results
        self.limits: list[int] = []

    async def execute(self, *, limit: int = 50) -> list[AlertChannelDispatchResult]:
        self.limits.append(limit)
        return self._results


def _result(
    subscription_id: str,
    *,
    ok: bool,
    will_retry: bool = False,
    error: str | None = None,
    attempt: int = 1,
    delivery_id: str | None = None,
    channel: str = "webhook",
) -> AlertChannelDispatchResult:
    return AlertChannelDispatchResult(
        subscription_id=subscription_id,
        channel=channel,
        ok=ok,
        error=error,
        attempt=attempt,
        will_retry=will_retry,
        delivery_id=delivery_id,
    )


def test_worker_enabled_defaults_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(worker._ENV_ENABLED, raising=False)
    assert worker._worker_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "OFF", " False "])
def test_worker_enabled_explicit_off(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(worker._ENV_ENABLED, value)
    assert worker._worker_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "on", "cualquiera"])
def test_worker_enabled_any_other_value_on(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(worker._ENV_ENABLED, value)
    assert worker._worker_enabled() is True


def test_start_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(worker._ENV_ENABLED, "0")
    assert worker.start_alert_delivery_worker(_FakeSessionFactory()) is None  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_process_once_counts_by_outcome_and_alerts_dead_letter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = [
        _result("sub-ok", ok=True),
        _result("sub-retry", ok=False, will_retry=True, error="timeout", delivery_id="d-2"),
        _result(
            "sub-dead",
            ok=False,
            will_retry=False,
            error="presupuesto agotado",
            attempt=5,
            delivery_id="d-3",
            channel="email",
        ),
    ]
    use_case = _FakeUseCase(results)
    monkeypatch.setattr(
        worker,
        "get_process_alert_deliveries_use_case",
        lambda _session: use_case,
    )

    summary = await worker._process_once(_FakeSessionFactory())  # type: ignore[arg-type]

    assert summary == {"claimed": 3, "delivered": 1, "retryable_failed": 1, "dead_letter": 1}
    assert use_case.limits == [worker.DELIVERY_BATCH_LIMIT]


@pytest.mark.asyncio
async def test_process_once_logs_warning_per_dead_letter(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        worker,
        "get_process_alert_deliveries_use_case",
        lambda _session: _FakeUseCase(
            [_result("sub-dead", ok=False, will_retry=False, error="rechazado", delivery_id="d-9")]
        ),
    )
    with caplog.at_level(logging.WARNING, logger=worker.__name__):
        await worker._process_once(_FakeSessionFactory())  # type: ignore[arg-type]

    assert "DEAD_LETTER" in caplog.text
    assert "d-9" in caplog.text


@pytest.mark.asyncio
async def test_process_once_empty_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        worker, "get_process_alert_deliveries_use_case", lambda _session: _FakeUseCase([])
    )
    summary = await worker._process_once(_FakeSessionFactory())  # type: ignore[arg-type]
    assert summary == {"claimed": 0, "delivered": 0, "retryable_failed": 0, "dead_letter": 0}
