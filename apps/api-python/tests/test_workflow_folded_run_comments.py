"""Guarda del riesgo ``V2.40.2``: un ``#`` dentro de un bloque ``run: >`` plegado.

Por qué esta guarda existe
--------------------------
En YAML, un escalar **plegado** (``run: >``) convierte cada línea en **texto del comando**,
unido por espacios. Un ``#`` intercalado no es un comentario YAML: es el inicio de un
comentario de **shell**, así que comenta *todo lo que viene detrás en la misma línea de
comando*.

En las listas de ``--ignore`` de los workflows eso es silencioso y caro: la lista se
trunca en el punto del comentario y el job offline empieza a recoger ficheros que exigen
PostgreSQL. El síntoma no es un error de sintaxis, es un job que se pone ROJO por
``connection refused`` o —peor— un job que sigue verde con la mitad de la batería sin
correr (el motivo por el que el propio ``release-tag-ci.yml`` documenta el hazard desde
V2.40.2).

El sello ``v2.88.180-beta`` volvió a caer en él: tres comentarios dentro del bloque
plegado descartaron **44** exclusiones en el CI del tag y **45** en ``Python CI``. El tag
quedó rojo. Esta prueba es la red que impide la recaída.

Qué comprueba
-------------
1. **Ningún ``#`` dentro de un ``run: >``**. Recorre los workflows con la indentación real
   (no con el YAML ya parseado, que perdería la distinción plegado/literal) y falla con
   fichero y línea.
2. **La lista de exclusiones no se trunca**: los bloques plegados que llevan ``--ignore``
   deben ver *todas* sus líneas como texto del comando, es decir, ninguna puede empezar por
   ``#``. Es la comprobación 1 aplicada al caso que dolió.
3. **El escáner ve los workflows** (control negativo): si el descubrimiento se rompiera, la
   comprobación 1 pasaría en falso; por eso se ancla que se han leído los workflows reales
   y que al menos uno contiene un bloque plegado con ``--ignore``.

Las líneas de comentario **literales** (``run: |``) quedan fuera a propósito: en un bloque
literal cada línea es una línea de shell distinta y un ``#`` es un comentario legítimo.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOWS = _ROOT / ".github" / "workflows"

#: Cabecera de un escalar de bloque. Captura el estilo (``>`` plegado, ``|`` literal) y
#: admite los modificadores de chomping (``>-``, ``|+``).
_RUN_HEADER = re.compile(r"^(?P<indent>\s*)(?:-\s+)?run:\s*(?P<style>[>|])[+-]?\s*$")

#: Workflows que el censo conoce y que deben existir; si faltan, el escáner está ciego.
_REQUIRED = ("python-ci.yml", "release-tag-ci.yml")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _folded_blocks(path: Path) -> list[tuple[int, list[tuple[int, str]]]]:
    """Devuelve ``[(línea_de_la_cabecera, [(n, texto), ...]), ...]`` de los ``run: >``."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[int, list[tuple[int, str]]]] = []
    index = 0
    while index < len(lines):
        match = _RUN_HEADER.match(lines[index])
        if match is None or match.group("style") != ">":
            index += 1
            continue
        base = _indent(lines[index])
        content: list[tuple[int, str]] = []
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if not line.strip():
                cursor += 1
                continue
            if _indent(line) <= base:
                break
            content.append((cursor + 1, line))
            cursor += 1
        blocks.append((index + 1, content))
        index = cursor
    return blocks


def _workflow_files() -> list[Path]:
    return sorted(_WORKFLOWS.glob("*.yml")) + sorted(_WORKFLOWS.glob("*.yaml"))


def test_the_scanner_sees_the_real_workflows() -> None:
    """Control negativo: sin workflows no habría nada que vigilar y todo pasaría en falso."""
    files = _workflow_files()
    names = {path.name for path in files}
    missing = [name for name in _REQUIRED if name not in names]
    assert not missing, f"el escáner no ve workflows obligatorios: {missing}"

    folded_with_ignores = [
        path
        for path in files
        if any(
            any("--ignore=" in line for _n, line in content) for _header, content in _folded_blocks(path)
        )
    ]
    assert folded_with_ignores, "ningún workflow tiene un run: > con --ignore: el escáner está ciego"


def test_no_comment_inside_a_folded_run_block() -> None:
    """Un ``#`` dentro de ``run: >`` comentaría el resto del comando (V2.40.2)."""
    offenders: list[str] = []
    for path in _workflow_files():
        for header, content in _folded_blocks(path):
            for number, line in content:
                if line.lstrip().startswith("#"):
                    offenders.append(f"{path.name}:{number} (bloque abierto en la línea {header})")
    assert not offenders, (
        "comentario dentro de un bloque plegado `run: >`: cada línea es texto del comando y "
        "el `#` comenta el resto (descartaría las líneas siguientes, p. ej. los --ignore). "
        "Muévelo a las líneas de comentario del step, FUERA del bloque:\n  " + "\n  ".join(offenders)
    )


def test_the_ignore_lists_of_the_offline_jobs_are_not_truncated() -> None:
    """El caso que dolió: las listas de ``--ignore`` deben llegar enteras al comando."""
    for name in _REQUIRED:
        path = _WORKFLOWS / name
        blocks = [content for _header, content in _folded_blocks(path)]
        ignore_lines = [line for content in blocks for _n, line in content if "--ignore=" in line]
        commented = [
            number
            for content in blocks
            for number, line in content
            if line.lstrip().startswith("#")
        ]
        assert ignore_lines, f"{name}: no se encontró ninguna lista de --ignore en un run: >"
        assert not commented, (
            f"{name}: hay comentarios dentro del bloque plegado (líneas {commented}); "
            "la lista de --ignore que venga después NO se ejecutaría"
        )


def test_the_c1_pg_file_is_ignored_offline_in_both_workflows() -> None:
    """``readGaps`` exige PostgreSQL: si deja de estar en ``--ignore``, el job offline se rompe.

    No es una comprobación de estilo sino de corrección: el fichero no lleva guarda de
    ``skip`` cuando el gate está activo, así que en un job sin PostgreSQL **falla** — que es
    justo lo que pasó al truncarse la lista.
    """
    target = "test_auto_chain_read_gaps_pg.py"
    for name in _REQUIRED:
        text = (_WORKFLOWS / name).read_text(encoding="utf-8")
        assert f"--ignore=apps/api-python/tests/{target}" in text, (
            f"{name}: falta --ignore para {target} en el job offline"
        )
