"""Handler ``dia_d_replay`` — subproceso aislado, timeout y artefacto atómico.

Hermético: el subproceso se simula con un doble que escribe (o no) el artefacto en
el ``cwd`` temporal. Cubre los criterios falsables del plan:

* exit 0 + artefacto válido ⇒ parte con el resumen del replay;
* exit ≠ 0 ⇒ fallo con el ``tail`` de stderr y el artefacto ANTERIOR intacto;
* timeout ⇒ ``kill`` y fallo declarado;
* artefacto de otra cuenta o de otro día ⇒ NO se publica (falla cerrado).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_ops_dia_d as handler


class _FakeProc:
    def __init__(self, *, code: int = 0, hang: bool = False) -> None:
        self.returncode: int | None = None
        self._code = code
        self._hang = hang
        self.killed = False
        self.stdout = None
        self.stderr = None

    async def wait(self) -> int:
        if self._hang and not self.killed:
            import asyncio

            await asyncio.sleep(3600)
        self.returncode = self._code
        return self._code

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class _FakeFactory:
    """Sesiones cortas del publisher (el job repo se sustituye aparte)."""

    def __call__(self) -> Any:
        return _FakeSessions()


class _FakeSessions:
    async def __aenter__(self) -> _FakeSessions:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _FakeJobRepo:
    def __init__(self, _session: Any = None) -> None:
        self.progress: dict[str, Any] = {}

    async def set_progress(self, _job_id: str, progress: dict[str, Any]) -> None:
        self.progress = dict(progress)

    async def touch(self, _job_id: str) -> None:
        return None


def _root(tmp_path: Path) -> Path:
    (tmp_path / "apps" / "api-python" / "scripts").mkdir(parents=True)
    (tmp_path / "apps" / "api-python" / "scripts" / "v2_89_dia_d_auto_replay.py").write_text(
        "", encoding="utf-8"
    )
    return tmp_path


def _job(day: str = "2026-10-17", account: str = "acc-1") -> Any:
    return SimpleNamespace(id="job-1", day=day, account_id=account)


def _write_artifact(root: Path, day: str, account: str = "acc-1") -> Path:
    path = handler.artifact_path(root, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "day": day,
                "meta": {"account": account, "bump": "v2.88.150", "watchSize": 3},
                "summary": {"verdict": "INCONCLUSIVE"},
                "limits": ["sample_small"],
            }
        ),
        encoding="utf-8",
    )
    return path


def _install(monkeypatch: pytest.MonkeyPatch, proc: _FakeProc, on_spawn: Any) -> None:
    monkeypatch.setattr(handler, "_repo_root", lambda: on_spawn.root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)

    async def _spawn(*cmd: str, **kwargs: Any) -> _FakeProc:
        on_spawn.cmd = list(cmd)
        on_spawn.kwargs = kwargs
        return proc

    monkeypatch.setattr(handler.asyncio, "create_subprocess_exec", _spawn)


@pytest.mark.asyncio
async def test_success_returns_the_artifact_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()

    async def _spawn(*cmd: str, **kwargs: Any) -> _FakeProc:
        _write_artifact(root, job.day)
        progress = handler.progress_path(root, job.id)
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(
            json.dumps({"phase": "done", "percent": 100}) + "\n", encoding="utf-8"
        )
        return _FakeProc(code=0)

    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(handler.asyncio, "create_subprocess_exec", _spawn)

    result = await handler.run_dia_d_replay_job(
        job, _FakeFactory(), timeout_seconds=60
    )

    assert result["day"] == "2026-10-17"
    assert result["accountId"] == "acc-1"
    assert result["bump"] == "v2.88.150"
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["timedOut"] is False
    assert result["limits"] == ["sample_small"]


@pytest.mark.asyncio
async def test_nonzero_exit_fails_and_keeps_the_previous_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()
    previous = _write_artifact(root, job.day)
    before = previous.read_text(encoding="utf-8")

    proc = _FakeProc(code=2)
    holder = SimpleNamespace(root=root)
    _install(monkeypatch, proc, holder)

    with pytest.raises(handler.DiaDReplayFailed, match="exit 2"):
        await handler.run_dia_d_replay_job(job, _FakeFactory(), timeout_seconds=60)

    assert previous.read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_timeout_kills_the_process_and_fails_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    proc = _FakeProc(hang=True)
    holder = SimpleNamespace(root=root)
    _install(monkeypatch, proc, holder)

    real_wait_for = handler.asyncio.wait_for

    async def _fast_timeout(awaitable: Any, timeout: float) -> Any:  # noqa: ARG001
        import asyncio

        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        raise TimeoutError

    monkeypatch.setattr(handler.asyncio, "wait_for", _fast_timeout)

    with pytest.raises(handler.DiaDReplayFailed, match="Timeout"):
        await handler.run_dia_d_replay_job(_job(), _FakeFactory(), timeout_seconds=1)

    assert proc.killed is True
    monkeypatch.setattr(handler.asyncio, "wait_for", real_wait_for)


def test_artifact_of_another_account_is_fail_closed(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "2026-10-17", account="acc-2")

    with pytest.raises(handler.DiaDReplayFailed, match="otra cuenta"):
        handler._load_and_validate(path, day="2026-10-17", account_id="acc-1")


def test_artifact_of_another_day_is_fail_closed(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "2026-10-16")

    with pytest.raises(handler.DiaDReplayFailed, match="se pidió 2026-10-17"):
        handler._load_and_validate(path, day="2026-10-17", account_id="acc-1")


def test_missing_or_corrupt_artifact_is_fail_closed(tmp_path: Path) -> None:
    missing = tmp_path / "dia-d-auto-2026-10-17.json"
    with pytest.raises(handler.DiaDReplayFailed, match="sin artefacto"):
        handler._load_and_validate(missing, day="2026-10-17", account_id="acc-1")

    missing.write_text("{no-es-json", encoding="utf-8")
    with pytest.raises(handler.DiaDReplayFailed, match="JSON legible"):
        handler._load_and_validate(missing, day="2026-10-17", account_id="acc-1")
