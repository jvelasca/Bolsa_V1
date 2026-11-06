"""Tripwire del hazard de los bloques plegados `run: >` en el CI del tag.

Por qué existe
--------------
El sello `.182` quedó con el job `python (ruff/imports/mypy/pytest offline)` en rojo
(8 fallos, todos `connection refused` contra `127.0.0.1:5432`) porque tres ficheros
que exigen PostgreSQL real se colaron en la selección offline. La causa no era la
lista de `--ignore`: era un comentario `#` **dentro** del `run: >`.
YAML pliega el bloque en UNA sola línea de shell, así que el primer `#` intercalado
convierte en comentario todo lo que sigue —incluidos los `--ignore` posteriores—.
El step ejecutó solo los tests anteriores al comentario y el job quedó rojo por un
motivo que el diff no dejaba ver.

Los dos defectos concretos del `.182`
-------------------------------------
1. Comentarios intercalados en el `run: >` del job `python` (release-tag-ci.yml).
2. `apps/api-python/tests/test_workspace_persistence.py` no estaba en ninguna lista
   de `--ignore` (no tiene guarda de skip: sin PG falla, que es lo correcto).

Este fichero ancla las dos cosas. Es YAML que nadie ejecuta en local: sin un test,
un refactor puede reintroducir el comentario y el job volverá a salir rojo solo en
el tag, que es el peor sitio para descubrirlo.

Criterio del parser: líneas, no PyYAML (el job `python` no instala PyYAML para sus
tests; mismo criterio que `test_release_tag_ci_a7_gate_wiring.py`). Se usan ANCLAS
POSITIVAS: si el parser deja de ver los bloques o el step offline, falla por vacuo.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release-tag-ci.yml"

#: Inicio de un bloque escalar plegado (`run: >`, con o sin modificador).
_FOLDED_START = re.compile(r"^(\s*)run:\s*>\s*$")

#: Ficheros PG que el `.182` coló en el job offline. Cada uno falló por conexión.
_PG_ONLY_SUITES = (
    "apps/api-python/tests/test_workspace_persistence.py",
    "packages/py/infrastructure/tests/test_mandate_sync_orphan_instrument.py",
    "packages/py/infrastructure/tests/test_f3b_alembic_data_epoch.py",
)


def _folded_run_blocks() -> list[list[str]]:
    """Cuerpo (líneas) de cada bloque `run: >` del workflow, en orden."""
    lines = _WORKFLOW.read_text(encoding="utf-8").splitlines()
    blocks: list[list[str]] = []
    index = 0
    while index < len(lines):
        match = _FOLDED_START.match(lines[index])
        if not match:
            index += 1
            continue
        base_indent = len(match.group(1))
        body: list[str] = []
        index += 1
        while index < len(lines):
            line = lines[index]
            if line.strip() == "":
                body.append(line)
                index += 1
                continue
            if len(line) - len(line.lstrip()) <= base_indent:
                break
            body.append(line)
            index += 1
        blocks.append(body)
    return blocks


def _offline_pytest_block(blocks: list[list[str]]) -> list[str]:
    """El `run: >` del job offline: el que selecciona la batería de pytest."""
    matches = [
        body
        for body in blocks
        if any("uv run pytest" in line for line in body)
        and any("--ignore=apps/api-python/tests/" in line for line in body)
    ]
    assert len(matches) == 1, (
        f"se esperaba UN bloque `run: >` de pytest offline, se vieron {len(matches)}"
    )
    return matches[0]


def test_the_parser_sees_the_folded_blocks() -> None:
    """Ancla positiva: el workflow usa varios `run: >` y uno es el pytest offline."""
    blocks = _folded_run_blocks()
    assert len(blocks) >= 5, f"el parser solo ve {len(blocks)} bloques `run: >`"
    block = _offline_pytest_block(blocks)
    assert any("uv run pytest" in line for line in block)


def test_folded_blocks_carry_no_shell_comments() -> None:
    """Ningún `#` puede empezar línea dentro de un `run: >`.

    En un bloque plegado cada línea es texto del MISMO comando de shell: un `#`
    inicial comenta el resto del comando, no solo esa línea. Un comentario ahí
    anula en silencio todos los argumentos posteriores (fue la causa del `.182`).
    """
    offenders: list[str] = []
    for body in _folded_run_blocks():
        for line in body:
            if line.strip().startswith("#"):
                offenders.append(line.strip())
    assert not offenders, (
        "hay comentarios dentro de un bloque `run: >`; en YAML plegado comentan "
        f"el resto del comando de shell: {offenders}"
    )


def test_offline_job_ignores_every_postgres_only_suite_that_broke_the_seal() -> None:
    """Los tres ficheros que tumbaron el `.182` están escritos en `--ignore`.

    Esto cubre el defecto 2 (una entrada que nunca existió en la lista). El
    defecto 1 —la lista existente pero anulada por un `#`— lo cubre
    `test_folded_blocks_carry_no_shell_comments`, porque el truncado ocurre al
    interpretar el shell y no deja rastro en el texto del YAML.
    """
    joined = "\n".join(_offline_pytest_block(_folded_run_blocks()))
    for suite in _PG_ONLY_SUITES:
        assert f"--ignore={suite}" in joined, (
            f"{suite} no se ignora en el job offline: sin PostgreSQL el job falla "
            "(y el `.182` falló exactamente así)"
        )


def test_offline_pytest_command_is_not_truncated() -> None:
    """El bloque conserva su forma completa: arranque, cierre `-q` y último `--ignore`.

    Es un ancla estructural (una edición que borre el final del bloque se ve aquí);
    el truncado *en ejecución* por un `#` lo detecta el test de comentarios.
    """
    body = _offline_pytest_block(_folded_run_blocks())
    tokens = [line.strip() for line in body if line.strip()]
    assert tokens, "el bloque de pytest offline está vacío"
    assert tokens[0] == "uv run pytest"
    assert tokens[-1] == "-q", f"el bloque no termina en `-q`: último token {tokens[-1]!r}"
    assert "--ignore=packages/py/infrastructure/tests/test_lifecycle_event_store_pg.py" in tokens
