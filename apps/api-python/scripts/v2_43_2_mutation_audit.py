"""Sonda de MUTACIONES del audit-pack v2.43.2 (Hardening de contabilidad + Exit Governance).

Aplica cada una de las 13 mutaciones del §2 del relevo de cierre, corre las suites que deben morder
y **restaura desde el texto original en memoria**. El objetivo es que la matriz del §10 del pack diga
lo MEDIDO y no lo esperado: un pack que afirma "este test se pondria rojo" sin haberlo medido es humo.

Patron copiado de ``v2_40_4_mutation_audit.py`` (NO de ``a9_mutation_audit.py``): aquel restauraba con
``git checkout -- <file>``, que descarta el trabajo no commiteado del fichero (costo una reconstruccion
manual de ``auto_v2_entry.py`` en la sesion de v2.40.4). Aqui la restauracion es la copia en memoria y,
ademas, la sonda **verifica que deja el arbol exactamente como lo encontro** (huella de
``git status --porcelain`` de los ficheros tocados, antes y despues).

DSN fast-fail para las suites de ``apps/api-python``: el teardown de
``apps/api-python/tests/conftest.py`` (``purge_all_residuals``, fixture autouse de sesion) intenta
conectar a Postgres y, sin PG levantado, se queda colgado para siempre. Para las mutaciones que corren
ese directorio (M8/M9/M11/M12/M13) se inyecta un ``DATABASE_URL`` a un puerto local cerrado: el
``connect`` falla al instante y el ``except Exception`` del teardown lo traga, de modo que la sonda
devuelve los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo. El ``timeout`` se mantiene como red.

Uso: uv run --no-sync python apps/api-python/scripts/v2_43_2_mutation_audit.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- codigo de produccion mutado ---------------------------------------------------------------
LEDGER = "packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py"
ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"
MANAGER = "packages/py/application/src/bolsa_application/position_manager.py"
FRESH = "packages/py/analytics/src/bolsa_analytics/cognitive/data_freshness.py"
RESV = "packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reservation.py"
WORKER = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"

# --- suites que deben morder ---------------------------------------------------------------
T_LEDGER = "packages/py/analytics/tests/test_position_ledger.py"
T_ENTRY = "packages/py/application/tests/test_auto_v2_entry.py"
T_MANAGER = "packages/py/application/tests/test_position_manager.py"
T_KILL = "packages/py/analytics/tests/test_hard_kill_switch.py"
T_FRESH = "packages/py/analytics/tests/test_data_freshness.py"
T_RESV = "packages/py/analytics/tests/test_portfolio_reservation_ledger.py"
T_V44 = "apps/api-python/tests/test_auto_v44_exit_governance.py"

# Fragmentos multilinea (indentacion EXACTA, tal y como viven en el arbol).
M1_OLD = """        sold_qty += fact.quantity
        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            continue
        matched = min(fact.quantity, sellable)
        if avg_entry is not None:
            realized_pnl += matched * (fact.price - avg_entry)
            cost_basis -= matched * avg_entry
        if fact.quantity > matched + _QTY_EPS:
            violations.append(f"oversell_above_position:{fact.execution_id}")
        realized_qty += matched
"""
M1_NEW = """        avg_entry = (cost_basis / quantity) if quantity > _QTY_EPS else None
        sellable = quantity - realized_qty
        if sellable <= _QTY_EPS:
            violations.append(f"oversell_without_position:{fact.execution_id}")
            realized_qty += fact.quantity
            continue
        matched = min(fact.quantity, sellable)
        if avg_entry is not None:
            realized_pnl += matched * (fact.price - avg_entry)
            cost_basis -= matched * avg_entry
        if fact.quantity > matched + _QTY_EPS:
            violations.append(f"oversell_above_position:{fact.execution_id}")
        realized_qty += fact.quantity
"""

M4_OLD = """            distance = stop_distance(
                entry=float(entry), stop=float(stop), direction="long"
            )
            if distance is not None:
                risk_amount = distance * float(qty)
"""
M4_NEW = """            risk_amount = max(0.0, (float(entry) - float(stop)) * float(qty))
"""

M12_OLD = """            bucket = buys if reservation.is_buy else sells
            bucket.setdefault(reservation.instrument_id, []).append(reservation)
"""
M12_NEW = """            if reservation.is_sell:
                continue
            buys.setdefault(reservation.instrument_id, []).append(reservation)
"""

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("M1 realized_qty vuelve a inflarse (H1)", LEDGER, M1_OLD, M1_NEW, (T_LEDGER,)),
    (
        "M2 working_snapshot suma riesgo sobre base no medida (H2)",
        ENTRY,
        "    if has_committed_risk and snapshot.risk_is_complete:\n",
        "    if has_committed_risk:\n",
        (T_ENTRY,),
    ),
    (
        "M3 el rebuild re-deriva la medicion (H2)",
        ENTRY,
        "        risk_measurement=snapshot.risk_measurement,\n",
        "        risk_measurement=None,\n",
        (T_ENTRY,),
    ),
    ("M4 stop del lado equivocado vuelve a publicar 0.0 (H3)", ENTRY, M4_OLD, M4_NEW, (T_ENTRY,)),
    (
        "M5 sin dedupe por execution_id (H4)",
        LEDGER,
        "        if key in seen:\n",
        "        if False:\n",
        (T_LEDGER,),
    ),
    (
        "M6 el fold funde cuentas (H5)",
        LEDGER,
        "        grouped.setdefault((fact.account_id, fact.instrument_id), []).append(fact)\n",
        '        grouped.setdefault(("", fact.instrument_id), []).append(fact)\n',
        (T_LEDGER,),
    ),
    (
        "M7 un hecho sin fecha se ordena primero (H6)",
        LEDGER,
        "        0 if fact.applied_at else 1,\n",
        "        0,\n",
        (T_LEDGER,),
    ),
    (
        "M8 la parada dura no evalua la tabla con el gobernador OFF",
        ENTRY,
        "        if cfg.governor_enabled or halted:\n",
        "        if cfg.governor_enabled:\n",
        (T_V44,),
    ),
    (
        "M9 halted nunca llega a la tabla",
        ENTRY,
        "                halted=halted,\n",
        "                halted=False,\n",
        (T_V44,),
    ),
    (
        "M10 sin reafirmacion defensiva de venta total",
        MANAGER,
        "    if halted or regime_exit or risk_off:\n",
        "    if regime_exit:\n",
        (T_MANAGER,),
    ),
    (
        "M11 blocks_new_entry siempre False",
        FRESH,
        "        return reading is None or reading.status != FRESHNESS_FRESH\n",
        "        return False\n",
        (T_FRESH, T_V44),
    ),
    ("M12 committed_positions ignora las reservas sell (F9)", RESV, M12_OLD, M12_NEW, (T_RESV, T_V44)),
    (
        "M13 la reconciliacion casa por instrumento y no por lado (F9)",
        WORKER,
        "            applied.setdefault((fact.instrument_id, fact.side), []).append(\n",
        '            applied.setdefault((fact.instrument_id, "buy"), []).append(\n',
        (T_V44,),
    ),
]

# DSN a un puerto local cerrado: el connect falla al instante (en vez de colgar el teardown de PG).
FAST_FAIL_DSN = "postgresql+psycopg://bolsa:bolsa@127.0.0.1:9/bolsa_v1"


def _run(tests: tuple[str, ...]) -> set[str]:
    """Corre las suites y devuelve los nombres de test que se pusieron rojos.

    Con ``timeout`` a proposito: `apps/api-python/tests/conftest.py` purga residuos contra Postgres al
    cerrar la sesion SIN timeout, asi que sin PG levantado un run de esa carpeta se queda colgado
    eternamente despues de pasar los tests. Un auditor sin la base arrancada debe ver "TIMEOUT", no
    una sonda muda para siempre.

    Para las suites de ``apps/api-python`` se fuerza ademas un ``DATABASE_URL`` a un puerto cerrado:
    ``conftest._load_root_env`` usa ``override=False``, asi que el valor inyectado gana al ``.env`` y
    el teardown falla rapido (tragado por su ``except``) en lugar de colgarse.
    """
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
    """Huella del estado de git SOLO de los ficheros tocados (no del resto del arbol)."""
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
