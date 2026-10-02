"""AUTO v2.88.28 — exactly-once de los hechos durables de PROTECTION (hermético).

Qué certifica este fichero, sin I/O:

1. **Cada ``kind`` del vocabulario con su ``revision_id`` produce una clave determinista.**
   Un productor que aporta la revisión durable de la transición deriva
   ``auto_protection_event:{account}:{engine}:{cycle}:{kind}:{revision}`` y el alta es
   idempotente: el MISMO hecho reemitido es UNA fila.
2. **Una revisión nueva es un hecho nuevo.** Otra transición legítima (otra revisión) ⇒ otra
   clave ⇒ otra fila. La ``kind`` sola no basta (la propia doctrina de la 2.88.27).
3. **Sin revisión no se finge identidad.** Un hecho sin ``revision_id`` conserva ``NULL`` y el
   INSERT plano del histórico: es el límite DECLARADO, no una unicidad inventada.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from bolsa_api.background.auto_simulation_worker import AutoSimulationWorker
from bolsa_application.auto_operational_audit import durable_fact_dedupe_key
from bolsa_application.auto_operational_monitor import AUTO_PROTECTION_EVENT
from bolsa_application.protection_event_kind import PROTECTION_EVENT_KINDS

_ACCOUNT = "acc-prot"
_ENGINE = "auto-sim"
_CYCLE = "cyc-prot-1"
_REVISION = "REV-1111111111111111"


class _DedupingSink:
    """Sumidero con la MISMA semántica del ``append`` idempotente: una fila por ``dedupe_key``."""

    def __init__(self) -> None:
        self.by_key: dict[str, Any] = {}
        self.raw: list[Any] = []

    async def __call__(self, entry: Any) -> None:
        self.raw.append(entry)
        key = getattr(entry, "dedupe_key", None)
        if key:
            self.by_key.setdefault(key, entry)


def _worker(sink: Any) -> AutoSimulationWorker:
    worker = object.__new__(AutoSimulationWorker)
    worker._account_id = _ACCOUNT
    worker._engine_id = _ENGINE
    worker._operational_audit_sink = sink
    worker._time = SimpleNamespace(strftime=lambda _fmt: "2026-10-02T10:00:00Z")
    return worker


async def _emit(worker: AutoSimulationWorker, kind: str, revision_id: str | None) -> None:
    await worker._v2_journal_protection(
        kind=kind,
        instrument_id="AAA",
        cycle_id=_CYCLE,
        position_id="pos-1",
        lifecycle_from="OPEN",
        lifecycle_to="PROTECTED",
        stop_before=95.0,
        stop_after=97.0,
        revision_id=revision_id,
        source="protect",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", sorted(PROTECTION_EVENT_KINDS))
async def test_each_protection_kind_with_a_revision_is_idempotent(kind: str) -> None:
    """Reemitir la MISMA transición (misma revisión) de cualquier ``kind`` ⇒ 1 fila."""
    sink = _DedupingSink()
    worker = _worker(sink)
    await _emit(worker, kind, _REVISION)
    await _emit(worker, kind, _REVISION)

    assert len(sink.raw) == 2, "el productor emite en cada intento"
    assert len(sink.by_key) == 1, "pero el hecho durable es UNO"
    entry = sink.raw[0]
    assert entry.event_type == AUTO_PROTECTION_EVENT
    expected = durable_fact_dedupe_key(
        event_type=AUTO_PROTECTION_EVENT,
        account_id=_ACCOUNT,
        engine_id=_ENGINE,
        cycle_id=_CYCLE,
        kind=kind,
        revision_id=_REVISION,
    )
    assert entry.dedupe_key == expected


@pytest.mark.asyncio
async def test_a_distinct_revision_is_a_distinct_fact() -> None:
    """Otra transición legítima del mismo ``kind`` (otra revisión) ⇒ otra fila."""
    sink = _DedupingSink()
    worker = _worker(sink)
    await _emit(worker, "TRAIL_ADVANCED", _REVISION)
    await _emit(worker, "TRAIL_ADVANCED", "REV-2222222222222222")
    assert len(sink.by_key) == 2


@pytest.mark.asyncio
async def test_without_a_revision_the_fact_declares_no_identity() -> None:
    """Sin revisión durable no se inventa unicidad: ``dedupe_key`` queda ``None``."""
    sink = _DedupingSink()
    worker = _worker(sink)
    await _emit(worker, "PROTECT_APPLIED", None)
    assert len(sink.raw) == 1
    assert sink.raw[0].dedupe_key is None
    assert sink.by_key == {}
