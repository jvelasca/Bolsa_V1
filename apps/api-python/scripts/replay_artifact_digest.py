"""V2.88.7 / AUTO-MATERIAL-20 — DIGEST por secciones de un artefacto del replay OOS.

Por qué existe
--------------
El job ``replay-repro`` del CI contrasta el **SHA-256 del fichero entero** contra el sello.
Ese contraste es binario: cuando falla dice «no reproducido», pero **no dice dónde**. Y un
rojo que no dice dónde obliga a reproducir el runner a mano —justo lo que este trabajo
quiere eliminar—.

Este script descompone el artefacto en sus **secciones** y publica, por cada una, su tamaño
canónico y su SHA-256, más los conteos que explican ese tamaño. Así un fallo del job
publica en el log ``census=<hash A> replay=<hash B>`` y se puede comparar con la corrida
local **sin mover ficheros**: si difiere ``census`` el desvío es de ENTRADA (barras/catálogo)
y si difiere ``replay`` es del MOTOR (geometría, gates) — la mitad del árbol se poda de un
golpe.

Es read-only y no importa la aplicación (solo stdlib): se puede correr sobre cualquier
artefacto, en cualquier máquina.

Uso::

    uv run --no-sync python apps/api-python/scripts/replay_artifact_digest.py \
        --file operability_runs/replay-oos-durable-obs20-fix-20260929.json

    # salida legible por máquina (una línea por sección) para diffear dos corridas
    uv run --no-sync python apps/api-python/scripts/replay_artifact_digest.py --file x.json --lines
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from typing import Any

#: Conteos que explican el tamaño de cada sección (si no cuadran, la sección cambió).
_COUNT_PATHS: tuple[tuple[str, str], ...] = (
    ("census", "days"),
    ("replay", "perDay"),
    ("replay", "book.perDay"),
    ("replay", "score.byDay"),
    ("replay", "score.byYear"),
    ("replay", "score.byVersion"),
    ("replay", "finalBook.liveReservations"),
    ("replay", "finalBook.pendingTraces"),
)


def _canon(value: Any) -> bytes:
    """Serialización canónica: la misma que hace el artefacto (``sort_keys`` + UTF-8)."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    ).encode("utf-8")


def _dig_value(value: Any) -> tuple[int, str]:
    blob = _canon(value)
    return len(blob), hashlib.sha256(blob).hexdigest()[:16]


def _sections(doc: dict[str, Any]) -> dict[str, tuple[int, str]]:
    return {key: _dig_value(doc[key]) for key in sorted(doc)}


def _get(doc: Any, dotted: str) -> Any:
    node = doc
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _render_of(raw: bytes) -> str:
    """Etiqueta el render del fichero: ``CRLF`` (modo texto de Windows) o ``LF``."""
    return "CRLF (modo texto de Windows)" if raw.count(b"\r\n") else "LF"


def _canonical_lf(raw: bytes) -> bytes:
    """Contenido con salto de línea LF: quita la traducción del modo texto de Windows.

    El artefacto se escribe con ``indent=2`` y sus únicos bytes ``\\r`` son los que el SO
    intercala delante de cada ``\\n``; dentro de las cadenas JSON un salto va escapado
    (``\\n``), nunca en crudo. Normalizar ``\\r\\n`` → ``\\n`` no puede alterar la evidencia.
    """
    return raw.replace(b"\r\n", b"\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, type=pathlib.Path, help="artefacto JSON")
    parser.add_argument(
        "--lines",
        action="store_true",
        help="salida compacta «clave tamaño sha256» (para diffear dos corridas)",
    )
    args = parser.parse_args(argv)

    raw = args.file.read_bytes()
    canonical = _canonical_lf(raw)
    doc = json.loads(raw)

    if args.lines:
        print(f"fichero {len(raw)} {hashlib.sha256(raw).hexdigest().upper()}")
        print(f"render {_render_of(raw)} {len(canonical)} {hashlib.sha256(canonical).hexdigest().upper()}")
        for key, (size, digest) in _sections(doc).items():
            print(f"{key} {size} {digest}")
        replay = doc.get("replay") or {}
        if isinstance(replay, dict) and replay.get("totals"):
            print(f"totals {_canon(replay['totals']).decode('utf-8')}")
            score = replay.get("score")
            if score is not None:
                size, digest = _dig_value(score)
                print(f"score {size} {digest}")
            reasons = replay.get("journalReasons")
            if reasons is not None:
                size, digest = _dig_value(reasons)
                print(f"journalReasons {size} {digest}")
        return 0

    print(f"artefacto        {args.file}")
    print(f"bytes            {len(raw)}")
    print(f"sha256           {hashlib.sha256(raw).hexdigest().upper()}")

    print()
    print("SECCIÓN              TAMAÑO CANÓNICO   SHA-256 (16)")
    print("-" * 54)
    for key, (size, digest) in _sections(doc).items():
        print(f"{key:<20} {size:>16}   {digest}")

    print()
    print("CONTEOS QUE EXPLICAN EL TAMAÑO")
    print("-" * 54)
    for section, path in _COUNT_PATHS:
        value = _get(doc.get(section), path)
        if isinstance(value, list):
            print(f"{section}.{path:<26} {len(value)} elementos")
        elif value is not None:
            print(f"{section}.{path:<26} {value!r}")

    replay = doc.get("replay")
    if isinstance(replay, dict):
        print()
        print("MOTOR")
        print("-" * 54)
        for key in ("startDay", "endDay", "ticks", "daysWithFills"):
            print(f"{key:<32} {replay.get(key)!r}")
        print(f"{'totals':<32} {json.dumps(replay.get('totals'), sort_keys=True)}")
        reasons = replay.get("journalReasons")
        if reasons:
            blob = _canon(reasons)
            print(
                f"{'journalReasons':<32} {len(blob)} B · "
                f"{hashlib.sha256(blob).hexdigest()[:16]}"
            )
            print(f"{'':<32} {sorted(reasons.items(), key=lambda kv: -int(kv[1]))}")
        book = replay.get("book")
        if isinstance(book, dict):
            print(f"{'book.stall':<32} {json.dumps(book.get('stall'), sort_keys=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
