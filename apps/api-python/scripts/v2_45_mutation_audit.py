"""Sonda de MUTACIONES del invariante de AUTO-5 v2.45 (Golden Day 2.0).

Aplica cada mutación del plan de fase, corre las suites que DEBEN morder y **restaura desde
el texto original en memoria**. El objetivo es que la matriz del audit-pack afirme lo MEDIDO
y no lo esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_44_mutation_audit.py`` (y de ``v2_43_3``/``v2_43_2``/``v2_40_4``):
NUNCA ``git checkout -- <file>`` (descartaría trabajo no commiteado). La restauración es la
copia en memoria y, además, la sonda **verifica que deja el árbol exactamente como lo
encontró** (huella ``git status --porcelain`` de los ficheros tocados, antes y después).

El invariante nuevo (el embudo del día, su atribución y su disciplina de medición) tiene ocho
formas de romperse en silencio:

* **M1 (motivo tipificado)** — si una rechazada sin motivo deja de declararse, el embudo cierra
  con una decisión EN SILENCIO.
* **M2 (estado no catalogado)** — si un estado fuera del vocabulario no se declara, la
  oportunidad desaparece del embudo sin dejar rastro.
* **M3 (visto de más)** — si el ``seen`` del productor no cuadra con las filas y no se declara,
  faltan oportunidades por explicar y el día se da por bueno.
* **M4 (coste declarado)** — si un coste de oportunidad no medible se publica como ``0`` medido,
  se lee como "coste cero" (una afirmación falsa).
* **M5 (MAE/MFE declarado)** — si una operación con una pata ausente se da por completa, el
  agregado miente sobre la calidad de la medición.
* **M6 (atribución por estrategia)** — si las salidas dejan de atribuirse, el día pierde el
  vínculo operación→estrategia (y no lo declara).
* **M7 (identidad aditiva)** — si el journal V2 omite ``strategyVersion``, la identidad deja de
  viajar en el ``payload`` JSONB (sin migración no hay otra fuente).
* **M8 (fuente ``auto-2.0``)** — si el worker deja de leer la versión de la propuesta V2, el
  fill/cierre del camino V2 queda con versión NULL.

DSN fast-fail para las suites de ``apps/api-python``: el teardown del conftest intenta conectar
a Postgres y, sin PG levantado, se queda colgado. Se inyecta un ``DATABASE_URL`` a un puerto
local cerrado: el ``connect`` falla al instante y el ``except`` del teardown lo traga, de modo
que la sonda devuelve los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo.

Uso: uv run --no-sync python apps/api-python/scripts/v2_45_mutation_audit.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- código de producción mutado ----------------------------------------------------------------
JOURNAL = "packages/py/application/src/bolsa_application/auto_daily_journal.py"
ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"
WORKER = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"

# --- suites que deben morder ----------------------------------------------------------------
T_JOURNAL = "packages/py/application/tests/test_auto_daily_journal.py"
T_GOLDEN = "apps/api-python/tests/test_auto_v2_golden_day_evidence.py"
T_WORKER = "apps/api-python/tests/test_auto_simulation_worker.py"

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "M1 (motivo tipificado): una rechazada sin motivo deja de declararse",
        JOURNAL,
        "        if status != OPPORTUNITY_TRADED and not reason:\n"
        '            errors.append("rejection_without_reason")\n',
        '        if False:\n            errors.append("rejection_without_reason")\n',
        (T_JOURNAL,),
    ),
    (
        "M2 (estado no catalogado): el estado desconocido deja de declararse",
        JOURNAL,
        '            errors.append("opportunity_status_unknown")\n            continue\n',
        "            continue\n",
        (T_JOURNAL,),
    ),
    (
        "M3 (visto de mas): el seen del productor que no cuadra deja de declararse",
        JOURNAL,
        '        errors.append("funnel_seen_mismatch")\n',
        "        pass  # MUTATION: el visto de mas no se declara\n",
        (T_JOURNAL,),
    ),
    (
        "M4 (coste declarado): un coste no medible se publica como 0 medido",
        JOURNAL,
        "        if ref is None or sub is None or Decimal(str(ref)) == 0:\n"
        "            notes = (OPPORTUNITY_COST_UNMEASURED,)\n"
        "        else:\n",
        "        if ref is None or sub is None or Decimal(str(ref)) == 0:\n"
        '            missed_return = Decimal("0")\n'
        "            measurement = MEASUREMENT_COMPLETE\n"
        "            measured += 1\n"
        "        else:\n",
        (T_JOURNAL, T_GOLDEN),
    ),
    (
        "M5 (MAE/MFE declarado): una pata ausente se da por completa",
        JOURNAL,
        "    complete = sum(1 for m in measurements if m.mfe is not None and m.mae is not None)\n",
        "    complete = len(measurements)\n",
        (T_JOURNAL, T_GOLDEN),
    ),
    (
        "M6 (atribucion por estrategia): las salidas dejan de atribuirse",
        JOURNAL,
        '            version = str(r.strategy_version or "").strip()\n'
        "            if version:\n"
        "                strategy_exit_counts[version] = strategy_exit_counts.get(version, 0) + 1\n",
        '            version = str(r.strategy_version or "").strip()\n'
        "            if False:\n"
        "                strategy_exit_counts[version] = strategy_exit_counts.get(version, 0) + 1\n",
        (T_JOURNAL, T_GOLDEN),
    ),
    (
        "M7 (identidad aditiva): el journal V2 omite strategyVersion",
        ENTRY,
        '    if str(strategy_version or "").strip():\n'
        '        payload["strategyVersion"] = str(strategy_version)\n'
        "    # V2.43/AUTO-3 — las TRES dimensiones del gobernador en TODA decisión no-trade\n",
        "    if False:\n"
        '        payload["strategyVersion"] = str(strategy_version)\n'
        "    # V2.43/AUTO-3 — las TRES dimensiones del gobernador en TODA decisión no-trade\n",
        (T_GOLDEN,),
    ),
    (
        "M8 (fuente auto-2.0): la propuesta V2 deja de atribuir version",
        WORKER,
        "    for prefix in (_ACTIVE_STRATEGY_SOURCE_PREFIX, _V2_ENTRY_SOURCE_PREFIX):\n",
        "    for prefix in (_ACTIVE_STRATEGY_SOURCE_PREFIX,):\n",
        (T_WORKER,),
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
            timeout=900,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "<TIMEOUT 900s: revisar Postgres del teardown de apps/api-python/tests/conftest.py>"
        }
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
            print(
                f"\n### {label}\n  !! {rel} cambio desde el inicio de la sonda; ABORTO por seguridad"
            )
            return 1
        hits = current.count(old)
        if hits == 0:
            print(
                f"\n### {label}\n  !! no encontre el fragmento a mutar en {rel}; revisar la sonda"
            )
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
