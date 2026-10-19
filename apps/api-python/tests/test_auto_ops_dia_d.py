"""Handler ``dia_d_replay`` — subproceso aislado, timeout y artefacto atómico.

Hermético: el subproceso se simula con un doble que escribe (o no) el artefacto en
el ``cwd`` temporal. Cubre los criterios falsables del plan:

* exit 0 + artefacto válido ⇒ parte con el resumen del replay;
* exit ≠ 0 ⇒ fallo con el ``tail`` de stderr y el artefacto ANTERIOR intacto;
* timeout ⇒ ``kill`` y fallo declarado;
* artefacto de otra cuenta o de otro día ⇒ NO se publica (falla cerrado);
* **aislamiento por cuenta/día**: dos cuentas el mismo día escriben ficheros distintos y
  ningún artefacto se escribe en la ruta plana compartida;
* el CLI recibe ``--out`` con la ruta aislada (el worker no depende del default del script).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bolsa_api.background.auto_ops_dia_d as handler


class _FakeProc:
    """Doble SÍNCRONO de ``subprocess.Popen`` (``poll``/``wait``/``kill``).

    El handler ya no usa ``asyncio.create_subprocess_*``: Windows fuerza
    ``SelectorEventLoop`` y ese bucle no implementa subprocesos asíncronos.
    """

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
    path = handler.artifact_path(root, day, account)
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

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:
        on_spawn.cmd = list(cmd)
        on_spawn.kwargs = kwargs
        return proc

    monkeypatch.setattr(handler, "_spawn_process", _spawn)


@pytest.mark.asyncio
async def test_success_returns_the_artifact_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()

    spawned: dict[str, Any] = {}

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:
        spawned["cmd"] = list(cmd)
        _write_artifact(root, job.day, job.account_id)
        progress = handler.progress_path(root, job.id, job.account_id)
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(
            json.dumps({"phase": "done", "percent": 100}) + "\n", encoding="utf-8"
        )
        return _FakeProc(code=0)

    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(handler, "_spawn_process", _spawn)

    result = await handler.run_dia_d_replay_job(
        job, _FakeFactory(), timeout_seconds=60
    )

    assert result["day"] == "2026-10-17"
    assert result["accountId"] == "acc-1"
    assert result["bump"] == "v2.88.150"
    assert result["verdict"] == "INCONCLUSIVE"
    assert result["timedOut"] is False
    assert result["limits"] == ["sample_small"]

    # El CLI recibe `--out` con la ruta AISLADA por cuenta; nunca el default plano.
    cmd = spawned["cmd"]
    assert "--out" in cmd
    out_arg = cmd[cmd.index("--out") + 1]
    assert out_arg == str(handler.artifact_path(root, job.day, "acc-1"))
    assert "acc-1" in Path(out_arg).parts
    assert Path(out_arg).parent.name == "acc-1"
    assert result["artifactPath"] == str(
        handler.artifact_path(root, job.day, "acc-1").relative_to(root)
    ).replace("\\", "/")


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

    # El suelo del timeout es una constante: la prueba lo acorta sin dormir 30 s.
    monkeypatch.setattr(handler, "_MIN_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(handler, "_POLL_SECONDS", 0.01)

    with pytest.raises(handler.DiaDReplayFailed, match="Timeout"):
        await handler.run_dia_d_replay_job(_job(), _FakeFactory(), timeout_seconds=1)

    assert proc.killed is True


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


def test_artifact_path_is_isolated_per_account_and_day(tmp_path: Path) -> None:
    """D1: la ruta depende de (cuenta, día); la plana compartida ya no se usa para escribir."""
    a1 = handler.artifact_path(tmp_path, "2026-10-17", "acc-1")
    a2 = handler.artifact_path(tmp_path, "2026-10-17", "acc-2")
    a1_other_day = handler.artifact_path(tmp_path, "2026-10-18", "acc-1")
    legacy = tmp_path / "operability_runs" / "dia-d-auto" / "dia-d-auto-2026-10-17.json"

    assert a1 != a2
    assert a1 != a1_other_day
    assert a1 != legacy and a2 != legacy
    assert a1.parent.name == "acc-1"
    assert a2.parent.name == "acc-2"
    assert a1.name == "dia-d-auto-2026-10-17.json"


def test_unsafe_account_cannot_escape_the_artifact_tree(tmp_path: Path) -> None:
    """Una cuenta con separadores/rutas relativas se hashea y no escapa del árbol."""
    path = handler.artifact_path(tmp_path, "2026-10-17", "../otra")
    assert tmp_path in path.parents
    assert ".." not in path.parts
    assert path.parent.name.startswith("acct-")


def test_progress_path_is_isolated_per_account(tmp_path: Path) -> None:
    p1 = handler.progress_path(tmp_path, "job-1", "acc-1")
    p2 = handler.progress_path(tmp_path, "job-1", "acc-2")
    assert p1 != p2
    assert p1.parent.name == "progress"
    assert p1.parent.parent.name == "acc-1"


@pytest.mark.asyncio
async def test_two_accounts_same_day_do_not_share_the_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dos jobs (cuentas distintas, mismo día) escriben y validan ficheros distintos."""
    root = _root(tmp_path)
    jobs = [
        _job(account="acc-1"),
        SimpleNamespace(id="job-2", day="2026-10-17", account_id="acc-2"),
    ]

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001 — firma Popen
        account = cmd[list(cmd).index("--account-id") + 1]
        out = Path(cmd[list(cmd).index("--out") + 1])
        assert out == handler.artifact_path(root, "2026-10-17", account)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "day": "2026-10-17",
                    "meta": {"account": account, "bump": "v2.88.150"},
                    "summary": {"verdict": "INCONCLUSIVE"},
                    "limits": [],
                }
            ),
            encoding="utf-8",
        )
        return _FakeProc(code=0)

    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(handler, "_spawn_process", _spawn)

    results = await asyncio.gather(
        *(handler.run_dia_d_replay_job(job, _FakeFactory(), timeout_seconds=60) for job in jobs)
    )

    a1 = handler.artifact_path(root, "2026-10-17", "acc-1")
    a2 = handler.artifact_path(root, "2026-10-17", "acc-2")
    assert a1 != a2
    assert a1.is_file() and a2.is_file()
    assert [row["accountId"] for row in results] == ["acc-1", "acc-2"]
    # Ningún artefacto se escribió en la ruta plana compartida.
    assert not (root / "operability_runs" / "dia-d-auto" / "dia-d-auto-2026-10-17.json").exists()


@pytest.mark.asyncio
async def test_no_depende_de_subprocesos_asyncio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regresión Windows: ``SelectorEventLoop`` no implementa ``create_subprocess_*``.

    El worker fuerza ese bucle (psycopg async), así que el handler debe lanzar el CLI
    con ``subprocess.Popen`` y esperar por ``poll``; si vuelve a ``asyncio`` subprocess,
    todo replay DÍA-D falla con ``NotImplementedError`` en Windows.
    """
    root = _root(tmp_path)
    job = _job()

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001 — firma Popen
        _write_artifact(root, job.day, job.account_id)
        return _FakeProc(code=0)

    def _forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError(
            "el handler no debe usar asyncio.create_subprocess_* (falla en Windows)"
        )

    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(handler, "_spawn_process", _spawn)
    monkeypatch.setattr(handler.asyncio, "create_subprocess_exec", _forbidden)
    monkeypatch.setattr(handler.asyncio, "create_subprocess_shell", _forbidden)

    result = await handler.run_dia_d_replay_job(job, _FakeFactory(), timeout_seconds=60)

    assert result["verdict"] == "INCONCLUSIVE"
    assert result["accountId"] == "acc-1"


# ── modo VALOR (``dia_d_value_replay``) ─────────────────────────────────────────


def _write_value_artifact(
    root: Path,
    day: str,
    account: str = "acc-1",
    symbol: str = "SAN",
    *,
    watch: list[str] | None = None,
) -> Path:
    path = handler.value_artifact_path(root, day, account, symbol)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "day": day,
                "meta": {
                    "account": account,
                    "bump": "v2.88.152",
                    "watch": watch if watch is not None else [symbol],
                    "watchSize": 1,
                },
                "summary": {"verdict": "PARTIAL"},
                "limits": ["sandbox read-only"],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_value_artifact_lives_in_its_own_tree_and_not_in_the_day_artifact(
    tmp_path: Path,
) -> None:
    day = handler.artifact_path(tmp_path, "2026-10-17", "acc-1")
    value = handler.value_artifact_path(tmp_path, "2026-10-17", "acc-1", "SAN")
    assert value != day
    assert value.parent.name == "SAN"
    assert value.parent.parent.name == "values"
    assert value.parent.parent.parent.name == "acc-1"


def test_unsafe_symbol_cannot_escape_the_value_tree(tmp_path: Path) -> None:
    path = handler.value_artifact_path(tmp_path, "2026-10-17", "acc-1", "../etc")
    assert tmp_path in path.parents
    assert ".." not in path.parts
    assert path.parent.name.startswith("sym-")


@pytest.mark.asyncio
async def test_value_replay_passes_watch_and_writes_the_value_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()
    # El artefacto del día NO debe existir antes ni después: el modo valor no lo crea.
    assert not handler.artifact_path(root, job.day, job.account_id).exists()
    spawned: dict[str, Any] = {}

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001 — firma Popen
        spawned["cmd"] = list(cmd)
        _write_value_artifact(root, job.day, job.account_id, "SAN")
        return _FakeProc(code=0)

    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    monkeypatch.setattr(handler, "SqlAlchemyAutoOpsJobRepository", _FakeJobRepo)
    monkeypatch.setattr(handler, "_spawn_process", _spawn)

    result = await handler.run_dia_d_replay_job(
        job, _FakeFactory(), timeout_seconds=60, symbol="san"
    )

    cmd = spawned["cmd"]
    assert cmd[cmd.index("--watch") + 1] == "SAN"
    out_arg = Path(cmd[cmd.index("--out") + 1])
    assert out_arg == handler.value_artifact_path(root, job.day, "acc-1", "SAN")
    assert result["symbol"] == "SAN"
    assert result["verdict"] == "PARTIAL"
    # Ni se creó ni se pisó el artefacto del día completo.
    assert not handler.artifact_path(root, job.day, job.account_id).exists()


@pytest.mark.asyncio
async def test_value_replay_without_symbol_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(handler, "_repo_root", lambda: root)
    with pytest.raises(handler.DiaDReplayFailed, match="requiere símbolo"):
        await handler.run_dia_d_replay_job(_job(), _FakeFactory(), symbol="   ")


def test_value_artifact_with_another_watch_is_fail_closed(tmp_path: Path) -> None:
    """Un replay que ignorase ``--watch`` cubriría el universo: su evidencia no es la del valor."""
    path = _write_value_artifact(
        tmp_path, "2026-10-17", "acc-1", "SAN", watch=["SAN", "BBVA"]
    )
    with pytest.raises(handler.DiaDReplayFailed, match="no cubre el valor"):
        handler._load_and_validate(
            path, day="2026-10-17", account_id="acc-1", symbol="SAN"
        )


def test_value_artifact_without_watch_is_fail_closed(tmp_path: Path) -> None:
    path = _write_value_artifact(tmp_path, "2026-10-17", "acc-1", "SAN")
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["meta"].pop("watch")
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(handler.DiaDReplayFailed, match="no cubre el valor"):
        handler._load_and_validate(
            path, day="2026-10-17", account_id="acc-1", symbol="SAN"
        )


@pytest.mark.asyncio
async def test_value_replay_keeps_the_previous_value_artifact_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    job = _job()
    previous = _write_value_artifact(root, job.day, job.account_id, "SAN")
    before = previous.read_text(encoding="utf-8")

    holder = SimpleNamespace(root=root)
    _install(monkeypatch, _FakeProc(code=2), holder)

    with pytest.raises(handler.DiaDReplayFailed, match="exit 2"):
        await handler.run_dia_d_replay_job(
            job, _FakeFactory(), timeout_seconds=60, symbol="SAN"
        )

    assert previous.read_text(encoding="utf-8") == before
