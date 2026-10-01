#!/usr/bin/env python3
"""Selección de tests del CI — **censo** de lo que REALMENTE se ejecuta (peaje `OBS-19`).

Por qué existe este módulo
--------------------------
`OBS-19` describe una causa estructural: las listas de `pytest` de los workflows se
mantienen **a mano**, así que un fichero de test puede existir y no correr en NINGÚN job
sin que nada lo note. Ya ha mordido cuatro veces (los `v2.76`, `v2.88` y `FLAKE-1` lo
dejaron escrito en los comentarios del workflow; y en `v2.70`/AUTO-23 el certificador del
validador de evidencia estaba ROJO y nadie lo ejecutaba).

Este módulo es la **única fuente de verdad** del censo: no adivina por grep (eso miente,
porque los jobs recogen por *directorios* y los `--ignore` recortan). Deriva el conjunto
ejecutado de la misma forma en que lo hace `pytest`: expandiendo los objetivos de cada
invocación y restando los `--ignore` del propio job.

Qué NO hace
-----------
No cambia lo que corre. Es **instrumento**: mide y declara. El cableado de lo que falta
va por tandas (ver la línea base).

Uso::

    # Informe legible del censo (mismo cálculo que la guarda)
    uv run --no-sync python scripts/ci/test_selection.py --report

    # Sólo lo que NO ejecuta ningún job
    uv run --no-sync python scripts/ci/test_selection.py --missing

    # Regenerar la línea base (sólo tras cablear/declarar explícitamente)
    uv run --no-sync python scripts/ci/test_selection.py --write-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NamedTuple

#: Raíz del repositorio (``scripts/ci/test_selection.py`` → tres niveles arriba).
ROOT = Path(__file__).resolve().parents[2]

WORKFLOWS_DIR = ROOT / ".github" / "workflows"

#: Línea base del agujero DECLARADO: ficheros que hoy no ejecuta ningún job, con su motivo
#: y la tanda en la que se cablean. La guarda falla si aparece uno nuevo que no esté aquí.
BASELINE = Path(__file__).with_name("ci-test-selection-baseline.json")

#: Raíces donde viven los tests del proyecto.
TEST_ROOTS = ("packages/py", "apps/api-python")

#: Flags de pytest que no aportan objetivos (se descartan al normalizar).
_FLAGS_WITH_VALUE = {"-p", "-o", "-k", "-m", "--maxfail", "-n", "--deselect"}
_DROP_FLAGS = {"-q", "-v", "--tb=short", "--tb=long", "--tb=line", "--tb=no", "-rs", "-ra", "-rf"}


class Invocation(NamedTuple):
    """Una invocación de `pytest` en un workflow.

    Se usa ``NamedTuple`` y no ``dataclass`` a propósito: este módulo se carga también
    desde la guarda con ``spec_from_file_location``, y ``@dataclass(slots=True)`` exige que
    el módulo esté en ``sys.modules`` (si no, revienta al resolver las anotaciones). Un
    ``NamedTuple`` no tiene esa dependencia y el módulo se puede cargar de las dos formas.
    """

    workflow: str
    job: str
    args: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.workflow}::{self.job}"


def test_files_under(directory: Path) -> list[Path]:
    """Ficheros de test de un directorio (mismo patrón que pytest por defecto)."""
    found = {*directory.rglob("test_*.py"), *directory.rglob("*_test.py")}
    return sorted(found)


def universe() -> set[str]:
    """Todos los ficheros de test del repositorio, relativos a la raíz."""
    files: set[str] = set()
    for base in TEST_ROOTS:
        root = ROOT / base
        if not root.is_dir():
            continue
        for path in test_files_under(root):
            files.add(path.relative_to(ROOT).as_posix())
    return files


def _run_blocks(workflow: Path) -> list[tuple[str, str]]:
    """``(job, texto del run)`` de cada bloque ``run:`` del workflow.

    Parseo por indentación a propósito: evita depender de un lector de YAML en el job
    *offline* (donde la guarda corre) y no depende de que el fichero esté bien formado
    más allá de la indentación, que es lo único que este censo necesita.
    """
    blocks: list[tuple[str, str]] = []
    job = "?"
    lines = workflow.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        found_job = re.match(r"^ {2}([A-Za-z0-9_.-]+):\s*$", line)
        if found_job:
            job = found_job.group(1)
        if re.match(r"^\s{6,}run:\s*[>|]", line):
            indent = len(line) - len(line.lstrip())
            body: list[str] = []
            index += 1
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() == "":
                    body.append("")
                    index += 1
                    continue
                if len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt)
                index += 1
            blocks.append((job, "\n".join(body)))
            continue
        index += 1
    return blocks


def _tokenize(raw: str) -> list[str]:
    """Tokens de la invocación, con las continuaciones ``\\`` y los comentarios ya resueltos."""
    joined = raw.replace("\\\n", " ")
    kept = [line for line in joined.splitlines() if not line.strip().startswith("#")]
    return " ".join(kept).split()


def _pytest_args(tokens: list[str]) -> list[str] | None:
    """Argumentos de la primera invocación de ``pytest`` de un run, o ``None`` si no hay."""
    try:
        start = tokens.index("pytest")
    except ValueError:
        return None
    args: list[str] = []
    index = start + 1
    while index < len(tokens):
        token = tokens[index]
        if token == "|" or token.startswith(">"):
            break
        if token in _DROP_FLAGS or token.startswith("--tb="):
            index += 1
            continue
        if token in _FLAGS_WITH_VALUE:
            index += 2
            continue
        args.append(token)
        index += 1
    return args


def invocations() -> list[Invocation]:
    """Todas las invocaciones de `pytest` declaradas en los workflows, en orden."""
    found: list[Invocation] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for job, raw in _run_blocks(workflow):
            if "pytest" not in raw:
                continue
            tokens = _tokenize(raw)
            # Un run puede encadenar varios comandos: se censan TODOS los `pytest` del run.
            while True:
                args = _pytest_args(tokens)
                if args is None:
                    break
                found.append(Invocation(workflow.name, job, tuple(args)))
                try:
                    tokens = tokens[tokens.index("pytest") + 1 :]
                except ValueError:
                    break
    return found


def collected_by(invocation: Invocation) -> set[str]:
    """Ficheros que esa invocación recoge: objetivos expandidos menos sus ``--ignore``.

    Réplica de la semántica de `pytest` que importa aquí: un objetivo de DIRECTORIO se
    expande entero y luego se recorta con los ``--ignore``; un objetivo de FICHERO manda
    sobre el ``--ignore`` (por eso un fichero ignorado en el job offline puede seguir
    corriendo explícitamente en el job PG —y viceversa, que es justo el agujero a cazar).
    """
    ignored = [a.split("=", 1)[1].strip("/") for a in invocation.args if a.startswith("--ignore=")]
    collected: set[str] = set()
    for arg in invocation.args:
        if arg.startswith("-"):
            continue
        target = ROOT / arg
        if target.is_dir():
            for path in test_files_under(target):
                rel = path.relative_to(ROOT).as_posix()
                if any(rel == one or rel.startswith(one + "/") for one in ignored):
                    continue
                collected.add(rel)
        elif target.is_file() and (
            target.name.startswith("test_") or target.name.endswith("_test.py")
        ):
            collected.add(target.relative_to(ROOT).as_posix())
    return collected


def executed() -> set[str]:
    """Unión de lo que ejecuta algún job."""
    covered: set[str] = set()
    for invocation in invocations():
        covered |= collected_by(invocation)
    return covered


def declared_baseline() -> dict[str, Any]:
    """Línea base declarada del agujero (motivo + tanda por fichero)."""
    if not BASELINE.is_file():
        return {"entries": {}}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _classify(relative: str) -> tuple[str, str]:
    """``(motivo, tanda)`` de un fichero que hoy no ejecuta ningún job."""
    source = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
    if "integration/" in relative or re.search(r"httpx|requests\.|aiohttp|TestClient", source):
        return (
            "requiere API/red o E2E integrado (job playwright-integrated, opt-in)",
            "W-G2/3",
        )
    if re.search(
        r"db_session|create_engine|get_settings|Postgres|alembic|DATABASE_URL|psycopg",
        source,
    ):
        return (
            "requiere PostgreSQL o BD dedicada: se cablea en un job con PG, no en el offline",
            "W-G2/2",
        )
    return (
        "hermético: pasa offline; pendiente de cableado (directorio sin pase en el job offline)",
        "W-G2/1",
    )


def report() -> dict[str, Any]:
    """Censo completo: ejecutado, no ejecutado, declarado y lo NO declarado (lo que falla)."""
    total = universe()
    run = executed()
    missing = sorted(total - run)
    entries = declared_baseline().get("entries", {})
    declared = {path for path in missing if path in entries}
    undeclared = sorted(set(missing) - declared)
    stale = sorted(path for path in entries if path not in missing)
    return {
        "universe": sorted(total),
        "executed": sorted(run),
        "missing": missing,
        "declared": sorted(declared),
        "undeclared": undeclared,
        "stale_baseline_entries": stale,
        "max_undeclared": int(declared_baseline().get("maxUndeclared", 0)),
    }


def write_baseline(max_undeclared: int = 0) -> int:
    """Regenera la línea base a partir del censo actual (sólo con motivo y tanda)."""
    total = universe()
    run = executed()
    entries = {
        path: dict(zip(("reason", "wave"), _classify(path), strict=True))
        for path in sorted(total - run)
    }
    BASELINE.write_text(
        json.dumps(
            {
                "asOf": "2026-10-01",
                "note": (
                    "Agujero DECLARADO del peaje OBS-19: ficheros de test que hoy no ejecuta "
                    "ningún job. Cada entrada lleva su motivo y la tanda en la que se cablea. "
                    "La guarda (test_ci_test_selection_census.py) falla si aparece un fichero "
                    "NUEVO que no esté declarado aquí: el agujero puede encogerse, nunca crecer."
                ),
                "maxUndeclared": max_undeclared,
                "entries": entries,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="informe legible del censo")
    parser.add_argument("--missing", action="store_true", help="sólo lo que no ejecuta ningún job")
    parser.add_argument("--invocations", action="store_true", help="invocaciones de pytest halladas")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="regenera la línea base declarada (requiere revisión humana)",
    )
    args = parser.parse_args(argv)

    if args.write_baseline:
        count = write_baseline()
        print(f"# línea base escrita: {count} ficheros declarados en {BASELINE}")
        return 0

    if args.invocations:
        found = invocations()
        print(f"# invocaciones de pytest: {len(found)}")
        for invocation in found:
            files = len(collected_by(invocation))
            print(f"  {invocation.label:60s} args={len(invocation.args):3d} ficheros={files}")
        return 0

    data = report()
    if args.missing:
        for path in data["missing"]:
            print(path)
        return 0

    print(f"# universo            : {len(data['universe'])}")
    print(f"# ejecutado por el CI : {len(data['executed'])}")
    print(f"# NO ejecutado        : {len(data['missing'])}")
    print(f"#   declarado         : {len(data['declared'])}")
    print(f"#   SIN DECLARAR      : {len(data['undeclared'])}")
    print(f"# entradas obsoletas  : {len(data['stale_baseline_entries'])}")
    if data["undeclared"]:
        print("# SIN DECLARAR (esto es lo que la guarda considera un fallo):")
        for path in data["undeclared"]:
            print(f"    {path}")
    if data["stale_baseline_entries"]:
        print("# entradas de la línea base que ya NO faltan (regenerar):")
        for path in data["stale_baseline_entries"]:
            print(f"    {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
