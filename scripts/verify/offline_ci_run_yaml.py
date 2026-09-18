"""Runner local de los bloques offline de CI: extrae la invocacion DEL YAML.

Leccion de la fase 2b: medir con una copia a mano de la lista de pytest puede dar verde
midiendo OTRA cosa (el primer wiring de 2b anadio a ``quality`` una ruta inexistente, que en
pytest es exit 4 y habria puesto el job rojo). Aqui se lee el ``run`` del step de pytest del
job, se verifican las rutas y se corre el bloque con los ``--ignore`` del YAML mas los
ficheros PG que en CI saltan rapido (no hay servidor en ese job) y en local se cuelgan (el
``connect`` del DSN no responde ni rechaza).

Uso:
    uv run python scripts/verify/offline_ci_run_yaml.py <workflow.yml> <job> --with-pg-ignores

Codigos de salida: el de pytest; ``4`` si alguna ruta objetivo no existe (como haria pytest).
"""

from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Cualquier fichero de test con ``_pg`` en el nombre toca PostgreSQL. La primera version de
# este patron exigia ``_pg`` pegado al final del nombre (``_pg.py`` / ``_pg_x.py``) y se le
# escaparon ``test_a9_scheduler_process_pg_zero_human.py`` y
# ``test_auto_scheduler_real_pg_zero_human_intervention.py``: sin ``--ignore`` su ``connect``
# al DSN dejo la corrida local colgada 15 minutos.
PG_RE = re.compile(r"(^|/)test_[^/]*_pg[^/]*\.py$|(^|/)chaos/live_a7")


def load_pytest_args(workflow: str, job: str) -> list[str]:
    """Tokens del ``run`` del step de pytest del job (sin la palabra ``pytest``)."""
    import yaml

    path = ROOT / workflow
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = doc["jobs"]
    if job not in jobs:
        raise SystemExit(f"job {job} no existe en {workflow} (hay: {sorted(jobs)})")
    for step in jobs[job]["steps"]:
        run = step.get("run")
        if not run or "pytest" not in run:
            continue
        tokens = run.split()
        if "pytest" not in tokens:
            continue
        return tokens[tokens.index("pytest") + 1 :]
    raise SystemExit(f"sin step de pytest en {workflow}:{job}")


def pg_ignores(targets: list[str], already: set[str]) -> list[str]:
    """Ficheros PG que CI recolecta (y salta) pero que aqui hay que ignorar explicitamente."""
    extra: list[str] = []
    for target in targets:
        base = ROOT / target
        if not base.is_dir():
            continue
        for candidate in base.rglob("test_*pg*.py"):
            rel = candidate.relative_to(ROOT).as_posix()
            if rel not in already and rel not in targets and PG_RE.search(rel):
                extra.append(rel)
    return extra


def junit_counts(report: pathlib.Path) -> dict[str, int]:
    """Conteo por resultado leido del JUnit XML (independiente del stdout, que se trunca)."""
    import xml.etree.ElementTree as ET

    if not report.exists():
        return {}
    root = ET.parse(report).getroot()
    suites = root if root.tag == "testsuites" else [root]
    out = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in out:
            out[key] += int(suite.attrib.get(key, 0))
    out["passed"] = out["tests"] - out["failures"] - out["errors"] - out["skipped"]
    report.unlink(missing_ok=True)
    return out


def junit_failures(report: pathlib.Path) -> list[str]:
    """Nombres de los tests fallidos/erroneos del JUnit XML."""
    import xml.etree.ElementTree as ET

    if not report.exists():
        return []
    root = ET.parse(report).getroot()
    suites = root if root.tag == "testsuites" else [root]
    names: list[str] = []
    for suite in suites:
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                cls = case.attrib.get("classname", "")
                names.append(f"{cls}::{case.attrib.get('name', '')}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "workflow", help="ruta relativa al repo, p. ej. .github/workflows/python-ci.yml"
    )
    parser.add_argument("job", help="id del job (p. ej. quality, python)")
    parser.add_argument(
        "--with-pg-ignores",
        action="store_true",
        help="anade a --ignore los ficheros PG que CI recolecta y aqui cuelgan",
    )
    parser.add_argument("--log", default=None, help="ruta donde guardar la salida cruda de pytest")
    args = parser.parse_args()

    tokens = load_pytest_args(args.workflow, args.job)
    ignores = [t for t in tokens if t.startswith("--ignore")]
    flags = [t for t in tokens if t.startswith("-") and not t.startswith("--ignore")]
    targets = [t for t in tokens if not t.startswith("-")]
    print(f"== {args.workflow}:{args.job}")
    print(f"   rutas objetivo: {len(targets)} | ignores del YAML: {len(ignores)} | flags: {flags}")

    missing = [t for t in targets if not (ROOT / t).exists()]
    if missing:
        print("   RUTA INEXISTENTE (pytest = exit 4):")
        for rel in missing:
            print(f"     - {rel}")
        return 4
    print("   todas las rutas existen")

    extra: list[str] = []
    if args.with_pg_ignores:
        extra = pg_ignores(targets, {i.split("=", 1)[1] for i in ignores})
        print(f"   PG movidos a --ignore ({len(extra)}): {extra}")

    report = ROOT / ".tmp_offline_ci_junit.xml"
    cmd = [
        "uv",
        "run",
        "pytest",
        *targets,
        *ignores,
        *[f"--ignore={rel}" for rel in extra],
        *flags,
        # El conftest de la app tambien habla con PG: se corre sin conftest.
        "--noconftest",
        "-q",
        "-p",
        "no:cacheprovider",
        # Bajo ``subprocess`` en Windows el stdout de pytest con ``-q`` llega truncado y la
        # linea de resumen se pierde: el conteo se mide por JUnit XML (no cambia la
        # SELECCION de tests, solo el reporte).
        f"--junitxml={report}",
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if args.log:
        pathlib.Path(args.log).write_text(out, encoding="utf-8")
    failures = junit_failures(report)
    print(f"   JUNIT: {junit_counts(report)}")
    tail = [ln for ln in out.strip().splitlines() if ln.strip()][-3:]
    print("\n".join(f"   {ln}" for ln in tail))
    print(f"   bytes={len(out)} exit={proc.returncode}")
    if proc.returncode != 0:
        for name in failures[:10]:
            print(f"   FALLO: {name}")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
