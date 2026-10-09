"""PAPER-2 — DTO y contrato HTTP de ``/auto/paper-evidence``.

Certifica que el DTO de respuesta **valida** el payload del lector, que el fail-closed sin cuenta
no emite la confirmación (todos los criterios ``unknown``, ``UNKNOWN ≠ 0``) y que el aislamiento
por cuenta se respeta **a nivel de ruta HTTP**: la cabecera ``X-Account-Id`` acota la lectura y un
cierre durable de OTRA cuenta no entra en el DTO.

Hermético: no necesita PostgreSQL (la sesión y las fuentes durables se sustituyen por dobles).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_paper_evidence as route
from bolsa_api.api.dependencies import get_db_session
from bolsa_api.api.v1.routes.auto_paper_evidence import AutoPaperEvidenceDto
from bolsa_api.main import create_app
from bolsa_application.auto_operational_monitor import AUTO_CYCLE_SETTLEMENT_EVENT
from bolsa_application.paper_evidence_protocol import (
    PAPER_EVIDENCE_SNAPSHOT_EVENT,
    build_paper_evidence_snapshot_entry,
)
from bolsa_application.paper_evidence_reader import empty_paper_evidence

_ACCOUNT = "acc-http-1"
_OTHER_ACCOUNT = "acc-http-2"


def test_no_account_scope_is_a_valid_dto_with_all_criteria_unknown() -> None:
    payload = empty_paper_evidence("", ["orb-1"], note="no_account_scope")
    dto = AutoPaperEvidenceDto(**payload)

    assert dto.verdict == "NO_CONFIRMED"
    assert dto.readOnly is True
    assert dto.notes[0] == "no_account_scope"
    assert {item.status for item in dto.criteria} == {"unknown"}
    assert dto.metCriterionIds == []
    assert dto.fillsWindowFull is False
    assert dto.fillsTotalForAccount is None
    # El token reservado no aparece suelto (frontera de palabra): ``NO_CONFIRMED`` no lo es.
    assert re.search(r"\bCONFIRMED\b", json.dumps(payload)) is None


def test_dto_keeps_nullable_counts_as_none_and_never_zero() -> None:
    payload = empty_paper_evidence("acc-1")
    dto = AutoPaperEvidenceDto(**payload)

    window = next(item for item in dto.criteria if item.id == "window")
    assert window.status == "unknown"
    assert window.counts["days"] is None
    assert window.counts["episodes"] is None


# ── Contrato HTTP (aislamiento por cuenta + fail-closed), con dobles de las fuentes ──────────


@dataclass(frozen=True, slots=True)
class _Fill:
    execution_id: str
    side: str
    price: Decimal
    quantity: Decimal
    cycle_id: str | None
    reference_mid: Decimal | None = Decimal("100")
    strategy_version_id: str | None = "orb-1"
    account_id: str = _ACCOUNT


@dataclass(frozen=True, slots=True)
class _Entry:
    account_id: str | None
    event_type: str
    payload: dict[str, Any]
    decision_id: str = "JNL-x"


def _round_trip(cycle: str) -> list[_Fill]:
    return [
        _Fill(f"{cycle}#buy", "buy", Decimal("100"), Decimal("10"), cycle),
        _Fill(f"{cycle}#sell", "sell", Decimal("110"), Decimal("10"), cycle),
    ]


def _settlement(cycle: str, account_id: str | None) -> _Entry:
    return _Entry(
        account_id=account_id,
        event_type=AUTO_CYCLE_SETTLEMENT_EVENT,
        payload={
            "event": AUTO_CYCLE_SETTLEMENT_EVENT,
            "cycleId": cycle,
            "pnl": "100",
            "pnlMeasurement": "COMPLETE",
            "closedQty": "10",
        },
    )


class _FakeStore:
    def __init__(self, fills: list[_Fill], cycle_ids: list[str]) -> None:
        self._fills = fills
        self._cycle_ids = cycle_ids

    async def list_recent_cycle_ids(self, account_id: str | None, *, limit: int = 500) -> list[str]:
        return list(self._cycle_ids[:limit])

    async def list_by_cycle_ids(
        self, account_id: str | None, cycle_ids: list[str], limit: int = 5000
    ) -> list[_Fill]:
        return list(self._fills[:limit])

    async def count_by_strategy_version(
        self, *, account_id: str | None = None
    ) -> dict[str | None, int]:
        return {"orb-1": len(self._fills)}


class _FakeRepository:
    """Doble del spine durable: soporta lectura por decisión, ``list_entries`` y ``append``.

    ``append`` modela la idempotencia real del repositorio (``ON CONFLICT DO NOTHING`` sobre
    ``dedupe_key``): repetir la misma identidad natural no duplica la fila.
    """

    def __init__(self, entries: list[_Entry]) -> None:
        self._entries = entries

    async def list_by_decision_ids(self, decision_ids: list[str]) -> list[_Entry]:
        return list(self._entries)

    async def list_entries(
        self,
        *,
        account_id: str,
        instrument_id: str | None = None,
        since: str | None = None,
        event_type: str | None = None,
        engine_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Any], int]:
        rows = [
            entry
            for entry in self._entries
            if getattr(entry, "account_id", None) == account_id
            and (event_type is None or getattr(entry, "event_type", None) == event_type)
        ]
        return rows[offset : offset + limit], len(rows)

    async def append(self, entry: Any) -> Any:
        key = getattr(entry, "dedupe_key", None)
        if key and any(getattr(existing, "dedupe_key", None) == key for existing in self._entries):
            return entry
        self._entries.append(entry)
        return entry


def _patch_sources(
    monkeypatch: pytest.MonkeyPatch, store: _FakeStore, repo: _FakeRepository
) -> None:
    monkeypatch.setattr(
        "bolsa_application.sim_durable_store.PostgresSimFillFinanceContextStore",
        lambda session, autocommit=False: store,
    )
    monkeypatch.setattr(
        "bolsa_infrastructure.database.repositories.journal_repository.SqlAlchemyJournalRepository",
        lambda session: repo,
    )


class _Session:
    """Doble de ``AsyncSession``: solo lo que usan las rutas (``commit``/``rollback``)."""

    async def commit(self) -> None:  # pragma: no cover — trivially exercised by the POST route
        return None

    async def rollback(self) -> None:  # pragma: no cover
        return None


def _app_with_dummy_session():  # noqa: ANN202 — helper de test
    app = create_app()

    async def _session():  # noqa: ANN202 — doble: las fuentes ignoran la sesión
        yield _Session()

    app.dependency_overrides[get_db_session] = _session
    return app


async def _get(app, path: str, *, headers: dict[str, str] | None = None):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers)


@pytest.mark.asyncio
async def test_settlement_of_another_account_is_excluded_over_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un cierre de OTRA cuenta no entra en el DTO, y la cabecera acota la lectura a esta cuenta."""
    app = _app_with_dummy_session()
    cycle = "cyc-http-1"
    _patch_sources(
        monkeypatch,
        _FakeStore(fills=_round_trip(cycle), cycle_ids=[cycle]),
        _FakeRepository([_settlement(cycle, account_id=_OTHER_ACCOUNT)]),
    )
    seen: dict[str, str | None] = {}

    async def _scope(_request, account_id):  # noqa: ANN001 — registra la cuenta de la cabecera
        seen["account_id"] = account_id
        return account_id

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)

    response = await _get(
        app, "/api/auto/paper-evidence", headers={"X-Account-Id": _ACCOUNT}
    )

    assert response.status_code == 200
    body = response.json()
    # La cabecera viaja al scope: no hay degradación a lectura global.
    assert seen["account_id"] == _ACCOUNT
    assert body["accountId"] == _ACCOUNT
    assert body["reconciliation"]["fillsLoaded"] is True
    assert body["reconciliation"]["settlementsTotal"] == 0
    assert body["verdict"] == "NO_CONFIRMED"


@pytest.mark.asyncio
async def test_no_account_scope_is_fail_closed_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin cuenta visible el endpoint no lee nada: todos los criterios ``unknown`` (fail-closed)."""
    app = _app_with_dummy_session()

    async def _no_scope(_request, account_id):  # noqa: ANN001
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)

    response = await _get(app, "/api/auto/paper-evidence")

    assert response.status_code == 200
    body = response.json()
    assert body["notes"][0] == "no_account_scope"
    assert {item["status"] for item in body["criteria"]} == {"unknown"}
    assert body["fillsTotalForAccount"] is None
    assert body["verdict"] == "NO_CONFIRMED"


# ── Frente B — protocolo longitudinal PAPER (histórico + captura durable) ────────────────────


def _evidence(as_of: str) -> dict[str, Any]:
    """Lectura de evidencia mínima (la que consumiría el snapshot)."""
    return {
        "schemaVersion": "paper-evidence/1",
        "asOf": as_of,
        "metCriterionIds": ["operations"],
        "unmetCriterionIds": ["sessions"],
        "unknownCriterionIds": ["window"],
        "contradictions": [],
        "blockers": [],
        "fillsWindowFull": False,
        "fillsTotalForAccount": 3,
    }


async def _post(app, path: str, *, headers: dict[str, str] | None = None):  # noqa: ANN001
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, headers=headers)


@pytest.mark.asyncio
async def test_history_returns_durable_series_oldest_first_and_never_confirms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La serie sale del spine (una fila por día), ordenada, y jamás emite la confirmación."""
    app = _app_with_dummy_session()
    repo = _FakeRepository(
        [
            build_paper_evidence_snapshot_entry(
                account_id=_ACCOUNT, evidence=_evidence("2026-10-09T00:00:00Z")
            ),
            build_paper_evidence_snapshot_entry(
                account_id=_ACCOUNT, evidence=_evidence("2026-10-08T00:00:00Z")
            ),
            # Ruido: otra cuenta y otro tipo de evento no entran en la serie.
            build_paper_evidence_snapshot_entry(
                account_id=_OTHER_ACCOUNT, evidence=_evidence("2026-10-07T00:00:00Z")
            ),
            _Entry(account_id=_ACCOUNT, event_type="auto_entry_decision", payload={}),
        ]
    )
    _patch_sources(monkeypatch, _FakeStore([], []), repo)

    async def _scope(_request, account_id):  # noqa: ANN001
        return account_id

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)

    response = await _get(
        app, "/api/auto/paper-evidence/history", headers={"X-Account-Id": _ACCOUNT}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["readOnly"] is True
    assert body["verdict"] == "NO_CONFIRMED"
    assert body["accountId"] == _ACCOUNT
    assert [snapshot["asOf"] for snapshot in body["snapshots"]] == [
        "2026-10-08T00:00:00Z",
        "2026-10-09T00:00:00Z",
    ]
    assert body["snapshots"][0]["metCount"] == 1
    assert body["snapshots"][0]["unmetCount"] == 1
    assert body["snapshots"][0]["unknownCount"] == 1


@pytest.mark.asyncio
async def test_history_without_account_is_empty_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app_with_dummy_session()

    async def _no_scope(_request, account_id):  # noqa: ANN001
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)

    response = await _get(app, "/api/auto/paper-evidence/history")

    assert response.status_code == 200
    body = response.json()
    assert body["accountId"] is None
    assert body["snapshots"] == []
    assert body["notes"] == ["no_account_scope"]
    assert body["verdict"] == "NO_CONFIRMED"


@pytest.mark.asyncio
async def test_snapshot_post_records_one_durable_point_and_is_idempotent_per_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La captura escribe UNA fila durable por día; repetirla no duplica ni pisa la primera."""
    app = _app_with_dummy_session()
    repo = _FakeRepository([])
    _patch_sources(monkeypatch, _FakeStore([], []), repo)

    async def _scope(_request, account_id):  # noqa: ANN001
        return account_id

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)

    first = await _post(
        app, "/api/auto/paper-evidence/snapshot", headers={"X-Account-Id": _ACCOUNT}
    )
    second = await _post(
        app, "/api/auto/paper-evidence/snapshot", headers={"X-Account-Id": _ACCOUNT}
    )

    assert first.status_code == 200
    assert first.json()["recorded"] is True
    assert first.json()["verdict"] == "NO_CONFIRMED"
    assert second.status_code == 200
    recorded = [
        entry
        for entry in repo._entries
        if getattr(entry, "event_type", None) == PAPER_EVIDENCE_SNAPSHOT_EVENT
    ]
    assert len(recorded) == 1


@pytest.mark.asyncio
async def test_snapshot_post_without_account_does_not_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app_with_dummy_session()
    repo = _FakeRepository([])
    _patch_sources(monkeypatch, _FakeStore([], []), repo)

    async def _no_scope(_request, account_id):  # noqa: ANN001
        return None

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _no_scope)

    response = await _post(app, "/api/auto/paper-evidence/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["recorded"] is False
    assert body["note"] == "no_account_scope"
    assert repo._entries == []
