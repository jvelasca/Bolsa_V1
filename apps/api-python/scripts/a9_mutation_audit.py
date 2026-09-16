"""Sonda de MUTACIONES del audit-pack v2.40.3 (temporal, no se commitea).

Aplica cada mutación sobre el código real, corre el test hermético de claves y restaura con
`git checkout --`. El objetivo es que la tabla §5 del audit-pack diga lo MEDIDO y no lo
esperado: un pack que afirma "este test se pondría rojo" sin haberlo medido es humo.

Uso: uv run --no-sync python a9_mutation_audit.py
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]  # raíz del repo (este script vive en apps/api-python/scripts)
SIM = "packages/py/application/src/bolsa_application/simulated_settlement.py"
REC = "packages/py/application/src/bolsa_application/recovery_apply.py"
KEY = "packages/py/application/src/bolsa_application/idempotency_key.py"
TEST = "packages/py/application/tests/test_idempotency_key_budget.py"

LEGACY_SIM = """    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip()).strip("-") or "unknown"
    return f"sim-fin-{slug[:120]}"[-128:]"""
LEGACY_REC = """    slug = re.sub(r"[^A-Za-z0-9_]", "-", (execution_id or "").strip()).strip("-") or "unknown"
    return f"recovery-fin-{slug[:100]}"[-128:]"""

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 revertir SIM a slug[:120] (recorte histórico)",
        SIM,
        '    return bounded_idempotency_key("sim-fin-", execution_id, legacy_budget=120)',
        LEGACY_SIM,
    ),
    (
        "M2 revertir recovery a slug[:100] (recorte histórico)",
        REC,
        '    return bounded_idempotency_key("recovery-fin-", execution_id, legacy_budget=100)',
        LEGACY_REC,
    ),
    (
        "M3 rama larga sin digest (recorte duro, sin discriminador de cola)",
        KEY,
        '        digest = sha256(raw.encode("utf-8")).hexdigest()[:_DIGEST_HEX]\n        key = f"{prefix}{slug[:head]}{_MARK}{digest}"',
        '        key = f"{prefix}{slug[:head]}"[:IDEMPOTENCY_KEY_MAX_LEN]',
    ),
    (
        "M4 marcador que SÍ puede existir en un slug ('-')",
        KEY,
        '_MARK = "~"',
        '_MARK = "-"',
    ),
    (
        "M5 quitar el relleno del mínimo de 16",
        KEY,
        "    if len(key) < IDEMPOTENCY_KEY_MIN_LEN:\n        # Slug degenerado (p.ej. ``unknown``): el contrato exige 16. Se rellena con la\n        # MISMA marca (imposible en un slug) ⇒ tampoco colisiona con el camino normal.\n        key = key.ljust(IDEMPOTENCY_KEY_MIN_LEN, _MARK)",
        "    pass",
    ),
    (
        "M6 el digest no discrimina el fill_seq (digest del venue_order_id, sin la cola)",
        KEY,
        '        digest = sha256(raw.encode("utf-8")).hexdigest()[:_DIGEST_HEX]',
        '        digest = sha256(raw.split("#")[0].encode("utf-8")).hexdigest()[:_DIGEST_HEX]',
    ),
]


def _run() -> set[str]:
    out = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--tb=no", "-rf"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    failed: set[str] = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            node = line[len("FAILED ") :].split(" ")[0]
            failed.add(node.split("::")[-1].split("[")[0])
    if out.returncode != 0 and not failed:
        failed.add("<fallo sin detalle, revisar a mano>")
    return failed


def main() -> None:
    print("=== línea base (sin mutación) ===")
    print("fallos:", sorted(_run()) or "ninguno")
    for label, rel, old, new in MUTATIONS:
        path = ROOT / rel
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(
                f"\n### {label}\n  !! no encontré el fragmento a mutar en {rel}; revisar la sonda"
            )
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            failed = _run()
        finally:
            subprocess.run(["git", "checkout", "--", rel], cwd=ROOT, check=True)
        print(f"\n### {label}")
        print("  rojo en:", ", ".join(sorted(failed)) or "NADA (la mutación NO se detecta)")


if __name__ == "__main__":
    main()
