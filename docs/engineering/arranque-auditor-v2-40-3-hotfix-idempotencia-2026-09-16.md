# Arranque auditor externo — V2.40.3 / Hotfix de la clave de idempotencia financiera (colisión por recorte) + invariante del A9 sobre el ledger real (2026-09-16)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.40.3**. Auditas **desde GitHub**, sin acceso al
entorno local.

- **Delta de CÓDIGO a auditar:** `11e2cb83` (base auditada; era el tag `v2.40.2-beta` **antes** del
  re-sellado) → commit sellado **`581067c4`** (tag **`v2.40.2-beta` movido aquí**: borrado + re-tag,
  ver §0 del pack).
- **Commits posteriores a `581067c4` (docs + sondas, ninguna línea de producción):** `29466369`,
  `d6b9e1f3`, `d2a64d7e` y la punta actual. Contienen `CHANGELOG.md`, `docs/engineering/*` y **cuatro
  scripts de auditoría** en `apps/api-python/scripts/`: `a9_mutation_audit.py` y
  `a9_restart_mutation.py` (las sondas con las que se midió §5), `a9_identity_length_probe.py` (el
  barrido de longitudes que respalda la tabla de §1) y `a9_doc_refs_probe.py` (comprueba que las
  rutas citadas por estos documentos existen). **Compruébalo tú** con
  `git diff --stat 581067c4 <punta de main>`: el camino de dinero no debe aparecer.
- **Ojo con el nombre del tag:** `git rev-list -n 1 v2.40.2-beta` resuelve a **`581067c4`**, cuya
  versión es **`1.65.3-beta`** (fase V2.40.3). El nombre del tag **no** coincide con la versión del
  código que señala: es una **limitación declarada** (§7.1 del pack), no un error de sellado.
- **Package:** `1.65.3-beta` · **CHANGELOG:** `[1.65.3-beta]`.
- **Alembic head:** `041_unique_natural_keys` — esta fase **no añade migración**.
- **Flags:** sin cambios. `AUTO_ENGINE_SIM_V2` sigue **OFF por defecto**; con el flag sin definir el
  comportamiento es el de `v2.40.2-beta`.
- **Sello CI:** `python-ci` **GREEN** — run
  [`35068139514`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068139514) sobre `581067c4`
  (`quality` —con **Mypy**—, `lifecycle-pg`, `grammar-discovery-pg`, `paper-forward-pg`,
  `auto-v2-durable-pg`) · `release-tag-ci` **GREEN** — run
  [`35068488972`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068488972) sobre el tag movido
  (`certify` ✓; único skip: `playwright` integrado, opt-in) · los commits posteriores de docs+sondas
  también pasan `python-ci` (run
  [`35070893441`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35070893441)).
- **Verificación local (no sustituye al CI, la complementa):** batería **exacta** del job
  `lifecycle-pg` sobre PostgreSQL real en BD scratch recreada y migrada a `head` → **132 passed**;
  baterías offline de CI con el comando `pytest` **extraído del propio YAML** → **1626** (`quality`)
  y **1634** (`python` del tag); `ruff check` **0** · `lint-imports` **4/4**. **`mypy` no se pudo
  ejecutar en la máquina de verificación** (política de control de aplicaciones de Windows bloquea el
  DLL `mypyc`): lo certifica el CI, no una afirmación local.

**Regla:** NINGÚN estado ambiguo → NO CERTIFICAR. No inventes PASS. Compara **línea por línea**
`11e2cb83` → `581067c4` y registra P0/P1/P2/P3 con evidencia `archivo:línea`.

**Punto de entrada único:**
[`audit-pack-v2.40.3-idempotency-key-collision-2026-09-16.md`](./audit-pack-v2.40.3-idempotency-key-collision-2026-09-16.md)

---

## Resumen del delta (qué cambió y por qué)

El CI del tag anterior dejó `lifecycle-pg` en rojo con el invariante de **equity** del día AUTO. El
mensaje apuntaba al sitio equivocado: el ledger estaba bien; lo que pasaba es que **3 fills nunca se
materializaron** y ningún gate lo decía. El hotfix tiene tres piezas, y la primera es un **bug de
dinero**.

| #   | Pieza                         | Cambio                                                                                                                                           |
| --- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| F1  | Clave de idempotencia de fill | Módulo nuevo `bolsa_application.idempotency_key` (`bounded_idempotency_key`): recorte **sin pérdida** por digest. SIM y recovery delegan ahí     |
| F2  | Invariante de equity del A9   | Lee la posición del estado **canónico** (`positions`) y el P&L cerrado del espejo de fills, no de `position_states` (que el AUTO SIM no escribe) |
| F3  | Gate de cierre del día AUTO   | **Libro plano + cero fills sin materializar** (todos los `execution_events` `APPLIED` y todo contexto de fill con su transacción)                |
| —   | Test hermético nuevo          | `packages/py/application/tests/test_idempotency_key_budget.py` (10 tests, 0,2 s) **cableado** en los jobs `quality` y `python`                   |
| —   | Dos verdes falsos retirados   | Instrumento del test de restart determinista (antes 12,36 % de no-llenado) y contador del restart por **órdenes** (`distinct venue_order_id`)    |

---

## Foco 1 — La clave de fill es inyectiva y la compatibilidad es real

**Lee (fuentes reales, no solo docs):**

- `packages/py/application/src/bolsa_application/idempotency_key.py`
- `packages/py/application/src/bolsa_application/simulated_settlement.py`
  (`simulated_idempotency_key`) y `recovery_apply.py` (`recovery_idempotency_key`)
- `packages/py/application/tests/test_idempotency_key_budget.py`
- `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py` (caller de recovery)
- `packages/py/application/src/bolsa_application/execution_event.py`
  (`apply_execution_financial_once`, el `mark_retry`) y `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  (dónde se absorbe el fallo por símbolo)
- `apps/api-python/scripts/a9_identity_length_probe.py` (barrido de longitudes: mide **en qué régimen**
  de `engine_id` aparece el colapso, en vez de afirmarlo)

**Foco:**

1. ¿`bounded_idempotency_key` es **inyectiva** para `execution_id` distintos, en **ambas** ramas
   (corta y larga)? ¿Puede un `execution_id` largo producir la **misma** clave que uno corto distinto?
   La marca `~` pretende hacerlo estructuralmente imposible: ¿lo consigue, o hay una normalización que
   pueda introducir `~`?
2. La rama corta dice ser **byte a byte** la clave histórica (para no re-aplicar dinero de un fill en
   vuelo de un deploy anterior). **Compruébalo tú**: reproduce la derivación histórica y compara con
   la rama corta para un barrido de `execution_id` (incluye los que acaban en `-`/`_`, los vacíos y
   los `unknown`).
3. ¿El relleno del mínimo de 16 puede colisionar con una clave **normal**? ¿Y con una clave **larga**?
4. **Verifica por mutación** (matriz §5 del pack, filas **medidas**): revertir SIM a `slug[:120]` pone
   rojo en 6 tests; quitar el digest de la rama larga, en 5; `_MARK = "-"`, en 2; quitar el relleno,
   en 2. ¿Se te ocurre una mutación que la suite **no** detecte? Esa es la pregunta que importa.
5. ¿Queda algún camino que derive la clave de fill **fuera** de este módulo? Si encuentras un tercer
   derivador con recorte, es un **P0** (ver Foco 3, barrido ya hecho, verifícalo).

---

## Foco 2 — El gate de cierre es el que nombra el fallo (y el invariante de equity **no** es load-bearing)

**Lee:** `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`
(`_day_progress`, `_assert_full_day_closed`, `_filling_instrument_id`, `_scoped_buy_orders`,
`test_a9_scheduler_process_full_day_pg_zero_human`,
`test_a9_scheduler_process_restart_with_open_protected_position_pg`).

**Foco:**

1. El fallo del día AUTO se descubre por el gate **"ExecutionEvents fuera de APPLIED"**, no por el
   invariante de equity (el A/B del §6 del pack lo mide: el rojo dice literalmente _"deja 3
   ExecutionEvents sin materializar"_). ¿Es eso suficiente, o hay un fallo de dinero que **no** deje
   eventos fuera de `APPLIED` ni el libro abierto? Piensa en: fee mal calculada, notional con decimal
   redondeado, doble asiento con **payload idéntico** (que la guarda de payload no detecta), o una
   transacción extra sin contexto de fill.
2. La afirmación "el invariante de equity ya no es vacuo" (F2): con el día cerrándose **plano**, el
   término no realizado es 0 de todas formas, así que el invariante **no** es lo que detecta un día a
   medias. ¿En qué caso concreto el fix de F2 cambia el veredicto del test? Si la respuesta es
   "ninguno, solo el diagnóstico", dilo: es un hallazgo, no un problema.
3. `closed_pnl` se reconstruye del espejo de fills como Σ(+notional si sell −notional si buy). ¿Es
   correcto con un día que **no** sea un ciclo BUY→SELL simétrico (dos BUY, un SELL parcial, reentrada)?
4. ¿El test puede salir **verde** con la posición plana y el ledger cuadrado pero con un fill del
   espejo **sin** su gemelo en `transactions`? Recorre `materialized`/`unmaterialized` y busca el
   hueco (claves `None`, `idempotency_key` en la BD distinto del derivado, side ausente).
5. `_filling_instrument_id` elige un instrumento que **sí** llena según el ruido determinista del
   simulador. ¿Eso convierte el test en algo que certifica menos (solo certifica "el camino feliz")?
   ¿Debería existir además un caso que acepte el no-llenado y exija que el libro quede plano **igual**?

---

## Foco 3 — Barrido de identidades: ¿hay un tercer recorte?

Ya está barrido (y se declara para que lo verifiques, no para que lo creas):

- **Claves financieras compuestas, sin recorte:** `make_auto_execute_idempotency_key` (OR-T4),
  `make_position_event_idempotency_key`, `confirm_leg_idempotency_key` (V1.91/V1.96),
  `make_custody_idempotency_key`. Todas concatenan con `|`, no truncan.
  **Pregunta:** ¿alguna puede **superar** la longitud de la columna de `idempotency_key` con
  identificadores largos, y qué pasa entonces (error de BD fail-loud o recorte silencioso)?
- **Recortes que existen pero NO son identidad de dinero** (candidatos P3, declarados aquí):
  `packages/py/market/src/bolsa_market/sanity.py` (`f"data_freshness:sanity_anomaly:{warning[:120]}"`,
  es texto de motivo, no clave) y `packages/py/market/src/bolsa_market/filing_store.py`
  (`safe = re.sub(...)[:128]`, nombre de **directorio** por instrumento: dos instrumentos que
  compartan los primeros 128 chars caerían en el mismo directorio).
- **Búsqueda que debes repetir:** `rg "\[-\d{2,3}:\]|\[:\s*1[0-9]{2}\]"` sobre `packages/py` y
  `apps/api-python`, y `rg "idempotency_key"` sobre el camino de dinero.

**Foco:** si el patrón "truncar la cola de una identidad" reaparece en **algún** sitio que decida
dinero, es P0. Si reaparece en un sitio que solo decide texto/nombres, es P3 y va con evidencia.

---

## Foco 4 — Contrato de la clave y compatibilidad de despliegue

**Lee:** el contrato R-11 C2 en `packages/py/domain` (DTOs `DepositCashDto`/`WithdrawCashDto`/
`TradeRequestDto`), `idempotency_key.py` (`IDEMPOTENCY_KEY_MIN_LEN`/`_MAX_LEN`) y los consumidores que
**validan** claves de idempotencia.

**Foco:**

1. El contrato fija rango `16..128` y ausencia de whitespace. Las claves **largas** nuevas incluyen el
   carácter `~`. ¿Hay algún consumidor que valide el **alfabeto** (no solo rango/whitespace) y que por
   tanto rompería con las claves largas? Búscalo: es la limitación §7.2 y, si existe, es un P1 real.
2. **Reversibilidad del despliegue:** si se despliega esta versión y se vuelve atrás, ¿un fill nuevo
   (clave larga con digest) re-derivaría su clave histórica? ¿Puede eso re-aplicar dinero? Argumenta
   con la rama corta y con el hecho de que el digest es función del `execution_id` completo. **Lee
   antes §7.9 del pack**: ahí se declara el único caso en que la garantía **no** cruza el borde del
   despliegue (régimen truncado + caída entre `apply_finance` y `mark_applied` + redespliegue antes
   del vencimiento del lease). **No está medido**: si crees que el razonamiento es erróneo —en un
   sentido o en otro— es un hallazgo, no una opinión.
3. ¿La longitud máxima resultante es **exactamente** 128 en la rama larga con **ambos** prefijos
   (`sim-fin-` y `recovery-fin-`)? Calcula `head` para cada uno y comprueba que no se pasa (un
   `VARCHAR(128)` que revienta es fallo de dinero, no cosmético).
4. Los `execution_events` en `RETRY` **históricos** de una cuenta ya afectada no se reparan solos
   (§7.3). ¿Con qué operación se reanudan? ¿Puede un `RETRY` viejo, al reintentar, aplicar dinero
   contra un payload distinto y disparar la guarda de payload (`IdempotencyKeyReused`)?

---

## Foco 5 — Los verdes falsos: lo medido y lo **no** medido

**Lee:** §4 y §5 del pack, y `apps/api-python/scripts/a9_noise_probe.py`.

**Foco:**

1. La matriz de mutaciones §5 marca explícitamente qué está **medido** y qué **no**. Tu trabajo con
   las filas no medidas es ponerles rojo o declararlas indemostrables:
   - Contador del restart por **filas** en vez de órdenes: **medido y NO se pone rojo** en una pasada
     limpia (`1 passed in 23,46 s`). ¿Es un arreglo de robustez (evita un rojo espurio cuando una
     trancha queda en vuelo al matar el proceso) o una relajación del invariante? Argumenta con el
     código de `_scoped_buy_orders`.
   - Instrumento **aleatorio** en el restart: la lotería medida es del **12,36 %** de no-llenado
     (sonda `a9_noise_probe.py`, `n = 5000`). ¿Es aceptable elegir un instrumento que llena, o el test
     debería además cubrir el caso "el venue no llena" y exigir libro plano y cero fills?
   - F2 (leer la posición de `position_states`): revertirlo **no** debería poner rojo un día que cierra
     bien. Si consigues ponerlo rojo, tienes un hallazgo.
2. ¿Qué mutación **falta** en la matriz? En particular: alterar el **orden** de los fills de una
   misma orden, cambiar el `fill_seq` del sufijo, o hacer que dos `venue_order_id` distintos
   compartan prefijo largo.

---

## Foco 6 — Deuda declarada (no la arregles, verifícala)

1. **El CLI de Alembic ignora `DATABASE_URL` en modo online.** `run_migrations_online`
   (`packages/py/infrastructure/alembic/env.py`) construye el engine desde `sqlalchemy.url` de
   `alembic.ini` (`engine_from_config`), no desde `_resolved_url()` (que solo se usa en offline).
   Reproducción que se midió:
   `DATABASE_URL=postgresql://nope:nope@localhost:59999/nope_db uv run alembic current` →
   imprimió `041_unique_natural_keys (head)`, es decir conectó a la BD del `alembic.ini`. El camino
   programático (`ensure_migrated`, el que usan los tests y el bootstrap de los workers) **sí** honra
   la URL. **Pregunta:** ¿qué job/entorno de este repo podría aplicar una migración a la BD
   equivocada por esto? En CI no se nota porque el default coincide.
2. **El instrumento determinista del test depende del modelo de ruido del simulador.** Si el modelo
   de ruido cambia, el test falla de forma **informativa** (no silenciosa). ¿Lo consideras aceptable?

---

## No pedir

LIVE · bump de versiones · mover el tag otra vez · unificar ledger/mesa · re-diseñar ADR ·
refactorizar el settlement o el ledger · **arreglar el CLI de Alembic** (deuda declarada, fuera de
alcance de este hotfix) · activar `AUTO_ENGINE_SIM_V2` por defecto · tocar los umbrales de riesgo. La
regla de **fail-closed** y los gates CPCV/PBO/DSR/WFE/OOS **no se relajan**.

---

## Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada foco**, con
evidencia `archivo:línea` y el delta real `11e2cb83` → `581067c4`. Marca explícitamente lo que **no**
puedas verificar desde GitHub y requiera entorno local: en particular los tests con **PostgreSQL**
(`lifecycle-pg`, el día AUTO completo y el restart) y las **mutaciones** de §5 marcadas como no
medidas.
