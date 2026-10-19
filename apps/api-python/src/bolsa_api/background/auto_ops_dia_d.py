"""Handler del job ``dia_d_replay`` — ejecuta el sandbox DÍA-D AUTO como subproceso.

El motor de replay NO se refactoriza: se lanza el CLI existente
(``apps/api-python/scripts/v2_89_dia_d_auto_replay.py``) con el **mismo intérprete**
del proceso de workers (``sys.executable``), ``cwd`` en la raíz del repo, timeout y
lectura incremental del JSONL de progreso.

Reglas duras:

* **Un artefacto por ``(cuenta, día)``**: la ruta sale de
  :func:`bolsa_application.dia_d_artifacts.artifact_relpath` y se pasa al CLI con ``--out``.
  Dos cuentas que replayen el mismo día escriben ficheros distintos y no se pisan
  (antes ambas competían por ``dia-d-auto-<D>.json``).
* El artefacto se escribe de forma **atómica** en el script; un fallo nunca deja un JSON
  parcial que la API pueda leer como bueno.
* Se valida al terminar: ``exit 0`` + artefacto existente + ``day`` solicitado +
  ``meta.account`` de la cuenta. Cualquier desviación falla el job con motivo.
* Si el job falla, el artefacto ANTERIOR (si existía) permanece intacto: la UI lo
  etiqueta como «artefacto anterior».
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

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bolsa_application.dia_d_artifacts import (
    DIA_D_ARTIFACT_DIR,
    artifact_path_in,
    artifacts_root,
    progress_path_in,
)
from bolsa_infrastructure.database.repositories.auto_ops_job_repository import (
    SqlAlchemyAutoOpsJobRepository,
)

__all__ = [
    "DiaDReplayFailed",
    "artifact_path",
    "artifacts_dir_for_jobs",
    "progress_path",
    "run_dia_d_replay_job",
]

logger = logging.getLogger(__name__)

_SCRIPT_REL = pathlib.Path("apps") / "api-python" / "scripts" / "v2_89_dia_d_auto_replay.py"
_STDERR_TAIL_CHARS = 4000
_POLL_SECONDS = 1.0
#: Suelo del timeout (segundos). Constante para que una prueba pueda acortarlo.
_MIN_TIMEOUT_SECONDS = 30.0
_TAIL_BYTES = _STDERR_TAIL_CHARS * 2


class DiaDReplayFailed(RuntimeError):
    """El replay no produjo un artefacto válido para el día/cuenta solicitados."""

    def __init__(self, message: str, *, result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.result = result or {}


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        if (parent / _SCRIPT_REL).exists():
            return parent
    raise DiaDReplayFailed("no se encontró la raíz del repo (marcador v2_89)")


def artifact_path(root: pathlib.Path, day: str, account_id: str) -> pathlib.Path:
    """Artefacto de ``(cuenta, día)`` bajo la raíz del repo — **nunca** la ruta plana."""
    return artifact_path_in(root / DIA_D_ARTIFACT_DIR, day, account_id)


def artifacts_dir_for_jobs() -> pathlib.Path:
    """Carpeta ``…/dia-d-auto`` donde este worker ESCRIBE los artefactos.

    Debe coincidir con la que resuelven las rutas HTTP de lectura (``auto_dia_d`` y
    ``auto_dia_d_feedback``): ambas pasan por :func:`artifacts_root` con el mismo
    ``DIA_D_AUTO_DIR``. Si el worker ignorase el override, escribiría en el árbol del repo
    mientras la API lee del directorio redirigido y la UI diría «sin artefacto» con el
    fichero en disco.
    """
    return artifacts_root(_repo_root() / DIA_D_ARTIFACT_DIR, os.environ)


def progress_path(root: pathlib.Path, job_id: str, account_id: str) -> pathlib.Path:
    """JSONL de progreso del job bajo la raíz del repo, dentro del segmento de su cuenta."""
    return progress_path_in(root / DIA_D_ARTIFACT_DIR, job_id, account_id)


def _display_path(path: pathlib.Path, root: pathlib.Path) -> str:
    """Ruta presentable: relativa al repo si vive dentro; absoluta si el override la saca."""
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_last_progress(path: pathlib.Path, offset: int) -> tuple[dict[str, Any] | None, int]:
    """Última línea completa del JSONL a partir de ``offset`` (tolerante a escritura parcial)."""
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read()
    except OSError:
        return None, offset
    if not chunk:
        return None, offset
    last_newline = chunk.rfind(b"\n")
    if last_newline < 0:
        # Línea en curso: no consumirla (se leerá completa en el siguiente poll).
        return None, offset
    consumed = chunk[: last_newline + 1]
    new_offset = offset + len(consumed)
    last: dict[str, Any] | None = None
    for raw in consumed.decode("utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            last = parsed
    return last, new_offset


async def _spawn_process_async(
    cmd: list[str],
    *,
    cwd: pathlib.Path,
    env: dict[str, str],
    stdout: Any,
    stderr: Any,
) -> Any:
    """Lanza el CLI con ``subprocess.Popen`` (síncrono, en un hilo).

    Windows fuerza ``SelectorEventLoop`` en el worker (psycopg async no funciona en
    Proactor), y ese bucle **no** implementa ``asyncio.create_subprocess_*``: usarlo
    hacía fallar todo replay con ``NotImplementedError``. ``Popen`` es portable y la
    espera se hace desde el bucle con ``poll``/``kill`` (nunca bloquea al worker).
    """
    return await asyncio.to_thread(
        _spawn_process, cmd, cwd=cwd, env=env, stdout=stdout, stderr=stderr
    )


def _spawn_process(
    cmd: list[str],
    *,
    cwd: pathlib.Path,
    env: dict[str, str],
    stdout: Any,
    stderr: Any,
) -> Any:
    """``subprocess.Popen`` puro (lo ejecuta :func:`_spawn_process_async` en un hilo)."""
    return subprocess.Popen(  # noqa: S603 — comando interno, sin shell
        cmd,
        cwd=str(cwd),
        env=env,
        stdout=stdout,
        stderr=stderr,
    )


def _read_tail(handle: Any) -> str:
    """Últimos bytes de un fichero de salida (sin cargar todo el replay en memoria)."""
    handle.seek(0, os.SEEK_END)
    size = handle.tell()
    handle.seek(max(0, size - _TAIL_BYTES))
    data: bytes = handle.read()
    return data.decode("utf-8", errors="replace")


async def _wait_process(
    process: Any,
    *,
    publisher: _ProgressPublisher,
    timeout_seconds: float,
) -> tuple[bool, int | None]:
    """Espera al proceso publicando progreso; devuelve ``(timed_out, returncode)``."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(_MIN_TIMEOUT_SECONDS, float(timeout_seconds))
    while True:
        returncode = await asyncio.to_thread(process.poll)
        if returncode is not None:
            return False, returncode
        try:
            await publisher.tick()
        except Exception:  # noqa: BLE001 — progreso/latido best-effort
            logger.debug("dia_d_replay: fallo publicando progreso", exc_info=True)
        if loop.time() >= deadline:
            await asyncio.to_thread(process.kill)
            try:
                await asyncio.to_thread(process.wait, 15)
            except (subprocess.TimeoutExpired, OSError):  # pragma: no cover
                pass
            return True, None
        await asyncio.sleep(_POLL_SECONDS)


class _ProgressPublisher:
    """Publica el último evento JSONL como progreso del job y renueva el latido."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        job_id: str,
        path: pathlib.Path,
    ) -> None:
        self._session_factory = session_factory
        self._job_id = job_id
        self._path = path
        self._offset = 0
        self._last: dict[str, Any] | None = None

    async def tick(self) -> None:
        last, offset = _read_last_progress(self._path, self._offset)
        if last is None:
            return
        self._offset = offset
        if last == self._last:
            # Sin evento nuevo: solo se renueva el latido.
            async with self._session_factory() as session:
                await SqlAlchemyAutoOpsJobRepository(session).touch(self._job_id)
                await session.commit()
            return
        self._last = last
        async with self._session_factory() as session:
            await SqlAlchemyAutoOpsJobRepository(session).set_progress(
                self._job_id, dict(last)
            )
            await session.commit()


async def run_dia_d_replay_job(
    job: Any,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    timeout_seconds: float = 1800.0,
) -> dict[str, Any]:
    """Ejecuta el replay del día del job y devuelve el parte para ``result``."""
    day = str(job.day)
    account_id = str(job.account_id or "")
    if not account_id:
        raise DiaDReplayFailed("El replay DÍA-D requiere cuenta")

    root = _repo_root()
    script = root / _SCRIPT_REL
    # La carpeta de ESCRITURA honra `DIA_D_AUTO_DIR` igual que las rutas de lectura.
    artifacts_dir = artifacts_dir_for_jobs()
    out_path = artifact_path_in(artifacts_dir, day, account_id)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    progress_file = progress_path_in(artifacts_dir, job.id, account_id)
    progress_file.parent.mkdir(parents=True, exist_ok=True)

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
        "--progress-jsonl",
        str(progress_file),
    ]
    env = dict(os.environ)
    env.pop("PYTHONINSPECT", None)

    started = datetime.now(UTC)
    publisher = _ProgressPublisher(session_factory, job.id, progress_file)
    stdout_file = tempfile.TemporaryFile()
    stderr_file = tempfile.TemporaryFile()
    try:
        try:
            process = await _spawn_process_async(
                cmd,
                cwd=root,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
            )
        except OSError as exc:
            raise DiaDReplayFailed(f"No se pudo lanzar el replay: {exc}") from exc

        timed_out, returncode = await _wait_process(
            process, publisher=publisher, timeout_seconds=timeout_seconds
        )
        stderr_tail = _read_tail(stderr_file).strip()
        stdout_tail = _read_tail(stdout_file)
        returncode = process.returncode
    finally:
        stdout_file.close()
        stderr_file.close()

    tail = (stderr_tail or stdout_tail).strip()[-_STDERR_TAIL_CHARS:]
    elapsed = round((datetime.now(UTC) - started).total_seconds(), 1)
    base_result = {
        "day": day,
        "accountId": account_id,
        # Con `DIA_D_AUTO_DIR` fuera del repo la ruta no es relativa a `root`: se declara
        # absoluta en vez de reventar el job al formatear el resultado.
        "artifactPath": _display_path(out_path, root),
        "progressPath": _display_path(progress_file, root),
        "elapsedSeconds": elapsed,
        "timedOut": timed_out,
    }

    if timed_out:
        raise DiaDReplayFailed(
            f"Timeout del replay DÍA-D a los {elapsed}s", result=base_result
        )
    if returncode != 0:
        detail = tail or f"exit {returncode}"
        raise DiaDReplayFailed(
            f"El replay DÍA-D falló (exit {returncode}): {detail}",
            result=base_result,
        )

    artifact = _load_and_validate(out_path, day=day, account_id=account_id)
    base_result.update(
        {
            "bump": (artifact.get("meta") or {}).get("bump"),
            "verdict": (artifact.get("summary") or {}).get("verdict"),
            "summary": artifact.get("summary"),
            "watchSize": (artifact.get("meta") or {}).get("watchSize"),
            "limits": artifact.get("limits") or [],
        }
    )
    return base_result


def _load_and_validate(
    out_path: pathlib.Path, *, day: str, account_id: str
) -> dict[str, Any]:
    """Valida el artefacto final: existe, es JSON y pertenece al día/cuenta pedidos."""
    if not out_path.exists():
        raise DiaDReplayFailed(
            f"El replay terminó sin artefacto: {out_path.name}",
            result={"artifactPath": str(out_path)},
        )
    try:
        artifact = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiaDReplayFailed(
            f"El artefacto no es JSON legible: {exc}",
            result={"artifactPath": str(out_path)},
        ) from exc
    if not isinstance(artifact, dict):
        raise DiaDReplayFailed("El artefacto no es un objeto JSON")

    artifact_day = str(artifact.get("day") or "")
    if artifact_day != day:
        raise DiaDReplayFailed(
            f"El artefacto es del día {artifact_day or '(vacío)'}, se pidió {day}"
        )
    raw_meta = artifact.get("meta")
    meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    artifact_account = str(meta.get("account") or "")
    if artifact_account != account_id:
        raise DiaDReplayFailed(
            "El artefacto pertenece a otra cuenta "
            f"({artifact_account or '(vacía)'} != {account_id}); no se publica"
        )
    return artifact
