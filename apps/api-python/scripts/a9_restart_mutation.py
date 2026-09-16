"""Sonda de MUTACIÓN del invariante del restart (PG real), temporal y no commiteada.

Mide una sola cosa: si el contador del invariante del restart cuenta **filas** de
`execution_events` (comportamiento anterior a V2.40.3) en vez de **órdenes**
(`count(distinct venue_order_id)`), ¿el test se pone rojo? Es el verde falso que la fase
retiró: con F1 arreglado, las tranchas que quedaron en vuelo siguen materializándose tras
el restart y el contador viejo las leería como una re-compra.

Uso (contra la BD scratch recreada y migrada):
    uv run --no-sync python a9_restart_mutation.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]  # raíz del repo (este script vive en apps/api-python/scripts)
TEST_FILE = "apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py"
DB = os.environ.get("A9_SCRATCH_DB", "bolsa_a9v2403")

OLD = (
    "                    select(func.count(func.distinct(ExecutionEventRow.venue_order_id))).where("
)
NEW = "                    select(func.count()).where("

env = dict(os.environ)
env.update(
    {
        "DATABASE_URL": f"postgresql://bolsa:bolsa_dev@localhost:5432/{DB}",
        "DB_NAME": DB,
        "AUTO_SCHEDULER_PROCESS_PG_REQUIRED": "1",
        "AUTO_SCHEDULER_RESTART_PG_REQUIRED": "1",
        "AUTO_EQUITY_INVARIANT_PG_REQUIRED": "1",
        "JWT_SIGNING_KEY": "ci-lifecycle-pg-secret-key",
        "APP_AUTH_SECRET": "ci-lifecycle-pg-secret-key",
    }
)

TESTS = (
    "apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py"
    "::test_a9_scheduler_process_restart_with_open_protected_position_pg"
)


def run() -> tuple[int, str]:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line", "-rf"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    tail = "\n".join(line for line in out.stdout.splitlines() if line.strip())[-1500:]
    return out.returncode, tail


def main() -> None:
    path = ROOT / TEST_FILE
    original = path.read_text(encoding="utf-8")
    if OLD not in original:
        raise SystemExit("no encontré el fragmento a mutar; revisar la sonda")

    print("=== línea base (sin mutación: cuenta órdenes) ===")
    code, tail = run()
    print("exit:", code, "|", tail.splitlines()[-1] if tail else "")

    path.write_text(original.replace(OLD, NEW, 1), encoding="utf-8")
    try:
        print("\n=== mutación (cuenta filas, comportamiento anterior) ===")
        code, tail = run()
        print("exit:", code)
        print(tail)
    finally:
        subprocess.run(["git", "checkout", "--", TEST_FILE], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
