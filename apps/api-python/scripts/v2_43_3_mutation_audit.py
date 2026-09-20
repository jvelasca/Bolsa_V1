"""Sonda de MUTACIONES del cierre AUTO-3 v2.43.3 (kill durable, identidad de salida, orden UTC).

Aplica cada mutación del plan de cierre, corre las suites que DEBEN morder y **restaura desde
el texto original en memoria**. El objetivo es que la matriz de mutaciones afirme lo MEDIDO y no
lo esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_43_2_mutation_audit.py`` (y de ``v2_40_4_mutation_audit.py``): NUNCA
``git checkout -- <file>`` (descartaría trabajo no commiteado). La restauración es la copia en
memoria y, además, la sonda **verifica que deja el árbol exactamente como lo encontró** (huella
``git status --porcelain`` de los ficheros tocados, antes y después).

Las cuatro ventanas que cierra esta versión:

* **P0-1 (kill durable)** — si ``_v2_load_kill_state`` no restaura un HALT persistido, un
  reinicio reabre el motor: M1 debe poner rojo el caso de reinicio con parada durable. Si la
  liberación se concede sin ``reconciliation_id``, el levantamiento deja de ser auditable: M2.
* **P0-2 (identidad de salida)** — si la reconciliación no casa el INTENT con su reserva (M3) o
  el camino caliente no aplica el fill al INTENT (M4), la identidad durable queda decorativa.
* **P1-4 (política B)** — si el intent de emergencia no se persiste ni se para el sistema, la
  salida se emite sin rastro: M5.
* **P1-5 (orden temporal UTC)** — si el fold vuelve a ordenar por cadena ISO (M6), dos hechos
  con offsets distintos se ordenan por texto y no por instante.

DSN fast-fail para las suites de ``apps/api-python``: el teardown de
``apps/api-python/tests/conftest.py`` (``purge_all_residuals``) intenta conectar a Postgres y,
sin PG levantado, se queda colgado. Se inyecta un ``DATABASE_URL`` a un puerto local cerrado: el
``connect`` falla al instante y el ``except`` del teardown lo traga, de modo que la sonda devuelve
los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo.

Uso: uv run --no-sync python apps/api-python/scripts/v2_43_3_mutation_audit.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- código de producción mutado ----------------------------------------------------------------
LEDGER = "packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py"
WORKER = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"

# --- suites que deben morder ----------------------------------------------------------------
T_LEDGER = "packages/py/analytics/tests/test_position_ledger.py"
T_CRASH = "apps/api-python/tests/test_auto_v44_exit_crash_matrix.py"

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "M1 P0-1: el arranque NO restaura el HALT persistido",
        WORKER,
        "        if state is None or not state.engaged or self._v2_kill_switch.engaged:\n"
        "            return\n",
        "        if True:\n"
        "            return\n",
        (T_CRASH,),
    ),
    (
        "M2 P0-1: liberar la parada sin reconciliation_id",
        WORKER,
        "        if reconciliation_ok and not reconciliation_id:\n",
        "        if False:\n",
        (T_CRASH,),
    ),
    (
        "M3 P0-2: la reconciliación no casa el INTENT con su reserva",
        WORKER,
        '            filled, released = outcomes.get(order.reservation_id or "", (0.0, None))\n',
        "            filled, released = 0.0, None\n",
        (T_CRASH,),
    ),
    (
        "M4 P0-2: el fill no localiza el INTENT de salida",
        WORKER,
        "        await self._v2_apply_exit_fill(exit_order_id, qty, at=at)\n",
        "        await self._v2_apply_exit_fill(None, qty, at=at)\n",
        (T_CRASH,),
    ),
    (
        "M5 P1-4: sin intent de emergencia y sin parada (fail-open)",
        WORKER,
        "            if not await self._v2_save_exit_order(emergency):\n",
        "            if False:\n",
        (T_CRASH,),
    ),
    (
        "M6 P1-5: el fold vuelve a ordenar por cadena ISO",
        LEDGER,
        "    instant = _applied_instant(fact.applied_at)\n"
        "    if instant is None:\n"
        '        return (1, 0.0, str(fact.execution_id or ""))\n'
        '    return (0, instant, str(fact.execution_id or ""))\n',
        '    text = str(fact.applied_at or "")\n'
        "    if not text:\n"
        '        return (1, 0.0, str(fact.execution_id or ""))\n'
        '    return (0, 0.0, text)\n',
        (T_LEDGER,),
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
