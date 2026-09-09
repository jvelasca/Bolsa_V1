"""V2.14 E1 — ExecutionEvent idempotencia financiera (P1-01) GATED.

Semántica que el audit pide (no contador): la idempotencia es la key
``execution_id``; un fill duplicado no materializa dinero dos veces; y la
materialización real (Position/Ledger) NO se abre por defecto (H4/H3 honesto:
captura sin apply hasta go explícito).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from bolsa_application.execution_event import (
    LEASE_WINDOW_SECONDS,
    ExecutionEvent,
    InMemoryExecutionEventStore,
    apply_execution_financial_once,
    apply_fill_idempotent,
    apply_pending_execution,
    reap_stale_applying,
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
    first = await apply_fill_idempotent(store, execution=ev, permit=True, apply_finance=applier)
    assert first == "applied"
    second = await apply_fill_idempotent(store, execution=ev, permit=True, apply_finance=applier)
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
    decision = await apply_fill_idempotent(store, execution=ev, permit=False, apply_finance=applier)
    assert decision == "captured_pending_operator_consent"
    assert await store.get(ev.execution_id) is not None  # traza persistida


@pytest.mark.asyncio
async def test_applier_false_returns_captured_not_applied() -> None:
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        return False

    ev = _exec()
    decision = await apply_fill_idempotent(store, execution=ev, permit=True, apply_finance=applier)
    assert decision == "captured_not_applied"


@pytest.mark.asyncio
async def test_default_no_applier_never_materializes() -> None:
    """Incluso llamando sin applier ni permit: solo captura (fail-closed)."""
    store = InMemoryExecutionEventStore()
    ev = _exec()
    assert await apply_fill_idempotent(store, execution=ev) == "captured_pending_operator_consent"


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
    capture = await apply_fill_idempotent(store, execution=ev, permit=False, apply_finance=applier)
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

    decision = await apply_pending_execution(store, execution_id="ev-ghost", apply_finance=applier)
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


# ---------------------------------------------------------------------------
# V2.19 (P2-01) — workflow durable (Capture→APPLYING→APPLIED/FAILED/RETRY).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_durable_apply_fresh_materializes_once_and_marks_applied() -> None:
    """Un pass durable fresh: captura → APPLYING → apply → APPLIED (1 sola apply)."""
    store = InMemoryExecutionEventStore()
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return True

    ev = _exec("ev-durable-1")
    outcome = await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    assert outcome == "applied"
    assert calls == ["ev-durable-1"]
    row = await store.get(ev.execution_id)
    assert row is not None
    assert row.status == "APPLIED"
    assert row.applied_at is not None
    assert row.attempt_count == 1  # un solo APPLYING


@pytest.mark.asyncio
async def test_durable_apply_skips_when_already_applied() -> None:
    """Re-llamada idéntica tras APPLIED → already_applied; NO se re-materializa."""
    store = InMemoryExecutionEventStore()
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return True

    ev = _exec("ev-durable-2")
    assert (
        await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
        == "applied"
    )
    outcome = await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    assert outcome == "already_applied"
    assert calls == ["ev-durable-2"]  # una sola materialización


@pytest.mark.asyncio
async def test_durable_apply_retry_after_ineffective_apply() -> None:
    """Apply no efectivo → RETRY (reaplicable); el siguiente pass sí applica."""
    store = InMemoryExecutionEventStore()
    outcomes = iter([False, True])
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return next(outcomes)

    ev = _exec("ev-durable-retry")
    first = await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    assert first == "retry_scheduled"
    assert (await store.get(ev.execution_id)).status == "RETRY"  # type: ignore[union-attr]

    second = await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    assert second == "applied"
    assert calls == ["ev-durable-retry", "ev-durable-retry"]


@pytest.mark.asyncio
async def test_durable_apply_non_retryable_marks_failed() -> None:
    """Apply inefectivo y NO reaplicable → FAILED (revisión), no se reintenta solo."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        return False

    ev = _exec("ev-durable-failed")
    outcome = await apply_execution_financial_once(
        store,
        execution=ev,
        apply_finance=applier,
        retryable_on_ineffective=False,
    )
    assert outcome == "failed"
    assert (await store.get(ev.execution_id)).status == "FAILED"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_durable_apply_exception_marks_retry_not_applied() -> None:
    """Excepción en apply_finance → RETRY; JAMÁS se estampa un APPLIED falso."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        raise RuntimeError("network blip")

    ev = _exec("ev-durable-exc")
    outcome = await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    assert outcome == "retry_scheduled"
    row = await store.get(ev.execution_id)
    assert row is not None
    assert row.status == "RETRY"
    assert row.last_error == "apply_exception"


@pytest.mark.asyncio
async def test_durable_apply_reclaims_applying_stale_after_crash() -> None:
    """Crash tras APPLYING (antes de commit): tras vencer la lease un relaunch
    reclama y completa, sin que otro worker VIVO pueda robarlo.

    Simula el crash de proceso justo tras ``start_apply`` (fila dejada en APPLYING,
    dueño en vuelo). Mientras la lease es FRESCA un segundo pass NO puede robar el
    apply (no_apply_another_in_progress); solo cuando vence (dueño muerto/lease
    stale) el relaunch/reaper lo reclama por ``reclaim_stale_apply`` y completa
    exactamente una vez.
    """
    from datetime import timedelta

    store = InMemoryExecutionEventStore()
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return True

    ev = _exec("ev-durable-crash-apply")
    await store.capture(ev)
    assert await store.start_apply(ev.execution_id, owner="worker-a") is True  # crash en vivo.
    row = await store.get(ev.execution_id)
    assert row is not None and row.status == "APPLYING"

    # Mientras la lease es fresca, un segundo pass NO la roba (single-owner).
    fresh = await apply_execution_financial_once(
        store,
        execution=ev,
        apply_finance=applier,
        owner="worker-b",
    )
    assert fresh == "no_apply_another_in_progress"
    assert calls == []  # nadie aplicó todavía.

    # El dueño A ha caído (crash): el lease envejece → un relaunch reclama y aplica.
    now = datetime.now(UTC)
    store._rows[ev.execution_id] = replace(
        store._rows[ev.execution_id],
        updated_at=now - timedelta(seconds=LEASE_WINDOW_SECONDS + 60),
    )
    outcome = await apply_execution_financial_once(
        store,
        execution=ev,
        apply_finance=applier,
        owner="relaunch",
        lease_window_seconds=LEASE_WINDOW_SECONDS,
    )
    assert outcome == "applied"
    assert calls == ["ev-durable-crash-apply"]
    assert (await store.get(ev.execution_id)).status == "APPLIED"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_ineffective_reply_leaves_no_false_applied_signal() -> None:
    """Tras retry no se marca APPLIED por error; status queda coherente."""
    store = InMemoryExecutionEventStore()

    async def applier(execution: ExecutionEvent) -> bool:  # noqa: ARG001
        return False

    ev = _exec("ev-durable-sig")
    await apply_execution_financial_once(store, execution=ev, apply_finance=applier)
    row = await store.get(ev.execution_id)
    assert row.status == "RETRY"
    assert row.applied_at is None
    assert row.last_error == "apply_ineffective"


# ---------------------------------------------------------------------------
# V2.20 (P2-02) — reaper de APPLYING stale (lease del dueño caído).
# ---------------------------------------------------------------------------
def _age_event(store: InMemoryExecutionEventStore, execution_id: str, ago_s: int) -> None:
    from datetime import timedelta

    row = store._rows[execution_id]
    store._rows[execution_id] = replace(
        row,
        updated_at=datetime.now(UTC) - timedelta(seconds=ago_s),
    )


@pytest.mark.asyncio
async def test_reaper_reclaims_lease_stale_apply_to_applied() -> None:
    """P2-02: un APPLYING cuyo dueño murió (lease vencida) es barrido a APPLIED.

    El reaper reclama por lease (owner nuevo) y, con candidato + apply_finance
    idempotente, sube la traza a APPLYING→APPLIED UNA sola vez.
    """
    from datetime import timedelta

    store = InMemoryExecutionEventStore()
    calls: list[str] = []

    async def applier(execution: ExecutionEvent) -> bool:
        calls.append(execution.execution_id)
        return True

    id1, id2 = "ev-stale-a", "ev-live-b"
    for eid in (id1, id2):
        await store.capture(_exec(eid))
        await store.start_apply(eid, owner=f"dead-{eid}")
    _age_event(store, id1, LEASE_WINDOW_SECONDS + 90)  # A: dueño muerto → stale.
    # B: lease fresca (no stale) → el reaper NO la roba (single-owner).

    async def resolve(evt: ExecutionEvent) -> ExecutionEvent | None:
        return evt  # candidato = la propia fila reclaimada (re-aplicable).

    counts = await reap_stale_applying(
        store,
        owner="reaper-1",
        stale_before=datetime.now(UTC) - timedelta(seconds=LEASE_WINDOW_SECONDS),
        limit=10,
        resolve_candidate=resolve,
        apply_finance=applier,
    )

    assert counts["reclaimed"] == 1
    assert counts["applied"] == 1
    assert (await store.get(id1)).status == "APPLIED"  # type: ignore[union-attr]
    # B no fue robada (lease viva) ni aplicada.
    assert (await store.get(id2)).status == "APPLYING"  # type: ignore[union-attr]
    assert calls == [id1]


@pytest.mark.asyncio
async def test_reaper_orphan_without_candidate_becomes_retry() -> None:
    """P2-02: sin candidato re-derivable (bridge/sesión ausente) el reaper NO roba
    la fila ni la deja varada en APPLYING: la baja a RETRY (liberada, reaplicable)."""
    from datetime import timedelta

    store = InMemoryExecutionEventStore()
    eid = "ev-stale-orphan"
    await store.capture(_exec(eid))
    await store.start_apply(eid, owner="dead-worker")
    _age_event(store, eid, LEASE_WINDOW_SECONDS + 90)

    # Sin resolve_candidate ni apply_finance (fail-closed default).
    counts = await reap_stale_applying(
        store,
        owner="reaper-orphan",
        stale_before=datetime.now(UTC) - timedelta(seconds=LEASE_WINDOW_SECONDS),
    )

    assert counts["reclaimed"] == 1
    assert counts["retry"] == 1
    row = await store.get(eid)
    assert row is not None and row.status == "RETRY"
    assert row.lease_owner is None  # lease liberada.
    assert row.last_error == "lease_expired_no_candidate"
