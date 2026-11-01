"""Tripwire del cableado `a7-gate` en el CI del tag (un A7 verde con skips no sella).

Por qué existe
--------------
El riesgo residual del cierre `.174` no era el código de la guarda sino la LECTURA de su
resultado: `12 passed, 7 skipped` en verde se puede confundir con "A7 certificado". Lo que
lo cierra es el cableado del workflow — `LIVE_A7_PG_REQUIRED=1` (convierte el skip en
`AssertionError`) en el job `a7-gate`, `a7-gate` en el `needs` de `certify` y el `exit 1`
que impide sellar. Ese cableado es YAML: nadie lo ejecuta en local, así que puede
desaparecer en un refactor sin que ningún test se entere. Este fichero lo ancla.

Por qué se parsea por líneas y no con un lector YAML
----------------------------------------------------
Mismo criterio que `scripts/ci/test_selection.py`: el job `python` no instala PyYAML para
sus tests y una dependencia nueva solo para leer un workflow sería un peaje permanente. El
parser es deliberadamente mínimo (bloques por indentación y escalares `clave: valor`) y va
con ANCLAS POSITIVAS: si dejara de ver los jobs o los `needs`, el test falla por vacuo en
vez de pasar en falso.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release-tag-ci.yml"

#: Un job top-level del workflow (`  nombre:`) bajo `jobs:`.
_JOB_HEADER = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
#: `clave: valor` con cualquier indentación (escalares del YAML).
_SCALAR = re.compile(r"^(\s*)([A-Za-z0-9_.-]+):\s*(\S.*)?$")


def _lines() -> list[str]:
    return _WORKFLOW.read_text(encoding="utf-8").splitlines()


def _job_section() -> list[str]:
    """Líneas desde `jobs:` en adelante (antes de eso hay `on:`/`concurrency:`)."""
    lines = _lines()
    for index, line in enumerate(lines):
        if line.strip() == "jobs:":
            return lines[index + 1 :]
    raise AssertionError("el workflow no declara la sección 'jobs:'")


def _job_block(name: str) -> list[str]:
    """Líneas del job ``name`` (desde su cabecera hasta el siguiente job)."""
    lines = _job_section()
    for index, line in enumerate(lines):
        match = _JOB_HEADER.match(line)
        if match and match.group(1) == name:
            block = [line]
            for following in lines[index + 1 :]:
                if _JOB_HEADER.match(following):
                    break
                block.append(following)
            return block
    raise AssertionError(f"el workflow no declara el job '{name}'")


def _job_names() -> list[str]:
    return [match.group(1) for line in _job_section() if (match := _JOB_HEADER.match(line))]


def _scalars(block: list[str], key: str) -> list[tuple[int, str]]:
    """Pares ``(indentación, valor)`` de ``key`` dentro del bloque."""
    found: list[tuple[int, str]] = []
    for line in block:
        match = _SCALAR.match(line)
        if not match or match.group(2) != key:
            continue
        value = (match.group(3) or "").split("#", 1)[0].strip()
        found.append((len(match.group(1)), value))
    return found


def _normalized(value: str) -> str:
    return value.strip().strip("'\"")


# ---------------------------------------------------------------------------
# Anclas del parser (si se rompen, el resto de aserciones sería vacua)
# ---------------------------------------------------------------------------


def test_the_parser_sees_the_workflow_jobs_and_the_certify_needs() -> None:
    """Anclas positivas: 13 jobs y `certify` con más de diez dependencias."""
    jobs = _job_names()
    assert "a7-gate" in jobs
    assert "certify" in jobs
    assert len(jobs) >= 13, f"el parser solo ve {len(jobs)} jobs: {jobs}"
    block = _job_block("certify")
    assert any(line.strip() == "needs: [" or line.strip().startswith("needs:") for line in block)


# ---------------------------------------------------------------------------
# Gate duro dentro del job a7-gate
# ---------------------------------------------------------------------------


def test_a7_gate_sets_the_hard_gate_at_job_and_step_level() -> None:
    """`LIVE_A7_PG_REQUIRED: '1'` en el `env` del job Y en el step que corre la batería.

    Job-level: cualquier step del job (instalar, migrar, preparar la BD) hereda el gate.
    Step-level: el run de pytest lo declara explícitamente, así que no depende de que nadie
    mueva el `env` del job.
    """
    block = _job_block("a7-gate")
    occurrences = _scalars(block, "LIVE_A7_PG_REQUIRED")
    assert occurrences, "a7-gate no declara LIVE_A7_PG_REQUIRED"
    values = [_normalized(value) for _, value in occurrences]
    assert values == ["1"] * len(values), f"el gate no vale 1 en todos los sitios: {values}"
    indents = {indent for indent, _ in occurrences}
    assert 6 in indents, f"falta el gate en el env a nivel de job (indentaciones: {sorted(indents)})"
    assert 10 in indents, f"falta el gate en el env del step (indentaciones: {sorted(indents)})"


def test_a7_gate_runs_the_live_a7_battery() -> None:
    """El step de pytest apunta a `apps/api-python/tests/chaos/live_a7` (no a un subconjunto)."""
    block = _job_block("a7-gate")
    joined = "\n".join(block)
    assert "uv run pytest" in joined
    assert "apps/api-python/tests/chaos/live_a7" in joined


# ---------------------------------------------------------------------------
# Un a7-gate rojo no puede sellarse
# ---------------------------------------------------------------------------


def test_certify_requires_a7_gate() -> None:
    """`a7-gate` está en el `needs` de `certify`."""
    block = _job_block("certify")
    needs = "\n".join(line for line in block if "needs:" in line or "a7-gate" in line)
    assert "a7-gate" in needs, f"certify no depende de a7-gate: {needs!r}"


def test_certify_fails_the_release_when_a7_gate_is_not_success() -> None:
    """La condición de fallo nombra `needs.a7-gate.result` y termina en `exit 1`."""
    block = _job_block("certify")
    joined = "\n".join(block)
    assert "needs.a7-gate.result != 'success'" in joined, (
        "certify no falla cuando a7-gate no es success: el sello podría quedar GREEN"
    )
    assert re.search(r"^\s*exit 1\s*$", joined, re.MULTILINE), "certify no corta el run con exit 1"
    # El artefacto resumen también declara el job (trazabilidad del sello).
    assert "JOB_A7_GATE" in joined
    assert '"a7-gate": os.environ["JOB_A7_GATE"]' in joined
