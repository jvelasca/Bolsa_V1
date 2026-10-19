"""Integrada (auditoría 2026-10-19) — señal → plan → DÍA-D con DOS cuentas el mismo día.

Recorrido completo sobre piezas REALES, sin PostgreSQL:

1. ``RunEstudioDailyOps`` (módulo real) compone el parte diario con su identidad estable
   (``signalId``/``planId``) a partir de dobles de universo/opiniones/propose.
2. El worker ``dia_d_replay`` (módulo real) lanza DOS jobs concurrentes, uno por cuenta, con
   un doble del subproceso que escribe el artefacto en el ``--out`` recibido.
3. La ruta HTTP real ``/api/auto/dia-d-replay`` lee cada artefacto y lo sirve **solo** a su
   cuenta, con la identidad del parte (``executedDetail``) y sin fallback legacy.

Precondiciones: este test NO se marca ``skip``. Si un paso falta (parte sin identidad, job
sin artefacto, HTTP sin datos, artefactos compartidos), **falla**: esa es la evidencia que
el plan exige. El único doble es el subproceso (el CLI real necesita PG y 90 días de barras);
todo lo demás es el código de producción.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

import bolsa_api.api.v1.routes.auto_dia_d as route
import bolsa_api.background.auto_ops_dia_d as worker
from bolsa_api.main import create_app
from bolsa_application.estudio_daily_ops import STATUS_OK, RunEstudioDailyOps

_DAY = "2026-10-18"
_ACCOUNTS = ("acc-alpha", "acc-beta")
_IDENTITY: dict[str, dict[str, str]] = {}


# ── dobles del servicio diario (puertos, no lógica) ─────────────────────────


@dataclass(frozen=True)
class _Universe:
    instrument_ids: list[str]


@dataclass(frozen=True)
class _Opinion:
    instrument_id: str
    stance: str = "buy"
    dictamen_stars: int = 4
    as_of_bar_date: date = date(2026, 10, 18)
    reasons: tuple[str, ...] = ("momentum",)
    gate_status: str | None = "PASS"
    top_id: str | None = "top-1"
    top_version: int | None = 3
    engine_version: str = "opinion_v1"
    computed_at: datetime = datetime(2026, 10, 18, 20, 0)

    @property
    def reasons_list(self) -> list[str]:
        return list(self.reasons)


class _List:
    async def execute(self, list_id: str) -> Any:
        return _Universe(instrument_ids=["inst-1"])


class _Opinions:
    async def run_eod_batch(self, **kwargs: Any) -> list[Any]:
        return [_Opinion("inst-1")]


class _Propose:
    def __init__(self, account_id: str) -> None:
        self._account_id = account_id

    async def execute(self, payload: dict[str, Any]) -> dict[str, Any]:
        assert payload["execute"] is False, "el parte diario debe ser dry-run"
        return {
            "hits": [
                {
                    "instrumentId": "inst-1",
                    "symbol": "AAA",
                    "planId": f"plan-{self._account_id}",
                    "tradePlan": {
                        "status": "TRIGGERED",
                        "direction": "long",
                        "entry": 100.0,
                        "structuralStop": 95.0,
                        "target1": 110.0,
                        "target2": None,
                        "riskAmount": 250.0,
                        "expectedRR": 2.0,
                        "whyNot": [],
                    },
                    "signal": {
                        "id": f"sig-{self._account_id}",
                        "presetKey": "estudio_auto",
                        "strategyDefinitionId": "strat-1",
                        "strategyVersion": 1,
                    },
                }
            ],
            "skipped": [],
        }


async def _daily_report(account_id: str) -> dict[str, Any]:
    service = RunEstudioDailyOps(
        _List(),
        _Opinions(),
        _Propose(account_id),
    )
    return (await service.execute(account_id=account_id, as_of=_DAY)).to_dict()


# ── doble del CLI: escribe en el `--out` que recibe el worker ───────────────


class _FakeProc:
    def __init__(self) -> None:
        self.returncode: int | None = None

    def poll(self) -> int | None:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002 — firma Popen
        self.returncode = 0
        return 0

    def kill(self) -> None:  # pragma: no cover — no se usa en el camino feliz
        self.returncode = -9


class _Factory:
    def __call__(self) -> Any:
        return _Session()


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


class _JobRepo:
    def __init__(self, _session: Any = None) -> None:
        pass

    async def set_progress(self, _job_id: str, progress: dict[str, Any]) -> None:
        return None

    async def touch(self, _job_id: str) -> None:
        return None


def _install_fake_cli(monkeypatch: pytest.MonkeyPatch, root: Path) -> list[str]:
    """Instala el doble del CLI; devuelve la lista de `--out` usados (por referencia)."""
    seen: list[str] = []
    script = root / worker._SCRIPT_REL  # noqa: SLF001 — misma ruta que el worker
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("", encoding="utf-8")

    def _spawn(cmd: list[str], **kwargs: Any) -> _FakeProc:  # noqa: ARG001 — firma Popen
        args = list(cmd)
        account = args[args.index("--account-id") + 1]
        day = args[args.index("--at") + 1]
        out = Path(args[args.index("--out") + 1])
        seen.append(str(out))
        identity = _IDENTITY[account]
        payload = {
            "schemaVersion": "dia-d-auto-v1",
            "kind": "DIA_D_AUTO",
            "readOnly": True,
            "day": day,
            "meta": {
                "account": account,
                "versionA": "v283-window-a",
                "bump": "2.11.145-beta",
                "watchSize": 1,
                "horizonDays": 20,
                "replayStart": "2026-06-01",
                "replayEnd": day,
            },
            "comparison": [
                {
                    "step": "SIGNAL",
                    "declared": 1,
                    "executed": 1,
                    "verdict": "MATCH",
                    "measurement": "COMPLETE",
                }
            ],
            "summary": {
                "verdict": "PARTIAL",
                "match": 1,
                "divergent": 0,
                "notMeasured": 1,
                "steps": 1,
            },
            "oos": {
                "closedCount": 0,
                "openCount": 1,
                "realizedRTotal": 0,
                "unmeasuredCount": 1,
                "realized": [],
                "open": [],
            },
            "limits": ["sandbox read-only"],
            # La traza causal que la UI exige: la identidad del parte, no el ticker.
            "executedDetail": {
                "planId": identity["planId"],
                "signalId": identity["signalId"],
                "symbol": "AAA",
                "cycleId": f"cyc-{account}",
            },
        }
        # Escritura atómica, como el CLI real.
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(out)
        return _FakeProc()

    monkeypatch.setattr(worker, "_repo_root", lambda: root)
    monkeypatch.setattr(worker, "SqlAlchemyAutoOpsJobRepository", _JobRepo)
    monkeypatch.setattr(worker, "_spawn_process", _spawn)
    return seen


@pytest.mark.asyncio
async def test_signal_plan_and_dia_d_are_traced_and_isolated_per_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ── 1. Parte diario: identidad real por cuenta ─────────────────────────
    reports = {account: await _daily_report(account) for account in _ACCOUNTS}
    for account, report in reports.items():
        assert report["status"] == STATUS_OK, report
        assert report["universeCount"] == 1
        value = report["values"][0]
        assert value["strategy"]["signalId"] == f"sig-{account}"
        assert value["strategy"]["planId"] == f"plan-{account}"
        assert value["strategy"]["presetKey"] == "estudio_auto"
        assert value["opinion"]["topId"] == "top-1"
        _IDENTITY[account] = {
            "signalId": value["strategy"]["signalId"],
            "planId": value["strategy"]["planId"],
        }

    # ── 2. Dos jobs concurrentes, mismo día, cuentas distintas ─────────────
    used_out = _install_fake_cli(monkeypatch, tmp_path)
    jobs = [
        SimpleNamespace(id=f"job-{account}", day=_DAY, account_id=account)
        for account in _ACCOUNTS
    ]
    results = await asyncio.gather(
        *(
            worker.run_dia_d_replay_job(job, _Factory(), timeout_seconds=60)
            for job in jobs
        )
    )

    paths = [worker.artifact_path(tmp_path, _DAY, account) for account in _ACCOUNTS]
    assert paths[0] != paths[1]
    assert len(set(used_out)) == 2, used_out
    assert sorted(str(path) for path in paths) == sorted(used_out)
    for path in paths:
        assert path.is_file(), f"falta el artefacto {path}"
    # Ningún job escribió en la ruta plana compartida (D1).
    assert not (tmp_path / "operability_runs" / "dia-d-auto" / f"dia-d-auto-{_DAY}.json").exists()

    # El resultado del job declara su propio artefacto y cuenta (procedencia/rehidratación).
    assert [row["accountId"] for row in results] == list(_ACCOUNTS)
    assert {row["artifactPath"] for row in results} == {
        path.relative_to(tmp_path).as_posix() for path in paths
    }
    assert len({row["progressPath"] for row in results}) == 2

    for account, path in zip(_ACCOUNTS, paths, strict=True):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["meta"]["account"] == account
        assert payload["executedDetail"]["signalId"] == _IDENTITY[account]["signalId"]
        assert payload["executedDetail"]["planId"] == _IDENTITY[account]["planId"]

    # ── 3. Lectura HTTP por cuenta (y recarga: mismo artefacto) ────────────
    # `DIA_D_AUTO_DIR` apunta a la carpeta `dia-d-auto` (no a la raíz del repo).
    monkeypatch.setenv(
        "DIA_D_AUTO_DIR", str(tmp_path / "operability_runs" / "dia-d-auto")
    )
    app = create_app()

    async def _scope(request: Any, _account_id: str | None) -> str | None:
        return request.headers.get("x-account-id")

    monkeypatch.setattr(route, "resolve_account_scope_or_default", _scope)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for account in _ACCOUNTS:
            headers = {"X-Account-Id": account}
            listing = await client.get("/api/auto/dia-d-replay", headers=headers)
            assert listing.status_code == 200, listing.text
            assert listing.json()["days"] == [_DAY], listing.json()

            detail = await client.get(
                f"/api/auto/dia-d-replay/{_DAY}", headers=headers
            )
            assert detail.status_code == 200, detail.text
            body = detail.json()
            assert body["available"] is True
            assert body["meta"]["account"] == account
            assert body["notes"] == []  # ruta canónica, no legacy
            assert body["executedDetail"]["signalId"] == _IDENTITY[account]["signalId"]
            assert body["executedDetail"]["planId"] == _IDENTITY[account]["planId"]
            assert body["artifactModifiedAt"] is not None

            # Recarga: el artefacto leído es estable (no depende de estado en memoria).
            again = await client.get(
                f"/api/auto/dia-d-replay/{_DAY}", headers=headers
            )
            assert again.json() == body

        # Nunca se sirve a una cuenta el artefacto de la otra.
        stranger = await client.get(
            f"/api/auto/dia-d-replay/{_DAY}",
            headers={"X-Account-Id": "acc-otra"},
        )
        assert stranger.json()["available"] is False
        assert stranger.json()["notes"] == ["artifact_not_found"]
