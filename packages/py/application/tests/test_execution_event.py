"""V2.14 E1 — ExecutionEvent idempotencia financiera (P1-01) GATED.

Semántica que el audit pide (no contador): la idempotencia es la key
``execution_id``; un fill duplicado no materializa dinero dos veces; y la
materialización real (Position/Ledger) NO se abre por defecto (H4/H3 honesto:
captura sin apply hasta go explícito).
"""

from __future__ import annotations

import pytest

from bolsa_application.execution_event import (
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_fill_idempotent,
    apply_pending_execution,
)


def _exec(event_id: str = "ev-1", *, qty: str = "40") -> ExecutionEvent:
    from decimal import Decimal

    return ExecutionEvent(
        execution_id=event_id,
        order_id="lo-fill-1",
        venue="LIVE",
        venue_order_id="xtb-11",
        fill_seq=1,
        qty=Decimal(qty),
        account_id="acc-1",
    )


@pytest.mark.asyncio
async def test_duplicate_execution_id_skips_finance_apply() -> None:
    """El MISMO execution_id insertado dos veces → el 2º NO vuelve a materializar."""
    store = InMemoryExecutionEventStore()
    apply_calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        apply_calls.append(execution.execution_id)
        return True

    ev = _exec()
    first = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    assert first == "applied"
    second = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    # El duplicado se descarta: aunque permit=True y haya applier, NO se aplica 2×.
    assert second == "duplicate_skipped"
    assert apply_calls == ["ev-1"]  # una sola materialización


@pytest.mark.asyncio
async def test_permit_false_captures_but_never_materializes() -> None:
    """Sin go → la fila se captura pero Position/Ledger NO se tocan (default)."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        raise AssertionError("apply_finance no debe invocarse sin permit")

    ev = _exec()
    decision = await apply_fill_idempotent(
        store, execution=ev, permit=False, apply_finance=applier
    )
    assert decision == "captured_pending_operator_consent"
    assert await store.get(ev.execution_id) is not None  # traza persistida


@pytest.mark.asyncio
async def test_applier_false_returns_captured_not_applied() -> None:
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        return False

    ev = _exec()
    decision = await apply_fill_idempotent(
        store, execution=ev, permit=True, apply_finance=applier
    )
    assert decision == "captured_not_applied"


@pytest.mark.asyncio
async def test_default_no_applier_never_materializes() -> None:
    """Incluso llamando sin applier ni permit: solo captura (fail-closed)."""
    store = InMemoryExecutionEventStore()
    ev = _exec()
    assert (
        await apply_fill_idempotent(store, execution=ev)
        == "captured_pending_operator_consent"
    )


def test_event_requires_execution_id() -> None:
    from decimal import Decimal

    with pytest.raises(ValueError):
        ExecutionEvent(
            execution_id="",
            order_id="o",
            venue="LIVE",
            qty=Decimal("1"),
        )


# ---------------------------------------------------------------------------
# Auditoría 3 — dos fases: capitalizar sin go y aplicar DESPUÉS (go tardío)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_phase_consent_apply_pending_after_captured() -> None:
    """Regresión Aud3: un go otorgado DESPUÉS de la captura SÍ materializa.

    El flujo honesto de consentimiento del operador es: T0 captura sin go
    (permit=False, no se toca dinero); T1 llega el go aprobando y se aplica vía
    ``apply_pending_execution``. Antes de esta corrección la fase T1 chocaba con
    ``duplicate_skipped`` (la traza ya existía) y el dinero nunca se materializaba.
    """
    store = InMemoryExecutionEventStore()
    applied: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        applied.append(execution.execution_id)
        return True

    ev = _exec("ev-consent-1")

    # T0 — fase de captura, aún sin go: Position/Ledger NO se tocan.
    capture = await apply_fill_idempotent(
        store, execution=ev, permit=False, apply_finance=applier
    )
    assert capture == "captured_pending_operator_consent"
    assert applied == []  # sin materializar

    # T1 — el operador/máquina da el go y la capa aprobante retoma la traza.
    decision = await apply_pending_execution(
        store, execution_id=ev.execution_id, apply_finance=applier
    )
    assert decision == "applied"
    assert applied == ["ev-consent-1"]  # exactamente una materialización


@pytest.mark.asyncio
async def test_apply_pending_requires_existing_capture() -> None:
    """Fase 2 sobre una traza inexistente → event_not_found (fail-closed)."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        raise AssertionError("apply_finance no debe invocarse sin traza capturada")

    decision = await apply_pending_execution(
        store, execution_id="ev-ghost", apply_finance=applier
    )
    assert decision == "event_not_found"


@pytest.mark.asyncio
async def test_apply_pending_applier_false_not_consumed_allows_retry() -> None:
    """Si el apply no fue efectivo, NO se consume: el caller puede reintentar."""
    store = InMemoryExecutionEventStore()

    outcomes = iter([False, True])
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return next(outcomes)

    ev = _exec("ev-retry-1")
    await apply_fill_idempotent(store, execution=ev, permit=False)

    first = await apply_pending_execution(
        store, execution_id=ev.execution_id, apply_finance=applier
    )
    assert first == "captured_not_applied"
    # Reintento: la traza sigue ahí y el applier ahora es efectivo → applied.
    second = await apply_pending_execution(
        store, execution_id=ev.execution_id, apply_finance=applier
    )
    assert second == "applied"
    assert calls == ["ev-retry-1", "ev-retry-1"]


@pytest.mark.asyncio
async def test_two_phase_no_double_materialization_when_apply_idempotent() -> None:
    """Una confirmación repetida NO duplica dinero si apply_finance es idempotente.

    apply_finance es idempotente por ``execution_id``: al reintentar tras una
    materialización ya registrada no materializa de nuevo (devuelve False → la
    capa trata esa fila como ya aplicada sin volver a tocar Position/Ledger).
    """
    store = InMemoryExecutionEventStore()
    applied: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        # Idempotencia del kernel por execution_id: primer intento efectivo,
        # cualquiera posterior sin efecto (ya registrada).
        if execution.execution_id in applied:
            return False
        applied.append(execution.execution_id)
        return True

    ev = _exec("ev-double-1")
    await apply_fill_idempotent(store, execution=ev, permit=False)

    first = await apply_pending_execution(
        store, execution_id=ev.execution_id, apply_finance=applier
    )
    assert first == "applied"
    second = await apply_pending_execution(
        store, execution_id=ev.execution_id, apply_finance=applier
    )
    assert second == "captured_not_applied"
    assert applied == ["ev-double-1"]  # una sola materialización
