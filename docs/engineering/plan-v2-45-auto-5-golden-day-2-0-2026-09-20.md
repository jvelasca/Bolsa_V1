# Plan de fase — `V2.45` / `AUTO-5` — Golden Day 2.0 (`1.70.0-beta`)

**Fecha:** 2026-09-20 · **Punto de partida:** tag `v2.44-beta` → `c95819c1` (AUTO-4 Portfolio Optimizer
cerrado) · **Migración:** **ninguna** (decidido: head sigue en `043_exit_identity_and_kill_state`).
**Roadmap:** §7 de [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).
**Relevo de entrada:** [`traspaso-relevo-post-v2-44-auto-4-golden-day-2-0-2026-09-20.md`](./traspaso-relevo-post-v2-44-auto-4-golden-day-2-0-2026-09-20.md).

> **Aviso de numeración (declarado):** el plan de `v2.43.2` reutilizó la etiqueta «v2.44» para Exit
> Governance. Esta fase es la **`V2.45` del roadmap**: `AUTO-5 — Golden Day 2.0` / `1.70.0-beta`. Es el aviso
> que el plan de `v2.44` dejó escrito y que aquí se mantiene para que nadie confunda las dos etiquetas.

---

## 0. Decisiones del owner (fijadas 2026-09-20)

| Decisión       | Elección                                                                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alcance        | **Fase completa**: certificación end-to-end con PG real + proceso de scheduler real, **más** atribución por estrategia, MAE/MFE y coste de oportunidad de las rechazadas. |
| Migración      | **NINGUNA.** La identidad de estrategia entra como clave **aditiva** del `payload` JSONB del journal; `mfe_mae` ya vive en el JSONB de posición.                          |
| Capas del gate | **DOS**: embudo hermético en `quality` (por commit) **+** día real de proceso en `lifecycle-pg` del tag (al sellar).                                                      |
| Arranque       | **Agente nuevo** con este plan y el relevo; no se continúa la sesión de `v2.44`.                                                                                          |

## 1. Invariante que instala

> _El día completo (mercado → régimen → señales → ranking → decisión → reservas → orden → fills múltiples →
> posición → protección → T1 → trailing → salida → ledger → reconciliación → P&L → atribución → informe) se
> reproduce con **PostgreSQL real** y **proceso de scheduler real**, y **toda** oportunidad del día termina
> con un estado final y un motivo._

Corolario operativo: el informe del día debe ser **reconstruible desde la BD**, sin discrepancias de ledger y
con las decisiones **tomadas y no tomadas** atribuidas. «No tomada» con motivo tipificado, nunca en silencio.

## 2. Qué NO cambia (freeze)

- **`v2_43_governor_evidence.py` byte a byte igual y `exit 0`**, con su `"bump"` conservado en `1.68.0-beta`.
  Los ejes, la tabla, el gate y los umbrales del gobernador **no se tocan**.
- **Sin migración**: Alembic head `043`.
- **Byte-identidad con el flag OFF** (`AUTO_ENGINE_SIM_V2_OPTIMIZER=0`) ⇒ el camino V2 sigue siendo `v2.43.3`.
- **`AUTO-ENGINE_SIM_V2=0`** sigue siendo el comportamiento histórico (el camino legacy no se toca).
- **Los tags no se mueven**: `v2.44-beta` y anteriores quedan donde están; `v2.45-beta` será ref nueva.
- **Los gates PG** (`*_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo
  **no** certifica.

## 3. Piezas (qué se extiende, no qué se reinventa)

### 3.1 El día real (capa de proceso) — **extender** `test_a9_scheduler_process_pg_zero_human.py`

El patrón ya está en el repo y **no se reinventa**: `subprocess.Popen([sys.executable, "-m",
"bolsa_api.workers.scheduler_worker"])` (líneas 520-525 y 757-770), gate
`AUTO_SCHEDULER_PROCESS_PG_REQUIRED` (línea 34), presupuestos declarados `_TIMEOUT_S = 90`,
`_STARTUP_GRACE_S = 120`, `_RESTART_WATCH_S = 20`, `_CLOSED_DAY_POLLS = 4`.

Lo nuevo es el **día dorado 2.0**: un fichero `apps/api-python/tests/test_golden_day_v2_*_pg.py` que conduce
el mismo proceso real sobre PostgreSQL real y certifica:

1. **3–10 señales** en el día (el rango del roadmap), con al menos **dos estrategias** distintas.
2. **Fills múltiples por orden** (no una trancha): `count(distinct venue_order_id)` y `fills > orders`.
3. **T1 parcial**, **trailing** posterior a T1 y **cierre por régimen** (`REGIME_EXIT`/`RISK_EXIT`), cada uno
   atribuido en el journal.
4. **Cierre de día con libro plano**: posiciones a cero y ningún fill en vuelo.
5. **Todos los `execution_events` en `APPLIED`** y **todo fill con su transacción en el ledger** (el gate que
   en `V2.40.3` habría nombrado el fallo en una línea).
6. **`Σ motivos de salida == exits`**: ningún cierre sin explicar.
7. **Atribución por estrategia** del día, agregada desde la BD.
8. **MAE/MFE por operación** (ya persistidos en `mfe_mae` del JSONB) **leídos desde la BD**.
9. **Coste de oportunidad de las rechazadas**: toda rechazada conserva su motivo y su **precio posterior**
   cuando el dato existe; si falta, **se declara** (`unmeasured`), no se inventa.

Aviso de coste: el job `lifecycle-pg` del tag ya corre dos suites de proceso real (líneas 564-580). Un día de
3–10 señales con fills múltiples **alarga el job**; el presupuesto debe declararse (los `_*_S` de arriba) y el
test debe **fallar de forma informativa**, no quedarse minutos esperando.

### 3.2 El embudo (capa hermética) — **extender** `auto_daily_journal.py`

`AutoDailyReport` (líneas 69-122) hoy tiene `orders`, `fills`, `positions_created`, `exits`, `exit_reasons`,
`atr_sources`, `ledger_balance_status`, `errors`, `healthy`. Falta todo lo de §3.1 puntos 7-9. Los campos
nuevos son **aditivos** y con la **disciplina de medición del repo**: un agregado que no se puede medir se
declara (`UNKNOWN`/`PARTIAL` + `notes`), **jamás** se publica como `0`.

El invariante del embudo, hermético y por commit:

```
seen == traded + rejected + expired + missed      # y cada rechazo con motivo tipificado
```

Gate: extender el día hermético existente
(`apps/api-python/tests/test_auto_v2_golden_day_evidence.py`, 288 líneas) o su gemelo en
`packages/py/application/tests/` para el agregado puro. **La lista de `quality` es explícita**: un fichero
nuevo en `packages/py/application/tests` hay que **registrarlo** o no corre.

### 3.3 Identidad de estrategia en el journal (sin migración)

El journal durable es `DecisionJournalEntryRow`
(`packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:720-739`):
`(id, decision_id, session_id, account_id, instrument_id, event_type, actor, payload JSONB, created_at)`, **sin
columna de estrategia**. La identidad entra como **clave aditiva del `payload`** (mismo patrón que `AUTO-2` y
la `043` con el JSONB). La atribución del día se agrega desde ahí y desde las tablas `sim_*`, y la maquinaria
de atribución **ya existente** (`packages/py/application/tests/test_sim_strategy_attribution.py`, certificada
por commit en `lifecycle-pg`) **se reutiliza, no se duplica**.

### 3.4 Reason codes (aditivos)

Los motivos del embudo y de la atribución van a `auto_reason_codes.py` (la **casa única** del journal). Un
motivo nuevo **no** puede reutilizar un texto existente que signifique otra cosa: en `v2.44` la lección fue
que journalizar `edge_below_threshold` para una candidata no elegida por el optimizador habría sido **falso**.

## 4. Gate (lo que mide el roadmap §7)

| Capa             | Dónde                        | Fichero                                                       | Gate                                |
| ---------------- | ---------------------------- | ------------------------------------------------------------- | ----------------------------------- |
| Hermética (tick) | `quality` de `python-ci.yml` | embudo del día (3.2)                                          | sin gate PG (no toca la BD)         |
| **Real (PG)**    | `lifecycle-pg` del **tag**   | `test_golden_day_v2_*_pg.py` (proceso real, sin `run_tick()`) | `fail-if-skipped` + guard anti-skip |

Requisitos de cableado (un fichero nuevo **no entra solo**):

- Añadirlo a la lista del job `lifecycle-pg` del tag (junto a las líneas 564-580).
- Añadirlo a los **`--ignore`** de los jobs offline (`quality` de `python-ci.yml`, líneas 183-212; job
  `python` del tag). Comentario **fuera** del bloque plegado (trampa medida en V2.40.2) y `set -o pipefail`.
- Guard anti-skip en el job (log no vacío + `grep` de `skipped`), como ya hace `auto-v2-durable-pg`.
- **Sin `run_tick()` manual**: el día lo conduce el proceso.

## 5. Criterios de salida

1. **Informe de día reconstruible desde la BD**, sin discrepancias de ledger (`BALANCED`), y `healthy`.
2. **Todas las decisiones atribuidas**: `seen == traded + rejected + expired + missed`, con motivo en cada
   rechazo y con el **precio posterior** de la rechazada cuando el dato existe (declarado si falta).
3. **`Σ exit_reasons == exits`** y **todos los `execution_events` en `APPLIED`** con su transacción.
4. **Ambas capas en verde en CI real**, con las cifras citadas **del run que las produjo**.
5. **Matriz de mutaciones medida**: cada invariante nuevo debe tener su mutación que ponga la suite en rojo
   (patrón de `apps/api-python/scripts/v2_44_mutation_audit.py`: script de auditoría de mutaciones **propio de
   la fase, a crear**, con la huella del árbol intacta antes y después de medir).

## 6. Límites previstos (declarar, no maquillar)

1. **Sin productor de economía en el tick**: el día real **no** lleva el optimizador ON con economía real
   (`p_win`/medias son de `AUTO-7`). La evidencia «ON ≠ ranking» sigue siendo de **capa de test**.
2. **MAE/MFE: se recogen, no se calibran.** Calibrar stop/T1/T2/trailing/tiempo con ellos es `AUTO-7`.
3. **Coste de oportunidad: se recoge, no se decide con él.** Ninguna regla se relaja por esta medición.
4. **Correlación de hoy, no matriz por pares** (heredado de `AUTO-4`).
5. **Presupuesto de tiempo del job del tag**: el día real alarga `lifecycle-pg`; el coste se declara medido.
6. **La identidad de estrategia viaja en `payload` JSONB**: consultable, pero **no** indexada. Si el informe
   del día exigiera reconstrucción por SQL a gran escala, eso sería una migración **de otra fase**, declarada.

## 7. Estado de ejecución (2026-09-20) — lo implementado, con sus desviaciones

**Cerrado en el mismo día.** **Sin migración** (Alembic head sigue en `043_exit_identity_and_kill_state`)
y **sin tocar el gobernador** (`v2_43_governor_evidence.py` byte a byte igual y `exit 0`, con `"bump"`
todavía en `1.68.0-beta`).

| Pieza del plan                             | Estado                | Fichero                                                                                                                                |
| ------------------------------------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| §3.1 el día real (capa de proceso)         | hecho (con **D1–D5**) | `apps/api-python/tests/test_golden_day_v2_process_pg.py` (**nuevo**)                                                                   |
| §3.2 el embudo (capa hermética)            | hecho                 | `packages/py/application/src/bolsa_application/auto_daily_journal.py`                                                                  |
| §3.3 identidad de estrategia sin migración | hecho                 | `packages/py/application/src/bolsa_application/auto_v2_entry.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` |
| §3.4 reason codes aditivos                 | hecho                 | `packages/py/application/src/bolsa_application/auto_reason_codes.py`                                                                   |
| §4 gate en dos capas                       | hecho (ver **D4**)    | `python-ci.yml` (`quality`), `release-tag-ci.yml` (`python`, `lifecycle-pg`)                                                           |
| §5 matriz de mutaciones medida             | hecho                 | `apps/api-python/scripts/v2_45_mutation_audit.py`                                                                                      |

### 7.1 Desviaciones declaradas (el plan decía otra cosa)

- **D1 — el día real cierra por `time_exit` por el SEAM DURABLE, no por geometría.** El precio del camino
  SIM real es **plano** (`flat_price_script`, `auto_simulation_worker.py:265`, sin env que lo cambie) y el
  horizonte de la plantilla de política es de **21–90 días**: un día V2 **no** puede disparar T1
  parcial/trailing/régimen dentro del presupuesto de un test. La fase 2 detiene el proceso, lleva el
  **techo de mantenimiento** (`holdingDeadlineAt` del JSONB) al pasado —el techo se congela al nacer y
  sobrevive al reinicio, E1— y **reinicia el mismo engine**: el worker rehidrata el plan y vende por
  `time_exit`; libro canónico plano, todo `APPLIED` y cada fill con su transacción. El cierre por
  **geometría** (T1/trailing/régimen) y `Σ exit_reasons == exits` se certifican en la capa **hermética**,
  donde precio, reloj y decider se **inyectan**.
- **D2 — el día real no puede certificar atribución por estrategia, MAE/MFE ni coste «leídos desde la
  BD».** El spine determinista del proceso real es **`unversioned`** (`auto_simulation_worker.py:1728`) y
  el bucle AUTO SIM **no escribe** el journal durable (`DecisionJournalEntryRow` lo escriben los casos de
  uso de la API; el worker acumula `DecisionJournalEntryRecord` **en memoria** y el espejo durable de
  fills no tiene versión de estrategia). Esos tres agregados se certifican en la **capa hermética**
  (día del worker con dos versiones **distintas** —`orb-1` ×2 y `meanrev-2`— y 9 tests del agregado
  puro), junto con su disciplina de declaración (`UNKNOWN`/`PARTIAL`, nunca `0`).
- **D3 — identidad determinista por BARRIDA pura, y presupuestos propios.** El ruido de la cola SIM sale
  de `sha256(seed, instrument_id, side, ...)`; con id aleatorio el día es una moneda al aire. En vez del
  id del `a9` (elegido solo para `_minute = 0`) aquí se barre un id que garantiza, en **toda** la ventana
  de ticks del test, `≥2` tranchas en BUY y SELL **completa** (la SELL del cierre cae en el 2º proceso
  recién arrancado, que vuelve a `_minute = 0/1`). Sin `run_tick()` manual y con los presupuestos
  declarados (`_STARTUP_GRACE_S`, `_OPEN_POLLS`, `_CLOSE_POLLS`, `_CLOSED_DAY_POLLS`) y **fallo al
  instante** si el subproceso muere.
- **D4 — el gate se cuelga de las listas que YA existen.** El agregado puro (`test_auto_daily_journal.py`)
  ya estaba registrado explícitamente en `quality` desde `v2.42.2`; el día del worker entra por el pase de
  directorio de `apps/api-python/tests`; el fichero **PG nuevo** se añade a los `--ignore` de los dos
  jobs **offline** y corre en un **paso dedicado** de `lifecycle-pg` con `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`
  y guard anti-skip (log no vacío + `grep` de `skipped`). No se toca el `run: >` de los bloques
  existentes.
- **D5 — «≥2 estrategias» en el día REAL: no; en la capa hermética: sí.** Por D2 el proceso real produce
  tres señales (una por instrumento, 3 sectores) todas `unversioned`. Las dos versiones distintas del
  punto 1 del plan se certifican en la capa hermética.

### 7.2 Límites confirmados al medir (eran §6, ahora medidos)

- **Corrección de procedencia frente al §0 del plan:** esta máquina **SÍ tenía PostgreSQL alcanzable**
  (contenedor `bolsa-postgres` sano en `localhost:5432`, DSN de `docker-compose.yml`) ⇒ la capa real
  **se midió en local**: `1 passed` (solo) en **10,05 s**, con seis corridas en solitario de
  8,89 / 9,66 / 9,85 / 9,88 / 9,90 / 10,05 s. El «sin PG local» del arranque era cierto para el
  entorno del relevo, no para el estado del contenedor al ejecutar la fase.
- **Límite de método medido (y declarado en el fichero):** el barrido de residuos del conftest
  (`purge_all_residuals`: borra **toda** cuenta ajena y todo instrumento `inst-%` al terminar la
  **sesión** de pytest) hace que **dos sesiones de pytest a la vez contra la misma base se borren los
  datos entre sí** — se reprodujo: el motor quedaba reintentando liquidaciones (`retry_scheduled`) contra
  filas ya borradas. El gate del tag corre el fichero en **paso dedicado**, que es la forma soportada.
- **MAE/MFE se recogen, no se calibran**; **el coste se recoge, no decide**; **correlación de hoy**, no
  matriz por pares; **identidad de estrategia en `payload` JSONB no indexado**. Todo confirmado.
- **Presupuesto del job del tag:** el día real añade un paso con dos arranques de scheduler (×3
  instrumentos); medido en local en ~10 s por corrida, con techo declarado (120 s por fase) que **falla
  con diagnóstico**, no se queda en silencio.

### 7.3 Verificación medida

```text
ruff check packages/py apps/api-python --config pyproject.toml     → All checks passed (0)
mypy <5 paquetes + apps/api-python/src> --follow-imports=silent    → Success: 489 ficheros, 0 issues
lint-imports --config packages/py/.importlinter                    → 4 kept, 0 broken
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py     → vacío; script exit 0
las 3 suites de la fase juntas                                     → 44 passed
offline_ci_run_yaml.py ... python-ci.yml quality (baseline)        → 2087 passed, 0 skipped (exit 0)
offline_ci_run_yaml.py ... release-tag-ci.yml python (baseline)    → 2098 passed, 0 skipped (exit 0)
CI real · quality (run 35520898909)                                → 2087 passed, 38 skipped (v2.44: 2075 ⇒ +12)
CI real · auto-v2-durable-pg (mismo run)                           → 43 passed (sin cambio: no hay migración)
v2_45_mutation_audit.py                                            → 8/8 muerden, huella intacta (exit 0)
capa real PG (local, 6 corridas en solitario)                      → 1 passed cada una (8,89–10,05 s)
```

El `+12` de tests nuevos (9 en `test_auto_daily_journal.py`, 2 en `test_auto_v2_golden_day_evidence.py`,
1 en `test_auto_simulation_worker.py`) coincide **exacto** en las dos listas offline medidas (2087/2098
sobre 2075/2086) y con el `quality` de CI real.

---

## 8. Verificación (a rellenar con artefactos)

Cada cifra del informe final debe citar **el artefacto que la produjo** (aprendizaje declarado de `v2.44` §5:
una cifra atribuida al instrumento equivocado es un defecto de honestidad, no un redondeo).

| Artefacto                                                                                                              | Qué certifica                                                                                                                                                                                        |
| ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **commit de fase `ad800262`** (17 ficheros, `+2581/−16`)                                                               | el cuerpo entero de la fase (embudo, identidad, capa real, mutaciones, docs de auditoría)                                                                                                            |
| **commit `0fc85c17`**                                                                                                  | corrección del contrato declarado del id determinista + límite de método medido (paralelismo de sesiones)                                                                                            |
| `Python CI` run [`35520898909`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35520898909) **GREEN 5/5** en `main` | `quality` **2087 passed, 38 skipped, 0 failed** en 72,43 s (los **+12** exactos); `auto-v2-durable-pg` **43 passed**; `paper-forward-pg` **2**; `grammar-discovery-pg` **21**; `lifecycle-pg` **13** |
| `Gitleaks` run [`35520899318`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35520899318) **GREEN**                | sin secretos                                                                                                                                                                                         |
| `apps/api-python/scripts/v2_45_mutation_audit.py` (corrida local, `exit 0`)                                            | matriz **8/8 muerden** y huella del árbol intacta (el log nombra el test en rojo de cada mutación)                                                                                                   |
| `offline_ci_run_yaml.py` (JUnit XML, no copia a mano)                                                                  | baseline de `quality` **2087/0/0** y de `python` del tag **2098/0/0**                                                                                                                                |
| **capa real PG** corrida local con `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`                                                  | proceso real abre 3 posiciones (`fills > orders`), reinicio con el techo vencido cierra por `time_exit`, libro plano, todo `APPLIED` y cada fill con su transacción                                  |
| `ruff` / `mypy` / `lint-imports` (locales)                                                                             | 0 / 489 ficheros 0 issues / 4 kept 0 broken                                                                                                                                                          |
| gobernador                                                                                                             | `git diff` **vacío** y `exit 0` (freeze respetado)                                                                                                                                                   |
| **`Release tag CI`** del tag `v2.45-beta`                                                                              | `python` offline, `lifecycle-pg` con el **paso dedicado** del día real y el guard anti-skip, `certify` en `success` (cifras y run en el commit de evidencia posterior al sello)                      |
