# Audit pack — V2.42.2 / AUTO-2 slice 2c (cierre): evidencia de un día, ATR medido y cero política legacy (`1.67.2-beta`)

**Qué es:** el **cierre de `AUTO-2`**. El slice 2c no añade capacidades nuevas de gestión: añade la
**evidencia** que el §4 del roadmap exige para dar `AUTO-2` por cerrado y convierte en **estructural** la
afirmación de que con el motor V2 ON la política de protección antigua no se lee.

**Ref auditada:** tag anotado **`v2.42.2-beta` → ** _(commit y runs de CI en el §8.1, se rellenan al sellar)_.
Todo lo que se afirma aquí se mide contra esa ref; `main` puede ir por delante sólo con docs.

**Alcance de la auditoría:** slices 2c **y** la afirmación de cierre de `AUTO-2`. Lo publicado en 2b (E1, E2,
E3, H-1..H-7) **ya se auditó** en su pack; aquí se re-mide lo que 2c toca y se comprueba que 2c **no**
degradó nada de 2b (las baterías completas se declaran en el §8.2).

---

## 1. Qué afirma esta versión (y qué no)

**Afirma:**

1. Que el **día** sabe **por qué** cerró cada posición: la fila de cierre del journal del día lleva el motivo
   (`SimJournalRow.reason`) y el reporte lo agrega (`AutoDailyReport.exit_reasons`), con
   **`sum(exit_reasons) == exits`** — un cierre sin motivo declarado se cuenta como **`undeclared`**, nunca
   se le atribuye un motivo que no declaró.
2. Que el motivo es el **decisorio** (`primary_reason` → `day_exit_reason`), así que **un stop-out no se
   cuenta como salida por tesis** ni al revés (test medido con los tres desenlaces el mismo día).
3. Que la **procedencia del ATR** del día se **mide** (`real`/`fallback`/`missing`) y viaja al reporte; sin
   medición el reporte queda **vacío**, no inventado.
4. Que con `AUTO_ENGINE_SIM_V2=1` la **política de protección legacy no se evalúa en ningún caso** — es una
   condición **estructural** (el `else` está detrás de `not self._v2_enabled`), no de valor, y un **sensor
   que explota** (`AssertionError` en `protection_exit_reason`/`protection_exit_fraction`) demuestra que el
   día completo corre igual.
5. Que existe **evidencia reproducible** del día: un script sin DB ni red que corre el día, emite JSON con
   motivos + ATR + techo congelado + lecturas de la política legacy, y **sale ≠ 0** si el criterio no se
   cumple.
6. Que la suite offline de CI es **más ancha** que antes: `test_auto_daily_journal.py` (que existía desde
   `v2.24`) **no estaba en ninguna lista de CI** y ahora corre en los dos jobs offline — deuda de cobertura
   detectada por el runner que verifica rutas **contra el YAML**.

**NO afirma:**

1. Que el día evidencial sea una **sesión de mercado real**. Es un día **hermético** (stores `InMemory*`,
   precio y ATR inyectados, sin PG). Es un día **completo del motor** (33 ticks, 6 órdenes, 24 fills, 3
   posiciones, 3 desenlaces distintos), no un backtest con datos de mercado.
2. Que la `ProtectionConfig` **no se construya** nunca. Se sigue construyendo en el constructor
   (`_protection_config_from_env()`), porque el camino `AUTO_ENGINE_SIM_V2=0` debe conservar el
   comportamiento `v2.39.x`. Lo que 2c hace estructural es que **con V2 ON no se lee**.
3. Que el veto de ATR esté activo: **nace OFF** (D3 pedía **medir primero**). El día declara `veto: "0"`.
4. Que `REGIME_EXIT` o `RISK_EXIT` sean eventos del FSM: **no lo son** (§6).
5. Que se haya medido **PG real** en esta máquina: **no** (motivo medido y declarado, §6). La durabilidad la
   certifica CI en sus jobs con PG.
6. Que `TIME_EXIT`/`THESIS_EXIT` sesión a sesión estén ya flipados en producción: **siguen detrás del flag
   `AUTO_ENGINE_SIM_V2`** (y el atajo de tests, `v2_env`, no es una bandera de arranque).

---

## 2. Punto de partida verificado (lo que este slice cierra)

El §4 del roadmap de `AUTO-2` exige, como criterio de salida, **dos** cosas que 2b dejó abiertas:

| Criterio del §4                                                       | Estado antes de 2c                                                                 | Qué se hace en 2c                                                                |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `TIME_EXIT`/`THESIS_EXIT` con **evidencia en el journal de un día**   | Existían y vendían (2b), con tests herméticos y PG, pero **el día no los contaba** | El día cuenta y declara sus motivos (`exit_reasons`, con `undeclared` explícito) |
| `ProtectionConfig` **sin ninguna lectura** con `AUTO_ENGINE_SIM_V2=1` | El `if` legacy **se evaluaba** (y devolvía `None`) en `held == 0`/`price <= 0`     | El `else` legacy queda detrás de `not self._v2_enabled`: **no se evalúa**        |
| Medición del **ATR real** (D3: cablear y medir)                       | Contadores privados por origen; **nadie los leía** fuera de los tests              | `atr_source_counts()` público + `atr_sources` en el reporte del día              |

Deuda de cobertura cerrada de paso: `packages/py/application/tests/test_auto_daily_journal.py` **no estaba
en ninguna lista de CI** desde `v2.24`; sus gates (incluidos los de contabilidad del día) no corrían.

---

## 3. Matriz afirmación → código → test

### a) Etiqueta del día (motivo decisorio, dueño único)

- **Código:** `packages/py/application/src/bolsa_application/auto_reason_codes.py::day_exit_reason`
  (`TIME_STOP → time_exit`, `THESIS_INVALIDATION → thesis_exit`, `STRUCTURAL_STOP → structural_stop`,
  `PORTFOLIO_RISK → portfolio_risk`, targets, `TRAIL → trail`, `MANUAL → manual`) y
  `DAY_EXIT_REASON_UNDECLARED` para el cierre sin motivo. Un motivo no catalogado se declara **en
  minúsculas tal cual**: no se inventa etiqueta.
- **Test:** el día golden exige `{time_exit: 1, thesis_exit: 1, structural_stop: 1}` con los tres
  desenlaces el mismo día y `structural_stop` **fuera** de los motivos de gestión del journal rico.

### b) El motivo viaja en la fila del día

- **Código:** `auto_daily_journal.py::SimJournalRow.reason` (aditivo, default `""`) +
  `build_auto_daily_report(..., atr_sources=...)`, que agrega `exit_reasons` desde la `reason` de cada fila
  de cierre (`_sorted_counts`: conteo desc, etiqueta asc ⇒ orden determinista) y expone `as_dict()`.
- **Worker:** `_emit(..., reason=...)`; la fila `position_close` **con V2 ON** lleva la etiqueta del día
  (`_v2_last_exit_label`, poblada por `_v2_position_package` y **vaciada al inicio de cada turno** ⇒ sin
  atribuciones rancias), y **en el camino legacy** lleva el motivo de protección.
- **Tests:** 5 puros en `packages/py/application/tests/test_auto_daily_journal.py` (conteo, `undeclared` que
  no se disfraza, orden determinista, ATR medido, ATR no inventado).

### c) La procedencia del ATR se mide y se puede leer

- **Código:** `AutoSimulationWorker.atr_source_counts()` (público; devuelve copia) sobre
  `_v2_atr_source_counts`, incrementado en `_v2_atr_geometry` (`real`/`fallback`/`missing`).
- **Test:** el día golden exige `real > 0` y `fallback == 0` con ATR inyectado, y el caso de ATR real
  ausente declara la procedencia que **de verdad** ocurrió.

### d) Cero política legacy con V2 ON (estructural)

- **Código:** `auto_simulation_worker.py::auto_turn` — con V2 ON el camino es
  `if held > 0 and price > 0: v2_pkg = await self._v2_position_package(...)`, y el `else` de
  `protection_exit_reason` (con la supresión del T1 parcial legacy, `_t1_done`) queda detrás de
  `not self._v2_enabled`.
- **Test:** `test_v2_golden_day_never_reads_the_legacy_protection_policy` sustituye
  `protection_exit_reason` **y** `protection_exit_fraction` por funciones que **lanzan** y corre el día
  entero hasta cerrar el libro.

### e) Evidencia reproducible y CI

- **Script:** `apps/api-python/scripts/v2_42_2_golden_day_evidence.py` (`--out`; exit ≠ 0 si el día no
  cumple: `healthy`, `sum(motivos) == exits`, los tres motivos, `legacy_policy_reads == 0`, libro plano).
- **CI:** `test_auto_v2_golden_day_evidence.py` en el **pase de directorio** `apps/api-python/tests` del job
  `quality` y **explícito** en el job `python` del tag; `test_auto_daily_journal.py` **añadido a ambos**
  (antes: en ninguno).

---

## 4. Matriz de mutaciones **medida** (7 mutaciones, 7 rojos)

Cada mutación se aplicó sobre el árbol de trabajo, se corrió el target acotado y **se revirtió verificando
el contenido exacto** (medir con el árbol moviéndose es el fallo de proceso que la auditoría de 2a destapó y
que no se repite aquí).

| #   | Mutación                                                                           | Efecto medido                                     |
| --- | ---------------------------------------------------------------------------------- | ------------------------------------------------- |
| M1  | `TIME_STOP` se mapea a `thesis_exit` en la etiqueta del día                        | **2 rojos** (diario puro + día golden)            |
| M2  | La fila `position_close` pierde el motivo (el día vuelve a no saber por qué)       | **1 rojo** (el día golden exige los tres motivos) |
| M3  | Con V2 ON se vuelve a evaluar la política legacy (`held == 0` entra por el `else`) | **1 rojo** (el sensor del día explota)            |
| M4  | La medición de ATR del día se queda vacía (`atr_source_counts → {}`)               | **2 rojos**                                       |
| M5  | `STRUCTURAL_STOP` se mapea a `thesis_exit` (el stop-out se disfraza)               | **2 rojos**                                       |
| M6  | Un cierre sin motivo declarado se atribuye a `time_exit`                           | **3 rojos**                                       |
| M7  | El reporte del día olvida los motivos (`exit_reasons` vacío)                       | **4 rojos**                                       |

---

## 5. Cambios observables y breaking declarado (beta)

1. **`SimJournalRow`** gana `reason` (aditivo, default `""`): quien construya la fila posicionalmente no se
   rompe; quien lea `as_dict()` ve una clave nueva.
2. **`AutoDailyReport`** gana `exit_reasons` y `atr_sources` (tuples deterministas, default `()`): aditivo.
   `as_dict()` incluye `"exit_reasons"` y `"atr_sources"` como dicts.
3. **`build_auto_daily_report`** gana el parámetro keyword `atr_sources` (default `None` ⇒ sin medición).
4. **Consecuencia declarada del restructure (camino legacy):** en una SELL con `qty <= 0`, antes se emitía
   `hold_no_op` (la política legacy devolvía `None` y el tick se cerraba con "hold sin cantidad"); ahora ese
   caso cae por el camino normal (no emite la fila de hold). Es un cambio observable **sólo** en el camino
   legacy y **sólo** en un caso degenerado; se declara aquí en vez de esconderlo.
5. Sin migración (Alembic head sigue en `042_portfolio_reservations`). Bump `1.67.1-beta` → `1.67.2-beta`.

---

## 6. Límites declarados (lo que este slice NO resuelve)

- **Día hermético, no sesión real**: los precios y el ATR se inyectan; no hay feed. La evidencia cierra el
  criterio "journal de un día con `time_exit`/`thesis_exit`", no "un día de mercado".
- **PG real no medido aquí** (medido y declarado: el `connect` del DSN local no responde ni rechaza y cuelga).
  Lo certifica CI en los jobs con PG (`lifecycle-pg` del tag y los `-pg` de `python-ci.yml`).
- **Veto de ATR OFF por defecto** (D3: medir primero). Fliparlo es decisión del owner y va con el número
  delante (`atr_source_counts`: hoy `real = 15/15` en el día golden, que es un día **inyectado**).
- **`REGIME_EXIT` no es un evento del FSM** (existe en el camino legacy con precedencia absoluta). El
  régimen como evento y `RISK_EXIT` llegan con el **gobernador de `AUTO-3`**.
- **El emisor de `RECONCILED` sigue sin existir** en el camino del worker: `H-1` endurece la puerta, no la
  abre. Una posición adoptada sin estado verosímil se queda degradada (fail-closed) con
  `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING`, como se diseñó.
- **Horizonte por plantilla**, no por estrategia: `resolve_holding_horizon` lee
  `trading_policy_templates`; no hay política de horizonte por estrategia ni override por símbolo.
- **La protección legacy se sigue construyendo** en el constructor (necesaria para el camino flag-OFF).

---

## 7. Cómo reproducir la verificación

```bash
# 0) Estático con la invocación EXACTA de CI (no añadas packages/py/analytics/src: CI no lo compila)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src \
             --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# 1) Suites del slice (segundos)
uv run pytest packages/py/application/tests/test_auto_daily_journal.py \
              apps/api-python/tests/test_auto_v2_golden_day_evidence.py -q

# 2) Evidencia del día (JSON; sale != 0 si el criterio no se cumple)
uv run python apps/api-python/scripts/v2_42_2_golden_day_evidence.py --out /tmp/dia.json

# 3) Offline de los dos jobs, con la lista EXTRAÍDA del YAML (verifica que cada ruta existe;
#    los ficheros PG que en CI saltan por falta de servidor se ignoran si el DSN local cuelga)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# 4) PG real (certificación). Un skip es FALLO.
AUTO_V2_LIFECYCLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_lifecycle_pg.py -q
```

> Nota: el runner de CI vive en el repo (`scripts/verify/offline_ci_run_yaml.py`, stdlib + `pyyaml`) desde
> esta fase, precisamente para que la medición local sea reproducible y **no** una copia a mano de la lista
> (dos veces midió otra cosa que CI: la errata del §8.2).

---

## 8. Evidencia de verificación

### 8.1 CI real de GitHub

_(se rellena al sellar: commit, tag, runs de `Python CI` y `Release tag CI` con sus conteos)_

### 8.2 Baterías locales (medidas en el árbol final del slice, antes de publicar)

- `ruff`: **All checks passed** · `mypy`: **487 ficheros, 0 issues** · `lint-imports`: **4 kept / 0 broken**.
- Job `quality` (`python-ci.yml`), 41 rutas y 8 ficheros PG a `--ignore`: **1935 passed, 0 failed, 0 skipped**
  (53,2 s). Job `python` (`release-tag-ci.yml`), 50 rutas y 8 PG a `--ignore`: **1946 passed, 0 failed,
  0 skipped** (19,3 s). Medido por **JUnit XML** (el stdout de pytest no se recolecta bien bajo `subprocess`
  en Windows: la línea de resumen se pierde) y con `--noconftest` (el conftest de la app habla con PG).
  Los 21 tests de 2c están dentro de esas cifras (+18 del diario que ahora sí se recolecta, +3 del día golden).
- Lectura frente a CI: en CI esos 8 ficheros PG **se recolectan y saltan rápido** (no hay servidor en el job
  offline), así que los conteos de CI llevan un bloque de `skipped` que aquí no aparece. Es el mismo
  tratamiento distinto de las suites gated que ya se declaró en 2b.
- **Errata de herramienta declarada:** el runner local declaró una corrida colgada ~15 min porque su
  detección de PG exigía `_pg` **pegado al final del nombre** y se le escapaban dos ficheros de scheduler
  (`test_a9_scheduler_process_pg_zero_human.py`,
  `test_auto_scheduler_real_pg_zero_human_intervention.py`), cuyo `connect` al DSN local cuelga. Corregido
  (`test_*_pg*.py`) y **el runner pasa a vivir en el repo** (`scripts/verify/offline_ci_run_yaml.py`), para
  que la medición local deje de ser una copia a mano: es la segunda vez que un runner local mide **otra
  cosa** que CI.

### 8.3 Evidencia del día (salida del script, JSON)

```json
{
  "bump": "1.67.2-beta",
  "day": {
    "exit_reasons": { "structural_stop": 1, "thesis_exit": 1, "time_exit": 1 },
    "exits": 3,
    "positions_created": 3,
    "orders": 6,
    "fills": 24,
    "healthy": true,
    "ledger_balance_status": "BALANCED"
  },
  "positions": {
    "AAA": { "exit": "time_exit" },
    "BBB": { "exit": "thesis_exit" },
    "CCC": { "exit": "structural_stop" }
  },
  "atr": {
    "sources": { "real": 15, "fallback": 0, "missing": 0 },
    "signals": 15,
    "real_share_pct": 100.0,
    "veto": "0"
  },
  "holding_deadline_at": "2026-10-30T09:00:00Z",
  "journal_codes": ["thesis_exit", "time_exit"],
  "legacy_policy_reads": 0,
  "open_symbols_at_close": []
}
```

---

## 9. Auditoría externa: qué debería intentar romper

1. **La suma de motivos**: ¿hay algún camino de cierre que **no** pase por la fila `position_close` del día
   (y por tanto no se cuente en `exit_reasons`)? Si existe, `sum(exit_reasons) == exits` debería delatarlo.
2. **Atribución cruzada**: forzar un cierre por stop con la tesis "rozada" y comprobar que el día cuenta
   `structural_stop` (y que el journal rico **no** declara `thesis_exit`).
3. **Cero legacy**: quitar el `if self._v2_enabled` del restructure y comprobar que el sensor del día
   **explota** (si no explota, el test no prueba lo que dice).
4. **Atribución rancia**: buscar un camino en el que `_v2_last_exit_label[symbol]` sobreviva de un turno
   anterior (se vacía al inicio de cada `auto_turn`: ¿es suficiente? ¿y una venta del decider sin gestión
   V2 el mismo turno?).
5. **`undeclared`**: provocar un cierre V2 sin motivo declarado y comprobar que el día dice `undeclared` en
   vez de `time_exit`.
6. **ATR no inventado**: pedir el reporte sin `atr_sources` y comprobar que queda **vacío** (no `real: N`).
7. **El día golden, sin trampa**: ¿los tres desenlaces son **reales** (precio atravesando el nivel, techo
   vencido por reloj) o hay algún atajo (por ejemplo, una `replace()` sobre la copia del estado) que haga
   pasar el test sin que el motor lo haría? El atajo declarado es el nivel de invalidación de `BBB`
   (seam: hoy ningún productor lo manda al `TradePlan`); el resto es precio y reloj.
8. **Coste**: ¿2c cambió de verdad el comportamiento del día o solo el reporte? (diff de conteos: `quality`
   +21 tests; el resto de la suite sin cambios).
