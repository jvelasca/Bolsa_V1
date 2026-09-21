"""Sonda de MUTACIONES del invariante de AUTO-4 v2.44 (el ranking deja de ser la decisión).

Aplica cada mutación del plan de fase, corre las suites que DEBEN morder y **restaura desde el
texto original en memoria**. El objetivo es que la matriz del audit-pack afirme lo MEDIDO y no lo
esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_43_3_mutation_audit.py`` (y de ``v2_43_2``/``v2_40_4``): NUNCA
``git checkout -- <file>`` (descartaría trabajo no commiteado). La restauración es la copia en
memoria y, además, la sonda **verifica que deja el árbol exactamente como lo encontró** (huella
``git status --porcelain`` de los ficheros tocados, antes y después).

El invariante nuevo tiene una forma de romperse en silencio por mutación:

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
* **M8 (dirección short)** — si un stop corto del lado equivocado (``stop <= entry``) se acepta, la
  geometría de una corta deja de ser medible y su riesgo se inventa.
* **M9 (dirección desconocida)** — si una dirección no soportada se asume larga, una señal que no
  se sabe leer entra al comparador con la geometría y el coste de otra dirección.
* **M10 (target R short)** — si el premio de una corta se mide al revés, su ``R`` derivado del
  target sale con el signo cambiado.
* **M11 (cycle acuñado)** — si el ``cycle_id`` deja de ser determinista por ``(cuenta, señal)``,
  dos workers que evalúan la misma señal parten el ciclo en dos y la trazabilidad miente.
* **M12 (cycle propagado)** — si el journal deja de publicar el ``cycleId``, la cadena
  señal→decisión deja de ser reconstruible por el ciclo.
* **M13 (coste inventado)** — si el coste de rechazo sin precios se publica como ``0.0`` en vez de
  declararse no medido, el informe afirma "no dejó pasar nada" cuando en realidad no se midió.
* **M14 (embudo cerrado sin medir)** — si el embudo sin oportunidades se declara ``COMPLETE`` con
  ``seen = 0``, un periodo sin datos se lee como un periodo sin oportunidades.
* **M15 (ciclo contado dos veces)** — si la identidad repetida de un ciclo deja de descartarse, el
  informe suma dos veces el mismo resultado (mentiría igual que un doble fill).
* **M16 (colisión silenciosa)** — si el dedupe deja de devolver las candidatas superadas, la
  política vuelve a ser muda: dos señales del mismo instrumento y solo una sobrevive sin rastro.
* **M17 (kill recargado)** — si tras el reinicio el HALT durable deja de adoptarse, el motor
  arranca operando contra una parada persistida (el crash reabriría el sistema).
* **M18 (coste de otra dirección)** — si la dirección deja de llegar al estimador de coste, el
  ida y vuelta de una corta se cobra con las patas de una larga y el neto sale más barato de lo
  que la operación cuesta de verdad.

DSN fast-fail para las suites de ``apps/api-python``: el teardown de
``apps/api-python/tests/conftest.py`` (``purge_all_residuals``) intenta conectar a Postgres y,
sin PG levantado, se queda colgado. Se inyecta un ``DATABASE_URL`` a un puerto local cerrado: el
``connect`` falla al instante y el ``except`` del teardown lo traga, de modo que la sonda devuelve
los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo.

Bytecode (V2.46.1, defecto REAL de la sonda): un ``.pyc`` solo se considera vigente si coinciden
el mtime del fuente truncado a SEGUNDOS y su tamaño, y las mutaciones de esta matriz sustituyen
por fragmentos del MISMO tamaño. Escribir el mutante y restaurar dentro del mismo segundo dejaba
el ``.pyc`` del mutante "vigente" para el fuente restaurado: la matriz podía reportar un rojo que
NO venía del árbol actual (se observó exactamente eso en ``test_a_short_target_r_...``). Ahora se
borra el ``.pyc`` de cada módulo mutado antes de cada corrida y se corre con
``PYTHONDONTWRITEBYTECODE=1``, de modo que cada corrida compila el fuente de verdad.

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
EXPECTED_VALUE = "packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py"
AUTO_SELF_EVAL = "packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py"
WORKER = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"

# --- suites que deben morder ----------------------------------------------------------------
T_OPT = "packages/py/analytics/tests/test_portfolio_optimizer.py"
T_EV = "packages/py/analytics/tests/test_expected_value.py"
T_WIRE = "packages/py/application/tests/test_auto_v4_optimizer_wiring.py"
T_CYCLE = "packages/py/application/tests/test_auto_v47_cycle_trace.py"
T_IDENTITY = "packages/py/application/tests/test_auto_v47_signal_identity.py"
T_HARDKILL = "apps/api-python/tests/test_auto_v46_hardkill_recovery.py"
T_SELF = (
    "packages/py/analytics/tests/test_auto_self_evaluation.py",
    "packages/py/application/tests/test_auto_self_evaluation_feed.py",
)
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
        "                    reason_by_id.get(_key_of(signal), OPTIMIZER_NOT_SELECTED),\n"
        "                    actor=actor,\n",
        '                    "edge_below_threshold",\n'
        "                    actor=actor,\n",
        (T_WIRE,),
    ),
    (
        "M7 (flag): con ON el tick vuelve al ranking sin declararlo",
        ENTRY,
        "    if cfg.optimizer_enabled and ordered:\n",
        "    if False and ordered:\n",
        (T_WIRE, T_WORKER),
    ),
    (
        "M8 (direccion short): un stop corto del lado equivocado se acepta",
        EXPECTED_VALUE,
        "    if resolved == _SHORT:\n"
        "        if s <= e:\n"
        "            return None, EV_GEOMETRY_UNMEASURED\n",
        "    if resolved == _SHORT:\n"
        "        if False:\n"
        "            return None, EV_GEOMETRY_UNMEASURED\n",
        (T_EV,),
    ),
    (
        "M9 (direccion desconocida): una direccion no soportada se asume larga",
        EXPECTED_VALUE,
        "    resolved_direction = _coerce_direction(direction)\n"
        "    if resolved_direction is None:\n"
        "        notes.append(EV_DIRECTION_UNSUPPORTED)\n",
        "    resolved_direction = _coerce_direction(direction) or _LONG\n"
        "    if False:\n"
        "        notes.append(EV_DIRECTION_UNSUPPORTED)\n",
        (T_EV,),
    ),
    (
        "M10 (target R short): el premio de una corta se mide al reves",
        EXPECTED_VALUE,
        "    if resolved == _SHORT:\n"
        "        distance = s - e\n"
        "        if distance <= 0.0:\n"
        "            return None\n"
        "        reward = e - t\n",
        "    if resolved == _SHORT:\n"
        "        distance = s - e\n"
        "        if distance <= 0.0:\n"
        "            return None\n"
        "        reward = t - e\n",
        (T_EV,),
    ),
    (
        "M11 (cycle acunado): el cycle_id deja de ser determinista por (cuenta, senal)",
        ENTRY,
        "    key = f\"{str(account_id or '').strip()}\\x1f{signal_id}\"\n"
        "    return f\"cyc-{sha256(key.encode('utf-8')).hexdigest()[:12]}\"",
        "    from uuid import uuid4 as _u\n"
        "    return f\"cyc-{_u().hex[:12]}\"",
        (T_CYCLE,),
    ),
    (
        "M12 (cycle propagado): el journal deja de publicar el cycleId",
        ENTRY,
        "    if str(cycle_id or \"\").strip():\n        payload[\"cycleId\"] = str(cycle_id)\n",
        "    if False:\n        payload[\"cycleId\"] = str(cycle_id)\n",
        (T_CYCLE,),
    ),
    (
        "M13 (coste inventado): el coste no medido se publica como 0.0",
        AUTO_SELF_EVAL,
        "        cost = _round4(measured_cost) if measured_rejection else None\n",
        "        cost = _round4(measured_cost)\n",
        (T_SELF),
    ),
    (
        "M14 (embudo cerrado sin medir): sin oportunidades el embudo se declara COMPLETE con 0",
        AUTO_SELF_EVAL,
        "            measurement=MEASUREMENT_UNKNOWN,\n            seen=None,\n",
        "            measurement=MEASUREMENT_COMPLETE,\n            seen=0,\n",
        (T_SELF),
    ),
    (
        "M15 (ciclo contado dos veces): la identidad repetida deja de descartarse",
        AUTO_SELF_EVAL,
        "        if cycle.identity in seen:\n            duplicates += 1\n            continue\n",
        "        if False:\n            duplicates += 1\n            continue\n",
        (T_SELF),
    ),
    (
        "M16 (colision silenciosa): el dedupe deja de declarar la candidata superada",
        ENTRY,
        "    return best, tuple(superseded)\n",
        "    return best, ()\n",
        (T_IDENTITY,),
    ),
    (
        "M17 (kill recargado): tras reiniciar, el HALT durable deja de adoptarse",
        WORKER,
        "        if state.engaged:\n            if self._v2_kill_switch.engaged:\n",
        "        if False:\n            if self._v2_kill_switch.engaged:\n",
        (T_HARDKILL,),
    ),
    (
        "M18 (coste de otra direccion): la direccion no llega al coste",
        EXPECTED_VALUE,
        "            direction=resolved_direction,\n            model=cost_model,\n",
        "            direction=_LONG,\n            model=cost_model,\n",
        (T_EV,),
    ),
]

# DSN a un puerto local cerrado: el connect falla al instante (en vez de colgar el teardown de PG).
FAST_FAIL_DSN = "postgresql+psycopg://bolsa:bolsa@127.0.0.1:9/bolsa_v1"


def _drop_bytecode(sources: tuple[str, ...]) -> None:
    """Borra el ``.pyc`` de los módulos mutados ANTES de cada corrida (ver nota de cabecera).

    Un ``.pyc`` es válido si coinciden el mtime del fuente (truncado a SEGUNDOS) y su tamaño.
    Las mutaciones de esta matriz son sustituciones del MISMO tamaño (``e - t`` por ``t - e``,
    ``if x:`` por ``if False:``...): escribir el mutante y restaurar dentro del MISMO segundo deja
    el ``.pyc`` del mutante "vigente" para el fuente restaurado. El resultado sería una matriz que
    MIENTE (un rojo que no viene del árbol actual, o peor, un "no detectado" falso). Se elimina el
    bytecode y se corre con ``PYTHONDONTWRITEBYTECODE=1``: cada corrida compila el fuente real.
    """
    for rel in sources:
        src = ROOT / rel
        cache = src.parent / "__pycache__"
        if not cache.is_dir():
            continue
        for pyc in cache.glob(f"{src.stem}.*.pyc"):
            try:
                pyc.unlink()
            except OSError:  # noqa: PERF203 — un pyc que no se puede borrar no aborta la sonda.
                continue


def _run(tests: tuple[str, ...], sources: tuple[str, ...]) -> set[str]:
    """Corre las suites y devuelve los nombres de test que se pusieron rojos."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    _drop_bytecode(sources)
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
        print(f"  {', '.join(tests)} ->", sorted(_run(tests, files)) or "ninguno")

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
            failed = _run(tests, (rel,))
        finally:
            path.write_text(originals[rel], encoding="utf-8")
        _drop_bytecode((rel,))
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
