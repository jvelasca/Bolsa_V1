"""Handler del job ``dia_d_as_run`` — DÍA-D retrospectivo as-run (ADR-049).

Lanza el CLI ``apps/api-python/scripts/v2_102_dia_d_as_run.py`` como subproceso con el
**mismo intérprete** del worker (``sys.executable``), ``cwd`` en la raíz del repo y timeout.
El artefacto se escribe de forma atómica y **aislado por cuenta y día** bajo
``operability_runs/dia-d-as-run/<segmento-cuenta>/as-run-<D>.json``.

Reglas duras:

* **Fail-closed**: al terminar se exige ``exit 0`` + artefacto existente + ``day`` solicitado
  + ``meta.account`` de la cuenta. Cualquier desviación falla el job con motivo.
* **Sin resultados vacíos con éxito**: un artefacto ``not_measured`` es un RESULTADO válido
  (declara sus huecos), pero un artefacto incoherente o de otra cuenta NO se publica.
* **Read-only**: el CLI no escribe en PostgreSQL; el job no toca el motor.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any

from bolsa_application.dia_d_artifacts import (
    AS_RUN_ARTIFACT_DIR,
    as_run_artifact_path_in,
    as_run_artifacts_root,
)

__all__ = [
    "DiaDAsRunFailed",
    "as_run_artifact_path",
    "as_run_artifacts_dir_for_jobs",
    "run_dia_d_as_run_job",
]

logger = logging.getLogger(__name__)

_SCRIPT_REL = pathlib.Path("apps") / "api-python" / "scripts" / "v2_102_dia_d_as_run.py"
_STDERR_TAIL_CHARS = 4000
_POLL_SECONDS = 0.5
_MIN_TIMEOUT_SECONDS = 30.0
_TAIL_BYTES = _STDERR_TAIL_CHARS * 2


class DiaDAsRunFailed(RuntimeError):
    """El job as-run no produjo un artefacto válido para el día/cuenta solicitados."""

    def __init__(self, message: str, *, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result or {}


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / _SCRIPT_REL).exists():
            return parent
    raise DiaDAsRunFailed("no se encontró la raíz del repo (marcador v2_102)")


def as_run_artifact_path(root: pathlib.Path, day: str, account_id: str) -> pathlib.Path:
    """Artefacto as-run de ``(cuenta, día)`` bajo la raíz del repo."""
    return as_run_artifact_path_in(root / AS_RUN_ARTIFACT_DIR, day, account_id)


def as_run_artifacts_dir_for_jobs() -> pathlib.Path:
    """Carpeta ``…/dia-d-as-run`` donde este worker ESCRIBE (honra ``DIA_D_AS_RUN_DIR``)."""
    return as_run_artifacts_root(_repo_root() / AS_RUN_ARTIFACT_DIR, os.environ)


def _display_path(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_tail(handle: Any) -> str:
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(max(0, size - _TAIL_BYTES))
    data: bytes = handle.read()
    return data.decode("utf-8", errors="replace")


def _spawn(cmd: list[str], *, cwd: pathlib.Path, env: dict[str, str], stdout: Any, stderr: Any) -> Any:
    return subprocess.Popen(  # noqa: S603 — comando interno, sin shell
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )


async def _wait(process: Any, *, timeout_seconds: float) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(_MIN_TIMEOUT_SECONDS, float(timeout_seconds))
    while True:
        returncode = await asyncio.to_thread(process.poll)
        if returncode is not None:
            return False
        if loop.time() >= deadline:
            await asyncio.to_thread(process.kill)
            try:
                await asyncio.to_thread(process.wait, 15)
            except (subprocess.TimeoutExpired, OSError):  # pragma: no cover
                pass
            return True
        await asyncio.sleep(_POLL_SECONDS)


async def run_dia_d_as_run_job(
    job: Any,
    session_factory: Any,  # noqa: ARG001 — mismo contrato que los demás handlers.
    *,
    timeout_seconds: float = 1800.0,
) -> dict[str, Any]:
    """Ejecuta el replay as-run del día del job y devuelve el parte para ``result``."""
    day = str(job.day)
    account_id = str(job.account_id or "")
    if not account_id:
        raise DiaDAsRunFailed("El replay DÍA-D as-run requiere cuenta")

    payload = job.payload if isinstance(job.payload, dict) else {}
    to_day = str(payload.get("to") or "").strip() or None
    cost_bps = payload.get("costBps")
    if cost_bps is not None:
        try:
            cost_bps = float(cost_bps)
        except (TypeError, ValueError) as exc:
            raise DiaDAsRunFailed(f"costBps inválido: {cost_bps!r}") from exc

    root = _repo_root()
    script = root / _SCRIPT_REL
    artifacts_dir = as_run_artifacts_dir_for_jobs()
    out_path = as_run_artifact_path_in(artifacts_dir, day, account_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(script),
        "--at",
        day,
        "--account-id",
        account_id,
        "--json",
        "--out",
        str(out_path),
    ]
    if to_day:
        cmd.extend(["--to", to_day])
    if cost_bps is not None:
        cmd.extend(["--cost-bps", str(cost_bps)])
    for key, flag in (
        ("engineStopMultiplier", "--engine-stop-multiplier"),
        ("engineTargetMultiplier", "--engine-target-multiplier"),
        ("commissionBps", "--commission-bps"),
        ("slippageBps", "--slippage-bps"),
        ("spreadBps", "--spread-bps"),
        ("maxParticipationPct", "--max-participation-pct"),
    ):
        value = payload.get(key)
        if value is not None:
            try:
                cmd.extend([flag, str(float(value))])
            except (TypeError, ValueError) as exc:
                raise DiaDAsRunFailed(f"{key} inválido: {value!r}") from exc

    gap_policy = payload.get("gapPolicy")
    if gap_policy is not None:
        policy = str(gap_policy).strip().lower()
        if policy not in ("open", "theoretical"):
            raise DiaDAsRunFailed(f"gapPolicy inválido: {gap_policy!r}")
        cmd.extend(["--gap-policy", policy])

    candidate_as_of = str(payload.get("candidateAsOf") or "").strip()
    if candidate_as_of:
        cmd.extend(["--candidate-as-of", candidate_as_of])
    universe_items = payload.get("universeInstruments")
    if isinstance(universe_items, (list, tuple)):
        for item in universe_items:
            text = str(item or "").strip()
            if text:
                cmd.extend(["--universe-instrument", text])
    if payload.get("verifyBars") is True:
        cmd.append("--verify-bars")
    for key, flag in (
        ("strategyVersion", "--strategy-version"),
        ("mandateVersion", "--mandate-version"),
    ):
        value = str(payload.get(key) or "").strip()
        if value:
            cmd.extend([flag, value])

    env = dict(os.environ)
    env.pop("PYTHONINSPECT", None)

    started = datetime.now(UTC)
    stdout_file = tempfile.TemporaryFile()
    stderr_file = tempfile.TemporaryFile()
    try:
        try:
            process = _spawn(
                cmd, cwd=root, env=env, stdout=stdout_file, stderr=stderr_file
            )
        except OSError as exc:
            raise DiaDAsRunFailed(f"No se pudo lanzar el replay as-run: {exc}") from exc

        timed_out = await _wait(process, timeout_seconds=timeout_seconds)
        stderr_tail = _read_tail(stderr_file).strip()
        stdout_tail = _read_tail(stdout_file)
        returncode = await asyncio.to_thread(lambda: process.returncode)
    finally:
        stdout_file.close()
        stderr_file.close()

    tail = (stderr_tail or stdout_tail).strip()[-_STDERR_TAIL_CHARS:]
    elapsed = round((datetime.now(UTC) - started).total_seconds(), 1)
    base_result: dict[str, Any] = {
        "day": day,
        "accountId": account_id,
        "artifactPath": _display_path(out_path, root),
        "elapsedSeconds": elapsed,
        "timedOut": timed_out,
    }
    if timed_out:
        raise DiaDAsRunFailed(f"Timeout del replay as-run a los {elapsed}s", result=base_result)
    if returncode != 0:
        detail = tail or f"exit {returncode}"
        raise DiaDAsRunFailed(
            f"El replay as-run falló (exit {returncode}): {detail}", result=base_result
        )

    artifact = _load_and_validate(out_path, day=day, account_id=account_id)
    raw_meta = artifact.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    certification = artifact.get("certification")
    base_result.update(
        {
            "bump": meta.get("bump"),
            "status": artifact.get("status"),
            "measured": bool(artifact.get("measured")),
            "gaps": artifact.get("gaps") or [],
            "costBps": artifact.get("costBps"),
            "certificationVerdict": (
                certification.get("verdict")
                if isinstance(certification, dict)
                else None
            ),
        }
    )
    return base_result


def _load_and_validate(
    out_path: pathlib.Path, *, day: str, account_id: str
) -> dict[str, Any]:
    """Valida el artefacto: existe, es JSON y pertenece al día/cuenta pedidos."""
    if not out_path.exists():
        raise DiaDAsRunFailed(
            f"El replay as-run terminó sin artefacto: {out_path.name}",
            result={"artifactPath": str(out_path)},
        )
    try:
        artifact = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiaDAsRunFailed(
            f"El artefacto as-run no es JSON legible: {exc}",
            result={"artifactPath": str(out_path)},
        ) from exc
    if not isinstance(artifact, dict):
        raise DiaDAsRunFailed("El artefacto as-run no es un objeto JSON")

    artifact_day = str(artifact.get("day") or "")
    if artifact_day != day:
        raise DiaDAsRunFailed(
            f"El artefacto es del día {artifact_day or '(vacío)'}, se pidió {day}"
        )
    raw_meta = artifact.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    artifact_account = str(meta.get("account") or "")
    if artifact_account != account_id:
        raise DiaDAsRunFailed(
            "El artefacto as-run pertenece a otra cuenta "
            f"({artifact_account or '(vacía)'} != {account_id}); no se publica"
        )
    if not isinstance(artifact.get("arms"), list) or not artifact.get("arms"):
        raise DiaDAsRunFailed("El artefacto as-run no declara brazos; no se publica")
    return artifact
