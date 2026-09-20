# Arranque del auditor — v2.46-beta (AUTO-6 · Crash/Recovery + Concurrent AUTO)

**Fecha:** 2026-09-20 · **Ref a atacar:** `v2.46-beta` (`1.71.0-beta`) · **Pack que manda:**
[`audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./audit-pack-v2.46-auto-6-crash-recovery-concurrent-2026-09-20.md).
Si algo de este arranque contradice al pack, **manda el pack**. El plan de fase, con sus
**desviaciones declaradas**, es
[`plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md`](./plan-v2-46-auto-6-crash-recovery-concurrent-2026-09-20.md) §7.

Este documento es de **solo lectura** y existe para una cosa: que el auditor externo no gaste su
presupuesto redisculpiendo lo ya medido. Cada afirmación trae **el comando exacto** para medirla.

---

## 1. Qué se instala aquí (y por qué importa)

Hasta `v2.45`, el día AUTO se certificaba **funcionando**. AUTO-6 certifica lo que pasa cuando las
cosas van **mal**, en dos escenarios y en dos capas cada uno:

1. **Crash/Recovery** — la RAM del proceso **muere** de verdad (en la capa hermética se descarta el
   objeto worker; en la real se **mata** el proceso `scheduler_worker`) sobre un fill **parcial**, y
   el reinicio debe **reconstruir y converger**: nada duplicado, nada perdido.
2. **Concurrent AUTO** — varias instancias del motor evalúan la **misma** cuenta/barra/señal a la
   vez: **1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills correctos**.

Dos consecuencias que el auditor debe atacar:

1. **Un crash puede duplicar dinero.** Si la orden, el fill o el compromiso de capital no tienen
   identidad **estable**, el reinicio (o el segundo worker) vuelve a hacer lo mismo y el estado
   queda con doble efecto — sin que ningún test «feliz» lo note.
2. **Una carrera puede comprometer dos veces.** Si el compromiso de capital se decide con
   «leer presupuesto → reservar», dos workers apilan **dos** compromisos sobre la **misma**
   oportunidad y el presupuesto se sobrepasa sin error visible.

---

## 2. Orden de ataque recomendado (por coste/beneficio)

### A1 · El claim atómico de la reserva (lo más caro si es falso)

```bash
sed -n '1444,1472p' packages/py/application/src/bolsa_application/auto_v2_entry.py
sed -n '97,122p' packages/py/application/src/bolsa_application/reservation_store.py
sed -n '451,500p' packages/py/application/src/bolsa_application/reservation_store.py
uv run pytest apps/api-python/tests/test_auto_v46_concurrent.py -q
```

Preguntas abiertas:

- ¿La identidad de la decisión `entry_decision_id` deriva de `(cuenta, señal)` **y de nada más**?
  ¿Dos workers con la MISMA señal producen el MISMO id? ¿Y dos **cuentas** distintas que vigilen el
  mismo instrumento **no** colisionan (la cuenta tiene que entrar en la clave, porque el capital es
  por cuenta)?
- ¿Qué pasa con una señal **sin** `signal_id` (sin barra)? ¿Se conserva la identidad aleatoria
  histórica (fail-open al azar) o se comparte por accidente un id (fail-**closed** silencioso,
  vetando a otro)?
- `save_claim` con una fila **LIBERADA**: ¿se **re-compromete** (`True`, la re-entrada legítima) o
  se veta para siempre (`False`)? Ojo a la **diferencia con `save`**, que responde otra pregunta
  («¿la fila existía?») y no sirve como claim.
- ¿La comprobación de «sigue vivo» es **atómica** (una sentencia con `WHERE` + `RETURNING`) o hay
  una ventana `SELECT` → decisión → `UPDATE` donde se cuela el otro worker?
- ¿El worker que **pierde** el claim veta su emisión **con motivo declarado**
  (`reservation_already_live`), o abre igual y apila el compromiso?

### A2 · El crash hermético: ¿se pierde de verdad la RAM?

```bash
sed -n '1,40p' apps/api-python/tests/test_auto_v46_crash_recovery.py
uv run pytest apps/api-python/tests/test_auto_v46_crash_recovery.py -q
```

Preguntas abiertas:

- ¿El «reinicio» construye un worker **NUEVO** sobre los mismos espejos durables, o reutiliza el
  objeto anterior (que conservaría RAM y convertiría la prueba en un no-op)?
- ¿La reconciliación de arranque se exige **convergente** (nunca `DIVERGENT`/`UNKNOWN`), o se
  acepta cualquier veredicto?
- ¿El test exige que reiniciar **no añada ni una traza BUY más** (no doble efecto), o sólo que la
  posición cuadre al final?
- ¿La liberación de la **cola NO llenada** de la reserva parcial está exigida en un test propio, o
  quedaría oculta detrás del cierre?

### A3 · El crash real (capa del tag): qué certifica y qué no

```bash
sed -n '1,45p' apps/api-python/tests/test_crash_recovery_day_process_pg.py
grep -n "AUTO_CRASH_RECOVERY_PG_REQUIRED" .github/workflows/release-tag-ci.yml
grep -n "test_crash_recovery_day_process_pg" .github/workflows/python-ci.yml .github/workflows/release-tag-ci.yml
```

Preguntas abiertas:

- El id del instrumento se elige por **barrida pura** (`_crash_instrument_id`): ¿garantiza BUY
  **parcial** (≥2 tranchas) y SELL **completo** en toda la ventana? (Si no, el test es una moneda al
  aire ⇒ rojo espurio.) ¿Falla con **diagnóstico** si ningún candidato cumple?
- La muerte, ¿es una muerte **sucia** (`kill()`/`terminate()`, sin apagado ordenado) sobre un
  estado **durable** de fill parcial, o un reinicio «limpio» disfrazado? ¿El test **siembra** el
  parcial o lo produce el **propio proceso**?
- Tras el reinicio, ¿se exige **ni una reserva viva** al final y cero trazas de venue **LIVE**?
- ¿Qué **NO** certifica esta capa? La interrupción **en vuelo** dentro de un tick: el venue SIM
  aplica el **schedule completo de la orden en el mismo tick**, así que esa ventana **no existe**
  (§7.1.1 del pack). Está declarado en el docstring del test.

### A4 · El concurrente real: ¿la carrera es real o un `gather` disfrazado?

```bash
sed -n '1,32p' apps/api-python/tests/test_concurrent_auto_pg.py
uv run pytest apps/api-python/tests/test_concurrent_auto_pg.py -q   # requiere PG
```

Preguntas abiertas:

- ¿Son **sesiones** concurrentes sobre el mismo PG (donde cada `await` es un punto de
  interleaving), o tres turnos en serie?
- El invariante, ¿mide el **INTENT** de orden (`Σ _order_seq`) o `count(distinct venue_order_id)`?
  Medir el venue **no** vale: su identidad es determinista por `(engine, minuto, lado, símbolo,
seq)`, así que una emisión duplicada **reutiliza** el mismo id y sería financieramente
  idempotente — invisible al `count`. El **intent** sí la ve.
- ¿Se exige **una sola fila** de reserva por `(cuenta, instrumento)` y que `Σ reserved_cash` viva
  sea la cola **no llenada** (jamás × nº de workers)?
- ¿Toda instancia que **no** abre declara **por qué** (ni un veto en silencio)?

### A5 · Cableado de CI: ¿el escenario puede desaparecer sin que nadie lo note?

```bash
grep -n "test_auto_v46\|test_crash_recovery_day_process_pg\|test_concurrent_auto_pg" \
  .github/workflows/python-ci.yml .github/workflows/release-tag-ci.yml
```

Preguntas abiertas:

- Los **dos herméticos**, ¿entran por el **pase de directorio** de `apps/api-python/tests` (sin
  registro explícito que se pueda olvidar)?
- Los **dos PG**, ¿están en el `--ignore` de **los dos** jobs offline (si no, skipearían en mudo
  allí) y a la vez en **pasos dedicados** del `lifecycle-pg` del tag?
- ¿Cada paso dedicado tiene `set -o pipefail`, `tee` a log y **guard anti-skip** (log no vacío +
  `grep` de `skipped`) con `if: always()`?
- ¿Los comentarios están **fuera** del bloque `run: >`? (Un `#` intercalado convirtió un step en
  936 tests en `V2.40.2`.)

---

## 3. Mutaciones que YA se midieron (no las redisculpas)

La matriz completa está en §4 del pack: **6/6 mordieron** (señal consumida, liberación por fill,
gate de reconciliación, idempotencia de `execution_events`, identidad determinista y el perdedor
del claim), con la huella `sha256` **intacta** antes/después. Si encuentras una **séptima** forma
de romper el invariante que **no** esté en la tabla, ese sí es un hallazgo.

Aviso de método reproducido en esta fase: la sonda **aborta** si encuentra `# MUTATION:` al
arrancar (una corrida interrumpida a mitad de mutación no puede pasar por «original»), y **no**
asume el DSN fast-fail: **sondea el puerto** primero, porque en Windows un puerto cerrado no
rechaza al instante y las suites de `apps/api-python` se quedan **colgadas** en lugar de devolver
el rojo.

---

## 4. Comandos exactos de verificación

```bash
# El gobernador NO se movió: debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run --no-sync python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Cubo estático
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# Capa hermética nueva (por commit)
uv run pytest apps/api-python/tests/test_auto_v46_crash_recovery.py \
  apps/api-python/tests/test_auto_v46_concurrent.py -q

# Matriz de mutaciones (mide y restaura; deja la huella intacta)
uv run --no-sync python apps/api-python/scripts/v2_46_mutation_audit.py

# Bloques offline extraídos del YAML (medida por JUnit XML, no copia a mano)
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml \
  quality --with-pg-ignores
uv run --no-sync python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml \
  python --with-pg-ignores

# Capa real. CON PostgreSQL alcanzable se mide YA en local (sin el gate, un skip es honesto):
#   env AUTO_CRASH_RECOVERY_PG_REQUIRED=1 / AUTO_CONCURRENT_PG_REQUIRED=1 → un skip es FALLO duro.
# OJO: no la corras en paralelo con otra sesión de pytest contra la misma base (el purgado de
# residuos del conftest borra las cuentas e instrumentos `inst-%` de la otra sesión).
uv run pytest apps/api-python/tests/test_crash_recovery_day_process_pg.py -q --tb=short -rs
uv run pytest apps/api-python/tests/test_concurrent_auto_pg.py -q --tb=short -rs
```

---

## 5. Qué NO es un hallazgo (declarado de antemano)

- Que el día real **no** se interrumpa «en mitad del fill»: el venue SIM aplica el schedule
  **completo** de una orden **en el mismo tick** y esa ventana **no existe**. Se certifica el
  estado durable del parcial (orden cortada con cola viva + reserva viva) y su cierre contable tras
  la muerte; **no se siembra nada** (§7.1.1 del pack).
- Que en Windows la muerte sea `terminate()` y no `SIGKILL`: el `SIGKILL` real es el del CI Linux;
  el test usa el máximo de cada plataforma y lo declara (§7.1.2).
- Que el claim atómico haya **tocado producción** (`entry_decision_id` + `save_claim`): el
  escenario concurrente **demostró** el defecto y el arreglo es el **mínimo** previsto por el plan
  (identidad determinista de la señal), **sin** locks explícitos y **sin** migración.
- Que la **byte-identidad** con el flag del optimizador **OFF** se conserve en **producto** pero no
  en la **identidad de la reserva** (de `dec-<uuid4>` a determinista por `(cuenta, señal)`): es el
  arreglo autorizado y su efecto **es** el invariante nuevo. Con ids aleatorios una identidad de
  reserva **no podía repetirse**, así que la distinción `save`/`save_claim` era **inalcanzable** en
  cualquier flujo histórico (§7.1.4 del pack). Con `AUTO-ENGINE-SIM-V2=0` no cambia nada.
- Que **`save` y `save_claim` sean métodos distintos**: `save` responde «¿la fila existía?»
  (replay) y `save_claim` responde «¿soy el dueño del compromiso **vivo**?» (concurrencia).
  Confundirlos veta la re-entrada legítima sobre una identidad liberada, o compromete dos veces el
  capital (§2.1 del pack).
- Que el gemelo PG **no** arranque tres procesos `scheduler_worker`: usa tres **sesiones**
  concurrentes (decisión del owner, §0 del plan); escalar a procesos es el **plan B declarado**.
- Que el MAE/MFE **no** se calibre y que no haya productor de economía en el tick: se **recoge**, no
  decide (`AUTO-7`).
- Que el día real cierre por el **seam durable** (`holdingDeadlineAt` vencido + reinicio) y no por
  geometría: precio SIM **plano** y horizonte de **21–90 días**.
- Que **no** se puedan correr dos sesiones de pytest en paralelo contra la misma base: el barrido de
  residuos del conftest es de **sesión**. Es un límite de **método** del arnés, medido y declarado;
  el gate del tag corre cada escenario en paso **dedicado**.
- Que el sello (§9 del pack) esté **pendiente**: las cifras locales están medidas y las de CI las
  produce el run. Ninguna cifra se atribuye a un run que no exista.

---

## 6. Formato del hallazgo

```
P0/P1/P2 · afirmación · ruta:línea · comando exacto · salida · ¿ya declarado en §4/§5/§7 del pack?
```

Las cifras del **tag** (`lifecycle-pg` con sus dos pasos dedicados) citan el run de `Release tag CI`
que las produjo; las locales citan el comando y su salida (§5 del pack). Ninguna cifra se atribuye a
un artefacto que no la produjo.
