"""Guarda de sesión: la suite no debe reescribir el latido del vigía de ventana.

``operability_runs/window-runs/`` **no está trackeado**, así que ``git status`` no puede
delatar que un test reescribió ``day-watch.json`` o añadió líneas a ``day-watch.jsonl``. La
única prueba posible es por contenido y fecha: ``sha256`` + tamaño + ``mtime_ns`` + líneas.

La atribución es determinista y no depende de ``git``: el latido declara el ``runId`` del
proceso que lo escribió, y la suite inyecta el suyo en el entorno (los subprocesos lo
heredan). Un latido del stack de desarrollo —que escribe el mismo fichero cada pocos
minutos— no lo lleva, de modo que se distingue de una escritura de la propia suite.

Este módulo se mantiene aparte del ``conftest`` para poder probar su lógica sin arrancar
una sesión de pytest anidada.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

#: Artefactos del latido que la suite NUNCA debe tocar.
DAY_WATCH_ARTIFACTS: tuple[str, ...] = ("day-watch.json", "day-watch.jsonl")

#: Marca que se usa cuando el payload no declara ``runId`` (formato antiguo o proceso ajeno).
NO_RUN_ID = "<sin-run-id>"


def fingerprint(base: Path) -> dict[str, tuple[str, int, int, int]]:
    """``{fichero: (sha256, bytes, mtime_ns, líneas)}`` de los latidos de ``base``."""
    result: dict[str, tuple[str, int, int, int]] = {}
    for name in DAY_WATCH_ARTIFACTS:
        path = base / name
        if not path.exists():
            result[name] = ("<ausente>", 0, 0, 0)
            continue
        raw = path.read_bytes()
        stat = path.stat()
        result[name] = (
            hashlib.sha256(raw).hexdigest(),
            len(raw),
            stat.st_mtime_ns,
            raw.count(b"\n"),
        )
    return result


def writers(
    before: dict[str, tuple[str, int, int, int]], base: Path
) -> set[str]:
    """``runId`` de quienes escribieron las líneas nuevas y el latido actual.

    ``before`` es el fingerprint de sesión: su cuarta componente (líneas) marca cuántas
    líneas del journal ya existían. Una línea nueva sin ``runId`` se declara
    ``NO_RUN_ID`` en vez de asumir nada.
    """
    payloads: list[object] = []

    journal = base / "day-watch.jsonl"
    before_lines = before["day-watch.jsonl"][3]
    if journal.exists():
        for raw in journal.read_text(encoding="utf-8").splitlines()[before_lines:]:
            if not raw.strip():
                continue
            try:
                payloads.append(json.loads(raw))
            except json.JSONDecodeError:
                payloads.append({})

    status = base / "day-watch.json"
    if status.exists():
        try:
            payloads.append(json.loads(status.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            payloads.append({})

    found: set[str] = set()
    for payload in payloads:
        run_id = payload.get("runId") if isinstance(payload, dict) else None
        found.add(run_id if isinstance(run_id, str) and run_id else NO_RUN_ID)
    return found


def polluted_by(run_id: str, found: set[str]) -> bool:
    """¿La reescritura lleva la firma de la corrida ``run_id``?"""
    return run_id in found
