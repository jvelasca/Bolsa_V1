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

AUTO-11 (estado Adaptive durable: cooldown reconstruido del journal) añade:

* **M42 (identidad sin cuenta)** — si el turno se identifica sin la cuenta, dos cuentas distintas
  comparten `decision_id` y la historia de una se lee como la de la otra.
* **M43 (fila sin plan)** — si sin plan se escribe una entrada vacía, el journal afirma "Adaptive
  evaluó y no recomendó nada" donde el hecho es "Adaptive no evaluó".
* **M44 (régimen disfrazado)** — si el régimen ausente de la recomendación se publica `UNKNOWN`,
  "no medido" se lee como medido.
* **M45 (contador normalizado)** — si un `0` entra al mapa de pausas, un contador apagado se
  reconstruye como una pausa viva.
* **M46 (racha sin corte)** — si la versión sigue contando después de reactivarse, el cooldown se
  alarga y una pausa ya cerrada revive al reiniciar.
* **M47 (saturación sin techo)** — si el contador deja de recortarse al umbral, un valor gigante
  afirma una antigüedad que la historia no prueba.
* **M48 (dedupe caído)** — si un reintento del sink cuenta dos veces el mismo turno, la racha se
  infla y se afirma un turno que no ocurrió.
* **M49 (historia corta silenciada)** — si no se declara que la ventana no se llenó, un suelo se
  lee como una cuenta completa.
* **M50 (hueco aprobado)** — si un ciclo **con** traza confirmada se declara además `missing`, la
  reconciliación grita huecos que no existen y deja de ser creíble.
* **M51 (no preguntado disfrazado)** — si el ciclo que nunca se consultó pasa a `missing`, un
  hueco operativo se disfraza de journal roto.
* **M52 (trazas contadas como filas)** — si el duplicado cuenta la entrada de decisión del mismo
  `decision_id`, todo ciclo normal reporta una traza doble.
* **M53 (filas de más silenciadas)** — si la lectura deja de declarar `extra_rows`, un reintento
  real y una fila de decisión se vuelven indistinguibles.
* **M54 (antigüedad por texto)** — si el denominador de R se elige comparando `created_at` como
  cadena, un formato con otro offset elige la reserva equivocada.
* **M55 (fecha ilegible silenciada)** — si el desempate sin fecha legible deja de declararse, el
  orden se decide por una fecha que se supone.
* **M56 (contador de salida)** — si la evidencia durable publica el estado POSTERIOR a decidir,
  la reconstrucción siembra un cooldown que el turno no usó.
* **M57 (recuperación que no siembra)** — si el journal se lee y el contador se descarta, la
  lectura paga I/O para nada y el reinicio vuelve a levantar la pausa.
* **M58 (reconciliación muda)** — si los huecos del rastro de ciclo se declaran limpios, la
  ventana `RESERVATION COMMITTED → CRASH → NO JOURNAL` vuelve a ser invisible.
* **M59 (flag OFF ignorado)** — si con Adaptive apagado el arranque paga la lectura igual, el
  flag deja de ser una frontera de comportamiento.

AUTO-12 (confianza estadística: muestra efectiva, ventanas, decay y encogimiento) añade:

* **M60 (muestra bruta por medida)** — si ``effective_n`` cuenta los ciclos sin R, una celda de
  40 ciclos con 4 medidos declara una muestra que no sostiene su número.
* **M61 (deterioro severo rebajado)** — si la ventana reciente en negativo deja de declararse
  ``SEVERE``, la estrategia que ha dejado de funcionar vuelve a leerse como sana.
* **M62 (techo sin poner)** — si ``decay = UNKNOWN`` deja de poner techo a la confianza, una
  muestra que no se pudo leer se premia como una que sí.
* **M63 (fila sin instante silenciada)** — si las filas sin instante legible dejan de declararse,
  la ventana reciente se calcula sobre un orden que nadie probó.
* **M64 (medición compuesta disuelta)** — si la completitud se declara ``COMPLETE`` sin combinar
  R, R neto y PnL, un cubo no medido pasa por medido.
* **M65 (cobertura fingida)** — si la cobertura de coste se afirma sobre la muestra bruta, se
  declara cubierto lo que no se midió.
* **M66 (orden por llegada)** — si las ventanas se recortan en el orden de ENTRADA en vez de por
  instante, la ventana reciente es la que el llamante puso la última.
* **M67 (recencia inventada)** — si sin instantes legibles se construye igualmente la ventana
  reciente, se finge una cronología que no existe.
* **M68 (encogimiento neutralizado)** — si el prior del encogimiento cae a ``0``, el reparto
  vuelve a pesar igual una muestra de 12 que una de 180 (*winner chasing*).
* **M69 (descuento por deterioro neutralizado)** — si el factor de ``decay SEVERE`` deja de
  aplicarse, el deterioro se declara pero el reparto lo ignora.
* **M70 (cierre por el primer fill)** — si el instante de cierre toma el PRIMER fill del ciclo,
  la ventana reciente se ordena con la fecha de entrada y no con la del resultado.
* **M71 (confianza no cableada)** — si el worker construye la confianza y no la pasa al plan, el
  cálculo se paga y el reparto publica el histórico.

AUTO-13 (Adaptive Data Gate: salud de la EVIDENCIA separada de la salud de la estrategia) añade:

* **M72 (efecto invertido)** — si la tabla estado→efecto deja de mapear ``OK`` a ``ADAPTS``, un
  gate sano limita el reparto que debía permitir.
* **M73 (OK por defecto)** — si un fallo del sink deja de producir ``DEGRADED``, el hecho se mide
  pero el gate lo publica como salud completa.
* **M74 (antigüedad que no bloquea)** — si la antigüedad del journal deja de bloquear al pasar el
  umbral, el journal muerto del §21 vuelve a ser invisible.
* **M75 (contador sin reset)** — si un éxito de publicación no resetea la racha, un fallo aislado
  arrastra y el estado se congela sin motivo.
* **M76 (ancla sin corroborar)** — si la antigüedad bloquea sin un fallo propio, un journal sano
  tras un hueco largo queda ``BLOCKED`` para siempre (``adaptive = None`` ⇒ no escribe ⇒ deadlock).
* **M77 (cadencia ignorada)** — si la antigüedad medida en segundos no se convierte a ciclos con la
  cadencia declarada, ``journal_age_cycles`` afirma una antigüedad que no es la de la regla.
* **M78 (``BLOCKED`` adaptando)** — si el tick con evidencia durable muerta sigue construyendo el
  plan, el único caso en que no se debe adaptar vuelve a adaptar.
* **M79 (``STALE`` reactivando)** — si una pausa viva levanta su cooldown con la evidencia ilegible,
  la reactivación se decide justo contra el dato que no se pudo leer.
* **M80 (``DEGRADED`` repartiendo con la confianza)** — si el gate limita y el plan recibe igual la
  confianza, se estrecha por la evidencia fina que el gate acababa de declarar no fiable.
* **M81 (régimen siempre disponible)** — si ``regime_available`` deja de declarar el hueco de
  régimen, el §20 se mide pero nunca limita.
* **M82 (completitud por el eje opcional)** — si la completitud del gate se compone con el net-R
  **opcional** (cuyo hueco cae por diseño al eje moneda) en vez de con los ejes que Adaptive exige,
  cualquier despliegue sin coste medido queda ``DEGRADED`` y apaga la confianza de AUTO-12.

AUTO-13 paso 4 (``RECOVERING`` y la rampa de reincorporación, §23/§24) añade:

* **M83 (rampa que sube por tiempo)** — si el escalón deja de depender de los ciclos de evidencia
  medidos, una versión vuelve al peso pleno por el mero paso del reloj: exactamente el salto que
  §24 prohíbe.
* **M84 (rampa que ensancha)** — si el ``min`` con el reparto pasa a ``max``, el techo se convierte
  en suelo y la reincorporación **premia**: lo contrario de lo que una vuelta gradual significa.
* **M85 (rampa que llega a 0)** — si el escalón inicial de una evidencia deteriorada es ``0``, la
  rampa deja de ser reincorporación y se vuelve una pausa encubierta sin pasar por la rotación.
* **M86 (pausa que publica su rampa)** — si la rotación devuelve a pausa y el escalón no se
  descarta, se publica una reincorporación que NO se aplicó (§24: la protección manda).
* **M87 (recuperación no derivada)** — si el estado operativo deja de derivarse del escalón, una
  versión que vuelve por la rampa se publica como ``active`` a peso pleno.
* **M88 (reincorporación sin corte probado)** — si el corte se fecha sin haber visto la pausa que
  lo precede (a través de un turno ilegible), se afirma una reincorporación que no se midió.
* **M89 (ventana ilegible declarada disponible)** — si el hueco de fechas deja de declararse, la
  rampa sube sobre evidencia que no se pudo ordenar (``recent_unavailable`` de AUTO-12, ignorado).
* **M90 (evidencia anterior al corte)** — si la cuenta no descarta los ciclos previos a la
  reactivación, la rampa sube con el edge que la estrategia tenía ANTES de ser pausada.
* **M91 (rampa no cableada)** — si el worker construye la evidencia de recuperación y no la pasa al
  plan, el cálculo se paga y la evidencia durable publica un plan sin rampa.
* **M92 (memoria de la rampa no sembrada)** — si el arranque ignora ``reactivated_at`` del journal,
  la reincorporación ocurrida ANTES del reinicio se olvida y la versión vuelve a peso pleno.
* **M93 (transición no fechada en el tick)** — si la pausa → activa observada por el proceso no se
  fecha, la versión corre un tick con peso pleno antes de que la rampa entre en el siguiente: el
  salto que §24 prohíbe se cuela por la mitad que no sobrevive al reinicio (la del proceso vivo).

DSN fast-fail para las suites de ``apps/api-python``: el teardown de
``apps/api-python/tests/conftest.py`` (``purge_all_residuals``) intenta conectar a Postgres y,
sin PG levantado, se queda colgado. Se inyecta un ``DATABASE_URL`` a un puerto local cerrado: el
``connect`` falla al instante y el ``except`` del teardown lo traga, de modo que la sonda devuelve
los rojos con NOMBRE en vez de un ``TIMEOUT`` mudo.

**Matiz medido en V2.52**: "puerto local cerrado" **no** basta en toda máquina. En este entorno un
firewall **descarta** el paquete en vez de rechazarlo (medido: `psycopg.connect` a
`127.0.0.1:9` sin timeout no termina nunca; con `PGCONNECT_TIMEOUT=2` tarda 2.03 s y falla), y
psycopg **no** trae timeout por defecto, así que la corrida se comía los 600 s del ``timeout`` de
la sonda y devolvía ``<TIMEOUT>`` en vez del nombre del test. Ahora se exporta además
``PGCONNECT_TIMEOUT``: el teardown falla en segundos y el rojo llega con nombre.

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
AUTO_ADAPTIVE_CONFIDENCE = (
    "packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py"
)
AUTO_ADAPTIVE_DATA_GATE = (
    "packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py"
)
CYCLE_RISK = "packages/py/application/src/bolsa_application/cycle_risk.py"
FEED = "packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py"
AUTO_CYCLE_JOURNAL = "packages/py/application/src/bolsa_application/auto_cycle_journal.py"
REGIME_READER = "packages/py/application/src/bolsa_application/auto_cycle_regime_reader.py"
ADAPTIVE_JOURNAL = "packages/py/application/src/bolsa_application/auto_adaptive_journal.py"
ADAPTIVE_RECOVERY = "packages/py/application/src/bolsa_application/auto_adaptive_recovery.py"
CYCLE_TRACE = "packages/py/application/src/bolsa_application/auto_cycle_reconciliation.py"
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
T_CONFIDENCE = "packages/py/analytics/tests/test_auto_adaptive_confidence.py"
T_FEED = "packages/py/application/tests/test_auto_self_evaluation_feed.py"
T_CONFIDENCE_SEAM = "apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py"
T_DATA_GATE = "packages/py/analytics/tests/test_auto_adaptive_data_gate.py"
T_DATA_GATE_SEAM = "apps/api-python/tests/test_auto_v54_auto13_data_gate_seam.py"
T_DATA_GATE_WIRE = "apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py"
T_RECOVERY_SEAM = "apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py"
T_ADAPTIVE_ENTRY = "packages/py/application/tests/test_auto_adaptive_entry.py"
T_CYCLE_RISK = "packages/py/application/tests/test_cycle_risk.py"
T_CYCLE_RISK_SEAM = "apps/api-python/tests/test_auto_v50_auto9_cycle_risk_seam.py"
T_CYCLE_JOURNAL = "packages/py/application/tests/test_auto_cycle_journal.py"
T_REGIME_READER = "packages/py/application/tests/test_auto_cycle_regime_reader.py"
T_CYCLE_JOURNAL_SEAM = "apps/api-python/tests/test_auto_v51_auto10_cycle_journal_seam.py"
T_REGIME_SEAM = "apps/api-python/tests/test_auto_v51_auto10_cycle_regime_seam.py"
T_ADAPTIVE_JOURNAL = "packages/py/application/tests/test_auto_adaptive_journal.py"
T_ADAPTIVE_RECOVERY = "packages/py/application/tests/test_auto_adaptive_recovery.py"
T_CYCLE_TRACE = "packages/py/application/tests/test_auto_cycle_reconciliation.py"
T_ADAPTIVE_SEAM = "apps/api-python/tests/test_auto_v52_auto11_adaptive_state_seam.py"
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
        # AUTO-12: el riesgo por ciclo se mide UNA sola vez en una local (la leen el informe y la
        # confianza). La sonda apunta a esa local en vez de a la llamada inline, que ya no existe.
        "        cycle_risk = await self._v2_cycle_risk(fills)\n",
        "        cycle_risk = None\n",
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
        # El cuerpo del sink de AUTO-10 y el de AUTO-11 son calcados: el fragmento lleva la
        # cola del ``except`` (unica de este sink) para que ``.replace(..., 1)`` no mute en
        # silencio el sink de la recomendacion Adaptive en vez de la traza del ciclo.
        "            await repository.append(entry)\n"
        "            await session.commit()\n"
        "        except Exception:\n"
        "            # Fail-open DE VERDAD: una escritura fallida deja la sesión envenenada y sin\n",
        "            await repository.append(entry)\n"
        "            if False:\n"
        "                await session.commit()\n"
        "        except Exception:\n"
        "            # Fail-open DE VERDAD: una escritura fallida deja la sesión envenenada y sin\n",
        (T_CYCLE_JOURNAL_SEAM,),
    ),
    (
        "M39 (sin confirmar): una fila con ese decision_id se cree sin mirar el payload",
        REGIME_READER,
        # La identidad de la traza vive en un solo sitio (``_is_trace``) desde V2.52: si se
        # comprobara otra vez en el camino de lectura, la copia seria inobservable y la sonda
        # afirmaria una cobertura que no tiene (la leccion del 33/33). Muta la guarda COMPARTIDA.
        '    return _clean(_payload_of(entry).get("cycleId")) == cycle_id\n',
        "    return True\n",
        (T_REGIME_READER, T_REGIME_SEAM),
    ),
    (
        "M40 (dedupe por llegada): gana la fila mas nueva aunque no confirme el ciclo",
        REGIME_READER,
        "        regime = next(\n"
        "            (found for entry in traces if (found := _confirmed_regime(entry, cycle_id))),\n"
        "            None,\n"
        "        )\n",
        "        regime = _confirmed_regime(candidates[0], cycle_id)\n",
        (T_REGIME_READER,),
    ),
    (
        "M41 (duplicado silencioso): la lectura deja de declarar las filas de mas",
        REGIME_READER,
        "            if len(traces) > 1:\n",
        "            if False:\n",
        (T_REGIME_READER, T_REGIME_SEAM),
    ),
    (
        "M42 (identidad sin cuenta): el turno se identifica sin la cuenta, dos cuentas colisionan",
        ADAPTIVE_JOURNAL,
        '    key = f"{_clean(account_id)}\\x1f{stamp}"\n',
        '    key = f"{stamp}"\n',
        (T_ADAPTIVE_JOURNAL,),
    ),
    (
        "M43 (fila sin plan): sin recomendacion se escribe una entrada vacia en vez de no-op",
        ADAPTIVE_JOURNAL,
        "    if plan is None:\n        return None\n",
        "    if False:\n        return None\n",
        (T_ADAPTIVE_JOURNAL,),
    ),
    (
        "M44 (regimen disfrazado): el regimen ausente de la recomendacion se publica UNKNOWN",
        ADAPTIVE_JOURNAL,
        '        "regime": regime or None,\n',
        '        "regime": regime or "UNKNOWN",\n',
        (T_ADAPTIVE_JOURNAL,),
    ),
    (
        "M45 (contador normalizado): un 0 entra al mapa de pausas como si fuera una pausa",
        ADAPTIVE_JOURNAL,
        "        if count > 0:\n",
        "        if count >= 0:\n",
        (T_ADAPTIVE_JOURNAL,),
    ),
    (
        "M46 (racha sin corte): la version sigue contando despues de reactivarse",
        ADAPTIVE_RECOVERY,
        "            if paused is None or version not in paused:\n",
        "            if paused is None:\n",
        (T_ADAPTIVE_RECOVERY,),
    ),
    (
        "M47 (saturacion sin techo): el contador publicado deja de recortarse al umbral",
        ADAPTIVE_RECOVERY,
        "        counts[version] = min(streak, cap)\n",
        "        counts[version] = streak\n",
        (T_ADAPTIVE_RECOVERY,),
    ),
    (
        "M48 (dedupe caido): un reintento del sink cuenta dos veces el mismo turno",
        ADAPTIVE_RECOVERY,
        "        if key in seen:\n",
        "        if False:\n",
        (T_ADAPTIVE_RECOVERY,),
    ),
    (
        "M49 (historia corta silenciada): no se declara que la racha es un suelo",
        ADAPTIVE_RECOVERY,
        "        insufficient_history=len(ordered) < size,\n",
        "        insufficient_history=False,\n",
        (T_ADAPTIVE_RECOVERY,),
    ),
    (
        "M50 (hueco aprobado): un ciclo CON traza confirmada se declara ademas como missing",
        CYCLE_TRACE,
        "        if cycle_id in confirmed:\n            continue\n",
        "        if False:\n            continue\n",
        (T_CYCLE_TRACE, T_ADAPTIVE_SEAM),
    ),
    (
        "M51 (no preguntado disfrazado): el ciclo que nunca se consulto pasa a ser un hueco",
        CYCLE_TRACE,
        "        if cycle_id not in asked:\n            unrequested.append(cycle_id)\n            continue\n",
        "        if False:\n            unrequested.append(cycle_id)\n            continue\n",
        (T_CYCLE_TRACE,),
    ),
    (
        "M52 (trazas contadas como filas): el duplicado cuenta la entrada de decision del ciclo",
        REGIME_READER,
        "            if len(traces) > 1:\n",
        "            if len(candidates) > 1:\n",
        (T_REGIME_READER, T_REGIME_SEAM),
    ),
    (
        "M53 (filas de mas silenciadas): la lectura deja de declarar extra_rows",
        REGIME_READER,
        "            if extra > 0:\n",
        "            if False:\n",
        (T_REGIME_READER, T_REGIME_SEAM),
    ),
    (
        "M54 (antiguedad por texto): el denominador de R se elige comparando created_at como cadena",
        CYCLE_RISK,
        "    instant = _instant(row.created_at)\n"
        "    return (\n"
        "        0 if instant is not None else 1,\n"
        "        instant.timestamp() if instant else 0.0,\n"
        "        _clean(row.reservation_id),\n"
        "    )\n",
        "    instant = _instant(row.created_at)\n"
        "    return (\n"
        "        0,\n"
        "        0.0,\n"
        "        _clean(row.created_at),\n"
        "    )\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M55 (fecha ilegible silenciada): el desempate sin fecha legible deja de declararse",
        CYCLE_RISK,
        "        notes.append(CYCLE_RISK_MULTIPLE_RESERVATIONS)\n        if undated:\n",
        "        notes.append(CYCLE_RISK_MULTIPLE_RESERVATIONS)\n        if False:\n",
        (T_CYCLE_RISK,),
    ),
    (
        "M56 (contador de salida): la evidencia durable publica el estado POSTERIOR a decidir",
        WORKER,
        "            paused_cycles=self._v2_adaptive_paused_cycles_entered,\n",
        "            paused_cycles=self._v2_adaptive_paused_cycles,\n",
        (T_ADAPTIVE_SEAM,),
    ),
    (
        "M57 (recuperacion que no siembra): el journal se lee y el contador se descarta",
        WORKER,
        "        self._v2_adaptive_paused_cycles = dict(reading.paused_cycles)\n",
        "        self._v2_adaptive_paused_cycles = {}\n",
        (T_ADAPTIVE_SEAM,),
    ),
    (
        "M58 (reconciliacion muda): los huecos del rastro de ciclo se declaran limpios",
        WORKER,
        "        if report.clean:\n",
        "        if True:\n",
        (T_ADAPTIVE_SEAM,),
    ),
    (
        "M59 (flag OFF ignorado): con Adaptive apagado el arranque paga la lectura igual",
        WORKER,
        "        if not self._v2_tunables.adaptive_enabled:\n            return\n",
        "        if False:\n            return\n",
        (T_ADAPTIVE_SEAM,),
    ),
    (
        "M60 (muestra bruta por medida): effective_n cuenta los ciclos sin R",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    sample_size = sum(cell.cycles for cell in cells)\n"
        "    effective_n = sum(cell.cycles - cell.cycles_without_risk for cell in cells)\n",
        "    sample_size = sum(cell.cycles for cell in cells)\n"
        "    effective_n = sum(cell.cycles for cell in cells)\n",
        (T_CONFIDENCE,),
    ),
    (
        "M61 (deterioro severo rebajado): la ventana reciente en negativo deja de ser SEVERE",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    if recent_r < 0:\n        return ADAPTIVE_DECAY_SEVERE\n",
        "    if False:\n        return ADAPTIVE_DECAY_SEVERE\n",
        (T_CONFIDENCE,),
    ),
    (
        "M62 (techo sin poner): decay UNKNOWN deja de limitar la confianza",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    if decay == ADAPTIVE_DECAY_UNKNOWN:\n"
        "        level = _ceiling(level, ADAPTIVE_CONFIDENCE_MEDIUM)\n",
        "    if False:\n        level = _ceiling(level, ADAPTIVE_CONFIDENCE_MEDIUM)\n",
        (T_CONFIDENCE,),
    ),
    (
        "M63 (fila sin instante silenciada): el orden sin fecha legible deja de declararse",
        AUTO_ADAPTIVE_CONFIDENCE,
        "        if undated:\n"
        "            # Hay filas sin instante: van al final y la ventana reciente puede contenerlas.\n",
        "        if False:\n"
        "            # Hay filas sin instante: van al final y la ventana reciente puede contenerlas.\n",
        (T_CONFIDENCE,),
    ),
    (
        "M64 (medicion compuesta disuelta): la completitud se declara COMPLETE sin combinar",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    completeness = combine_measurements(\n"
        "        row.risk_measurement,\n"
        "        row.net_r_measurement,\n"
        "        row.results_measurement,\n"
        "    )\n",
        "    completeness = MEASUREMENT_COMPLETE\n",
        (T_CONFIDENCE,),
    ),
    (
        "M65 (cobertura fingida): la cobertura de coste se afirma sobre la muestra bruta",
        AUTO_ADAPTIVE_CONFIDENCE,
        "        cost_coverage=_coverage(long_facts.cost_n, sample_size),\n",
        "        cost_coverage=_coverage(sample_size, sample_size),\n",
        (T_CONFIDENCE,),
    ),
    (
        "M66 (orden por llegada): las ventanas se recortan en el orden de ENTRADA",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    dated.sort(key=lambda item: (item[0], item[1], item[2]))\n",
        "    dated.sort(key=lambda item: item[2])\n",
        (T_CONFIDENCE,),
    ),
    (
        "M67 (recencia inventada): sin instantes legibles se construye la ventana reciente",
        AUTO_ADAPTIVE_CONFIDENCE,
        "    if undated >= len(ordered):\n",
        "    if False:\n",
        (T_CONFIDENCE,),
    ),
    (
        "M68 (encogimiento neutralizado): el prior del encogimiento cae a 0",
        AUTO_ADAPTIVE,
        "        prior = max(0.0, float(resolved.confidence_prior))\n",
        "        prior = 0.0\n",
        (T_ADAPTIVE,),
    ),
    (
        "M69 (descuento neutralizado): el factor de decay SEVERE deja de aplicarse",
        AUTO_ADAPTIVE,
        "        shrink *= max(0.0, float(policy.severe_decay_factor))\n",
        "        shrink *= 1.0\n",
        (T_ADAPTIVE,),
    ),
    (
        "M70 (cierre por el primer fill): el instante de cierre toma el PRIMER fill del ciclo",
        FEED,
        "    return max(instants).isoformat()\n",
        "    return min(instants).isoformat()\n",
        (T_FEED,),
    ),
    (
        "M71 (confianza no cableada): el worker la construye y no la pasa al plan",
        WORKER,
        "            confidence=confidence,\n",
        "            confidence=None,\n",
        (T_CONFIDENCE_SEAM,),
    ),
    (
        "M72 (efecto invertido): la tabla estado->efecto deja de mapear OK a ADAPTS",
        AUTO_ADAPTIVE_DATA_GATE,
        "    DATA_GATE_OK: DATA_GATE_ADAPTS,\n",
        "    DATA_GATE_OK: DATA_GATE_LIMITS,\n",
        (T_DATA_GATE,),
    ),
    (
        "M73 (OK por defecto): un fallo del sink deja de producir DEGRADED",
        AUTO_ADAPTIVE_DATA_GATE,
        "    if degraded_notes:\n"
        "        return _reading(DATA_GATE_DEGRADED, notes=degraded_notes, **facts)\n",
        "    if False:\n"
        "        return _reading(DATA_GATE_DEGRADED, notes=degraded_notes, **facts)\n",
        (T_DATA_GATE,),
    ),
    (
        "M74 (antiguedad que no bloquea): el journal muerto deja de bloquear al pasar el umbral",
        AUTO_ADAPTIVE_DATA_GATE,
        "    if age is not None and age >= int(resolved.journal_gap_blocked):\n",
        "    if False:\n",
        (T_DATA_GATE,),
    ),
    (
        "M75 (contador sin reset): un exito de publicacion no resetea la racha",
        WORKER,
        "        self._v2_adaptive_sink_failures = 0\n",
        "        self._v2_adaptive_sink_failures = self._v2_adaptive_sink_failures\n",
        (T_DATA_GATE_SEAM,),
    ),
    (
        "M76 (ancla sin corroborar): la antiguedad bloquea sin un fallo de escritura propio",
        WORKER,
        "        if failures <= 0:\n            return None\n",
        "        if False:\n            return None\n",
        (T_DATA_GATE_SEAM,),
    ),
    (
        "M77 (cadencia ignorada): la antiguedad en segundos no se convierte a ciclos",
        AUTO_ADAPTIVE_DATA_GATE,
        "    return int(elapsed // cycle)\n",
        "    return int(elapsed)\n",
        (T_DATA_GATE,),
    ),
    (
        "M78 (BLOCKED adaptando): el tick con evidencia durable muerta sigue construyendo plan",
        WORKER,
        "        if reading.blocks_adaptation:\n",
        "        if False:\n",
        (T_DATA_GATE_WIRE,),
    ),
    (
        "M79 (STALE reactivando): una pausa viva levanta su cooldown con la evidencia ilegible",
        WORKER,
        "        if reading.effect != DATA_GATE_FREEZES or not live:\n            return live\n",
        "        if True:\n            return live\n",
        (T_DATA_GATE_WIRE,),
    ),
    (
        "M80 (DEGRADED repartiendo): el plan recibe la confianza que el gate declaro no fiable",
        WORKER,
        "            confidence=None if reading.limits_adaptation else confidence,\n",
        "            confidence=confidence,\n",
        (T_DATA_GATE_WIRE,),
    ),
    (
        "M81 (regimen siempre disponible): el hueco de regimen se mide y nunca limita",
        WORKER,
        "        return (\n"
        "            coerce_market_regime(regime) != ADAPTIVE_REGIME_UNKNOWN\n"
        "            or to_market_regime(regime) != ADAPTIVE_REGIME_UNKNOWN\n"
        "        )\n",
        "        return True\n",
        (T_DATA_GATE_WIRE,),
    ),
    (
        "M82 (completitud por el eje opcional): el net-R sin medir apaga la confianza",
        WORKER,
        "            completeness = combine_measurements(\n"
        "                *(\n"
        "                    combine_measurements(row.risk_measurement, row.results_measurement)\n"
        "                    for row in rows\n"
        "                )\n"
        "            )\n",
        "            completeness = combine_measurements(\n"
        "                *(row.net_r_measurement for row in rows)\n"
        "            )\n",
        (T_DATA_GATE_WIRE,),
    ),
    (
        "M83 (rampa que sube por tiempo): el escalon deja de depender de la evidencia medida",
        AUTO_ADAPTIVE,
        "    index = min(len(steps) - 1, cycles // per)\n",
        "    index = len(steps) - 1\n",
        (T_ADAPTIVE,),
    ),
    (
        "M84 (rampa que ensancha): el TECHO del reparto se convierte en suelo",
        AUTO_ADAPTIVE,
        "            multipliers[version] = _clamp_unit(min(multipliers[version], float(reading.step)))\n",
        "            multipliers[version] = _clamp_unit(max(multipliers[version], float(reading.step)))\n",
        (T_ADAPTIVE,),
    ),
    (
        "M85 (rampa que llega a 0): el escalon inicial de una evidencia deteriorada es 0",
        AUTO_ADAPTIVE,
        "            step=steps[0],\n            step_index=0,\n",
        "            step=0.0,\n            step_index=0,\n",
        (T_ADAPTIVE,),
    ),
    (
        "M86 (pausa que publica su rampa): el escalon de una version pausada no se descarta",
        AUTO_ADAPTIVE,
        "            if version and not rotation.is_paused(version):\n",
        "            if version:\n",
        (T_ADAPTIVE,),
    ),
    (
        "M87 (recuperacion no derivada): una version que vuelve por la rampa se publica active",
        AUTO_ADAPTIVE,
        "            if reading is not None and reading.step < 1.0:\n",
        "            if False:\n",
        (T_ADAPTIVE,),
    ),
    (
        "M88 (reincorporacion sin corte probado): se fecha a traves de un turno ilegible",
        ADAPTIVE_RECOVERY,
        "        if proven and started_at is not None:\n",
        "        if started_at is not None:\n",
        (T_ADAPTIVE_RECOVERY,),
    ),
    (
        "M89 (ventana ilegible declarada disponible): la rampa sube sobre fechas no ordenables",
        FEED,
        "            window_available=dated and recent_available,\n",
        "            window_available=True,\n",
        (T_FEED,),
    ),
    (
        "M90 (evidencia anterior al corte): la cuenta no descarta los ciclos previos a la pausa",
        FEED,
        "        if instant is None or instant <= since:\n",
        "        if instant is None:\n",
        (T_FEED,),
    ),
    (
        "M91 (rampa no cableada): el worker la construye y no la pasa al plan",
        WORKER,
        "                recovery=evidence or None,\n",
        "                recovery=None,\n",
        (T_RECOVERY_SEAM,),
    ),
    (
        "M92 (memoria de la rampa no sembrada): el corte durable del journal no llega a la rampa",
        WORKER,
        "        self._v2_adaptive_reactivated_at = dict(reading.reactivated_at)\n",
        "        self._v2_adaptive_reactivated_at = {}\n",
        (T_RECOVERY_SEAM,),
    ),
    (
        "M93 (transicion no fechada en el tick): la reincorporacion observada no se fecha",
        WORKER,
        "        if fresh:\n            stamp = self._v2_instant()\n",
        "        if False:\n            stamp = self._v2_instant()\n",
        (T_RECOVERY_SEAM,),
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
        # V2.52: el puerto cerrado NO basta donde un firewall DESCARTA el paquete (medido: sin
        # timeout, el connect no termina nunca y la sonda devolvía ``<TIMEOUT>`` en vez del nombre
        # del test). psycopg no trae timeout por defecto; con él, el teardown falla en segundos.
        env["PGCONNECT_TIMEOUT"] = "5"
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
