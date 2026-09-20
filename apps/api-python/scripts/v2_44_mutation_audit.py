"""Sonda de MUTACIONES del invariante de AUTO-4 v2.44 (el ranking deja de ser la decisión).

Aplica cada mutación del plan de fase, corre las suites que DEBEN morder y **restaura desde el
texto original en memoria**. El objetivo es que la matriz del audit-pack afirme lo MEDIDO y no lo
esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_43_3_mutation_audit.py`` (y de ``v2_43_2``/``v2_40_4``): NUNCA
``git checkout -- <file>`` (descartaría trabajo no commiteado). La restauración es la copia en
memoria y, además, la sonda **verifica que deja el árbol exactamente como lo encontró** (huella
``git status --porcelain`` de los ficheros tocados, antes y después).

El invariante nuevo tiene siete formas de romperse en silencio, una por mutación:

* **M1 (objetivo)** — si el desempate deja de comparar, gana la PRIMERA combinación factible (un
  greedy disfrazado) y la cartera deja de maximizar valor esperado.
* **M2 (vacío compite)** — si las combinaciones no positivas dejan de descartarse, el optimizador
  siempre encuentra "algo que comprar" y la opción de no operar desaparece.
* **M3 (tope)** — si el tope de combinatoria se ignora, la enumeración corre igual: un espacio
  grande bloquea el tick en vez de ceder el paso al ranking.
* **M4 (EV no medido)** — si una candidata sin economía medible entra con valor ``0``, se cuela como
  "la peor de las medidas" y puede ganar la combinación por desempate.
* **M5 (correlación)** — si una correlación DESCONOCIDA deja de ser infeasible, el gate de
  correlación se convierte en fail-open.
* **M6 (motivo honesto)** — si el journal declara ``edge_below_threshold`` para una candidata que
  solo fue no seleccionada, el operador lee un motivo FALSO.
* **M7 (flag)** — si el flag ON deja de gobernar, con ON el tick vuelve al ranking sin decirlo.

DSN fast-fail para las suites de ``apps/api-python``: el teardown de
``apps/api-python/tests/conftest.py`` (``purge_all_residuals``) intenta conectar a Postgres y,
sin PG levantado, se queda colgado. Se inyecta un ``DATABASE_URL`` a un puerto local cerrado: el
``connect`` falla al instante y el ``except`` del teardown lo traga, de modo que la sonda devuelve
los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo.

Uso: uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- código de producción mutado ----------------------------------------------------------------
OPTIMIZER = "packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py"
ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"

# --- suites que deben morder ----------------------------------------------------------------
T_OPT = "packages/py/analytics/tests/test_portfolio_optimizer.py"
T_WIRE = "packages/py/application/tests/test_auto_v4_optimizer_wiring.py"
T_WORKER = (
    "apps/api-python/tests/test_auto_v2_worker_integration.py"
    "::test_v2_optimizer_on_without_an_economic_producer_is_fail_closed"
)

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "M1 (objetivo): el desempate deja de comparar ⇒ gana la primera factible",
        OPTIMIZER,
        "    if candidate.value != current.value:\n        return candidate.value > current.value\n",
        "    return False\n",
        (T_OPT, T_WIRE),
    ),
    (
        "M2 (vacio): las combinaciones no positivas dejan de descartarse",
        OPTIMIZER,
        "        if item.value <= 0.0:\n            continue\n",
        "        if False:\n            continue\n",
        (T_OPT,),
    ),
    (
        "M3 (tope): el tope de combinatoria se ignora",
        OPTIMIZER,
        "    if total_subsets > cap:\n",
        "    if False:\n",
        (T_OPT,),
    ),
    (
        "M4 (EV no medido): la candidata sin economia entra y se suma como 0.0",
        OPTIMIZER,
        "            rejected[instrument_id] = OPTIMIZER_EXPECTED_VALUE_UNMEASURED\n"
        "            continue\n",
        "            pass\n",
        (T_OPT,),
    ),
    (
        "M5 (correlacion): una correlacion DESCONOCIDA deja de ser infeasible",
        OPTIMIZER,
        "        if correlation is None:\n            return OPTIMIZER_CORRELATION_UNKNOWN\n",
        "        if correlation is None:\n            return None\n",
        (T_OPT,),
    ),
    (
        "M6 (motivo honesto): el journal miente con edge_below_threshold",
        ENTRY,
        "                    reason_by_id.get(signal.instrument_id, OPTIMIZER_NOT_SELECTED),\n",
        '                    "edge_below_threshold",\n',
        (T_WIRE,),
    ),
    (
        "M7 (flag): con ON el tick vuelve al ranking sin declararlo",
        ENTRY,
        "    if cfg.optimizer_enabled and ordered:\n",
        "    if False and ordered:\n",
        (T_WIRE, T_WORKER),
    ),
]

# DSN a un puerto local cerrado: el connect falla al instante (en vez de colgar el teardown de PG).
FAST_FAIL_DSN = "postgresql+psycopg://bolsa:bolsa@127.0.0.1:9/bolsa_v1"


def _run(tests: tuple[str, ...]) -> set[str]:
    """Corre las suites y devuelve los nombres de test que se pusieron rojos."""
    env = dict(os.environ)
    if any(t.startswith("apps/api-python") for t in tests):
        env["DATABASE_URL"] = FAST_FAIL_DSN
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no", "-rf"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
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

    print("\n=== linea base (sin mutacion) ===")
    for tests in sorted({m[4] for m in MUTATIONS}, key=lambda t: t):
        print(f"  {', '.join(tests)} ->", sorted(_run(tests)) or "ninguno")

    for label, rel, old, new, tests in MUTATIONS:
        path = ROOT / rel
        current = path.read_text(encoding="utf-8")
        if current != originals[rel]:
            print(f"\n### {label}\n  !! {rel} cambio desde el inicio de la sonda; ABORTO por seguridad")
            return 1
        hits = current.count(old)
        if hits == 0:
            print(f"\n### {label}\n  !! no encontre el fragmento a mutar en {rel}; revisar la sonda")
            continue
        if hits > 1:
            print(
                f"\n### {label}\n  !! el fragmento aparece {hits} veces en {rel}: el "
                f"`.replace(..., 1)` mutaria la PRIMERA y la sonda mentiria. ABORTO."
            )
            return 1
        path.write_text(current.replace(old, new, 1), encoding="utf-8")
        try:
            failed = _run(tests)
        finally:
            path.write_text(originals[rel], encoding="utf-8")
        restored = path.read_text(encoding="utf-8") == originals[rel]
        print(f"\n### {label}")
        print("  rojo en:", ", ".join(sorted(failed)) or "NADA (la mutacion NO se detecta)")
        print("  restaurado byte a byte:", "si" if restored else "NO !! revisar a mano")

    status_after = _status(files)
    print("\n=== huella del arbol ===")
    print("estado git de esos ficheros (despues):", status_after.strip() or "limpio")
    if status_after != status_before:
        print("  !! la sonda dejo los ficheros en un estado distinto al inicial")
        return 1
    print("  intacto: la sonda no altero el arbol")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
