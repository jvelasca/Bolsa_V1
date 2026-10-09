"""Frente B — driver periódico de la foto durable PAPER (protocolo longitudinal, ADR-046).

Certifica (y una mutación debe poder romper):

* Con el flag apagado el worker es **no-op** (``start_*`` devuelve ``None``): ``Δ motor = 0``.
* Un tick captura **una** foto por cuenta con identidad, idempotente por ``(cuenta, día)``.
* Una cuenta sin identidad **no** se finge y un fallo de una cuenta **no** tumba las demás.
* El snapshot escribe **solo** la traza del protocolo (``verdict`` literal ``NO_CONFIRMED``).

Hermético: sin PostgreSQL, sin red; repositorios y sesión sustituidos por dobles.
"""

from __future__ import annotations

import pytest

from bolsa_api.background import paper_evidence_snapshot_worker as w


class _FakeAccount:
    def __init__(self, account_id: str | None) -> None:
        self.id = account_id


class _FakeSession:
    def __init__(self, appended: list[object]) -> None:
        self.appended = appended
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args: object) -> bool:  # noqa: ANN401 — doble de sesión
        return False

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class _FakeSessionFactory:
    def __init__(self, appended: list[object]) -> None:
        self.appended = appended
        self.sessions: list[_FakeSession] = []

    def __call__(self) -> _FakeSession:
        session = _FakeSession(self.appended)
        self.sessions.append(session)
        return session


def _install_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    accounts: list[_FakeAccount],
    appended: list[object],
    evidence: dict[str, object] | None = None,
    fail_for: set[str] | None = None,
) -> None:
    from bolsa_infrastructure.database.repositories import account_repository as acc_repo
    from bolsa_infrastructure.database.repositories import journal_repository as jnl_repo

    failing = fail_for or set()

    class _Accounts:
        def __init__(self, session: object) -> None:
            self._session = session

        async def list_accounts(self) -> list[_FakeAccount]:
            return accounts

    class _Journal:
        def __init__(self, session: object) -> None:
            self._session = session

        async def append(self, entry: object) -> object:
            dedupe = getattr(entry, "dedupe_key", None)
            if dedupe and any(
                getattr(existing, "dedupe_key", None) == dedupe for existing in appended
            ):
                return entry
            appended.append(entry)
            return entry

    payload = evidence or {
        "schemaVersion": "paper-evidence/1",
        "asOf": "2026-10-09T12:00:00Z",
        "metCriterionIds": ["operations"],
        "unmetCriterionIds": [],
        "unknownCriterionIds": [],
        "contradictions": [],
        "blockers": [],
        "fillsWindowFull": False,
        "fillsTotalForAccount": 1,
    }

    async def _read(session: object, account_id: str, **kwargs: object) -> dict[str, object]:
        if account_id in failing:
            raise RuntimeError("fuente caída")
        return dict(payload)

    monkeypatch.setattr(acc_repo, "SqlAlchemyAccountRepository", _Accounts)
    monkeypatch.setattr(jnl_repo, "SqlAlchemyJournalRepository", _Journal)
    monkeypatch.setattr(w, "read_paper_evidence", _read)


def test_start_is_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAPER_EVIDENCE_SNAPSHOT_ENABLED", raising=False)
    assert w.start_paper_evidence_snapshot_worker(_FakeSessionFactory([])) is None


@pytest.mark.asyncio
async def test_tick_records_one_snapshot_per_account_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appended: list[object] = []
    _install_fakes(
        monkeypatch,
        accounts=[_FakeAccount("acc-1"), _FakeAccount("acc-2")],
        appended=appended,
    )
    factory = _FakeSessionFactory(appended)

    first = await w._record_snapshots_once(factory)  # noqa: SLF001 — unidad bajo prueba
    second = await w._record_snapshots_once(factory)  # noqa: SLF001

    assert first["recorded"] == 2
    # La identidad (cuenta, día) hace el reintento idempotente: sigue habiendo 2 filas.
    assert second["recorded"] == 2
    assert len(appended) == 2
    assert {entry.payload["accountId"] for entry in appended} == {"acc-1", "acc-2"}  # type: ignore[attr-defined]
    assert all(entry.payload["verdict"] == "NO_CONFIRMED" for entry in appended)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_account_without_identity_is_not_faked(monkeypatch: pytest.MonkeyPatch) -> None:
    appended: list[object] = []
    _install_fakes(
        monkeypatch,
        accounts=[_FakeAccount(None), _FakeAccount("acc-1")],
        appended=appended,
    )
    result = await w._record_snapshots_once(_FakeSessionFactory(appended))  # noqa: SLF001

    assert result["recorded"] == 1
    assert result["skipped"] == 1
    assert len(appended) == 1


@pytest.mark.asyncio
async def test_one_account_failure_does_not_break_the_tick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appended: list[object] = []
    _install_fakes(
        monkeypatch,
        accounts=[_FakeAccount("acc-bad"), _FakeAccount("acc-ok")],
        appended=appended,
        fail_for={"acc-bad"},
    )
    result = await w._record_snapshots_once(_FakeSessionFactory(appended))  # noqa: SLF001

    assert result["recorded"] == 1
    assert [entry.payload["accountId"] for entry in appended] == ["acc-ok"]  # type: ignore[attr-defined]
