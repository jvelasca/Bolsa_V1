"""Sonda de MUTACIONES del invariante de AUTO-4 v2.44 (el ranking deja de ser la decisión).

Aplica cada mutación del plan de fase, corre las suites que DEBEN morder y **restaura desde el
texto original en memoria**. El objetivo es que la matriz del audit-pack afirme lo MEDIDO y no lo
esperado: una sonda que dice "este test se pondría rojo" sin haberlo medido es humo.

Patrón copiado de ``v2_43_3_mutation_audit.py`` (y de ``v2_43_2``/``v2_40_4``): la restauración es la copia
en memoria y, además, la sonda **verifica que deja el árbol exactamente como lo encontró** (huella
``git status --porcelain`` de los ficheros tocados, antes y después). El ``git checkout`` NO es la vía
normal —descartaría trabajo no commiteado— pero SÍ es la red de seguridad de último recurso: en esta
máquina, restaurar ``auto_v2_entry.py`` tras la mutación 16 falla de forma reproducible con
``OSError [Errno 22]`` de Windows (el mismo par escritura/restauración funciona aislado), y una sonda
que se cae dejando el MUTANTE dentro del árbol es peor que una que aborta. Esa ruta solo se usa si
fallan el reintento y el reemplazo atómico, y entonces la sonda **aborta** en vez de seguir midiendo.

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
* **M19 (rotación por salud)** — si la salud probadamente negativa deja de pausar, una estrategia
  perdedora sigue compitiendo.
* **M20 (rotación por régimen)** — si la pausa en régimen adverso deja de aplicarse, una muestra
  fina se activa a ciegas en un mercado que castiga.
* **M21 (asignación monótona)** — si el multiplicador deja de acotarse a ``[0, 1]``, la asignación
  puede ENSANCHAR el riesgo por operación.
* **M22 (sin evidencia neutral)** — si el multiplicador de una versión sin evidencia cae a ``0``,
  "no medido" se convierte en "riesgo cero" (el defecto que AUTO-8.1 corrige).
* **M23 (gate por fila)** — si una muestra no decisoria entra al reparto proporcional, una racha
  de suerte mueve el presupuesto de las estrategias que SÍ demostraron.
* **M24 (policy version)** — si el plan deja de sellar la versión de política, dos planes iguales
  no son reproducibles ni distinguibles de reglas futuras.
* **M25 (hysteresis régimen)** — si el umbral de reactivación baja al de pausa, desaparece la zona
  muerta y la rotación oscila.
* **M26 (muestra decisoria)** — si sin decisividad la pausa de salud se declara vigente, una
  métrica fina mantiene una pausa que su evidencia no sostiene.
* **M27 (cooldown)** — si la pausa mínima deja de respetarse, la rotación parpadea tick a tick.

AUTO-9 (evidencia por ciclo) y AUTO-10 (journal durable del régimen) añaden:

* **M28 (denominador de R)** — si el denominador toma la reserva más NUEVA en vez de la más
  antigua del ciclo, el riesgo comprometido deja de ser el de la entrada.
* **M29 (reserva de venta)** — si la venta entra como denominador, un ciclo sin riesgo real se
  mide como si lo tuviera.
* **M30 (hueco silencioso)** — si un ciclo sin reservas desaparece del mapa, "no medido" se
  convierte en "no existía".
* **M31 (dato no medido)** — si el coste ausente se publica como clave nula, `null` pasa a leerse
  como una medición.
* **M32 (costura muda)** — si el informe ignora la evidencia de riesgo que se le pasa, el
  productor deja de entrar en la evaluación.
* **M33 (worker sin denominador)** — si el camino Adaptive deja de leer el riesgo por ciclo, la
  evidencia existe pero nadie la consume.
* **M34 (identidad derivada)** — si un `cycle_id` ajeno al prefijo también se deriva, se afirma
  una identidad que no se puede probar.
* **M35 (payload sin cycleId)** — si la traza deja de publicar de qué ciclo es, la lectura
  confirma contra la nada y el régimen se pierde.
* **M36 (régimen disfrazado)** — si el régimen ausente se declara `COMPLETE`, "no medido" se lee
  como medido.
* **M37 (sink sin usar)** — si el turno deja de publicar el régimen del ciclo, el hueco que
  `AUTO-10` cierra vuelve a abrirse en silencio.
* **M38 (sink sin commit)** — si la escritura se queda en `flush`, la fila muere al cerrar la
  sesión: "escrito" sin serlo.
* **M39 (sin confirmar)** — si una fila con ese `decision_id` se cree sin mirar el payload, una
  derivación equivocada lee el régimen de un ciclo ajeno.
* **M40 (dedupe por llegada)** — si gana la fila más nueva aunque no confirme, la entrada de
  ventana (que comparte `decision_id` y es más nueva) roba el régimen.
* **M41 (duplicado silencioso)** — si la lectura deja de declarar las filas de más, una tormenta
  de reintentos se vuelve invisible.

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
import time

# La salida de la sonda incluye ``⇒``/acentos; cuando stdout es un pipe (p. ej. corrida en
# segundo plano o con ``Tee-Object``), Windows usa ``cp1252`` y el ``print`` revienta con
# ``UnicodeEncodeError`` ANTES de llegar a la huella del árbol. Forzar UTF-8 explícitamente.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[3]

# --- código de producción mutado ----------------------------------------------------------------
OPTIMIZER = "packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py"
ENTRY = "packages/py/application/src/bolsa_application/auto_v2_entry.py"
EXPECTED_VALUE = "packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py"
AUTO_SELF_EVAL = "packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py"
AUTO_ADAPTIVE = "packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py"
CYCLE_RISK = "packages/py/application/src/bolsa_application/cycle_risk.py"
FEED = "packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py"
AUTO_CYCLE_JOURNAL = "packages/py/application/src/bolsa_application/auto_cycle_journal.py"
REGIME_READER = "packages/py/application/src/bolsa_application/auto_cycle_regime_reader.py"
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
T_ADAPTIVE = "packages/py/analytics/tests/test_auto_adaptive.py"
T_ADAPTIVE_ENTRY = "packages/py/application/tests/test_auto_adaptive_entry.py"
T_CYCLE_RISK = "packages/py/application/tests/test_cycle_risk.py"
T_CYCLE_RISK_SEAM = "apps/api-python/tests/test_auto_v50_auto9_cycle_risk_seam.py"
T_CYCLE_JOURNAL = "packages/py/application/tests/test_auto_cycle_journal.py"
T_REGIME_READER = "packages/py/application/tests/test_auto_cycle_regime_reader.py"
T_CYCLE_JOURNAL_SEAM = "apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py"
T_REGIME_SEAM = "apps/api-python/tests/test_auto_v51_auto10_cycle_regime_seam.py"
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
        '                    "edge_below_threshold",\n                    actor=actor,\n',
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
        '    from uuid import uuid4 as _u\n    return f"cyc-{_u().hex[:12]}"',
        (T_CYCLE,),
    ),
    (
        "M12 (cycle propagado): el journal deja de publicar el cycleId",
        ENTRY,
        '    if str(cycle_id or "").strip():\n        payload["cycleId"] = str(cycle_id)\n',
        '    if False:\n        payload["cycleId"] = str(cycle_id)\n',
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
    (
        "M19 (rotacion por salud): la estrategia probadamente negativa deja de pausarse",
        AUTO_ADAPTIVE,
        "        if expectancy_bad or pf_bad:\n            return ADAPTIVE_STRATEGY_UNHEALTHY\n",
        "        if False:\n            return ADAPTIVE_STRATEGY_UNHEALTHY\n",
        (T_ADAPTIVE,),
    ),
    (
        "M20 (rotacion por regimen): la pausa en regimen adverso deja de aplicarse",
        AUTO_ADAPTIVE,
        "    if adverse and not health.decisive:\n"
        "        if health.win_rate is not None and health.win_rate < policy.win_rate_floor:\n"
        "            return ADAPTIVE_STRATEGY_REGIME_RISK\n",
        "    if False and not health.decisive:\n"
        "        if health.win_rate is not None and health.win_rate < policy.win_rate_floor:\n"
        "            return ADAPTIVE_STRATEGY_REGIME_RISK\n",
        (T_ADAPTIVE, T_ADAPTIVE_ENTRY),
    ),
    (
        "M21 (asignacion monotona): el multiplicador deja de acotarse a [0, 1]",
        AUTO_ADAPTIVE,
        "                multipliers[version] = _clamp_unit((weight / total) * count)\n",
        "                multipliers[version] = (weight / total) * count\n",
        (T_ADAPTIVE,),
    ),
    (
        "M22 (sin evidencia neutral): el multiplicador de una version sin evidencia cae a 0",
        AUTO_ADAPTIVE,
        "    neutral = _clamp_unit(resolved.unknown_multiplier)\n",
        "    neutral = 0.0\n",
        (T_ADAPTIVE,),
    ),
    (
        "M23 (gate por fila): una muestra no decisoria entra al reparto proporcional",
        AUTO_ADAPTIVE,
        "        if row is None or not row.decisive:\n            continue\n",
        "        if row is None:\n            continue\n",
        (T_ADAPTIVE,),
    ),
    (
        "M24 (policy version): el plan deja de sellar la version de politica",
        AUTO_ADAPTIVE,
        '            "policyVersion": self.policy_version,\n',
        '            "policyVersion": "auto8-v0",\n',
        (T_ADAPTIVE, T_ADAPTIVE_ENTRY),
    ),
    (
        "M25 (hysteresis regimen): el umbral de reactivacion baja al de pausa (sin zona muerta)",
        AUTO_ADAPTIVE,
        "    return health.win_rate is not None and health.win_rate < policy.win_rate_reactivate_floor\n",
        "    return health.win_rate is not None and health.win_rate < policy.win_rate_floor\n",
        (T_ADAPTIVE,),
    ),
    (
        "M26 (muestra decisoria): sin decisividad la pausa de salud se declara vigente",
        AUTO_ADAPTIVE,
        "    if not health.decisive:\n        return False\n    expectancy_ok = health.expectancy_currency is not None and health.expectancy_currency > Decimal(\n",
        "    if not health.decisive:\n        return True\n    expectancy_ok = health.expectancy_currency is not None and health.expectancy_currency > Decimal(\n",
        (T_ADAPTIVE,),
    ),
    (
        "M27 (cooldown): la pausa minima deja de respetarse",
        AUTO_ADAPTIVE,
        "        if count < max(0, int(resolved.min_pause_cycles)):\n",
        "        if False:\n",
        (T_ADAPTIVE,),
    ),
    (
        "M28 (denominador de R): se usa la reserva de entrada MAS NUEVA en vez de la mas antigua",
        CYCLE_RISK,
        "    entry = candidates[0] if candidates else None\n",
        "    entry = candidates[-1] if candidates else None\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M29 (reserva de venta): la venta entra como denominador (riesgo 0 admitido)",
        CYCLE_RISK,
        "        if row.is_buy and (risk := _dec(row.reserved_risk)) is not None and risk > 0\n",
        "        if (risk := _dec(row.reserved_risk)) is not None and risk >= 0\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M30 (hueco silencioso): un ciclo sin reservas desaparece del mapa en vez de declararse",
        CYCLE_RISK,
        "        for key in keys\n    }\n",
        "        for key in keys\n        if key in grouped\n    }\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M31 (dato no medido): el coste ausente se publica como clave nula en vez de omitirse",
        CYCLE_RISK,
        '        if self.cost is not None:\n            fields["cost"] = self.cost\n',
        '        fields["cost"] = self.cost\n',
        (T_CYCLE_RISK,),
    ),
    (
        "M32 (costura muda): el informe ignora la evidencia de riesgo que le llega",
        FEED,
        "        cycles=apply_cycle_risk(cycles_from_fills(fills or ()), cycle_risk),\n",
        "        cycles=cycles_from_fills(fills or ()),\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M33 (worker sin denominador): el camino Adaptive deja de leer el riesgo por ciclo",
        WORKER,
        "        report = build_auto_self_evaluation(\n"
        "            fills=fills, cycle_risk=await self._v2_cycle_risk(fills)\n"
        "        )\n",
        "        report = build_auto_self_evaluation(\n            fills=fills\n        )\n",
        (T_CYCLE_RISK_SEAM,),
    ),
    (
        "M34 (identidad derivada): un cycle_id ajeno al prefijo tambien se deriva",
        AUTO_CYCLE_JOURNAL,
        "    if not text.startswith(CYCLE_ID_PREFIX):\n        return None\n",
        "    if False:\n        return None\n",
        (T_CYCLE_JOURNAL, T_REGIME_READER),
    ),
    (
        "M35 (payload sin cycleId): la traza deja de publicar de que ciclo es",
        AUTO_CYCLE_JOURNAL,
        '        "event": AUTO_CYCLE_REGIME_EVENT,\n        "cycleId": text,\n',
        '        "event": AUTO_CYCLE_REGIME_EVENT,\n        "cycleId": "",\n',
        (T_CYCLE_JOURNAL,),
    ),
    (
        "M36 (regimen disfrazado): el regimen ausente se declara COMPLETE",
        AUTO_CYCLE_JOURNAL,
        "    measurement: MeasurementStatus = MEASUREMENT_COMPLETE if regime else MEASUREMENT_UNKNOWN\n",
        "    measurement: MeasurementStatus = MEASUREMENT_COMPLETE\n",
        (T_CYCLE_JOURNAL,),
    ),
    (
        "M37 (sink sin usar): el turno deja de publicar el regimen del ciclo",
        WORKER,
        "        await self._v2_journal_cycle_regime(persisted)\n",
        "        if False:\n            await self._v2_journal_cycle_regime(persisted)\n",
        (T_CYCLE_JOURNAL_SEAM,),
    ),
    (
        "M38 (sink sin commit): la traza se hace flush y se pierde al cerrar la sesion",
        WORKER,
        "            await repository.append(entry)\n            await session.commit()\n",
        "            await repository.append(entry)\n            if False:\n                await session.commit()\n",
        (T_CYCLE_JOURNAL_SEAM,),
    ),
    (
        "M39 (sin confirmar): una fila con ese decision_id se cree sin mirar el payload",
        REGIME_READER,
        '    if _clean(payload.get("cycleId")) != cycle_id:\n        return None\n',
        "    if False:\n        return None\n",
        (T_REGIME_READER, T_REGIME_SEAM),
    ),
    (
        "M40 (dedupe por llegada): gana la fila mas nueva aunque no confirme el ciclo",
        REGIME_READER,
        "        regime = next(\n"
        "            (found for entry in candidates if (found := _confirmed_regime(entry, cycle_id))),\n"
        "            None,\n"
        "        )\n",
        "        regime = _confirmed_regime(candidates[0], cycle_id)\n",
        (T_REGIME_READER,),
    ),
    (
        "M41 (duplicado silencioso): la lectura deja de declarar las filas de mas",
        REGIME_READER,
        "            if len(candidates) > 1:\n",
        "            if False:\n",
        (T_REGIME_READER, T_REGIME_SEAM),
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
        return {
            "<TIMEOUT 600s: revisar Postgres del teardown de apps/api-python/tests/conftest.py>"
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


def _is_clean_in_git(rel: str) -> bool:
    """True si ``rel`` no tiene cambios sin commitear (``git checkout`` sería inocuo)."""
    out = subprocess.run(
        ["git", "status", "--porcelain", "--", rel],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return not out.stdout.strip()


def _restore(path: pathlib.Path, rel: str, original: str) -> bool:
    """Devuelve el fichero a su contenido original; NUNCA deja el árbol mutado.

    Un ``write_bytes`` que falla aquí deja el MUTANTE dentro del árbol, que es el peor
    resultado posible de una sonda (el siguiente paso mediría sobre un árbol corrupto). Se
    observó en esta máquina un ``OSError [Errno 22]`` de Windows al restaurar
    ``auto_v2_entry.py`` tras la mutación 16, reproducible y no atribuible al contenido
    (el mismo par escritura/restauración funciona aislado). Por eso hay tres capas: reintento
    con pausa, reemplazo atómico con ``os.replace`` y, como último recurso, ``git checkout``.

    **El último recurso solo se usa si el fichero está LIMPIO en git.** Si tuviera cambios sin
    commitear, ``git checkout`` los descartaría: en ese caso la sonda **aborta** declarándolo
    en vez de destruir trabajo ajeno. Es la regla que el patrón de este script protegía.
    """
    payload = original.encode("utf-8")
    for attempt in range(3):
        try:
            path.write_bytes(payload)
            if path.read_text(encoding="utf-8") == original:
                return True
        except OSError:
            pass
        time.sleep(0.5 * (attempt + 1))
    try:
        tmp = path.with_suffix(path.suffix + ".restore")
        tmp.write_bytes(payload)
        os.replace(tmp, path)
        if path.read_text(encoding="utf-8") == original:
            return True
    except OSError:
        pass
    if not _is_clean_in_git(rel):
        print(
            f"  !! {rel} tiene cambios SIN COMMITEAR y no se puede restaurar en memoria: "
            "NO se usa git checkout (descartaria trabajo). Abortar y revisar a mano."
        )
        return False
    subprocess.run(["git", "checkout", "--", rel], cwd=ROOT, capture_output=True, text=True)
    return path.read_text(encoding="utf-8") == original


def main(argv: list[str] | None = None) -> int:
    # Filtro opcional por etiqueta (``M28``, ``M29``…): permite verificar un tramo de la
    # matriz sin arrastrar las 30 corridas anteriores (útil cuando una sola mutación se
    # quiere comprobar sola). Sin argumentos corre la matriz COMPLETA, como siempre.
    selected = [token.strip().upper() for token in (argv or sys.argv[1:]) if token.strip()]
    matrix = [
        mutation
        for mutation in MUTATIONS
        if not selected or any(str(mutation[0]).upper().startswith(token) for token in selected)
    ]
    if selected and not matrix:
        print("!! ningun rotulo casa con el filtro:", ", ".join(selected))
        return 1

    files = tuple(sorted({rel for _, rel, _, _, _ in matrix}))
    originals = {rel: (ROOT / rel).read_text(encoding="utf-8") for rel in files}
    status_before = _status(files)

    print("=== ficheros mutados ===")
    for rel in files:
        print(f"  {rel}")
    print("estado git de esos ficheros (antes):", status_before.strip() or "limpio")
    if selected:
        print("filtro de rotulos:", ", ".join(selected), f"({len(matrix)}/{len(MUTATIONS)})")

    print("\n=== linea base (sin mutacion) ===")
    for tests in sorted({m[4] for m in matrix}, key=lambda t: t):
        print(f"  {', '.join(tests)} ->", sorted(_run(tests, files)) or "ninguno")

    # Mutaciones cuyo fragmento ya no existe: NO midieron nada. Se listan al final y la sonda
    # falla, porque una matriz con huecos silenciosos afirma mas cobertura de la que tiene.
    missing: list[str] = []

    for label, rel, old, new, tests in matrix:
        path = ROOT / rel
        current = path.read_text(encoding="utf-8")
        if current != originals[rel]:
            print(
                f"\n### {label}\n  !! {rel} cambio desde el inicio de la sonda; ABORTO por seguridad"
            )
            return 1
        hits = current.count(old)
        if hits == 0:
            # Un fragmento que ya no existe es una mutacion que NO mide: la matriz perderia
            # cobertura en silencio (paso 5 de AUTO-10: M25/M26/M30/M33 se quedaron sin
            # morder asi, por deriva del codigo). Se declara y la sonda falla al final.
            print(
                f"\n### {label}\n  !! no encontre el fragmento a mutar en {rel}; revisar la sonda"
            )
            missing.append(label)
            continue
        if hits > 1:
            print(
                f"\n### {label}\n  !! el fragmento aparece {hits} veces en {rel}: el "
                f"`.replace(..., 1)` mutaria la PRIMERA y la sonda mentiria. ABORTO."
            )
            return 1
        # Escritura binaria con LF explícito: en Windows el modo texto convierte
        # ``\n`` → ``\r\n`` y la huella ``git status --porcelain`` marcaría el fichero
        # como modificado aunque el contenido lógico sea idéntico
        # (``attr/text=auto eol=lf``). ``newline="\n"`` no basta en todos los
        # intérpretes/versiones; ``write_bytes`` es inequívoco.
        path.write_bytes(current.replace(old, new, 1).encode("utf-8"))
        try:
            failed = _run(tests, (rel,))
        finally:
            restored_ok = _restore(path, rel, originals[rel])
            _drop_bytecode((rel,))
        print(f"\n### {label}")
        print("  rojo en:", ", ".join(sorted(failed)) or "NADA (la mutacion NO se detecta)")
        print(
            "  restaurado byte a byte:",
            "si" if restored_ok else "NO !! arbol restaurado por git, revisar a mano",
        )
        if not restored_ok:
            return 1

    status_after = _status(files)
    print("\n=== huella del arbol ===")
    print("estado git de esos ficheros (despues):", status_after.strip() or "limpio")
    if status_after != status_before:
        print("  !! la sonda dejo los ficheros en un estado distinto al inicial")
        return 1
    print("  intacto: la sonda no altero el arbol")
    if missing:
        print("\n  !! mutaciones SIN medir (fragmento ausente): " + "; ".join(missing))
        print("  La matriz no puede afirmar cobertura sobre esas etiquetas: sonda en ROJO.")
        return 1
    print(f"  medidas: {len(matrix)}/{len(matrix)} (ninguna se quedo sin fragmento)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
