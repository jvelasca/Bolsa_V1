# Runbook de cierre `P1`-`P4` — operativa diaria de la ventana PAPER (2026-10-15)

> **Qué es:** la secuencia **manual y guiada** para operar la ventana PAPER de `AUTO` y cerrar los
> pendientes operativos `P1`-`P4` de la auditoría `v2.88.134-beta`, con los instrumentos del sello
> `v2.88.136-beta` (lane alineada al universo **ESTUDIO**, bundle de evidencia `v2_100` y helper de
> pin `window:pin`).
>
> **Qué NO es:** no es un pipeline de CI. **≥4 días de CALENDARIO operables** salen del **reloj de
> pared** y de un **mercado que permita LONG**: no se fabrica ni se fuerza el régimen. Si el mercado
> veta LONG, el día **no es medible** y se declara `NO_MEDIDO_REGIMEN` (no es un fallo).

**Base:** [`docs/engineering/evidence/v2.88.136/README.md`](./evidence/v2.88.136/README.md) ·
**Criterios falsables:** [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md) §6.

---

## 0. Preparación (una vez)

- **PostgreSQL** arriba y migrado (head `054_dia_d_verified_and_alerts`).
- **API** arriba: `GET /api/health/ready` → `status: ready` (el scheduler de barras vive en el API).
- **Universe ESTUDIO sembrado** (~35 valores): si `resolve_daily_watch` devuelve `empty`/`unavailable`,
  el watch de la ventana queda vacío y el día **no se opera** (fail-closed). Siémbralo **antes** de empezar.
- **Flags de motor OFF** (SIM-only): `AUTO_ORCHESTRATOR_ENABLED` / `AUTO_SIMULATION_WORKER_ENABLED`
  no se activan para medir la ventana PAPER (la ventana usa el harness `v2_76`).
- **Defaults de aislamiento INTACTOS:** `BROKER_VENUE=paper` y **sin** `LIVE_EXECUTION_UNLOCKED` ni
  `LIVE_EXECUTION_AUTHORIZED` (los inyecta el runner; no los pongas a mano).

---

## 1. Secuencia diaria (UNA corrida por día de pared)

Todos los comandos, desde la raíz del repo:

### Paso 1 — Comprobar el freeze (fail-closed)

```bash
pnpm run window:freeze
```

- Debe imprimir **`freeze OK`** (`HEAD:apps`/`HEAD:packages` == pin).
- Si imprime **`TREE_MOVED`**: el árbol commiteado cambió. **No operes**: re-ancla con
  `pnpm run window:pin -- --note "<motivo>"` (solo si el avance del árbol es legítimo) y revisa el
  commit. Un `run-day` sobre un árbol movido **no** certifica.

### Paso 2 — Preflight (¿el mercado admite LONG hoy?)

```bash
pnpm run window:preflight
```

- `exit 0` y eje operable ⇒ **el día es medible**: sigue al paso 3.
- `exit 2` con veto (`BEAR_TREND`/`UNKNOWN`) ⇒ **LONG VETADAS**: el día se registra como
  **`NO_MEDIDO_REGIMEN`** y **no se opera** (el runner lo hace solo). **No se fuerza el régimen.**
  Repite en el siguiente día operable.
- Error duro (sin payload, PostgreSQL caído, watch ESTUDIO vacío) ⇒ **no** es veto: revísalo antes de
  continuar. El runner solo acepta un `exit 2` como veto si trae el **payload de preflight válido**
  (`mode: preflight` + `marketRegime`); un `exit 2` **sin** payload (p. ej. el intérprete no arrancó)
  se trata como **FALLO DURO** (exit 1), nunca como veto. Así se distingue «no hay entradas
  permitidas» de «no se pudo ejecutar o medir».

### Paso 3 — Correr el día (forward + journal + ventana + auditoría)

```bash
pnpm run window:run-day
```

El runner inyecta, **solo en el hijo**: `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`,
`BROKER_VENUE=paper`, y pasa `--watch-from-estudio` (universo **ESTUDIO** ∩ allowlist). Encadena
`v2_76` (forward) → `v2_77` (journal) → `v2_80` (ventana) → `v2_83` (auditoría) y sella
`operability_runs/window-runs/<DIA>/`.

### Paso 4 — Bundle de evidencia del día (`P1`-`P4`)

```bash
pnpm run window:evidence
```

Escribe `operability_runs/daily-evidence/<DIA>/evidence.{json,md}` con la matriz `P1`-`P4`
(certificador `v2_98` + cadena ESTUDIO `v2_99` + enlace DÍA-D + aislamiento). Regla `UNKNOWN ≠ 0`:
un hueco se declara `null` y **no** cierra el pendiente.

### Paso 5 — Estado de la ventana

```bash
pnpm run window:status
```

Lee el ledger: días medidos / vetados / declarados y el gate (`≥4 días`, `≥2 episodios`, `≥32 ciclos`)
**ligado al run** (un ledger `STALE` no certifica).

> **Nota:** si un `run-day` quedó a medias y el lock diario es huérfano, `pnpm run window:unlock`
> (nunca salta un PID vivo de este host).

---

## 2. Criterios de CIERRE (falsables, sin rebajar)

### `P1` — Ventana PAPER real (ADR-046)

Repite la secuencia en **≥4 fechas de calendario distintas y operables** y certifica:

```bash
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py \
  --account-id 1484e253d2d54645945a6b1d7 \
  --strategy-version v283-window-a --strategy-version v283-window-b \
  --json
```

**Cierra** con `verdict == READY`, `days ≥ 4`, `episodes ≥ 2`, `measurableCycles ≥ 32` y
`missingCriterionIds` **vacío**. Si el mercado veta LONG, sigue **`INCONCLUSIVE`** (hueco honesto).

### `P2` — Evidencia por valor de ESTUDIO

```bash
uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py \
  --account-id 1484e253d2d54645945a6b1d7 --engine-id auto-sim --json
```

**Cierra** con valores medidos **`>0/35`** y cadenas que alcanzan `FILL`/`CYCLE_CLOSED` (9 etapas) con
`pnl.reconciled == true`.

### `P3` — Enlace DÍA-D ↔ ciclo

Tras el **primer ciclo AUTO real** con `strategyPresetKey` sellado:

1. En `/auto/operar`, pulsa **«Verificar D→hoy»**.
2. Lee el resultado:

```bash
# cycleId = el del ciclo AUTO que acaba de cerrar
GET /api/auto/dia-d-verifications?cycleId=<cycleId>
```

**Cierra** con una fila real en `dia_d_cycle_verifications` cuyo `cycleId` case con el ciclo AUTO y
`executedVsDiaD.matches != null` (True o False; nunca fabricado con una sola fuente).

### `P4` — Aislamiento fail-closed (MANTENER)

No requiere acción diaria; **evidencia** = suite de aislamiento verde **+** invariante de venue.

**Criterio ESTRICTO (corregido en `v2.88.135`).** El bundle `v2_100` sólo cierra `P4` con
`BROKER_VENUE == "paper"` **explícito**, las dos envs LIVE ausentes **y** CERO trazas con venue LIVE
**medidas**. Antes cerraba con `venue != "live"`, que era **más débil** que este contrato: un venue
vacío, `xtb` o desconocido podía cerrar `P4`. Un venue vacío/desconocido ahora **no** cierra `P4`.
`UNKNOWN ≠ 0`: si la BD no se puede leer, el conteo es un hueco y `P4` queda **ABIERTO**, nunca `0`.

```sql
-- Debe devolver 0 con los defaults (venue=paper, envs LIVE ausentes).
SELECT count(*) FROM execution_events
WHERE account_id = '1484e253d2d54645945a6b1d7'
  AND lower(venue) IN ('live', 'broker_live', 'xtb', 'real', 'live_bridge');
```

`P4` es un invariante de **mantenimiento**: su verde **no** acredita la operación PAPER.

---

## 3. Registro y trazabilidad

- **Por día:** `operability_runs/window-runs/<DIA>/` (manifest + pasos) y
  `operability_runs/daily-evidence/<DIA>/` (matriz `P1`-`P4`).
- **Días no operables:** quedan como `NO_MEDIDO_REGIMEN` en el ledger (declarados, no cuentan como
  medidos).
- **No fabricar:** nunca rellenar `cycle_id`/`reserved_risk`, ni backdatear `created_at`, ni forzar
  `AUTO_ENGINE_SIM_V2_REGIME`, ni bajar umbrales para alcanzar un `READY`.

---

## 4. Re-anclaje del pin (solo cuando el árbol avance por un commit legítimo)

```bash
pnpm run window:freeze                                   # ¿freeze OK o TREE_MOVED?
pnpm run window:pin -- --note "sello v2.88.136"          # re-ancla commit/appsHash/packagesHash
pnpm run window:freeze                                   # debe volver a freeze OK
```

`window-pin.mjs` vive en `scripts/` (no participa del freeze), así que re-anclar **no** mueve a su vez
el árbol. El commit de re-anclaje es el **POST-TAG** (después del sello/tag), como en los sellos
previos.

---

## 5. Qué queda ABIERTO al terminar el runbook

- `P1`/`P2`/`P3` dependen de **días de mercado operables** (`P2`/`P3` dependen de `P1`).
- La **magnitud/rentabilidad** del P&L sigue **NO MEDIDA**.
- Con `BEAR_TREND`, el cierre puede tardar **semanas**: es **MERCADO**, no software.

---

## 6. Incidencia de CI `S5-04` — medir el primer intento, NO cambiar `timeouts`

**Diagnóstico.** El primer intento del journey integrado `GP-V288-S5-04` supera los 60 s y el retry
pasa. No es un defecto del producto: es **lentitud del primer arranque**. El fix de `v2.88.135` hizo
el test idempotente ante reintentos, pero **no** eliminó esa lentitud.

**Instrumentación read-only (sin tocar `timeout` ni `retries`).**

- El job `playwright (integrated AUTO S5)` de [`release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml)
  añade un segundo reporter **JSON** a fichero (`/tmp/s5-integrated-report.json`); el reporter `list`
  sigue alimentando el guard anti-skip (`/tmp/s5-integrated.log`), que **no** se toca.
- Un paso publica los tiempos por intento con [`scripts/ci/playwright-attempt-timings.mjs`](../../scripts/ci/playwright-attempt-timings.mjs)
  (parser puro) y sube el JSON + `s5-timings.txt` como artefacto
  `playwright-integrated-auto-s5-timings` (incluso en rojo).
- Los tramos lentos de `S5-04` (abrir la operación, lanzar la verificación D→hoy, esperar la
  evidencia LAB, guardar/verificar el enlace durable) se nombran con `test.step`, de modo que el
  informe JSON declara **qué fase** consume el tiempo.

**Regla operativa.** No ampliar `timeout` ni `retries` para «pasar». Primero **medir** en varias
ejecuciones (local o CI); solo con el delta y la fase identificada se decide una optimización, y
nunca ocultando el fallo mediante reintentos.

Reproducción local (mismo informe):

```bash
cd apps/web
PLAYWRIGHT_JSON_OUTPUT_NAME=/tmp/s5-integrated-report.json \
  pnpm exec playwright test gp-v288-s5 --reporter=list --reporter=json --retries=1
node ../../scripts/ci/playwright-attempt-timings.mjs /tmp/s5-integrated-report.json
```

### 6.1 Diagnóstico del arranque en frío de `S5-04`: de «dónde espera» a «qué componente tarda»

Lo anterior mide **dónde** espera el test (`test.step`), no **qué componente** consume el tiempo. Para
atribuir los ~60 s del primer intento a una fase con evidencia medida, se añade instrumentación
**read-only** (commiteada) en tres capas. **No** se amplía `timeout`, **no** se cambia `retries: 1`,
**no** se tocan aserciones, umbrales ADR-046 ni se crea sello nuevo.

**A. Fases del servidor (`RunAndSaveBacktest`).** En [`backtests.py`](../../packages/py/application/src/bolsa_application/backtests.py),
`_PhaseTimer` cronometra con `perf_counter` cada fase (`instrument_lookup`, `strategy_lookup`,
`ohlcv_load`, `fingerprints`, `compute`, `manifest`, `save_run`, `trial`, `evidence`) y emite **una**
línea por `POST /api/backtests/run`, **gated** por `BOLSA_BACKTEST_TIMING=1` (default **OFF**: sin la
env, el comportamiento es equivalente al histórico; no cambia el resultado ni el contrato HTTP):

```
[backtest-timing] label=run_and_save_backtest instrument_lookup=..ms ohlcv_load=..ms compute=..ms \
  ... total=..ms instrument_id=.. strategy_type=.. bars=.. limit=..
```

**B. Red/navegador.** [`apps/web/e2e/helpers/s5-network-timings.ts`](../../apps/web/e2e/helpers/s5-network-timings.ts)
se engancha en el test `S5-04` (listeners `requestfinished`/`requestfailed`) y registra
`{method, pathname, resourceType, status, durationMs, offsetMs}` por petición. Vuelca a
`<S5_TIMINGS_OUT>.attempt<N>.json` — **un fichero por intento**, para que el retry no sobrescriba al
primer intento — y lo hace en `finally` (también en rojo). Sin `S5_TIMINGS_OUT` es un **no-op**.

**C. Parser puro.** [`scripts/ci/s5-network-timings.mjs`](../../scripts/ci/s5-network-timings.mjs)
(+ `s5-network-timings.test.mjs`, ejercitado por `pnpm ci:timings:test`) agrupa por fase
(`api:run`, `api:detail`, `api:ohlcv`, `api:strategy-top`, `api:dia-d-verifications`, `module:src`,
`module:dep`, `other`), suma/`max`/conteo (para detectar re-runs) y **compara primer intento vs retry**.
Un informe ausente es un **hueco declarado** (exit 0), nunca un rojo.

**D. Cableado en CI.** El job `playwright (integrated AUTO S5)` enciende `BOLSA_BACKTEST_TIMING=1`,
redirige la salida de la API a `/tmp/s5-api.log`, exporta `S5_TIMINGS_OUT=/tmp/s5-network-timings.json`
al paso de Playwright y añade un paso read-only que renderiza el parser de red; el artefacto
`playwright-integrated-auto-s5-timings` pasa a incluir los JSON de red, `s5-network.txt` y `s5-api.log`.

**Reproducción local en frío (primero local, luego CI).**

```bash
pnpm ci:s5:cold        # vacía apps/web/node_modules/.vite, stack fresco (webServer→pnpm dev),
                       # playwright test gp-v288-s5 --retries=1, y renderiza AMBOS parsers
S5_COLD_GREP=GP-V288-S5-04 pnpm ci:s5:cold   # el journey AISLADO (caso más frío: nada lo precalienta)
```

Repetir **N≥3** veces para tener varias muestras del primer intento. Requiere PostgreSQL arriba y
migrado y las dependencias instaladas (se declara, no se finge).

**Criterio de decisión (evidencia → causa; no se pre-decide):**

| Observación medida | Causa | Fix candidato (sin tocar timeout/retries) |
| --- | --- | --- |
| `module:src`/`module:dep` altos **solo** en intento 1 y retry plano | Vite dev transforma en frío dentro del tramo | `optimizeDeps.include` o servir build/`preview` |
| Fases Python altas **solo** en la 1ª llamada y planas después | import/warm-up del proceso | pre-calentar la ruta en el setup de CI |
| `ohlcv_load`/`compute` altos **también** en caliente | datos/cálculo | limitar barras / índices |
| `POST /api/backtests/run` contado > 1 en el tramo | re-run por orquestación cliente | corregir la orquestación |

**Resultado medido — arranque en frío local (caché de Vite vaciada en cada corrida).**

En las tres muestras completas no hubo **ningún** reintento: los 4 tests pasan en el primer intento.

| corrida | 4 tests | `S5-04` | abrir la operación | esperar evidencia LAB | guardar |
| --- | --- | --- | --- | --- | --- |
| 1 | 27.8s | 4.65s | 3.44s | **0.68s** | 0.37s |
| 2 | 27.9s | 5.26s | 3.57s | **1.21s** | 0.40s |
| 3 (sesión previa) | 27.6s | 5.23s | 3.47s | **1.25s** | 0.40s |

Fases del servidor por `POST /api/backtests/run` (`BOLSA_BACKTEST_TIMING=1`; una línea por llamada):

| llamada | instrument_lookup | strategy_lookup | ohlcv_load | compute | save_run | total |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 37.1ms | 4.5ms | 9.4ms | 1.4ms | 64.6ms | 126.3ms |
| 2 | 2.7ms | 0.9ms | 2.6ms | 1.4ms | 64.5ms | 78.9ms |
| 3 | 6.6ms | 1.1ms | 2.4ms | 1.3ms | 57.4ms | 74.9ms |
| 4 | 4.3ms | 4.3ms | 3.4ms | 1.2ms | 59.2ms | 78.3ms |

Ninguna fase se acerca a los ~60 s y **no hay pico de «primera llamada»** (la #1 no es más lenta que
la #4). La mayor es `save_run` (escritura durable), ~57-65 ms y **estable** en todas las llamadas.

Red (intento 0): `module:src` 739 peticiones (máx **0.17-0.19s**), `module:dep` 222 (máx 0.19s),
`api:run` 2 (máx 0.25s), `api:other` 40-44 (máx 1.20-1.22s). **Ninguna petición supera ~1.3 s** y hay
**una sola** petición `document` (no hubo recarga de página ⇒ no se disparó el re-optimize de Vite).

**Caso más frío (aislado).** `S5_COLD_GREP=GP-V288-S5-04 pnpm ci:s5:cold` (el journey solo, sin que
ningún test previo precaliente módulos): test 7.18s, con el sobrecoste de frío en **abrir la
operación AUTO** (6.05s vs 3.44-3.57s de la corrida completa) y **no** en la espera de evidencia LAB
(**0.66s**, incluso menor que en la corrida completa). Es decir: el paso que se cuelga en CI
—`expect(save).toBeVisible({ timeout: 60_000 })`— es el **menos** sensible al frío.

**Conclusión del diagnóstico (mapea evidencia → causa).**

| Rama del criterio | Evidencia medida | Veredicto |
| --- | --- | --- |
| Vite dev frío | 739 `module:src` pero máx 0.17-0.19 s/petición; el frío se paga al **montar** la UI (+~2.5 s) y la espera LAB aislada es 0.66 s | real pero ~2.5 s: **no explica los ~60 s** |
| Python frío | todas las fases <65 ms y sin pico en la 1ª llamada | **refutado** |
| Cómputo/datos | `ohlcv_load` 2-9 ms y `compute` 1.2-1.4 ms en todas las llamadas | **refutado** |
| Waterfall/re-run cliente | `api:run` = 2 en toda la corrida (uno por run); `S5-04` dispara **un** run | **refutado** |

**No se reproduce** en local (N=3 completas + 1 aislada) ningún tramo cercano a los ~60 s: el
fenómeno es **solo de CI** y no queda atribuido a ninguna fase medida. Por el criterio de decisión
**no hay causa demostrada que corregir**, así que se cierra sin tocar `timeout`/`retries` y sin
enmascarar nada: la instrumentación read-only queda cableada para que el próximo CI de tag deje la
distribución real (red + fases) en el artefacto `playwright-integrated-auto-s5-timings`, que es el
único sitio donde el fenómeno aparece.

### 6.2 Comparación con CI `38735478442` (evidencia cruda)

El run de CI [`38735478442`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38735478442) sí dejó
los artefactos crudos de la instrumentación. Se conservan **verbatim** en
[`docs/engineering/evidence/v2.88.135/s5-ci-run-38735478442/`](./evidence/v2.88.135/s5-ci-run-38735478442/)
(`s5-timings.txt`, `s5-network.txt`, `s5-network-timings.json.attempt0.json`, `…attempt1.json`,
`s5-integrated-report.json`). Esta es la comparación directa con el N=3 local:

**Tiempos por intento (`s5-timings.txt`).**

| test | intento | estado | duración | tramos |
| --- | --- | --- | --- | --- |
| `S5-04` | 1 | **failed** | **64.59s** | esperar la evidencia de la sesión LAB **60.00s** · abrir la operación AUTO 4.34s · lanzar la verificación D→hoy 0.17s |
| `S5-04` | 2 (retry) | passed | 7.39s | abrir la operación AUTO 5.17s · esperar la evidencia de la sesión LAB **1.35s** · guardar y verificar el enlace durable 0.44s |

Delta primer intento − retry: **57.21s**. El timeout cae **exactamente** en el tramo
`esperar la evidencia de la sesión LAB` (el `expect(save).toBeVisible({ timeout: 60_000 })`), el
**mismo** paso que en local tarda 0.66-1.25 s.

**Red por intento (`s5-network.txt`).**

| fase | intento 0 (failed) | retry (passed) | delta |
| --- | --- | --- | --- |
| `api:other` | 52 pet. · suma 11.97s · **máx 8.89s** | 38 pet. · suma 3.64s · máx 0.23s | +8.33s |
| `module:src` | 739 pet. · máx 0.56s | 739 pet. · máx 0.65s | −20.39s (suma) |
| `module:dep` | 222 pet. · máx 0.55s | 222 pet. · máx 0.63s | +3.74s (suma) |
| `api:run` | 2 pet. · máx 0.10s | 2 pet. · máx 0.37s | −0.54s (suma) |

La petición más lenta del intento 0 es **`POST /api/instruments/cmv9ispyq00074cgfg32n5jdl/sync`**:
`status 200`, `durationMs **8892**`, `offsetMs 13803` (`s5-network-timings.json.attempt0.json`,
`index 1006`). En el retry **no se repite**: `api:other` baja a máx 0.23s y **desaparece** la petición
`/sync`.

**Lectura (evidencia → causa, acotada).**

- El fenómeno es **solo de CI**: el N=3 local no reproduce ningún tramo cercano a 60 s (§6.1).
- La espera que revienta es la **readiness asíncrona de la cadena LAB/scan** (el botón
  `Guardar Evidence` aparece cuando la evidencia de sesión está lista), **no** el motor de
  backtesting ni el cálculo de indicadores: las fases Python medidas siguen <65 ms y sin pico en la
  1ª llamada, y `api:run` = 2 en ambos intentos (sin waterfall/re-run).
- El `POST /instruments/<id>/sync` de **8.89 s** es un **coste observable** del arranque en frío,
  pero **no demuestra por sí solo** ser la causa de los ~60 s de espera: es un único candidato medido
  dentro de `api:other`, no el tramo que agota el timeout. El retry también pasa **sin** `/sync`
  porque parte de estado caliente.

**Alcance del cierre.** Esto **cierra la incidencia de DIAGNÓSTICO** (`S5-04` medido, causa acotada,
sin tocar `timeout`/`retries`). **No** demuestra que la intermitencia del runner de CI haya
desaparecido: la reproducción local confirma **estabilidad local**, no elimina el fallo intermitente
del runner.

**Guardarraíles.** No se toca `timeout`/`retries`/aserciones; sin cambios de contrato HTTP; los logs
son env-gated (default OFF). `PAPER` sigue **`INCONCLUSIVE`**; los vetos `BEAR_TREND` siguen
registrados como `NO_MEDIDO_REGIMEN` y **no** cuentan como días medidos ni ciclos.

---

## 7. Auditoría de calidad de señales (cuando existan ciclos)

`P1`/`P2`/`P3` solo se pueden **auditar** cuando la ventana produzca ciclos medibles. Mientras el
mercado vete LONG, este checklist queda **sin aplicar** (no se fabrica). Por instrumento del
universo ESTUDIO, sobre el artefacto de `v2_99` (`auto_chain_durable_reader`):

1. **Secuencia completa de 9 etapas** — `SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL →
   PROTECTION → SETTLEMENT → CYCLE_CLOSED`; una etapa sin traza durable se declara `None` (hueco),
   **no** `0`.
2. **Identidad** — la estrategia EJECUTADA del ciclo resuelta por identidad EXACTA (`presetKey`),
   no la «mejor disponible» por accidente.
3. **Riesgo ↔ fill** — `RESERVATION`/`reserved_risk` coherente con el fill y la cantidad.
4. **Protección y liquidación** — `PROTECTION`/`SETTLEMENT` presentes antes de `CYCLE_CLOSED`.
5. **Conciliación del P&L** — `pnl.reconciled == true` (la magnitud/rentabilidad es análisis
   **separado**, no parte de la certificación operativa).
6. **Enlace DÍA-D** — `executedVsDiaD.matches != null` (True o False; nunca fabricado con una sola
   fuente).

Solo con esta secuencia verificada hay evidencia para valorar el funcionamiento operativo.
