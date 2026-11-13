"""Handler ``dia_d_as_run`` — subproceso aislado, timeout y artefacto fail-closed.

Hermético: el subproceso se simula con un doble que escribe (o no) el artefacto. Cubre los
criterios falsables de ADR-049:

* exit 0 + artefacto válido ⇒ parte con ``status``/``gaps`` del artefacto;
* exit ≠ 0 ⇒ fallo con el ``tail`` de stderr y el artefacto ANTERIOR intacto;
* timeout ⇒ ``kill`` y fallo declarado;
* artefacto de otra cuenta, de otro día o sin brazos ⇒ NO se publica;
* aislamiento por cuenta/día: dos cuentas el mismo día escriben ficheros distintos bajo
  ``operability_runs/dia-d-as-run`` (árbol propio, separado de ``dia-d-auto``).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_ops_dia_d_as_run as handler


class _FakeProc:
    """Doble síncrono de ``subprocess.Popen`` (Windows usa ``SelectorEventLoop``)."""

    def __init__(self, *, code: int = 0, hang: bool = False) -> None:
        self.returncode: int | None = None
        self._code = code
        self._hang = hang
        self.killed = False

    def poll(self) -> int | None:
        if self._hang and not self.killed:
            return None
        if self.returncode is None:
            self.returncode = self._code
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002 — firma Popen
        if self._hang and not self.killed:
            raise AssertionError("el handler debe matar el proceso antes de esperar")
        if self.returncode is None:
            self.returncode = self._code
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def _root(tmp_path: Path) -> Path:
    scripts = tmp_path / "apps" / "api-python" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "v2_102_dia_d_as_run.py").write_text("", encoding="utf-8")
    return tmp_path


def _job(day: str = "2026-09-30", account: str = "acc-1", **payload: Any) -> Any:
    return SimpleNamespace(id="job-1", day=day, account_id=account, payload=dict(payload))


def _artifact(day: str, account: str = "acc-1") -> dict[str, Any]:
    return {
        "engine": "dia-d-as-run-v1",
        "day": day,
        "account": account,
        "status": "measured",
        "measured": True,
        "costBps": 32.0,
        "arms": [
            {"arm": "as_run", "measured": True, "realizedR": 1.0},
            {"arm": "cash", "measured": True, "realizedR": 0.0},
        ],
        "gaps": [{"arm": "candidate", "reason": "candidate_not_provided"}],
        "hash": "h",
        "meta": {"account": account, "bump": "v2.11.201"},
    }


def _write_artifact(root: Path, day: str, account: str = "acc-1") -> Path:
    path = handler.as_run_artifact_path(root, day, account)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_artifact(day, account)), encoding="utf-8")
    return path


def _install(monkeypatch: pytest.MonkeyPatch, root: Path, spawn: Any) -> None:
    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "_spawn", spawn)


@pytest.fixture(autouse=True)
def _no_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIA_D_AS_RUN_DIR", raising=False)


@pytest.mark.asyncio
async def test_success_returns_status_and_gaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()
    spawned: dict[str, Any] = {}

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:
        spawned["cmd"] = list(cmd)
        spawned["kwargs"] = kwargs
        _write_artifact(root, job.day, job.account_id)
        return _FakeProc(code=0)

    _install(monkeypatch, root, _spawn)

    result = await handler.run_dia_d_as_run_job(job, None, timeout_seconds=60)

    assert result["day"] == "2026-09-30"
    assert result["status"] == "measured"
    assert result["measured"] is True
    assert result["bump"] == "v2.11.201"
    assert result["gaps"] == [{"arm": "candidate", "reason": "candidate_not_provided"}]
    assert result["timedOut"] is False
    assert result["artifactPath"] == str(
        handler.as_run_artifact_path(root, job.day, "acc-1").relative_to(root)
    ).replace("\\", "/")
    cmd = spawned["cmd"]
    assert cmd[cmd.index("--out") + 1] == str(
        handler.as_run_artifact_path(root, job.day, "acc-1")
    )


@pytest.mark.asyncio
async def test_payload_options_are_forwarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job(to="2026-10-15", costBps=41, engineStopMultiplier=1.2)

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001
        _write_artifact(root, job.day, job.account_id)
        holder["cmd"] = list(cmd)
        return _FakeProc(code=0)

    holder: dict[str, Any] = {}
    _install(monkeypatch, root, _spawn)

    await handler.run_dia_d_as_run_job(job, None, timeout_seconds=60)

    cmd = holder["cmd"]
    assert cmd[cmd.index("--to") + 1] == "2026-10-15"
    assert cmd[cmd.index("--cost-bps") + 1] == "41.0"
    assert cmd[cmd.index("--engine-stop-multiplier") + 1] == "1.2"


@pytest.mark.asyncio
async def test_nonzero_exit_fails_and_keeps_the_previous_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()
    previous = _write_artifact(root, job.day, job.account_id)
    before = previous.read_text(encoding="utf-8")
    _install(monkeypatch, root, lambda *_a, **_k: _FakeProc(code=2))

    with pytest.raises(handler.DiaDAsRunFailed, match="exit 2"):
        await handler.run_dia_d_as_run_job(job, None, timeout_seconds=60)

    assert previous.read_text(encoding="utf-8") == before


@pytest.mark.asyncio
async def test_timeout_kills_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    proc = _FakeProc(hang=True)
    _install(monkeypatch, root, lambda *_a, **_k: proc)
    monkeypatch.setattr(handler, "_MIN_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(handler, "_POLL_SECONDS", 0.01)

    with pytest.raises(handler.DiaDAsRunFailed, match="Timeout"):
        await handler.run_dia_d_as_run_job(_job(), None, timeout_seconds=1)

    assert proc.killed is True


@pytest.mark.asyncio
async def test_missing_account_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, _root(tmp_path), lambda *_a, **_k: _FakeProc())
    with pytest.raises(handler.DiaDAsRunFailed, match="requiere cuenta"):
        await handler.run_dia_d_as_run_job(_job(account=""), None)


@pytest.mark.asyncio
async def test_invalid_cost_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, _root(tmp_path), lambda *_a, **_k: _FakeProc())
    with pytest.raises(handler.DiaDAsRunFailed, match="costBps inválido"):
        await handler.run_dia_d_as_run_job(_job(costBps="no-numero"), None)


def test_artifact_of_another_account_is_fail_closed(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "2026-09-30", account="acc-2")
    with pytest.raises(handler.DiaDAsRunFailed, match="otra cuenta"):
        handler._load_and_validate(path, day="2026-09-30", account_id="acc-1")


def test_artifact_of_another_day_is_fail_closed(tmp_path: Path) -> None:
    path = _write_artifact(tmp_path, "2026-09-29")
    with pytest.raises(handler.DiaDAsRunFailed, match="se pidió 2026-09-30"):
        handler._load_and_validate(path, day="2026-09-30", account_id="acc-1")


def test_missing_or_corrupt_artifact_is_fail_closed(tmp_path: Path) -> None:
    missing = tmp_path / "as-run-2026-09-30.json"
    with pytest.raises(handler.DiaDAsRunFailed, match="sin artefacto"):
        handler._load_and_validate(missing, day="2026-09-30", account_id="acc-1")

    missing.write_text("{no-es-json", encoding="utf-8")
    with pytest.raises(handler.DiaDAsRunFailed, match="JSON legible"):
        handler._load_and_validate(missing, day="2026-09-30", account_id="acc-1")


def test_artifact_without_arms_is_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "as-run-2026-09-30.json"
    path.write_text(
        json.dumps({"day": "2026-09-30", "meta": {"account": "acc-1"}, "arms": []}),
        encoding="utf-8",
    )
    with pytest.raises(handler.DiaDAsRunFailed, match="no declara brazos"):
        handler._load_and_validate(path, day="2026-09-30", account_id="acc-1")


def test_artifact_path_is_isolated_per_account_and_day(tmp_path: Path) -> None:
    a1 = handler.as_run_artifact_path(tmp_path, "2026-09-30", "acc-1")
    a2 = handler.as_run_artifact_path(tmp_path, "2026-09-30", "acc-2")
    other_day = handler.as_run_artifact_path(tmp_path, "2026-10-01", "acc-1")

    assert a1 != a2 != other_day and a1 != other_day
    assert a1.parent.name == "acc-1"
    assert a1.name == "as-run-2026-09-30.json"
    # Árbol PROPIO: no es el del replay del motor.
    assert handler.AS_RUN_ARTIFACT_DIR.parts[-1] == "dia-d-as-run"
    assert "dia-d-auto" not in a1.parts


def test_unsafe_account_cannot_escape_the_as_run_tree(tmp_path: Path) -> None:
    path = handler.as_run_artifact_path(tmp_path, "2026-09-30", "../otra")
    assert tmp_path in path.parents
    assert ".." not in path.parts
    assert path.parent.name.startswith("acct-")


@pytest.mark.asyncio
async def test_two_accounts_same_day_do_not_share_the_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    jobs = [_job(account="acc-1"), _job(account="acc-2")]

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001
        account = cmd[list(cmd).index("--account-id") + 1]
        out = Path(cmd[list(cmd).index("--out") + 1])
        assert out == handler.as_run_artifact_path(root, "2026-09-30", account)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(_artifact("2026-09-30", account)), encoding="utf-8")
        return _FakeProc(code=0)

    _install(monkeypatch, root, _spawn)

    first = await handler.run_dia_d_as_run_job(jobs[0], None, timeout_seconds=60)
    second = await handler.run_dia_d_as_run_job(jobs[1], None, timeout_seconds=60)

    a1 = handler.as_run_artifact_path(root, "2026-09-30", "acc-1")
    a2 = handler.as_run_artifact_path(root, "2026-09-30", "acc-2")
    assert a1 != a2 and a1.is_file() and a2.is_file()
    assert first["accountId"] == "acc-1"
    assert second["accountId"] == "acc-2"
