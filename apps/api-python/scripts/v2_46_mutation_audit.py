"""Sonda de MUTACIONES del invariante de AUTO-6 v2.46 (Crash/Recovery + Concurrent).

Aplica cada mutación del plan de fase, corre las suites que DEBEN morder y **restaura desde
el texto original en memoria**. El objetivo es que la matriz del audit-pack afirme lo MEDIDO
y no lo esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_45_mutation_audit.py`` (y de ``v2_44``/``v2_43_3``/``v2_43_2``/
``v2_40_4``): NUNCA ``git checkout -- <file>`` (descartaría trabajo no commiteado). La
restauración es la copia en memoria y, además, la sonda **verifica que deja el árbol
exactamente como lo encontró** (huella ``git status --porcelain`` de los ficheros tocados,
antes y después).

AUTO-6 no añade producto: instala un invariante de *recuperación y exclusión mutua* sobre las
costuras que ya existían. Sus seis formas de romperse en silencio:

* **M1 (dedupe de señal consumida)** — si la señal ya consumida deja de filtrarse, la MISMA
  barra re-abre la oportunidad tomada (doble BUY en el siguiente tick).
* **M2 (liberación de reserva por fill)** — si el fill materializado deja de liberar el
  compromiso, el capital sigue retenido tras el cierre (sobre-compromiso permanente).
* **M3 (gate de reconciliación)** — si una proyección divergente deja de vetar aperturas, el
  trabajador abre sobre un estado del que no puede fiarse.
* **M4 (idempotencia de execution_events)** — si un evento ya ``APPLIED`` deja de atajarse, el
  reclaim/replay vuelve a tocar dinero.
* **M5 (claim atómico: identidad determinista)** — si la identidad de la decisión de entrada
  deja de derivarse de ``(cuenta, señal)``, dos workers apilan dos compromisos sobre la misma
  oportunidad (carrera leer-presupuesto → reservar).
* **M6 (claim atómico: el perdedor NO emite)** — si el perdedor del claim ignora
  ``inserted=False``, emite igualmente su orden: 1 señal ⇒ 2 órdenes.

Postgres para las suites de ``apps/api-python``: se **sondea el puerto** antes de decidir. Con
PG viva (estación de trabajo) se corre contra ella, que es lo que mide de verdad. Sin PG se
inyecta un ``DATABASE_URL`` a un puerto local cerrado —el ``connect`` falla al instante y el
``except`` del teardown del conftest lo traga— de modo que la sonda devuelve los rojos con
NOMBRE en vez de un ``TIMEOUT`` mudo. (Ojo: en Windows no todo puerto cerrado rechaza rápido;
por eso el sondeo manda, en vez de asumir.)

Uso: uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py

La sonda lee/escribe el contenido RAW (los ficheros del árbol están en CRLF) y su verificación
final es un sha256 del raw: antes == después. Además aborta si encuentra el marcador
``# MUTATION:`` al arrancar, señal de que una ejecución anterior murió a mitad de mutación.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- código de producción mutado ----------------------------------------------------------------
ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"
WORKER = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"
EVENTS = "packages/py/application/src/bolsa_application/execution_event.py"

# --- suites que deben morder ----------------------------------------------------------------
T_ENTRY = "packages/py/application/tests/test_auto_v2_entry.py"
T_EXEC_EVENT = "packages/py/application/tests/test_execution_event.py"
T_PARTIAL_FILLS = "apps/api-python/tests/test_auto_v2_partial_fills.py"
T_V46_CRASH = "apps/api-python/tests/test_auto_v46_crash_recovery.py"
T_V46_CONCURRENT = "apps/api-python/tests/test_auto_v46_concurrent.py"

# (etiqueta, fichero, fragmento original, fragmento mutado, ficheros de test a correr)
MUTATIONS: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "M1 (dedupe de senal consumida): la senal ya tomada deja de filtrarse",
        ENTRY,
        "    consumed = {str(x).strip() for x in consumed_signal_ids if str(x).strip()}\n",
        "    consumed = set()  # MUTATION: la senal consumida deja de filtrar\n",
        (T_ENTRY, T_V46_CRASH),
    ),
    (
        "M2 (liberacion de reserva por fill): el fill deja de liberar el compromiso",
        WORKER,
        "            fill_qty = min(available, reservation.remaining_qty)\n"
        "            released: PortfolioReservation | None = None\n"
        "            if fill_qty > 0:\n",
        "            fill_qty = min(available, reservation.remaining_qty)\n"
        "            released: PortfolioReservation | None = None\n"
        "            if False:  # MUTATION: el fill no libera la reserva\n",
        (T_V46_CRASH, T_V46_CONCURRENT),
    ),
    (
        "M3 (gate de reconciliacion): lo divergente deja de vetar aperturas",
        WORKER,
        "        return self._reconciliation.get(symbol) in {\n"
        "            POSITION_PROJECTION_DIVERGENT,\n"
        "            POSITION_PROJECTION_UNKNOWN,\n"
        "        }\n",
        "        return False  # MUTATION: lo divergente no veta\n",
        (T_PARTIAL_FILLS,),
    ),
    (
        "M4 (idempotencia de execution_events): el APPLIED deja de atajarse",
        EVENTS,
        '    if row.status == "APPLIED":\n        return "already_applied"\n',
        '    if False:  # MUTATION: el APPLIED no se ataja\n        return "already_applied"\n',
        (T_EXEC_EVENT,),
    ),
    (
        "M5 (claim atomico I): la decision de entrada deja de ser determinista",
        ENTRY,
        "    return f\"dec-{sha256(key.encode('utf-8')).hexdigest()[:12]}\"\n",
        "    from uuid import uuid4\n\n"
        "    return f\"dec-{uuid4().hex[:12]}\"  # MUTATION: identidad aleatoria\n",
        (T_V46_CONCURRENT,),
    ),
    (
        "M6 (claim atomico II): el perdedor del claim emite igualmente",
        WORKER,
        "            if not claimed_ok:\n",
        "            if False:  # MUTATION: el perdedor del claim emite\n",
        (T_V46_CONCURRENT,),
    ),
]

# DSN a un puerto local cerrado: el connect falla al instante (en vez de colgar el teardown de PG).
FAST_FAIL_DSN = "postgresql+psycopg://bolsa:bolsa@127.0.0.1:9/bolsa_v1"

# DSN compuesto por defecto (mismos defaults que docker-compose.yml) cuando el entorno no trae
# DATABASE_URL: se sondea el puerto para saber si hay PG viva.
DEFAULT_PG_HOST = "localhost"
DEFAULT_PG_PORT = 5432

RUN_TIMEOUT_S = 300


def _host_port(dsn: str) -> tuple[str, int] | None:
    """Extrae ``(host, puerto)`` de un DSN SQLAlchemy; ``None`` si no se puede leer."""
    rest = dsn.split("://", 1)[-1]
    authority = rest.split("@")[-1].split("/")[0]
    if ":" not in authority:
        return None
    host, port = authority.rsplit(":", 1)
    try:
        return host or DEFAULT_PG_HOST, int(port)
    except ValueError:
        return None


def _pg_reachable() -> bool:
    """¿Hay PG viva donde el entorno apunta (o en el default de docker-compose)?"""
    import socket

    candidates: list[tuple[str, int]] = []
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn:
        parsed = _host_port(dsn)
        if parsed is not None:
            candidates.append(parsed)
    candidates.append((DEFAULT_PG_HOST, DEFAULT_PG_PORT))
    for host, port in candidates:
        try:
            with socket.create_connection((host, port), timeout=0.75):
                return True
        except OSError:
            continue
    return False


def _run(tests: tuple[str, ...]) -> set[str]:
    """Corre las suites y devuelve los nombres de test que se pusieron rojos."""
    env = dict(os.environ)
    if any(t.startswith("apps/api-python") for t in tests) and not _pg_reachable():
        env["DATABASE_URL"] = FAST_FAIL_DSN
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no", "-rf", "-p", "no:randomly"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_S,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            f"<TIMEOUT {RUN_TIMEOUT_S}s: revisar Postgres del teardown de "
            "apps/api-python/tests/conftest.py>"
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


MARKER = "# MUTATION:"

# --- E/S byte a byte --------------------------------------------------------------------------
# Los ficheros del árbol están en CRLF (autocrlf). ``read_text``/``write_text`` normalizan los
# finales de línea, así que la verificación "restaurado byte a byte" mediría la copia NORMALIZADA
# y no el byte real. Se lee el raw, se busca sobre el texto normalizado a ``\n`` y se reescribe con
# el EOL que tenía el fichero; la restauración es el raw original, sin recomponer nada.


def _read(rel: str) -> tuple[str, str]:
    """Devuelve ``(texto normalizado a \\n, EOL del fichero)``."""
    text = (ROOT / rel).read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), eol


def _write(rel: str, text: str, eol: str) -> None:
    (ROOT / rel).write_bytes(text.replace("\n", eol).encode("utf-8"))


def _fingerprints(files: tuple[str, ...]) -> dict[str, str]:
    """sha256 del contenido RAW de cada fichero: la huella que de verdad importa."""
    import hashlib

    return {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in files}


def main() -> int:
    files = tuple(sorted({rel for _, rel, _, _, _ in MUTATIONS}))
    originals = {rel: (ROOT / rel).read_bytes() for rel in files}
    texts = {rel: _read(rel) for rel in files}
    fingerprints_before = _fingerprints(files)
    status_before = _status(files)

    print("=== ficheros mutados ===")
    for rel in files:
        print(f"  {rel}")
    print("estado git de esos ficheros (antes):", status_before.strip() or "limpio")
    print(
        "Postgres alcanzable:",
        "si (se corre contra ella)" if _pg_reachable() else "no (DSN de fallo rapido)",
        flush=True,
    )

    # Guarda anti-resto: una ejecución ANTERIOR interrumpida a mitad (p. ej. un kill) deja el
    # mutante escrito sin restaurar y, si se re-lanza sin mirar, la sonda tomaría el mutante por
    # "original" y mediría mentiras. Se aborta pidiendo la restauración a mano.
    leftovers = [rel for rel in files if MARKER in texts[rel][0]]
    if leftovers:
        print("\n!! hay mutantes sin restaurar de una ejecución anterior:", flush=True)
        for rel in leftovers:
            print(f"     {rel}")
        print("   restauralos a mano (git diff) antes de volver a medir. ABORTO.")
        return 1

    print("\n=== linea base (sin mutacion) ===", flush=True)
    for tests in sorted({m[4] for m in MUTATIONS}, key=lambda t: t):
        print(f"  {', '.join(tests)} ->", sorted(_run(tests)) or "ninguno", flush=True)

    for label, rel, old, new, tests in MUTATIONS:
        current, eol = _read(rel)
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
        _write(rel, current.replace(old, new, 1), eol)
        try:
            failed = _run(tests)
        finally:
            (ROOT / rel).write_bytes(originals[rel])
        restored = (ROOT / rel).read_bytes() == originals[rel]
        print(f"\n### {label}")
        print("  rojo en:", ", ".join(sorted(failed)) or "NADA (la mutacion NO se detecta)")
        print("  restaurado byte a byte:", "si" if restored else "NO !! revisar a mano", flush=True)

    fingerprints_after = _fingerprints(files)
    print("\n=== huella del arbol ===")
    print("estado git de esos ficheros (despues):", _status(files).strip() or "limpio")
    changed = [rel for rel in files if fingerprints_before[rel] != fingerprints_after[rel]]
    if changed:
        print("  !! la sonda dejo estos ficheros con OTRO contenido:")
        for rel in changed:
            print(f"     {rel}")
        return 1
    print("  intacto: sha256 identico en los ficheros tocados (antes == despues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
