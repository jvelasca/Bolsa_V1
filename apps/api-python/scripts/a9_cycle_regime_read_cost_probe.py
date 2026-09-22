"""Sonda de MEDICIÓN (paso 1 de `V2.50`/`AUTO-9`): ¿cuánto cuesta leer el régimen por ciclo?

`marketRegime` **no** es una columna: vive en el JSONB de `decision_journal_entries.payload`. El
plan `v2.50` §6.4 prohíbe asumir que leerlo por `cycle_id` sea barato y exige decidir con la
medición delante entre:

* **(a)** resolver por el `decision_id` del ciclo, si el vínculo existe en un campo **indexado**;
* **(b)** índice de expresión aditivo sobre `payload->>'cycleId'` (migración `045`, solo índice).

Esta sonda entrega las dos mitades de esa decisión.

**MITAD OFFLINE (corre siempre).** Demuestra que (a) es *posible*: `entry_decision_id` y
`auto_cycle_id` hashean la MISMA clave (``cuenta \\x1f signal_id``) con el MISMO sha256, así que
solo cambia el prefijo y el `decision_id` se **deriva** del `cycle_id` por sustitución de cadena,
sin consultar nada. Y demuestra el **límite** de esa derivación: un `cycle_id` acuñado por el
fallback aleatorio (`uuid4`) tiene la MISMA forma, de modo que la forma no prueba origen y el
llamante está obligado a **confirmar** que el `payload->>'cycleId'` de la fila leída es el ciclo
pedido. Esa confirmación es lo que hace la derivación segura: una derivación equivocada no puede
leer el régimen de un ciclo ajeno, solo fallar y dejar el ciclo en `UNKNOWN`.

**MITAD ONLINE (requiere PostgreSQL).** Mide de verdad, con `EXPLAIN (ANALYZE, BUFFERS)`, lo que
cuestan las dos vías sobre la tabla real, e inventaría los índices que existen hoy.

Códigos de salida:

* ``0`` — medido (la mitad online se ejecutó).
* ``1`` — la propiedad offline **no** se cumple: el contrato de identidad cambió y (a) dejó de ser
  segura. Es un fallo, no una medición pendiente.
* ``2`` — **bloqueado**: sin PostgreSQL no hay medición, y "no medido" no se imprime como medido.

Uso: ``uv run --no-sync python apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py``

Sonda puntual (no permanente): no la llama ningún workflow de CI.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from bolsa_application.auto_v2_entry import V2Signal, auto_cycle_id, entry_decision_id

if TYPE_CHECKING:  # pragma: no cover — solo para anotar el cursor de psycopg.
    import psycopg

# El DSN de desarrollo del repo (``docker-compose.yml``). ``DATABASE_URL`` manda si está puesto.
DEFAULT_DSN = "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1"

# Batería de identidades: estable, repetida (la identidad no depende de la posición), otra cuenta
# (la cuenta desambigua) y SIN identidad de señal (fallback aleatorio: el caso que (a) no cubre).
_BATTERY: tuple[tuple[str, str], ...] = (
    ("acc-1", "sig-abc"),
    ("acc-1", "sig-abc"),
    ("acc-2", "sig-abc"),
    ("acc-1", ""),
)

# El ciclo de un tick sin identidad de señal: `cyc-` + 12 hex del fallback. Sirve para demostrar que
# la forma NO distingue el origen (y por eso (a) exige confirmación, no confianza en el patrón).
_HEX = "0123456789abcdef"

_Q_DERIVED = """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT payload->>'cycleId' AS cycle_id,
       payload->>'marketRegime' AS market_regime,
       created_at
FROM decision_journal_entries
WHERE decision_id = %s
ORDER BY created_at
"""

_Q_JSONB = """
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT payload->>'cycleId' AS cycle_id,
       payload->>'marketRegime' AS market_regime,
       created_at
FROM decision_journal_entries
WHERE payload->>'cycleId' = %s
ORDER BY created_at
"""

_REPEATS = 3


def _signal(signal_id: str) -> V2Signal:
    return V2Signal(instrument_id="AAA", action="BUY", price=100.0, signal_id=signal_id)


def _looks_like_a_cycle(value: str) -> bool:
    """¿Tiene la forma ``cyc-`` + 12 hex? Tener la forma **no** prueba que viniera de una señal."""
    text = str(value or "").strip()
    digest = text[4:] if text.startswith("cyc-") else ""
    return len(digest) == 12 and all(char in _HEX for char in digest)


def decision_id_from_cycle_id(cycle_id: str) -> str | None:
    """Vía (a) — el `decision_id` del ciclo, derivado de su identidad, **sin tocar la base**.

    `entry_decision_id` y `auto_cycle_id` hashean la misma clave, así que el digest del ciclo *es*
    el digest de la decisión y basta cambiar el prefijo. ``None`` si la cadena no tiene la forma,
    porque entonces no se adivina: el ciclo queda `UNKNOWN` en régimen y lo declara el llamante.
    """
    text = str(cycle_id or "").strip()
    if not _looks_like_a_cycle(text):
        return None
    return f"dec-{text[4:]}"


def _offline() -> bool:
    """Prueba (o refuta) que (a) es posible, y enseña el límite que obliga a confirmar la fila."""
    print("== MITAD OFFLINE - es posible (a)? ==")
    ok = True
    for account_id, signal_id in _BATTERY:
        signal = _signal(signal_id)
        cycle_id = auto_cycle_id(account_id=account_id, signal=signal)
        decision_id = entry_decision_id(account_id=account_id, signal=signal)
        derived = decision_id_from_cycle_id(cycle_id)
        if not signal_id:
            # Fallback aleatorio: la sonda NO afirma nada sobre la relación entre ambos (los dos
            # son `uuid4` independientes). Solo declara que la derivación aquí es ciega.
            print(
                f"  cuenta={account_id!r} sin-identidad: {cycle_id} -> {derived} "
                f"(aleatorio: IRRELEVANTE frente al real {decision_id})"
            )
            continue
        same = derived == decision_id
        ok = ok and same
        verdict = "identico por prefijo" if same else "DIVERGE - el contrato de identidad cambio"
        print(f"  cuenta={account_id!r} senal={signal_id!r}: {cycle_id} -> {derived} ({verdict})")

    # Dos identidades distintas no pueden colapsar en el mismo digest (o dos señales compartirían
    # decisión, que es la propiedad que sostiene el claim de reserva).
    digests = {
        auto_cycle_id(account_id=account, signal=_signal(sid))[4:]
        for account, sid in _BATTERY
        if sid
    }
    distinct = len(digests) == len({(a, s) for a, s in _BATTERY if s})
    ok = ok and distinct
    print(f"  digests distintos para identidades distintas: {distinct}")

    print("\n  LIMITE DECLARADO: el fallback aleatorio tiene la MISMA forma, asi que la forma no")
    print("  prueba origen. Decision (a) exige CONFIRMAR la fila leida:")
    print("      payload->>'cycleId' == cycle_id   (si no coincide => regimen UNKNOWN)")
    print("  Con esa confirmacion, una derivacion equivocada no lee el regimen de un ciclo ajeno:")
    print("  solo deja el hueco declarado. Sin ella, (a) seria un invento.")
    return ok


def _redact(dsn: str) -> str:
    """No imprimir credenciales: ``postgresql://user:***@host``."""
    head, separator, rest = dsn.partition("://")
    if not rest or "@" not in rest:
        return dsn
    creds, _, host = rest.rpartition("@")
    user, colon, _password = creds.partition(":")
    if not colon:
        return f"{head}{separator}{creds}@{host}"
    return f"{head}{separator}{user}{colon}***@{host}"


def _execution_time(plan: str) -> str:
    """La última línea ``Execution Time`` del plan (la del nodo raíz)."""
    times = [line.strip() for line in plan.splitlines() if "Execution Time:" in line]
    return times[-1].split("Execution Time:")[-1].strip() if times else "?"


def _explain(
    cursor: psycopg.Cursor[tuple[str]],
    sql: str,
    param: str,
) -> tuple[str, list[str]]:
    """Corre el EXPLAIN ``_REPEATS`` veces y devuelve (mejor plan, tiempos de ejecución)."""
    plan = ""
    times: list[str] = []
    for _ in range(_REPEATS):
        cursor.execute(sql, (param,))
        plan = "\n".join(row[0] for row in cursor.fetchall())
        times.append(_execution_time(plan))
    return plan, times


def _online(dsn: str) -> bool:
    """Mide las dos vías sobre la tabla real. Lanza si no hay PostgreSQL: no se simula."""
    import psycopg

    with psycopg.connect(dsn, connect_timeout=5) as conn, conn.cursor() as cursor:
        print("\n== MITAD ONLINE - cuanto cuesta de verdad? ==")
        cursor.execute("SELECT current_database(), current_setting('server_version')")
        database, version = cursor.fetchone()  # type: ignore[misc]
        print(f"  base: {database} (PostgreSQL {version})")

        cursor.execute("SELECT count(*) FROM decision_journal_entries")
        total = cursor.fetchone()[0]  # type: ignore[index]
        cursor.execute("SELECT count(*) FROM decision_journal_entries WHERE payload ? 'cycleId'")
        with_cycle = cursor.fetchone()[0]  # type: ignore[index]
        print(f"  filas en decision_journal_entries: {total} (con cycleId: {with_cycle})")
        print("  OJO: un plan medido sobre 0 filas describe la SENDA, no el coste. Repite la sonda")
        print("  con datos reales antes de sellar (a)/(b).")

        cursor.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE tablename = 'decision_journal_entries' ORDER BY indexname"
        )
        indexes = cursor.fetchall()
        print("  indices hoy:")
        if not indexes:
            print("    (ninguno)")
        for name, definition in indexes:
            print(f"    {name}: {definition}")
        has_expression = any("cycleId" in str(definition or "") for _, definition in indexes)
        print(
            f"  indice de expresion sobre payload->>'cycleId': {'SI' if has_expression else 'NO'}"
        )

        cursor.execute(
            "SELECT cycle_id FROM portfolio_reservations "
            "WHERE cycle_id IS NOT NULL ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        sample = str(row[0]) if row else None
        if sample is None:
            print("  sin ciclos en portfolio_reservations: se describe la senda con un ciclo")
            print("  sintetico (la fila no existe y el plan lo declara); repetir con datos.")
        target = sample or "cyc-000000000000"
        derived = decision_id_from_cycle_id(target)
        print(f"  ciclo de la muestra: {target}")
        print(f"  decision_id derivado: {derived}")

        for label, sql, param in (
            ("(a) por decision_id derivado", _Q_DERIVED, derived),
            ("(b) por payload->>'cycleId'", _Q_JSONB, target),
        ):
            assert param is not None
            plan, times = _explain(cursor, sql, param)
            print(f"\n  --- {label} ---")
            for line in plan.splitlines():
                print(f"    {line}")
            print(f"  ejecucion ({_REPEATS} pasadas): {' | '.join(times)}")

        print("\n  REGLA DE DECISION (plan 6.4), con estos numeros delante:")
        print("    * si (a) resuelve por indice y su coste es despreciable frente a (b) => (a),")
        print("      sin migracion: la derivacion + confirmacion basta.")
        print("    * si (a) no es utilizable y (b) recorre la tabla => (b) exige el indice de")
        print("      expresion aditivo (migracion 045, solo indice; el esquema no cambia).")
        return True


def main() -> int:
    # La sonda escribe en la consola del desarrollador (cp1252/cp850 en Windows en el peor caso).
    # Un UnicodeEncodeError AL IMPRIMIR no puede parecer un fallo de medicion.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    if not _offline():
        print("\n== FALLO ==\n  la propiedad offline no se cumple: (a) dejo de ser segura.")
        return 1

    dsn = (os.environ.get("DATABASE_URL") or "").strip() or DEFAULT_DSN
    try:
        measured = _online(dsn)
    except Exception as exc:  # noqa: BLE001 — sin PG no hay medición: se declara, no se simula.
        print(f"\n== BLOQUEADO ==\n  no hay medicion: {type(exc).__name__}: {exc}")
        print(f"  DSN: {_redact(dsn)}")
        print("  Levanta PostgreSQL (`docker compose up -d postgres`) y repite la sonda.")
        return 2
    return 0 if measured else 2


if __name__ == "__main__":
    sys.exit(main())
