"""Sonda de MUTACIONES del audit-pack v2.40.4 (AUTO Safety & Accounting).

Aplica cada mutación sobre el código real, corre las suites que deben morder y **restaura desde
el texto original en memoria**. El objetivo es que la matriz de mutaciones del audit-pack diga lo
MEDIDO y no lo esperado: un pack que afirma "este test se pondría rojo" sin haberlo medido es humo.

Diferencia deliberada con `a9_mutation_audit.py` (v2.40.3): aquel restauraba con
`git checkout -- <file>`, que **descarta el trabajo no commiteado** del fichero. Eso costó una
reconstrucción manual de `auto_v2_entry.py` durante la sesión de v2.40.4. Aquí la restauración es
la copia en memoria y, además, la sonda **verifica que deja el árbol exactamente como lo encontró**
(huella de `git status --porcelain` de los ficheros tocados, antes y después).

Uso: uv run --no-sync python apps/api-python/scripts/v2_40_4_mutation_audit.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"
ENGINE = "packages/py/application/src/bolsa_application/portfolio_decision_engine.py"

T_ENTRY = "packages/py/application/tests/test_auto_v2_entry.py"
T_ORCH = "packages/py/application/tests/test_auto_investment_system.py"
T_ENGINE = "packages/py/application/tests/test_portfolio_decision_engine.py"
T_WORKER = "apps/api-python/tests/test_auto_v2_worker_integration.py"

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "M1 quitar la rama top_n_excluded de plan_v2_tick",
        ENTRY,
        "    excluded: list[DecisionJournalEntryRecord] = [\n",
        "    excluded: list[DecisionJournalEntryRecord] = []\n"
        "    _dead_excluded: list[DecisionJournalEntryRecord] = [\n",
        (T_ENTRY, T_ORCH),
    ),
    (
        "M2 volver buying_power a cash bruto (reserved_cash=None en el allocator)",
        ENGINE,
        "        reserved_cash=(snapshot.reserved_cash if snapshot is not None else None),\n",
        "        reserved_cash=None,\n",
        (T_ENGINE, T_WORKER),
    ),
    (
        "M3 desactivar los escalones de measurement",
        ENGINE,
        "    if cfg.require_complete_measurement and snapshot is not None:\n",
        "    if False and cfg.require_complete_measurement and snapshot is not None:\n",
        (T_ENGINE, T_WORKER, T_ENTRY),
    ),
    (
        "M4 saltarse validate_trade_plan en decide_portfolio",
        ENGINE,
        "    plan_violations = validate_trade_plan(plan)\n",
        "    plan_violations = ()\n",
        (T_ENGINE,),
    ),
]


def _run(tests: tuple[str, ...]) -> set[str]:
    """Corre las suites y devuelve los nombres de test que se pusieron rojos.

    Con ``timeout`` a proposito: `apps/api-python/tests/conftest.py` purga residuos contra Postgres al
    cerrar la sesion SIN timeout, asi que sin PG levantado un run de esa carpeta se queda colgado
    eternamente despues de pasar los tests. Un auditor sin la base arrancada debe ver "TIMEOUT", no
    una sonda muda para siempre.
    """
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no", "-rf"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"<TIMEOUT 600s: revisar Postgres del teardown de apps/api-python/tests/conftest.py>"}
    failed: set[str] = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            node = line[len("FAILED ") :].split(" ")[0]
            failed.add(node.split("::")[-1].split("[")[0])
    if out.returncode != 0 and not failed:
        failed.add("<fallo sin detalle, revisar a mano>")
    return failed


def _status(files: tuple[str, ...]) -> str:
    """Huella del estado de git SOLO de los ficheros tocados (no del resto del árbol)."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", *files],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return out.stdout


def main() -> int:
    files = tuple(sorted({rel for _, rel, _, _, _ in MUTATIONS}))
    originals = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in files}
    status_before = _status(files)

    print("=== ficheros mutados ===")
    for rel in files:
        print(f"  {rel}")
    print("estado git de esos ficheros (antes):", status_before.strip() or "limpio")

    print("\n=== línea base (sin mutación) ===")
    for tests in sorted({m[4] for m in MUTATIONS}, key=lambda t: t):
        print(f"  {', '.join(tests)} ->", sorted(_run(tests)) or "ninguno")

    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        current = path.read_text(encoding="utf-8")
        if current != originals[rel]:
            print(f"\n### {label}\n  !! {rel} cambió desde el inicio de la sonda; ABORTO por seguridad")
            return 1
        if old not in current:
            print(f"\n### {label}\n  !! no encontré el fragmento a mutar en {rel}; revisar la sonda")
            continue
        path.write_text(current.replace(old, new, 1), encoding="utf-8")
        try:
            failed = _run(tests)
        finally:
            path.write_text(originals[rel], encoding="utf-8")
        restored = path.read_text(encoding="utf-8") == originals[rel]
        print(f"\n### {label}")
        print("  rojo en:", ", ".join(sorted(failed)) or "NADA (la mutación NO se detecta)")
        print("  restaurado byte a byte:", "sí" if restored else "NO !! revisar a mano")

    status_after = _status(files)
    print("\n=== huella del árbol ===")
    print("estado git de esos ficheros (después):", status_after.strip() or "limpio")
    if status_after != status_before:
        print("  !! la sonda dejó los ficheros en un estado distinto al inicial")
        return 1
    print("  intacto: la sonda no alteró el árbol")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
