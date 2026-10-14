# Plan de arranque operativo de la ventana PAPER (ADR-046) — 2026-10-14

> **Documento único y de solo lectura sobre el código.** No modifica fuentes de producción, no escribe
> en la base de datos, no ejecuta `git commit/tag/push`. Todas las afirmaciones llevan `file:line`; lo que
> no se puede afirmar hoy se declara explícitamente como **NO MEDIDO** (ver §E).
>
> **Veredicto de una línea:** el `0` de `cycle_id`/`measurable_cycles` **no es un hueco de software** —la
> cadena AUTO **sí** sella `cycle_id` y `regime` de punta a punta—; es **falta de operación** (§B lo
> argumenta con el código y §C da el runbook para cerrarla).

---

## A. Criterios exactos de la ventana (fuente única)

**Umbrales (fuente única de verdad):**

```
packages/py/application/src/bolsa_application/operability_window.py:88-90
    MARKET_WINDOW_MIN_DAYS    = 4      # días de CALENDARIO
    MARKET_WINDOW_MIN_EPISODES = 2     # regímenes DISTINTOS
    MARKET_WINDOW_MIN_CYCLES  = 32     # ciclos MEDIBLES con R
```

**Cómo se cuentan los tres ejes** (`window_gate`, `operability_window.py:493-530`):

- `days` = `len({row["day"]})` — días ISO `YYYY-MM-DD` **distintos** (§A.1).
- `episodes` = unión de `row["regimes"]` (y `row["regime"]`) — **regímenes distintos** (§A.2).
- `cycles` = `sum(row["measurableCycles"])` — ciclos medibles con `R` (§A.3).

**Contrato del certificador** (`packages/py/application/src/bolsa_application/paper_window_certification.py`):
`certify_paper_window` (`:167-207`) replica los mismos tres criterios sobre `PaperWindowMaterial`, calcula
`missing` y **preserva `UNKNOWN ≠ 0`**: sin material medido los conteos son `None` (hueco), nunca un `0`
de relleno (`:20-24` del certificador `v2_98`). Un material **leído y vacío** sí es un `0` **Medido**.

**Salida medida hoy del certificador `v2_98`:**
`dias=42/4  episodios=0/2  ciclos=0/32 => INCONCLUSIVE` — faltan `episodes` y `measurable_cycles`.

### A.1 Eje DÍAS (calendario) — cómo cuenta un día

- El día sale del **reloj de pared** del instante durable, no de la corrida:
  `apps/api-python/scripts/v2_80_market_window.py:60-63` (`_day_of`).
- Se agrupan fills, ciclos **cerrados** y journal por día (`:192-208`) y los días son la **unión** de las
  tres fuentes: `days = sorted(set(fills_by_day) | set(cycles_by_day) | set(journal_by_day))` (`:211`).
- Consecuencia: **varios ciclos en un mismo día de pared = 1 día**. Para llegar a ≥4 hacen falta **≥4
  fechas distintas** en `created_at` durable. Un día entra con **cualquiera** de las tres fuentes (basta
  un fill, un ciclo cerrado o una entrada de journal), pero cada fuente debe existir **ese día real**.

### A.2 Eje REGÍMENES — de dónde sale `episodes`

- `episodes` se calcula **solo desde los ciclos**, no desde el journal: `build_window_row` deriva
  `regimes` de la lista de **ciclos** del día y `window_gate` los une (`operability_window.py`
  `window_gate:493-530`). El régimen viaja en la fila de ciclo.
- La fuente durable del régimen por ciclo es el **journal AUTO-10**:
  `auto_simulation_worker.py:2989-3032` (`_v2_journal_cycle_regime`) **escribe** la traza al nacer la
  reserva de entrada; el sink se cablea de verdad en el tick (`build_cycle_regime_sink`, `:6853-6887`)
  y el lector la recupera **confirmándola** (`auto_cycle_regime_reader.read_cycle_regimes`, importado en
  `:158`).
- `_collect` lee esos regímenes y los pasa al cálculo de riesgo por ciclo:
  `v2_80_market_window.py:178` (`read_cycle_regimes`) → `:179-184` (`cycle_risk_from_reservations` →
  `adaptive_instrument_cycles`).
- Si no hay **ciclos cerrados**, `regimes` está vacío ⇒ `episodes = 0` (el caso medido). No es un bug: el
  régimen es un atributo **del ciclo**, y sin ciclo no hay régimen que contar. El journal (que sí tiene
  material) **no** alimenta este eje por diseño.

### A.3 Eje CICLOS MEDIBLES — de dónde sale `measurableCycles` y `R`

- `adaptive_instrument_cycles(fills, cycle_risk)` agrupa **fills** por `cycle_id` y **descarta** el ciclo
  si no tiene `cycle_id` o si su cantidad abierta ≠ 0 (no se puede fechar el cierre):
  `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:177-219`
  (`cycles_from_fills`) y `:271-288` (`adaptive_instrument_cycles`).
- `R` solo cuenta si hay **riesgo reservado > 0** y PnL realizado:
  `packages/py/application/src/bolsa_application/auto_adaptive_confidence.py:376-415`
  (`_measured_r`/`measured_r`) y `cycle_risk.py:231-240` (la reserva de **entrada** es la que aporta
  `reserved_risk`; sin ella `R` no es medible).
- `build_window_row` filtra y suma a `measurableCycles` (`operability_window.py:422-428`).
- **Por tanto `measurableCycles` depende del JOIN ciclo→fill por `cycle_id`** (y de la reserva por
  `cycle_id`): sin `cycle_id` en fills **y** reservas, es 0. Ese JOIN se apoya en los índices
  `sim_fill_finance_context.cycle_id` y `portfolio_reservations.cycle_id` (§B).

---

## B. ¿Hueco de SOFTWARE o falta de OPERACIÓN? (veredicto por eje)

### B.0 El camino AUTO **sí** sella `cycle_id` (no es hueco de software)

Cadena completa, de la acuñación al fill durable:

| Paso | Evidencia |
| --- | --- |
| Acuñación determinista `cyc-<hash>` | `packages/py/application/src/bolsa_application/auto_v2_entry.py:1806-1826` (`auto_cycle_id`), propagada a `plan.cycles` (`:1479`) y a la reserva (`:2053`) |
| El worker resuelve el ciclo del símbolo | `auto_simulation_worker.py:2753-2770` (`_v2_cycle_for`) |
| `_settle` **recibe** `cycle_id` | `auto_simulation_worker.py:1739` (parámetro) |
| `_settle` lo **pasa** a la orden simulada | `auto_simulation_worker.py:1773` y `:1800` (`cycle_id=cycle_id`) |
| La settlement lo aplica | `packages/py/application/src/bolsa_application/simulated_settlement.py:186` (parámetro), `:214-228` (`persist_fill_finance_context`), `submit_simulated_order` `:263`/`:330` |
| El contexto de fill lo **persiste** | `packages/py/application/src/bolsa_application/sim_finance_context.py:43` y `:89` |
| Store durable | `packages/py/application/src/bolsa_application/sim_durable_store.py:123` (campo) y `:545` (save) |
| Columna física + índice | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:2327` (`sim_fill_finance_context.cycle_id`), índice `:2297` |

- En el camino **legacy** (`AUTO_ENGINE_SIM_V2=0`) `_v2_cycle_for` devuelve `None` ⇒ el fill se guarda con
  `cycle_id = NULL`. **Ese es el origen del `cycle_id=0` observado**: fills de **otras lanes**
  (manual/legacy) o de cuentas que nunca corrieron el pipeline V2.
- La migración que creó estas columnas lo declara explícitamente (aditiva, **sin backfill**: `NULL` =
  "fila anterior, desconocido"): `packages/py/infrastructure/alembic/versions/044_auto_cycle_trace.py:11-22`.
  Las reservas nacieron en `042_portfolio_reservations.py`.

**Veredicto B.0:** el JOIN ciclo→fill por `cycle_id` existe, está indexado y el camino AUTO lo rellena.
El `0` **no** es un hueco de software: es **falta de operación** (el pipeline V2 no ha corrido en la
cuenta declarada).

### B.1 Veredicto por eje

| Eje | ¿SOFTWARE o OPERACIÓN? | Evidencia |
| --- | --- | --- |
| **DÍAS** | **OPERACIÓN** (el software está bien) | El día deriva del reloj durable (`v2_80_market_window.py:60-63`, `:211`). Hay 42 días de **journal**, pero sin fills ni ciclos cerrados en la cuenta declarada. Falta correr el motor ≥4 fechas reales. |
| **REGÍMENES** | **OPERACIÓN** (el software está bien) | `episodes` cuenta regímenes de **ciclos cerrados** (`window_gate:493-530`); el escritor/lector AUTO-10 existe y está cableado (`auto_simulation_worker.py:2989-3032`, `:6853-6887`, `:158`). Sin ciclos → `episodes=0`. |
| **CICLOS** | **OPERACIÓN** (el software está bien) | El camino AUTO **sella `cycle_id`** (§B.0). `measurableCycles` depende de ese JOIN (`auto_self_evaluation_feed.py:177-219`; `operability_window.py:422-428`). Sin operación V2 → 0. |

### B.2 No hay bloqueador de software, pero sí dos **límites de diseño** que hay que conocer (no son bugs)

1. **El journal no alimenta el eje de regímenes.** Solo los **ciclos cerrados** aportan `regime`
   (`window_gate:493-530`). Es coerente con "el ciclo es la unidad", pero implica que **no se puede
   alcanzar `episodes≥2` sin ciclos cerrados**, aunque el journal esté lleno. Si el propietario quisiera
   que el journal contase, sería un cambio de criterio (fuera de alcance; **NO aplicar**).
2. **Un ciclo abierto/a-anónimo no cuenta.** `cycles_from_fills` descarta el ciclo sin `cycle_id` o con
   cantidad abierta ≠ 0 (`auto_self_evaluation_feed.py:177-219`). Un ciclo que cruce la medianoche cuenta
   en su **día de cierre** (`closed_instant`, `v2_80_market_window.py:200`). Es deseado, pero obliga a
   **cerrar** los ciclos dentro de la ventana.

### B.3 Precondición de infraestructura (operativa, no de motor)

- El runner forward está **pinnado** a un `commit`/`appsHash`/`packagesHash` (`WINDOW_CONFIG`,
  `scripts/lib/window-forward.mjs:256-270`). Si el árbol ha avanzado, el preflight aborta con
  `TREE_MOVED` y hay que **re-anclar** el pin (es un fichero de `scripts/`, fuera del pin de motor) o
  arrancar con `--unsafe-override-window-config` (declarado inseguro: **no** sirve como evidencia de
  ventana). Este paso es **operación**, no un hueco de la cadena de sellado. *(El detalle exacto del pin
  vigente debe leerse en el momento: ver §E.)*

---

## C. Lo que es OPERACIÓN — runbook reproducible

> Cuenta PAPER declarada: `1484e253d2d54645945a6b1d7` (confirmada en
> `scripts/lib/window-forward.mjs:259`). Pares A/B: `v283-window-a` / `v283-window-b` (`:260-261`),
> `watchSize: 20` (`:262`). Flags de operación inyectados **solo** en el `env` del hijo (`:266-268`):
> `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`, `BROKER_VENUE=paper`.

### C.0 Flags que encienden el motor (todos **off-by-default**)

- Orquestador AUTO: `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py:55-58` y `:137-139`.
- Worker SIM-only: `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:284` (default OFF)
  y `sim_worker_enabled()` en `:370-378` (acepta `1/true/yes/on`).
- Snapshots del protocolo longitudinal: `PAPER_EVIDENCE_SNAPSHOT_ENABLED`
  (`packages/py/infrastructure/src/bolsa_infrastructure/config.py:143`, off por defecto). En la ventana se
  activa **como política de entorno** (ADR-046 `docs/adr/046-protocolo-longitudinal-paper.md:71-73`).
- **Permisos SIM-only:** la ejecución se aplica por la vía `require_sim_only_scope`
  (`auto_simulation_worker.py:6800-6855`): no hay permiso LIVE; el runner fuerza `BROKER_VENUE=paper`.

> **NO fijar `AUTO_ENGINE_SIM_V2_REGIME`.** Si se fija a un literal (p. ej. `BULL_TREND`), **todos** los
> ciclos heredan un único régimen y `episodes` queda en 1. Dejar que el régimen se **descubra** del
> mercado real (`_v2_regime`, `auto_simulation_worker.py:1912-1926`; fuente `DiscoveryRegimeSource`,
> cableada en `_compose_regime_source` `:7153-7192`) es lo que permite ≥2 regímenes distintos (§C.3).

### C.1 Secuencia exacta (por día, un comando)

El runner encadena todo el pipeline (`scripts/window-forward-runner.mjs:6-10`), con los scripts reales en
`:74-77` (`v2_76` forward, `v2_77` journal, `v2_80` ventana, `v2_83` auditoría):

```
# 0) una sola vez: dependencias + BD al día (operación, fuera de este doc)
pnpm install
pnpm --filter ...      # migrar BD hasta head 044_auto_cycle_trace (ver runbook v2.78)

# 1) preflight read-only: declara el régimen de HOY y valida el freeze del árbol
pnpm run window:preflight

# 2) día completo (preflight -> v2_76 -> v2_77 -> v2_80 -> v2_83)
pnpm run window:run-day            # añadir --force solo si se sabe por qué

# 3) estado de la ventana (días/episodios/ciclos + si está desbloqueada)
pnpm run window:status

# 4) `window:unlock` NO re-ancla el pin: solo reclama/borra el lock diario (.run.lock/).
#    Ante `TREE_MOVED` hay que re-anclar WINDOW_CONFIG (ver §G.1), no hacer unlock.
#    Úsalo solo si un lock diario quedó colgado sin proceso vivo.
pnpm run window:unlock
```

`package.json:67-71` define esos cuatro scripts npm; `window-forward-runner.mjs:119-120` declara las
operaciones `preflight | run-day [--force] | status | unlock`.

### C.2 Cómo correr el ciclo/día de forma segura

- **Cuenta:** siempre `1484e253d2d54645945a6b1d7` (`WINDOW_CONFIG.account`). No mezclar cuentas: cada
  ventana se mide por `account_id` (`_collect` acota por cuenta, `v2_80_market_window.py:168-171`).
- **Venv/env:** el runner inyecta los flags de operación en el `env` del hijo (`window-forward.mjs:266-268`);
  no hay que exportarlos a mano, pero **sí** hay que tener el venv y la BD correctos
  (`WINDOW_PY`/`WINDOW_UV`, ver runbook v2.78).
- **Un día de pared distinto por corrida:** `run-day` se ejecuta **cada día** que se quiera contar; la
  ventana exige ≥4 **fechas** distintas (§A.1). Correr 32 ciclos en un día = 1 día.

### C.3 Cómo conseguir ≥2 regímenes distintos

- Depende **del mercado real de esos días** (y del universo/ESTUDIO que escucha el motor), **no** de un
  literal de entorno. `_v2_regime` clasifica el régimen desde barras diarias cerradas
  (`auto_simulation_worker.py:1912-1926`); `_compose_regime_source` carga esas barras para el watch
  (`:7153-7192`). Regímenes distintos exigen **días con mercado distinto** (p. ej. `BULL_TREND` vs
  `RANGE`/`BEAR_TREND`) o **cortes de universo** que clasifiquen distinto.
- Consecuencia operativa: **no se puede "forzar"** el segundo régimen sin falsear la medición; hay que
  **correr días de mercado diferentes**. Si todos los días fueran del mismo régimen, `episodes` seguiría
  en 1 y el eje de regímenes seguiría NO MEDIDO (y se **declara**, no se inventa).

### C.4 Cerrar los ciclos (para que sean medibles)

- Un ciclo solo cuenta cuando está **cerrado** y con `R` (reserva con `reserved_risk>0`)
  (`auto_self_evaluation_feed.py:177-219`; `cycle_risk.py:231-240`). Hay que dejar que las salidas de
  AUTO se ejecuten y **settleen** (no forzar cierres a mano), respetando la protección del motor.
- No se debe escribir en la BD para "fabricar" ciclos/reservas: cualquier fabricación rompe el
  `UNKNOWN ≠ 0` y descalifica la evidencia.

---

## D. Criterio FALSABLE de éxito (números que debe imprimir `v2_98`)

**Instrumento de medida (el certificador):**

```
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py \
    --account-id 1484e253d2d54645945a6b1d7 \
    --strategy-version v283-window-a --strategy-version v283-window-b \
    --json --out operability_runs/paper-window-certification/cert.json
```

Argumentos reales: `v2_98_paper_window_certification.py:171-192` (`--account-id` obligatorio,
`--strategy-version` repetible, `--days/--since/--limit`, `--json`, `--out`). El instrumento de ventana
subyacente es `v2_80_market_window.py:340-374`.

**Éxito FALSABLE — debe salir exactamente esto (con `ready/certified = true`):**

- `dias >= 4` (**fechas de calendario distintas**, no corridas) — `days ≥ MARKET_WINDOW_MIN_DAYS`
  (`operability_window.py:88`).
- `episodios >= 2` (regímenes distintos, de ciclos **cerrados**) — `operability_window.py:89`.
- `ciclos >= 32` (`measurableCycles` con `R`) — `operability_window.py:90`.
- Veredicto del certificador: **`CERTIFIED`** (no `INCONCLUSIVE`), con `missing` **vacío**.
- Y los `cycles` deben contar con `cycle_id` **no nulo** en fills **y** reservas de esa cuenta (el JOIN
  de §A.3). Si `ciclos < 32` mientras hay fills, el fallo es de `cycle_id` ausente ⇒ lane equivocada.

**Prueba negativa (falsación):** si tras ≥4 días de operación real la salida sigue con `episodios=0` **y**
hay ciclos con `cycle_id`, entonces **sí** habría un hueco de software en el escritor de régimen (habría
que investigar `_v2_journal_cycle_regime` / sink). Hoy esa condición **no** se cumple (no hay ciclos), por
lo que la hipótesis de software **no está probada**; solo está probado que **falta operación**.

---

## E. Límites de lo que NO se puede afirmar (evidencia insuficiente declarada)

1. **No se puede afirmar que no exista NINGÚN hueco de software.** Lo verificado es que la cadena de
   sellado de `cycle_id` (§B.0) y el escritor/lector de régimen AUTO-10 existen y están cableados en el
   código. **No** se ha ejecutado el pipeline contra PostgreSQL en esta sesión (solo lectura de código):
   no hay evidencia de **runtime real** de que, con `AUTO_ENGINE_SIM_V2=1`, un fill acabe con `cycle_id`
   no nulo en esta máquina. La falsación de §D es justamente la prueba que lo comprobaría.
2. **No se puede afirmar cuántos días/regímenes producirá el mercado.** `episodes` depende del mercado
   real de los días que se corran (§C.3); ningún conteo futuro es afirmable desde el código.
3. **No se afirma el estado exacto del pin de la ventana ni de los hashes vigentes.** `WINDOW_CONFIG`
   (`window-forward.mjs:256-270`) está en el fichero con un pin concreto, pero el árbol puede haber
   avanzado; el valor efectivo debe leerse al arrancar y puede exigir re-anclaje (`TREE_MOVED`).
4. **No se ha medido la BD en esta sesión.** Se parte del contexto medido aportado (451 cuentas con
   `distinct_days=1`; cuenta declarada con 0 fills; reservas 38/19/13; `auto_paper_evidence_snapshot=0`;
   `v2_98` → `dias=42/4 episodios=0/2 ciclos=0/32`). Estos números **no** se re-midieron aquí.
5. **No se afirma que el `0` actual provenga de una única lane.** El `cycle_id=0` observado es compatible
   con fills manual/legacy y con cuentas que nunca corrieron V2; la atribución exacta por lane exigiría
   consultar la BD (no hecho).
6. **Alcance del cambio de criterio.** Hacer que el **journal** alimente `episodes` (hoy no lo hace,
   §B.2) sería una decisión de producto, **no** aplicada aquí.

---

## F. Índice de evidencias clave (para revisión rápida)

| Tema | `file:line` |
| --- | --- |
| Umbrales 4/2/32 | `packages/py/application/src/bolsa_application/operability_window.py:88-90` |
| `window_gate` (days/episodes/cycles) | `packages/py/application/src/bolsa_application/operability_window.py:493-530` |
| `measurableCycles` (filtro `measured`) | `packages/py/application/src/bolsa_application/operability_window.py:422-428` |
| Certificador (criterios + `UNKNOWN≠0`) | `packages/py/application/src/bolsa_application/paper_window_certification.py:167-207` |
| Día ISO desde reloj durable | `apps/api-python/scripts/v2_80_market_window.py:60-63` |
| Unión de fuentes por día | `apps/api-python/scripts/v2_80_market_window.py:192-211` |
| `cycle_id` → fills/reservas/régimen | `apps/api-python/scripts/v2_80_market_window.py:168-185` |
| Ciclos medibles (por `cycle_id`) | `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:177-219`, `:271-288` |
| `R` medible (reserva > 0) | `packages/py/application/src/bolsa_application/auto_adaptive_confidence.py:376-415`; `cycle_risk.py:231-240` |
| Acuñación `cyc-<hash>` | `packages/py/application/src/bolsa_application/auto_v2_entry.py:1806-1826` |
| Sellado de `cycle_id` en el worker | `auto_simulation_worker.py:1739,1773,1800,2753-2770` |
| Sellado en settlement / contexto / store | `simulated_settlement.py:186,214-228,263,330`; `sim_finance_context.py:43,89`; `sim_durable_store.py:123,545` |
| Columna/índice físico | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:2327`, `:2297` |
| Migración `cycle_id` (sin backfill) | `packages/py/infrastructure/alembic/versions/044_auto_cycle_trace.py:11-22` |
| Régimen AUTO-10 (escritor/lector/sink) | `auto_simulation_worker.py:2989-3032,6853-6887,158`; `_v2_regime` `:1912-1926` |
| Flags de motor (default OFF) | `auto_orchestrator_worker.py:55-58,137-139`; `auto_simulation_worker.py:284,370-378` |
| Snapshots longitudinales | `packages/py/infrastructure/src/bolsa_infrastructure/config.py:143`; `docs/adr/046-protocolo-longitudinal-paper.md:71-73` |
| Permisos SIM-only | `auto_simulation_worker.py:6800-6855` |
| Runner y CLIs | `scripts/window-forward-runner.mjs:6-10,74-77,119-120`; `package.json:67-71` |
| Cuenta/versiones/flags de operación | `scripts/lib/window-forward.mjs:256-270` |
| Certificador `v2_98` | `apps/api-python/scripts/v2_98_paper_window_certification.py:6-31,171-192` |

---

## G. Estado del pin a 2026-10-14 (preflight real)

> Sección de **solo lectura** sobre el código y la BD (preflight/status read-only). No re-ancla nada, no
> escribe en la BD, no avanza la ventana. Evidencia medida hoy, con salida **literal**.

### G.1 El freeze y el re-anclaje legítimo del pin (punto c)

**Qué es el freeze (TREE_MOVED).** El runner forward exige que el árbol de código que va a medir la
ventana sea **un único árbol congelado**. Antes de correr cualquier paso de un día, compara
`git rev-parse "HEAD:apps" "HEAD:packages"` con los hashes pinneados en `WINDOW_CONFIG`
(`scripts/lib/window-forward.mjs:256-258`) y, si no coinciden, **aborta fail-closed** con
`TREE_MOVED` (`scripts/window-forward-runner.mjs:600-611`, chequeo en `gitFreeze` `:234-253`, contraste
en `freezeCheck` `scripts/lib/window-forward.mjs:573-585`). El commit `commit: '9b8e4904'` es solo el
**nombre** del commit cuyo árbol queda pinneado; lo que se compara de verdad son los dos **tree hashes**
(`appsHash` / `packagesHash`).

**Cómo se calcula el hash del árbol.** No es un hash de ficheros ni del working tree: es el
**tree object id de git** para los subdirectorios `apps/` y `packages/` en `HEAD`, obtenido con
`git rev-parse "HEAD:apps" "HEAD:packages"` (`window-forward-runner.mjs:236`) y parseado en
`parseRevParse` (`window-forward.mjs:557-567`, dos líneas en orden `apps`, `packages`). Por diseño
**`scripts/` no participa del pin** (por eso editar `WINDOW_CONFIG` no mueve a su vez el árbol;
`window-forward.mjs:43-45,54-55`). Caveat declarado: el freeze lee el **árbol de `HEAD` (commits
commiteados)**, no el working tree; modificaciones/ficheros sin commitear bajo `apps/`/`packages/`
**no** los detecta el freeze.

**Qué hace `window:unlock`.** Nada que ver con el pin: `window:unlock` es un *escape hatch* que reclama
(el borra, si procede) el **directorio-lock diario** `.run.lock/` de un día, aplicando la misma lógica de
ownership que `run-day` (`cmdUnlock` `window-forward-runner.mjs:920-957`; `unlockDecision`
`window-forward.mjs:417-449`). Nunca borra el lock de un PID vivo de este host; `--force` solo reclama
un lock ajeno con TTL fresco o ilegible. **No re-ancla el pin ni desbloquea el gate de la ventana.** Por
tanto, la redacción de §C.1 («si el gate está bloqueado por el pin del árbol … `window:unlock`») es
imprecisa: ante un `TREE_MOVED` real hay que **re-anclar `WINDOW_CONFIG`** (G.1), no `unlock`.

**Qué implica `--unsafe-override-window-config` (y por qué NO sirve como evidencia).** Permite que las
variables `WINDOW_APPS_HASH`/`WINDOW_PACKAGES_HASH`/`WINDOW_ACCOUNT`/`WINDOW_VERSION_A`/
`WINDOW_VERSION_B`/`WINDOW_WATCH_SIZE` sustituyan la config certificada (`windowConfig`
`window-forward.mjs:294-319`; `FREEZE_ENV_KEYS` `:276-284`). Sella `configMode = 'UNSAFE'` y el runner
avisa de que el gate de esos días **no es válido** (`window-forward-runner.mjs:1029-1034`). Además la
provenance lo **rechaza** explícitamente: `verifyWindowProvenance` empuja el problema
`config_override_unsafe` y el gate sale `STALE`/`NO_MEDIDO` (`window-forward.mjs:687`; test
`window-forward.test.mjs:322-332`). Es un bypass administrativo para depurar, **no** un mecanismo de
ventana: con él, el material medido no acredita la ventana. No usarlo como evidencia.

**Procedimiento de re-anclaje legítimo (documental; NO ejecutado aquí).** No existe **ninguna** CLI ni
script en `scripts/` que recalcule o actualice `appsHash`/`packagesHash` (búsqueda en `scripts/` de
`appsHash|packagesHash|HEAD:apps|rev-parse|hash-object|tree`: solo aparecen el propio modulador y el
runner). El re-anclaje es **edición manual** de `WINDOW_CONFIG` en
`scripts/lib/window-forward.mjs:256-258`, siguiendo el patrón ya documentado en
`docs/engineering/runbook-ventana-forward-v2.78-2026-09-27.md:15-26` (§0) y en los múltiples
«RE-ANCLAJE» del propio fichero (`window-forward.mjs:45-253`). Pasos:

1. Fijar el árbol de código que se quiere congelar (el `HEAD` actual del repo, ya commiteado).
2. `git rev-parse "HEAD:apps" "HEAD:packages"` → dos hashes (orden `apps`, `packages`).
3. Editar en `WINDOW_CONFIG` los tres campos: `commit` (nombre corto del commit), `appsHash` y
   `packagesHash`. Los campos de identidad (`account`, `versionA`, `versionB`, `watchSize`) **no** se
   tocan (`window-forward.mjs:259-263`).
4. Regla de legitimidad: el re-anclaje es legítimo cuando el árbol movido **no cambia el motor** relativamente
   al pin anterior (Δ motor = 0; los RE-ANCLAJE del fichero lo exigen y el replay-repro byte a byte lo
   certifica). Si el pin anterior aún no había medido ningún día, mover el pin no invalida nada.

**¿Invalida la ventana ya medida?** No hay nada que invalidar hoy: la ventana está **NO MEDIDO** (ledger
vacío, §G.3) y el certificador `v2_98` nunca dio `CERTIFIED`. Regla general: si el pin se re-anclara con
días ya `MEDIDO` bajo el árbol viejo, esos días dejarían de verificar (`verifyWindowProvenance` exige
`manifest.freeze.apps === frozen.appsHash` → los días viejos caerían a `STALE`, `window-forward.mjs:681-685`).

### G.2 Salida LITERAL del preflight (punto a)

Comando: `pnpm run window:preflight` (exit code del runner = `0`; el script Python devolvió `exit 2` = veto de régimen, que el runner **declara**, no trata como fallo). Ejecutado 2026-10-14:

```text
> bolsa-v1@2.11.128-beta window:preflight C:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1
> node scripts/window-forward-runner.mjs preflight

node.exe : INFO alembic.runtime.plugins setup plugin alembic.autogenerate.schemas
En C:\Users\josea\AppData\Roaming\npm\pnpm.ps1: 24 Carácter: 5
+     & "node$exe"  "$basedir/node_modules/pnpm/bin/pnpm.cjs" $args
+     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (INFO alembic.ru...enerate.schemas:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

INFO alembic.runtime.plugins setup plugin alembic.autogenerate.tables
INFO alembic.runtime.plugins setup plugin alembic.autogenerate.types
INFO alembic.runtime.plugins setup plugin alembic.autogenerate.constraints
INFO alembic.runtime.plugins setup plugin alembic.autogenerate.defaults
INFO alembic.runtime.plugins setup plugin alembic.autogenerate.comments
INFO alembic.runtime.plugins setup plugin alembic.autogenerate.checkconstraint_byname
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
# preflight: entradas LONG VETADAS (eje BEAR_TREND); no se escribió nada
{
  "account": "(no sembrada: el preflight no escribe)",
  "bump": "2.01.0-beta",
  "level": "evidence",
  "marketRegime": {
    "aggregateTrialRegime": "trend_down",
    "barsLoaded": 20,
    "bySymbol": {
      "0a5dc12fd5a24f0a89a91d36a": "trend_down",
      "0cf0907837fc422db221b0149": "trend_down",
      "240a4ae01a944d3bba1cf1b24": "range",
      "31f9a597d03249319ea0c9345": "trend_down",
      "381dd3b0699a44e8b9d13ac13": "range",
      "49596ff25acb4294b265f321b": "trend_down",
      "4d24ea029283461cb9304421a": "trend_up",
      "54283bcb54674ec1b70b4db72": "trend_down",
      "5a130eea1ad54dcaaa50b67b9": "trend_down",
      "5c34aaec1448406ebec94b20f": "trend_up",
      "615d243eb830473ab009c8997": "range",
      "6655c5faff8a458186dcd8adc": "range",
      "67c117a7d88f4c75a7174e998": "trend_down",
      "6db46176cc2d4845845b6ee6e": "trend_up",
      "6f6215d935c04e0f9ac7bfef7": "trend_up",
      "74c66a856dde4cbaad4888908": "range",
      "7721cde9af0c49d29576786d5": "range",
      "840a307d2b074e2db4dfc3373": "range",
      "856510e40dda4c758f4d4df89": "trend_up",
      "8601a0c3f8d248b0b8052b963": "trend_down"
    },
    "counts": {
      "range": 7,
      "trend_down": 8,
      "trend_up": 5
    },
    "entriesAllowedLong": false,
    "operationalRegime": "BEAR_TREND"
  },
  "minBars": 60,
  "minCyclesPerStrategy": 32,
  "mode": "preflight",
  "phase": "V2.76 AUTO-MATERIAL-4 MARKET MATERIAL FORWARD",
  "venue": "paper",
  "watchA": [
    "0a5dc12fd5a24f0a89a91d36a",
    "0cf0907837fc422db221b0149",
    "240a4ae01a944d3bba1cf1b24",
    "31f9a597d03249319ea0c9345",
    "381dd3b0699a44e8b9d13ac13",
    "49596ff25acb4294b265f321b",
    "4d24ea029283461cb9304421a",
    "54283bcb54674ec1b70b4db72",
    "5a130eea1ad54dcaaa50b67b9",
    "5c34aaec1448406ebec94b20f"
  ],
  "watchB": [
    "615d243eb830473ab009c8997",
    "6655c5faff8a458186dcd8adc",
    "67c117a7d88f4c75a7174e998",
    "6db46176cc2d4845845b6ee6e",
    "6f6215d935c04e0f9ac7bfef7",
    "74c66a856dde4cbaad4888908",
    "7721cde9af0c49d29576786d5",
    "840a307d2b074e2db4dfc3373",
    "856510e40dda4c758f4d4df89",
    "8601a0c3f8d248b0b8052b963"
  ],
  "watchSize": 20
}
[window] preflight: eje BEAR_TREND · LONG VETADAS (exit 2)
[window] veto de regimen legitimo: se DECLARA NO_MEDIDO_REGIMEN; no se fuerza el gobernador
```

Notas de lectura: las líneas `node.exe : ... NativeCommandError` son **ruido de PowerShell** al envolver
el `stderr` del hijo (no son errores); el JSON y las dos líneas `[window] ...` son la salida real. El
preflight declaró «no se escribió nada» y `mode: "preflight"`; no se ejecutó ninguna migración (Alembic
solo inicializa su contexto). **El preflight NO comprueba el freeze**: `cmdPreflight`
(`window-forward-runner.mjs:508-541`) no llama a `gitFreeze`; el `TREE_MOVED` solo lo evalúa `run-day`
(`:600-611`). Por eso el preflight pasó pese a que el árbol está movido (§G.4).

### G.3 Salida LITERAL de `window:status` (read-only)

Comando: `pnpm run window:status` (exit code `0`). Ejecutado 2026-10-14:

```text
> bolsa-v1@2.11.128-beta window:status C:\Users\josea\Documents\Informatica\Typescript\Bolsa_V1
> node scripts/window-forward-runner.mjs status

[window] estado de la ventana · 4 dias / 2 episodios / 32 ciclos
node.exe : [window] ledger vacio: aun no hay ningun dia registrado (NO MEDIDO, nunca 0)
En C:\Users\josea\AppData\Roaming\npm\pnpm.ps1: 24 Carácter: 5
+     & "node$exe"  "$basedir/node_modules/pnpm/bin/pnpm.cjs" $args
+     ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: ([window] ledger...EDIDO, nunca 0):String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError

  resumen: medidos=0 veto=0 declarados=0 duros=0
  gate: NO_MEDIDO (sin dias medidos)
  ledger: operability_runs/window-runs/ledger.jsonl
```

`window:status` es read-only (solo lee `ledger.jsonl` y los `manifest.json`/`window.json` de los runs;
`cmdStatus` `window-forward-runner.mjs:869-910`). Confirma el estado real: **ledger vacío** (0 días
registrados), gate `NO_MEDIDO`. Coincide con la medición de `v2_98` de §A (`INCONCLUSIVE`).

### G.4 Diagnóstico (¿TREE_MOVED? ¿qué falta?)

**Evidencia git medida hoy (2026-10-14, rama `main`):**

```text
HEAD                                    = 0d0a8c15 (v2.88.128 sello ...)
git rev-parse HEAD:apps                 = 25c8fc8f0e90379273522f331cd1e035d9d6a273
git rev-parse HEAD:packages             = 7882ea89127eefd11bad470e216bce620194724b
pin appsHash   (esperado)               = 79fb268580fb46e4b2766c961b2b87f2d7c13b38
pin packagesHash (esperado)             = f80b2285da4624474a56e8df71c6e56b532120f0
git cat-file -t 9b8e4904                = commit  (existe)
git rev-parse 9b8e4904:apps              = 79fb2685... (coincide con el pin)
git rev-parse 9b8e4904:packages          = f80b2285... (coincide con el pin)
```

**Veredicto: el pin está DESFASADO ⇒ `TREE_MOVED` garantizado.** El pin apunta al árbol del commit
`9b8e4904` (sello `v2.88.77-beta`); el HEAD actual es `0d0a8c15` (sello `v2.88.128`). Ambos tree hashes
difieren de los pinneados. Si se lanzara `pnpm run window:run-day`, abortaría con `TREE_MOVED` **antes**
de la fase de preflight (`window-forward-runner.mjs:600-611`), sin escribir la ventana.

**Qué bloquea hoy, en orden, para arrancar la ventana:**

1. **Pin desfasado (`TREE_MOVED`)** — bloqueador **operativo** del runner, no un hueco de motor (§B). Es
   el único bloqueador **medido hoy** con certeza a nivel de runner: sin re-anclar, `run-day` no arranca.
2. **Sin días registrados** — el ledger está vacío (`≠` 0 fabricado; es «no medido»). No hay ventana en
   curso: `v2_98` sigue `INCONCLUSIVE` (dias=42/4, episodios=0/2, ciclos=0/32).
3. **Régimen de HOY = `BEAR_TREND` con LONG vetadas** — el preflight de hoy declara veto legítimo. Esto
   **no** es un fallo ni se fuerza: un día con veto se registra `NO_MEDIDO_REGIMEN` (§C.1). Para sumar
   `episodes`/`cycles` hacen falta días de mercado operables (LONG permitidas) y **días distintos** (§C.3).
4. **Precondiciones de entorno que hoy SÍ responden:** el preflight cargó `barsLoaded: 20` desde la BD
   (PostgreSQL + venv operativos en esta máquina). No se midió el estado de la API `/api/health/ready`
   (el preflight no la exige; solo `run-day` la exige para el forward, `:670-686`) ⇒ **no verificado hoy**.

No hay, por tanto, un bloqueador de software en el camino de la ventana: el bloqueo es **operar**
(re-anclar pin + correr días operables reales). La falsación de §D sigue sin cumplirse (no hay ciclos).

### G.5 Siguiente paso concreto y responsable

1. **Quién/cuándo — re-anclar (responsable: propietario del repo / operador de la ventana; cuando se decida
   arrancar).** Editar `WINDOW_CONFIG` en `scripts/lib/window-forward.mjs:256-258` con:
   - `commit`: `0d0a8c15`
   - `appsHash`: `25c8fc8f0e90379273522f331cd1e035d9d6a273`
   - `packagesHash`: `7882ea89127eefd11bad470e216bce620194724b`

   (valores medidos hoy; **no re-anclados en esta sesión**). Antes de fijarlos, confirmar la regla de
   legitimidad de G.1 (Δ motor = 0 respecto al pin anterior, o ventana aún no medida —hoy lo segundo se
   cumple—). Es un fichero de `scripts/`, fuera del pin de motor.
2. **Verificar el re-anclaje sin medir:** `node scripts/window-forward-runner.mjs --dry-run run-day`
   (valida config/freeze/cadena **sin** abrir el motor; `dryRunDay` `window-forward-runner.mjs:802-836`
   y exige `freeze.ok`). Debe imprimir `freeze OK`. (No ejecutado aquí por ser potencialmente
   preparatorio del run-day; el freeze se puede previsualizar con el `git rev-parse` de G.4.)
3. **Arrancar la operación real** — solo con re-anclaje hecho y un día de mercado **operable**: la
   secuencia de §C.1/§C.2 (`window:preflight` → `window:run-day` → `window:status`), un día de pared
   distinto por corrida, sin forzar régimen y sin escribir en la BD. `window:unlock` **no** es parte de
   este paso (solo gestiona el lock diario huérfano).
4. **Certificar** con `v2_98` (§D) cuando haya ≥4 fechas, ≥2 regímenes y ≥32 ciclos medibles.

### G.6 Puntos no verificados en esta sección (declarados)

- No se ejecutó `window:run-day` (ni `--dry-run run-day`), `window:unlock` ni `window:task:*`; **no** se
  re-ancló el pin. El `TREE_MOVED` se **infiere** de los `git rev-parse` (G.4), no de un run real.
- No se comprobó `/api/health/ready` (la API que mantiene las barras frescas para el forward); el
  preflight no la requiere, así que su estado queda **NO MEDIDO**.
- El preflight leyó PostgreSQL (contexto Alembic + `barsLoaded`) pero **no** se ejecutó ninguna migración
  ni escritura; el propio script declara `mode: "preflight"` y «no se escribió nada».
- El freeze compara el árbol de `HEAD` **commiteado**, no el working tree: cambios o ficheros sin
  commitear bajo `apps/`/`packages/` no los vería (a la fecha de esta sección el árbol estaba **limpio**
  en `0d0a8c15`; verificar el working tree antes de medir es responsabilidad del operador).
