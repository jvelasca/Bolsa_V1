# Verificación independiente — operativa PAPER multi-día de AUTO

- **Fecha:** 2026-10-26
- **Rama:** `audit/c1-c4-integrity-fold-2026-10-25`
- **Objeto verificado:** [`dictamen-paper-multidia-operativa-auto-2026-10-26.md`](./dictamen-paper-multidia-operativa-auto-2026-10-26.md)
- **Naturaleza:** verificación **read-only**. No se modifica código, CI, migraciones, `package.json`,
  PR [#76](https://github.com/jvelasca/Bolsa_V1/pull/76), tags, pin PAPER ni `operability_runs/`.
- **C-4 no se reabre.** Este documento no certifica rentabilidad ni autoriza dinero real.

Este anexo **no reescribe** el dictamen: lo contrasta. Cada afirmación se clasifica con un veredicto
propio y toda divergencia se declara en la §7, sin corregir nada en silencio.

---

## 1. Baseline verificado

| Elemento | Valor comprobado | Cómo |
| --- | --- | --- |
| Rama local | `audit/c1-c4-integrity-fold-2026-10-25` | `git branch --show-current` |
| `HEAD` local | `6a9f7cab3bb1a69775ba09ed3c7c6ddf8ace7a7d` | `git rev-parse HEAD` |
| Rama remota | `6a9f7cab…` (idéntica) | `gh api .../git/ref/heads/audit/c1-c4-…` |
| `main` remoto | `26250187a61ef3e71ea5e7a0e0b8387a7347f404` (intacto) | `gh api .../git/ref/heads/main` |
| PR #76 | `OPEN`, `draft`, cabeza `fccdd69ab81e112f76b5e1e2ffb5a4defc5ba58e`, `MERGEABLE`/`CLEAN`, **2 ficheros** | `gh pr view 76` |
| Tag `v2.88.161-beta` | tag **anotado** `9de9e08f…` → commit `9b6d325256ce1e839539488ce6d4899884260df5` (tagger `2026-10-23T15:22:56Z`) | `gh api .../git/ref/tags/...` + `.../git/tags/9de9e08f` |
| Pin PAPER | `commit 64e23eaf`, `apps d06695aba31c…`, `packages 243cd09cfe16…` | [`window-forward.mjs:716-719`](../../scripts/lib/window-forward.mjs#L716-L719) |
| Árbol del pin | `64e23eaf:apps` = `d06695ab…`, `64e23eaf:packages` = `243cd09c…` | `git rev-parse "64e23eaf:apps" "64e23eaf:packages"` |
| Árbol del commit del tag | `9b6d3252:apps` / `:packages` = **los mismos** hashes | `git rev-parse "9b6d3252:apps" "9b6d3252:packages"` |
| Árbol de `HEAD` | `apps 82c9d91f…`, `packages fb2d1870…` ⇒ **`TREE_MOVED`** contra el pin | `git rev-parse "HEAD:apps" "HEAD:packages"` |
| Estado de trabajo | 2 modificados preexistentes (`PROJECT_STATE.md`, `evidencia-c4-…md`) + 3 untracked (2 dictámenes + este anexo) | `git status --short` |

El pin está **autoconsistente**: `freezeStatus()` compara **sólo** los dos tree hashes y trata
`commit` como etiqueta informativa ([`window-pin.mjs:60-68`](../../scripts/window-pin.mjs#L60-L68)).
Que `HEAD` no sea el árbol pinneado es lo correcto: la ventana se mide desde el árbol sellado.

---

## 2. Evidencia publicada (verificada hoy en GitHub)

### 2.1 Run del SHA certificado

[`40287111793`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40287111793) — `workflowName`
`Python CI`, `headSha` `b345689700848682f62b0fac04ad0247768023eb`, `conclusion` `success`,
**5/5 jobs en `success`**:

| Job | id | Conclusión |
| --- | --- | --- |
| `quality` | `121453273130` | `success` |
| `auto-v2-durable-pg (Alembic 040-045 + reinicio real, per-commit)` | `121453273112` | `success` |
| `lifecycle-pg (Alembic + A12 E2E, per-commit)` | `121453273131` | `success` |
| `paper-forward-pg (Alembic + A13 E2E, per-commit)` | `121453272821` | `success` |
| `grammar-discovery-pg (Alembic + A14 E2E, per-commit)` | `121453273163` | `success` |

Conteos leídos del **log** del job durable (no del dictamen):

- `124 passed in 24.11s` — lote durable (22 ficheros PG).
- `3 passed in 1.79s` — paso `Pytest C-4 coste ambiguo PG (fail if skipped)`.
- Paso `Fail on skipped C-4 coste ambiguo PG (no skip silencioso)` presente y ejecutado (grep del
  log: `grep -qE '(^|[0-9]+ )skipped|SKIPPED' /tmp/c4-ambiguous-cost-pg.log`).
- `C4_AMBIGUOUS_COST_PG_REQUIRED: 1` en el `env` del job.

Log del job `quality`: **`5367 passed, 50 skipped`**. Sus pasos sustantivos son
`Ruff`, `Import-linter`, `Mypy`, `Pytest` — **ningún** paso anti-skip para las suites herméticas.

### 2.2 Run del sello

[`39977948590`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39977948590) — `headSha`
`9b6d3252…`, `conclusion` `success`: **13 `success` + 1 `skipped`**, y el omitido es
`playwright (integrated E2E, opt-in)` (opt-in por diseño, no un hueco del sello).

### 2.3 El commit documental no tiene runs

`gh run list --commit 6a9f7cab --json databaseId,name,conclusion` devuelve **`[]`**.
La distinción del dictamen (`b3456897` certifica el run, `6a9f7cab` sólo publica el documento) queda
**confirmada**.

---

## 3. Evidencia local reproducida (no CI)

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Suites herméticas del objeto | `uv run --no-sync python -m pytest test_a9_1_crash_battery.py test_a9_1_durability_integrity.py test_auto_v46_hardkill_recovery.py test_window_day_watch.py test_operability_window.py test_paper_window_certification.py -q` | **126 passed in 1.57s** |
| Censo de selección de tests | `uv run --no-sync python scripts/ci/test_selection.py --report` | universo **656**, ejecutado **656**, **0** sin ejecutar, **0** sin declarar, **0** entradas obsoletas |

El censo acredita **cobertura de jobs**, no **frecuencia por commit**: que cada fichero lo ejecute
*algún* job no implica que corra en cada push.

---

## 4. Operativa AUTO: ledger y gate (leídos, no mutados)

`operability_runs/window-runs/ledger.jsonl` — **12 filas**. Resumen literal:

| Día | Estado | Inicio (UTC) | Fin (UTC) | Duración | Gate de la fila |
| --- | --- | --- | --- | --- | --- |
| `20261014`–`20261017` | `NO_MEDIDO_REGIMEN` (×4) | — | — | 1–6 s | — |
| `20261017`, `20261018` | `NON_MARKET_DAY` | — | — | 0 s | — |
| `20261019` | `HARD_ERROR` (`API_NOT_READY`) y después `MEDIDO` | `16:08:55` | `2026-10-20T06:36:52` | **14:27:57** | `d=2 e=0 c=0 INCONCLUSIVE` |
| `20261021` | `HARD_ERROR` y después `MEDIDO` | `17:45:59` | `2026-10-22T15:54:32` | **22:08:32** | `d=4 e=0 c=0 INCONCLUSIVE` |
| `20261022` | `MEDIDO` | `16:30:01` | `2026-10-23T11:54:20` | **19:24:18** | `d=5 e=0 c=0 INCONCLUSIVE` |
| `20261025` | `NON_MARKET_DAY` (domingo) | — | — | 0 s | — |

Último gate del ledger:

```json
{"days":5,"episodes":0,"cycles":0,"minDays":4,"minEpisodes":2,"minCycles":32,
 "ready":false,"measured":true,"verdict":"INCONCLUSIVE","regimes":[],
 "dayList":["2026-10-19","2026-10-20","2026-10-21","2026-10-22","2026-10-23"]}
```

`day-watch.json` (leído hoy, `at = 2026-10-26T09:58:18+01:00`) declara
**`20261020:MISSED`** y **`20261023:MISSED`** con motivo `ledger_sin_dia_previo`, y hoy
`NOT_DUE`. Ningún aviso sobre `20261021` ni `20261022`, ambos `MEDIDO` con **0 ciclos**.

Consecuencia aritmética verificada: **5 días de material proceden de 3 ejecuciones**, y 2 de esos
5 días no tuvieron ejecución propia. Que el gate cuente «días con material» y el vigía «días
ejecutados» es coherente en cada instrumento; **no son intercambiables**.

### 4.1 Los dos días `MISSED` sí se intentaron (artefactos, no memoria)

Los directorios `20261020/` y `20261023/` existen y contienen `preflight.*` y `forward.*`, pero
**ni `manifest.json` ni fila en el ledger**. El run murió en el paso `forward`, después del
preflight y antes de escribir su fila:

| Día | Artefactos presentes | `forward.out` | Lectura |
| --- | --- | --- | --- |
| `20261020` | `preflight.json/out/err`, `forward.err/out` | **vacío** | el forward no llegó a emitir ni un tick |
| `20261023` | `preflight.json/out/err`, `forward.err/out` | `ticks=140 prices=80/80 cycles=0/0 verdict=BLOCKED` | el forward **sí** corrió y midió precios; cerró con 0 ciclos |

Esto tiene dos consecuencias que el dictamen no explicita y que esta verificación **sí** ha medido:

1. `MISSED` en el vigía significa «sin fila de ledger», **no** «el operador no ejecutó el día».
   `20261023` acumuló 140 ticks con `prices=80/80` y **no** dejó rastro en el ledger.
2. El gate del `20261022` incluye `2026-10-20` y `2026-10-23` en su `dayList` —los cuenta como
   días de ventana— mientras el vigía los declara `MISSED`. La discrepancia no es un bug de uno
   de los dos: son dos definiciones distintas de «día», y conviven sin conciliarse.

No se puede afirmar, en lectura read-only, si esos dos días aportaron `fills` al canónico; lo que
**sí** está medido es que su `forward` no publicó ciclos (`cycles=0/0`) y que no hay fila de ledger.

---

## 5. La capa que casi siempre se omite: árbol medido vs árbol pinneado

| Día medido | `apps` | `packages` | Relación con el pin `.161` |
| --- | --- | --- | --- |
| `2026-10-19` | `f37b6da0…` (fila `20261021`) | `b33bf1e0…` | anterior ⇒ `STALE` |
| `2026-10-21` | — (fila `20261019`) | — | anterior ⇒ `STALE` |
| `2026-10-22` | `4be4a32f…` | `0824c030…` | anterior ⇒ `STALE` |
| Pin `.161` | `d06695ab…` | `243cd09c…` | referencia |

Los `freeze.apps`/`freeze.packages` de cada fila del ledger **no coinciden** con el pin: los tres
`MEDIDO` corrieron sobre árboles anteriores. El dictamen lo declara (`STALE` bajo `.161`) y esta
verificación lo confirma con los valores del propio ledger.

### 5.1 Qué parte del código cambió desde el tag

`git diff --stat 9b6d3252..HEAD` sobre los módulos que sostienen los hallazgos:

| Fichero | Diff tag..HEAD |
| --- | --- |
| `sim_durable_store.py` | vacío |
| `sim_reconciliation.py` | vacío |
| `applied_fills.py` | vacío |
| `kill_switch_store.py` | vacío |
| `exit_plan.py` | vacío |
| `auto_price_provider.py` | vacío |
| `operability_window.py` | vacío |
| `auto_simulation_worker.py` | **+321 líneas** (no vacío) |

Y los cinco métodos del worker que sostienen R-1, R-2 y P-1 **no aparecen** en el diff
(`git diff -U0 9b6d3252..HEAD` filtrado por `readopt_positions`, `_read_projection`,
`_reconcile_before_trusting`, `_openings_vetoed`, `_v2_load_kill_state` ⇒ **sin coincidencias**).
Lo añadido post-tag en ese fichero son el handoff ESTUDIO→AUTO (migración 058), el bloque de
adopción V2 (C-1..C-4) y el productor TOP3.

---

## 6. Matriz de veredictos

Criterio: **CONFIRMADA** = el comportamiento se sigue del código citado y se puede falsar con una
prueba concreta; **MATIZADA** = el núcleo es cierto pero la formulación del dictamen es imprecisa;
**NO VERIFICABLE** = exige material o ejecución que esta verificación read-only no ha hecho.

**Método.** Cada foco se contrastó **dos veces y a ciegas**: seis verificaciones independientes
recibieron **sólo la afirmación a falsar y las rutas**, no el dictamen, y devolvieron veredicto +
cita + escenario + test existente + diseño falsable. Después se releyó el código en `HEAD` para
resolver cada discrepancia entre esos informes y este documento. Las divergencias que aparecieron
en ese contraste **están todas** en la §7: ninguna se ha corregido en silencio.

### 6.1 Readopción entre sesiones

| Id | Afirmación | Veredicto | Evidencia (código de `HEAD`) | Cobertura de test |
| --- | --- | --- | --- | --- |
| R-1 | Fallo de lectura de la proyección ⇒ readopción **fail-open** | **CONFIRMADA** | `readopt_positions` captura la excepción, marca `_readopted` y devuelve `_open` vacío ([`auto_simulation_worker.py:1536-1541`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1536-L1541)); `_reconciliation` queda `{}`; `_openings_vetoed` sólo veta `DIVERGENT`/`UNKNOWN` ([`:1790-1795`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1790-L1795)); el BUY consulta ese veto ([`:7065-7067`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7065-L7067)) | `test_c3i_crash_during_readopt_is_safe` sólo asegura «no se inventa posición» ([`test_a9_1_crash_battery.py:171-182`](../../apps/api-python/tests/test_a9_1_crash_battery.py#L171-L182)). **No** hay test de que el BUY quede vetado |
| R-2 | Canónico **de cuenta** vs proyección **de motor**; `REBUILT` escribe el total en la fila del motor | **CONFIRMADA (matizada)** | El canónico se compone sin `engine_id` ([`:7994-8050`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7994-L8050)); `read_projection` filtra por motor ([`sim_durable_store.py:854-885`](../../packages/py/application/src/bolsa_application/sim_durable_store.py#L854-L885)); con `expected == actual` y `projection != actual` el veredicto es `REBUILT` ([`sim_reconciliation.py:157-167`](../../packages/py/application/src/bolsa_application/sim_reconciliation.py#L157-L167)) y el worker escribe `canonical_qty` en la fila de **ese** motor ([`:1691-1699`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1691-L1699)); `_open` adopta el total de la cuenta en RAM ([`:1550`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1550)) | Los tests de motor duplicado usan canónico **100** ([`test_a9_1_crash_battery.py:301-336`](../../apps/api-python/tests/test_a9_1_crash_battery.py#L301-L336) ⇒ `OK`, no `REBUILT`; [`:337-361`](../../apps/api-python/tests/test_a9_1_crash_battery.py#L337-L361) ⇒ `REBUILT`, deja el total en **150 sobre un real de 100 y no lo asserta**). `_duplicate_engines_reader(..., facts_qty=…)` existe pero nunca se usa con otro valor. **No** hay prueba con canónico = suma de dos motores |
| R-3a | `_t1_done` no se restaura; efecto **nulo** con V2 ON | **CONFIRMADA** | Se inicializa vacío ([`:1222`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1222)) y sólo se consulta en la rama `else` de la política legacy ([`:6980-6989`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L6980-L6989)), que no se ejecuta con `_v2_enabled` | — |
| R-3b | `_sim_realized_pnl` no se restaura; sólo afecta con gobernador ON | **CONFIRMADA** | Acumulador en RAM ([`:1391`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1391)) usado en la equity de marca ([`:2354`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L2354)); el gobernador es **OFF por defecto** ([`auto_v2_entry.py:239`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py#L239)) y se enciende por env ([`:453`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py#L453)) | — |
| R-3c | `_v2_positions` no se restaura; adopción perezosa | **CONFIRMADA** | Dict vacío al nacer ([`:1259`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1259)); se rellena en el primer tick de gestión ([`:6197-6217`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L6197-L6217)) | — |
| R-4 | La identidad de motor la fija el **runner**, no el worker | **CONFIRMADA** | `auto-v76-{urandom}` si falta la variable ([`v2_76_forward_market_material.py:640-641`](../../apps/api-python/scripts/v2_76_forward_market_material.py#L640-L641)); el worker lee `AUTO_ENGINE_SIM_ENGINE_ID` con fallback estable `auto-sim` y sin guarda dura ([`:8736-8745`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L8736-L8745)); el runner inyecta `auto-window-1484e253` ([`window-forward.mjs:748`](../../scripts/lib/window-forward.mjs#L748)) | — |
| R-5 | Readopción una sola vez, sin re-adopción | **CONFIRMADA** | Único llamante de producción, guardado por `_readopted` ([`:7571-7573`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7571-L7573)) | — |
| R-6 | Fila recién nacida sin coste: hueco declarado | **MATIZADA** | El coste se resuelve libro → espejo → `None` declarado ([`:5724`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L5724), [`:5944-5957`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L5944-L5957)). **Pero sí existe cura/backfill**: para filas con veredicto `OK` y `entry_price IS NULL` se escribe el coste del libro ([`:1714-1769`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1714-L1769)), con guard de ambigüedad ([`:1742-1750`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1742-L1750)). El hueco real es más estrecho: sólo queda sin coste la fila `REBUILT` sin libro legible o con libro ambiguo y sin espejo | Cura cubierta por `test_a9_1_crash_battery.py` (`healed`), **no** hay test de «crash entre fill y upsert ⇒ primera adopción sin coste» |
| R-7 | Un símbolo ausente de la **proyección** no genera veto | **MATIZADA** | `read_projection` descarta `quantity <= 0` ([`sim_durable_store.py:870-872`](../../packages/py/application/src/bolsa_application/sim_durable_store.py#L870-L872)), así que ese símbolo no entra por la proyección. **Pero** `reconcile_sim_account` amplía el conjunto con los símbolos del **canónico** ([`sim_reconciliation.py:246-250`](../../packages/py/application/src/bolsa_application/sim_reconciliation.py#L246-L250)): si el libro sí lo tiene, entra en `_reconciliation` y **puede** vetar (`REBUILT`/`DIVERGENT`). Sólo hay silencio cuando el símbolo falta en **ambas** fuentes | Ese caso «falta en ambas» no tiene prueba |

**Nota de precisión sobre R-1:** el camino del **lector canónico** sí es fail-closed y **sí** tiene
prueba (`test_unreadable_ledger_vetoes_openings_and_keeps_position`,
[`test_auto_v2_partial_fills.py:486-521`](../../apps/api-python/tests/test_auto_v2_partial_fills.py#L486-L521)).
El hueco es el camino **anterior**: el fallo de `_read_projection`, que nunca llega al reconciliador.

Dos acotaciones más, medidas sobre el código:

1. **Alcanzabilidad.** En el arranque durable, `load_book_equity` corre **antes** de `real_turn`
   ([`:8624`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L8624)); si la
   causa del fallo también deja ilegible la equity, el BUY se veta por `_book_equity_unreadable`
   ([`:7068`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7068)). El
   fail-open exige que falle **sólo** la consulta de proyección.
2. **El hueco es más ancho que «mapa vacío».** `_reconciliation` sólo recibe entradas **por
   símbolo**; un símbolo ausente del mapa —no sólo el mapa entero— tampoco está vetado **nunca**
   ([`:1790-1795`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1790-L1795)).
   El mapa vacío es el caso extremo, no el único. Los demás consumidores del estado de
   reconciliación (`reconciliation_blocks_openings` en [`:1979-1986`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1979-L1986),
   el snapshot de [`:2655`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L2655)
   y `_v2_recon_status` en [`:5709-5721`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L5709-L5721))
   son **observabilidad o protección de salidas**: el único veto de apertura es la línea 7065.

### 6.2 Parada dura durable

| Id | Afirmación | Veredicto | Evidencia | Cobertura de test |
| --- | --- | --- | --- | --- |
| P-1 | Fallo de lectura del HALT deja el latch sin restaurar | **CONFIRMADA** | `_v2_load_kill_state` marca el flag y **retorna** sin tocar el latch si `store.load()` lanza ([`auto_simulation_worker.py:2413-2419`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L2413-L2419)); el latch nace desengaged ([`:1306`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1306)) | No hay test de «`load()` falla ⇒ no se abre». El único store ilegible de los tests falla `execution_events`, no el kill state |
| P-1b | `_v2_kill_state_loaded` se escribe y **nunca se lee** | **CONFIRMADA** | `grep` del identificador: escritura en [`:1297`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1297) y [`:2412`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L2412), menciones sólo en comentarios ([`:1294`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1294), [`:1346`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1346)). **Cero lecturas** | — |
| P-1c | Se llama en **cada** tick, no una vez por proceso | **CONFIRMADA** | Único call-site de producción dentro de `real_turn` ([`:7568`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7568)), invocado por `run_tick` en el bucle ([`:8408-8409`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L8408-L8409), [`:8427`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L8427)) | — |
| P-2 | Se habilita `BAR_OHLC` (`Low(D) <= stop`) y la **gestión** se evalúa con **un único precio `open(B)`** | **CONFIRMADA (matizada)** | Modelo habilitado ([`operative_granularity.py:31-39,78`](../../packages/py/domain/src/bolsa_domain/operative_granularity.py#L31-L39)); contrato `execution = open(B)` ([`auto_price_provider.py:163-172`](../../apps/api-python/src/bolsa_api/background/auto_price_provider.py#L163-L172), implementación en [`:241-247`](../../apps/api-python/src/bolsa_api/background/auto_price_provider.py#L241-L247)); `high/low` de `B` no se leen nunca ([`:264-269`](../../apps/api-python/src/bolsa_api/background/auto_price_provider.py#L264-L269)); stop por `mark <= stop` ([`exit_plan.py:97-101`](../../packages/py/analytics/src/bolsa_analytics/cognitive/exit_plan.py#L97-L101), [`:183-186`](../../packages/py/analytics/src/bolsa_analytics/cognitive/exit_plan.py#L183-L186)) | `BAR_OHLC` sólo aparece en `packages/py/domain/tests/test_operative_granularity.py` (gate, no semántica). `test_auto_v2_bar_short_circuit.py:266-305` **aparenta** cubrir el breach intrabar pero lo logra mutando un `price_script` constante, no con OHLC |
| P-2b | Cadena completa precio → stop | **CONFIRMADA** | `raw_price = self._v2_price_exec(...)` ([`:6949`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L6949)) → `_v2_position_package(symbol, price)` ([`:6975`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L6975)) → `plan_v2_position_outcome(mark_price=float(price))` ([`:6241-6243`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L6241-L6243)) | — |
| P-3 | Cobertura CI asimétrica de la durabilidad | **CONFIRMADA** | Por commit van en `--ignore`: `test_paper_window_certification_pg.py` ([`python-ci.yml:456`](../../.github/workflows/python-ci.yml#L456)), `test_auto_v46_hardkill_recovery_pg.py` ([`:459`](../../.github/workflows/python-ci.yml#L459)), `test_auto_v46_crash_injection_pg.py` ([`:460`](../../.github/workflows/python-ci.yml#L460)), `test_auto_v46_multiprocess_pg.py` ([`:461`](../../.github/workflows/python-ci.yml#L461)). En el tag **sí** corren ([`release-tag-ci.yml:1778`](../../.github/workflows/release-tag-ci.yml#L1778), [`:1851`](../../.github/workflows/release-tag-ci.yml#L1851), [`:1874`](../../.github/workflows/release-tag-ci.yml#L1874), [`:1897`](../../.github/workflows/release-tag-ci.yml#L1897)) | El in-memory `test_auto_v46_hardkill_recovery.py` **sí** corre por commit (pase de directorio `apps/api-python/tests`, [`python-ci.yml:404`](../../.github/workflows/python-ci.yml#L404)) |
| P-4 | Liberación del HALT por comparación de instantes; sin prueba de **skew** | **MATIZADA** | El código compara instantes ([`:2441-2450`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L2441-L2450)) | **Sí** hay pruebas de **ordenación**: `test_a_durable_release_from_another_process_lifts_a_live_halt` ([`test_auto_v46_hardkill_recovery.py:212`](../../apps/api-python/tests/test_auto_v46_hardkill_recovery.py#L212)) y `test_a_stale_durable_release_does_not_lift_a_newer_halt` ([`:251`](../../apps/api-python/tests/test_auto_v46_hardkill_recovery.py#L251)). Lo que **no** existe es prueba de **desfase de reloj entre procesos** |

### 6.3 Ventana de evidencia multi-día

| Id | Afirmación | Veredicto | Evidencia | Cobertura de test |
| --- | --- | --- | --- | --- |
| W-1 | `MEDIDO` con 0 ciclos **no** alerta | **CONFIRMADA** | `"MEDIDO": ("OK", "ok")` ([`window_day_watch_worker.py:110-115`](../../apps/api-python/src/bolsa_api/background/window_day_watch_worker.py#L110-L115)); los únicos constructores de `severity="alert"` son `MISSED` y `HARD_ERROR`; `grep INCONCLUSIVE|measurableCycles` ⇒ **sólo** el docstring de cabecera ([`:6`](../../apps/api-python/src/bolsa_api/background/window_day_watch_worker.py#L6)). Cero consumidores del gate en `apps/api-python/src` | `test_measured_is_ok` afirma `OK`/`ok` y su helper `_row` sólo trae `day/status/reason` ([`test_window_day_watch.py:48-49,89-93`](../../apps/api-python/tests/test_window_day_watch.py#L89-L93)). No hay test de `MEDIDO` + `gate.verdict=INCONCLUSIVE` |
| W-2 | Los episodios se derivan **sólo** de los ciclos | **MATIZADA** | Cierto en el camino canónico: `build_window_row` **no** tiene parámetro `regimes` y los toma de `_regimes(cycles)` ([`operability_window.py:364-368`](../../packages/py/application/src/bolsa_application/operability_window.py#L364-L368), [`:432`](../../packages/py/application/src/bolsa_application/operability_window.py#L432), [`:449`](../../packages/py/application/src/bolsa_application/operability_window.py#L449)). **Pero**: (i) `window_gate` acepta además `row["regime"]` ([`:574-576`](../../packages/py/application/src/bolsa_application/operability_window.py#L574-L576)); (ii) existe un **segundo productor** de filas de gate, `v2_90_dia_d_feedback.py`, que inyecta `"regimes": [declared_row.get("regime")]` sin ciclos ([`v2_90_dia_d_feedback.py:384-385`](../../apps/api-python/scripts/v2_90_dia_d_feedback.py#L384-L385), consumido en [`:422`](../../apps/api-python/scripts/v2_90_dia_d_feedback.py#L422)) | `test_operability_window.py` usa `_gate_row`, que **inyecta** `regimes` a mano y nunca ejercita `build_window_row` ([`:160-161`](../../packages/py/application/tests/test_operability_window.py#L160-L161)). No hay test de `cycles=[]` + regímenes de mercado distintos |
| W-3 | El numerador de ciclos nace en 0; no se fabrica identidad | **NO VERIFICABLE aquí (citada)** | `bucket_closed_cycles` separa `unattributed` de `undated_with_identity` y no inventa día ([`:532-556`](../../packages/py/application/src/bolsa_application/operability_window.py#L532-L556)) | Los hechos (24 fills sin `cycle_id`, 0 reservas) son la medición del `PROJECT_STATE`; **no** se ha consultado PostgreSQL en esta verificación |
| W-4 | El gate cuenta días con **material**, no días **ejecutados** | **CONFIRMADA (y medida)** | `days = sorted(set(fills_by_day) | set(cycles_by_day) | set(journal_by_day))` ([`v2_80_market_window.py:208`](../../apps/api-python/scripts/v2_80_market_window.py#L208)) | Contrastado con artefactos: `dayList` incluye `2026-10-20` y `2026-10-23`, ambos sin fila de ledger y con `forward` fallido (§4.1) |
| W-5 | El certificador no comprueba el freeze | **CONFIRMADA** | El runner sí lo exige: `verifyWindowProvenance` rechaza `freeze.ok != true` y hashes no congelados ([`window-forward.mjs:1209-1214`](../../scripts/lib/window-forward.mjs#L1209-L1214)); `window-certify.mjs` sólo pasa `account`/`versionA`/`versionB` ([`window-certify.mjs:127-140`](../../scripts/window-certify.mjs#L127-L140)) y **no** consulta `appsHash`/`packagesHash` | — |
| W-5b | `v2_98` sale con 0 aunque el veredicto sea `INCONCLUSIVE` | **CONFIRMADA** | Declarado y ejecutado ([`v2_98_paper_window_certification.py:21-24`](../../apps/api-python/scripts/v2_98_paper_window_certification.py#L21-L24), retorno en [`:245`](../../apps/api-python/scripts/v2_98_paper_window_certification.py#L245)) | — |
| W-6 | Cobertura CI de la ventana | **CONFIRMADA** | `pnpm window:test` y `pnpm window:freeze` sólo en el tag ([`release-tag-ci.yml:62`](../../.github/workflows/release-tag-ci.yml#L62), [`:67`](../../.github/workflows/release-tag-ci.yml#L67)); `test_paper_window_certification_pg.py` en `--ignore` por commit ([`python-ci.yml:456`](../../.github/workflows/python-ci.yml#L456)) | — |
| E-1 | El pin está autoconsistente y no se re-ancla | **CONFIRMADA** | `WINDOW_CONFIG` ([`window-forward.mjs:716-719`](../../scripts/lib/window-forward.mjs#L716-L719)); `freezeStatus` compara sólo tree hashes ([`window-pin.mjs:60-68`](../../scripts/window-pin.mjs#L60-L68)); `9b6d3252:apps/:packages` coinciden con el pin | — |

> **Alcance exacto de W-2.** «0 ciclos ⇒ `episodes=0`» es válido **para el camino del runner, la
> auditoría y el certificador** (todos usan `build_window_row`, que no recibe regímenes por
> parámetro). **No** es una propiedad de `window_gate`, ni del repo: el informe Día-D sí puede
> acreditar episodios sin ciclos. Y `evidence["marketRegime"]` —el régimen operativo real del día—
> se usa **sólo** para el funnel ([`operability_window.py:313`](../../packages/py/application/src/bolsa_application/operability_window.py#L313)), nunca para `regimes`.
>
> **Alcance exacto de W-1.** `MEDIDO` no es la primera regla: antes deciden fin de semana, hora no
> vencida y lock vivo, y «gana la última fila del día» ([`window_day_watch_worker.py:180-191`](../../apps/api-python/src/bolsa_api/background/window_day_watch_worker.py#L180-L191)).
> En todas esas variantes tampoco hay alerta. El campo `gate` **sí viaja** en el ledger
> ([`window-forward-runner.mjs:636`](../../scripts/window-forward-runner.mjs#L636)) y el vigía lo
> ignora. El mensaje `OK` («la ventana avanzó un día de calendario») promete más de lo que el estado
> prueba: `MEDIDO` sólo significa que el paso `window` salió 0.

### 6.4 Acotaciones que cambian la magnitud (no el veredicto)

**R-2 — el total no siempre es 400.** Con **un** worker reiniciado la fila propia pasa a 200 y la
huérfana sigue en 100 ⇒ **300**. Los **400** exigen que **ambos** motores ejecuten su propio
`readopt_positions`. En los dos casos el total proyectado **supera** la posición real, y el estado
pasa después a `OK` (cada fila coincide ya con el canónico), de modo que la inflación se vuelve
**invisible**: el código nunca compara `Σ filas` contra el canónico. El guard multi-motor existente
(`_cost_basis_is_ambiguous`, [`:5946-5957`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L5946-L5957))
protege **sólo** `entry_price`, nunca la cantidad.

**P-2 — tres precisiones.**
1. «Un único precio» vale para la **gestión/protección**. La **decisión** sí lee otro precio:
   `mid` = `close(B-1)` ([`auto_price_provider.py:169-171`](../../apps/api-python/src/bolsa_api/background/auto_price_provider.py#L169-L171)).
2. El **gap overnight sí se evalúa**, al `open` del día siguiente: un hueco a la baja dispara el
   stop, aunque **al open** y no al nivel del stop. Lo que nunca se ve es el rango **intradía**: con
   `Open 100 · Low 80 · Close 105` y stop 95 el stop **no** dispara, y si `B+1` abre ≥ 95 el breach
   desaparece sin rastro.
3. `bolsa_analytics/backtest.py:365-369` **sí** implementa `bar_low <= structural_stop`. Leída como
   «el sistema», la afirmación sería **REFUTADA** para el backtester; para la gestión AUTO es
   **CONFIRMADA**. El `StrEnum` describe al backtester, no al motor.

Además, el MAE persistido (`apply_position_mark`) se alimenta del **mismo `mark`** (`open(B)`): el
«peor adverso» es el mínimo de los *opens*, no el `low`. `THESIS_INVALIDATION` es un segundo
disparador al mismo nivel y con el mismo insumo, no una cobertura intradía.

**P-1 — la exposición no es sólo «el tick que falla».** Si el store queda ilegible de forma
**persistente**, el latch no se restaura en **ningún** tick y el proceso opera publicando `RUNNING`
([`:7622-7627`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L7622-L7627)).
Con un fallo **transitorio**, la exposición es el tick que falla y se cierra en el siguiente. Y en el
camino PostgreSQL un error de `SELECT` suele dejar la sesión en `PendingRollback`, con lo que las
lecturas posteriores del mismo `real_turn` abortan antes de emitir: el fail-open es alcanzable para
excepciones que **no** envenenan la sesión (fila malformada, error Python previo al `execute`,
envoltorio del store).

---

## 7. Errata del dictamen original

| # | Dónde | Dice el dictamen | Dice la verificación | Impacto |
| --- | --- | --- | --- | --- |
| E-1 | §2.3 | «`git diff --stat 9b6d3252..HEAD` sobre esos ficheros devuelve **vacío**» | **Falso para `auto_simulation_worker.py`**: +321 líneas. Los otros **7** ficheros listados **sí** devuelven vacío | Afecta a la trazabilidad, **no** al veredicto: los cinco métodos que sostienen R-1/R-2/P-1 no aparecen en el diff. Debe leerse «sin cambios en los métodos que sostienen los hallazgos», no «fichero sin cambios» |
| E-2 | §2.3 | «Lo que sí cambió post-tag: la zona de adopción V2 del worker (**+321 líneas**, C-1..C-4)» | Las +321 líneas **no son sólo** C-1..C-4: incluyen el handoff ESTUDIO→AUTO (migración 058), la adopción V2 y el productor TOP3 | Incompleto, no incorrecto. La conclusión (`Δ` acotado) se mantiene |
| E-3 | §4.2 P-4 | «No hay evidencia ejecutada de skew; queda como hueco declarado» | Cierto para **skew**, pero existen **dos** pruebas de la **ordenación** por instantes (`release` posterior levanta el halt; `release` anterior no lo revive) | El veredicto `NO MEDIBLE` se mantiene; la frase debe acotarse a «desfase de reloj», no a «comparación de instantes» |
| E-4 | §3.2 R-1 | «La reconciliación sí es fail-closed … pero ese camino no se ejecuta» | Correcto, y conviene añadir que ese camino **tiene** prueba propia (`test_unreadable_ledger_vetoes_openings_and_keeps_position`) | Precisión: el hueco es el fallo de **proyección**, no la falta de cobertura del reconciliador |
| E-5 | §2.3 | Lista de módulos «sin cambios» omite `window_day_watch_worker.py` | Ese fichero **sí** cambió (+180 líneas, marcado del aviso), pero el **mapa de veredictos** que sostiene W-1 no aparece en el diff | El hallazgo W-1 se sostiene; la lista de ficheros era incompleta |
| E-6 | R-2 | «en `REBUILT` se escribe `canonical_qty` en **cada** fila ⇒ total 400» | Se escribe en la fila **de cada motor que ejecuta su propio `readopt`**: con **un** worker el total es **300**; los 400 exigen **ambos**. En los dos casos hay sobreconteo, y el estado pasa luego a `OK` (la inflación se vuelve invisible) | La gravedad se mantiene; la cifra «400» era el caso de dos motores, no el general |
| E-7 | R-6 | «Fila sin coste: `None` declarado, **sin backfill**» | **Sí hay cura**: filas con veredicto `OK` y `entry_price IS NULL` reciben el coste del libro ([`:1714-1769`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py#L1714-L1769)) | El hueco queda **más estrecho**: sólo la fila `REBUILT` sin libro legible o con libro ambiguo y sin espejo queda sin coste |
| E-8 | R-7 | «Un símbolo ausente de la proyección **no genera veto**» | Cierto por la proyección, pero `reconcile_sim_account` amplía el conjunto con los símbolos del **canónico** ([`sim_reconciliation.py:246-250`](../../packages/py/application/src/bolsa_application/sim_reconciliation.py#L246-L250)): si el libro lo tiene, **sí** entra y puede vetar. El silencio exige ausencia en **ambas** fuentes | Baja la gravedad percibida; el caso «falta en ambas» sigue sin prueba |
| E-9 | W-2 | «Los `episodes` se derivan **exclusivamente** de los regímenes de los ciclos» | Cierto para `build_window_row` (runner/auditoría/certificador), **no** para `window_gate`, que también lee `row["regime"]`, ni para el repo: `v2_90_dia_d_feedback.py` inyecta regímenes declarados sin ciclos ([`:384-385`](../../apps/api-python/scripts/v2_90_dia_d_feedback.py#L384-L385)) | El estancamiento del **runner** se mantiene; la formulación «exclusivamente» era demasiado fuerte |
| E-10 | P-2 | «La ejecución usa un único precio; `close` de `B` no se lee nunca; no hay prueba de gap» | Tres matices: la **decisión** lee `close(B-1)`; el **gap overnight sí se evalúa** al `open` del día siguiente; `backtest.py:365-369` implementa `Low(D) <= stop`. `close(B)` sí se lee, al día siguiente | El hueco real es el **rango intradía** de la gestión AUTO, no el gap |

### 7.1 Precisión de citas (sin efecto sobre el veredicto)

| Cita del dictamen | Ubicación real en `HEAD` |
| --- | --- |
| `auto_price_provider.py:163-172` para `execution()` | `163-172` es el **contrato** (`open(B)`); la implementación está en `241-247` |
| `auto_price_provider.py:235-246` para la construcción de `exec_` | `241-247` |
| `sim_durable_store.py:853-888` para `read_projection` | `854-885` (incluye `read_open` en `850-852`) |
| `sim_durable_store.py:890-941` para `upsert` | `887-944` |
| `_v2_persist_kill_state` en `:2456` | `:2457` |
| Latch inicial «~1297» | `:1297` es el **flag** `_v2_kill_state_loaded`; el latch nace en `:1306` |

Ninguna de estas desviaciones cambia una sola conclusión: todas apuntan al mismo código.

---

## 8. Registro P1 y prueba que cerraría cada hueco

> **Actualización 2026-10-26 (cierre verificable tras revisar el diff real).** Las pruebas de
> esta tabla ya existen: `apps/api-python/tests/test_auto_v2_audit_regressions.py` (R-1, R-2,
> P-1, P-2, R-4) y las ampliaciones de `apps/api-python/tests/test_window_day_watch.py` (W-1).
> Ese fichero de regresión estaba **sin trackear**; en este cierre se añade al índice junto con
> este anexo (ver §8.4), que es lo que lo hace ejecutable en CI. Toda la verificación de este
> apartado sigue siendo **local** hasta que el run remoto esté verde.

| Hueco | Disparador real | Prueba falsable (arrange / act / assert) |
| --- | --- | --- |
| **R-1** | `_read_projection` lanza en un proceso nuevo; el tick siguiente abre BUY | `position_store` que falla en `read_projection` (**sólo** esa consulta, para que la equity siga legible); `auto_turn` con decider BUY ⇒ assert `_openings_vetoed("AAA") is True`, `report.proposals == 0`, **0 fills**, `report.vetoes >= 1`; invariante propuesto: `reconciliation_status == {"AAA": "UNKNOWN"}` para el watch |
| **R-2** | Dos filas vivas (A=100, B=100) y canónico = 200 | Dos `upsert` con `entry_price=None`; lector canónico `{AAA: 200}` con **dos** `facts` de 100 (`_duplicate_engines_reader(..., facts_qty=100)` ×2); `readopt` del motor A ⇒ assert `REBUILT` **e invariante global** `sum(q de TODAS las filas vivas de "AAA") == 200`; después `readopt` del motor B ⇒ el mismo invariante (hoy daría **400**) |
| **P-1** | `kill_switch_store.load()` lanza con fila durable `engaged` | Store sembrado `engaged=True` con `fail_next=1`, decider BUY, y conducir **`real_turn`** (no `_load` a mano) ⇒ assert `kill state load failed` en el log, **0 órdenes** y un estado ilegible declarado (código nuevo: hoy **no existe** `KILL_STATE_UNREADABLE`). Segundo tick con `load` correcto ⇒ HALT restaurado, mismo `reason`/`engagement_id`, sigue sin abrir. Variante `always_fail=True` durante N ticks ⇒ ningún tick abre |
| **P-2** | Barra `O=100 · L=80 · C=105`, stop 95 | Sembrar barra `B` y posición con stop 95; `auto_turn` ⇒ assert `STRUCTURAL_STOP` disparado y precio de fill declarado. Test espejo de caracterización (debe pasar hoy): `build_exit_plan_from_position(stop=95, mark_price=100)` ⇒ **no** dispara, y la fuente no pide `low`/`high`. Variante gap: `B+1` abre en 90 con stop 95 ⇒ dispara **a 90**, no a 95 |
| **W-1** | Día `MEDIDO` con `measurableCycles=0` y gate `INCONCLUSIVE` durante N días | `evaluate_day_watch` con fila `MEDIDO` **y** `gate={"verdict":"INCONCLUSIVE","cycles":0}` (hoy el helper `_row` no lleva `gate`) ⇒ assert severidad `alert` con motivo propio; control negativo con `HARD_ERROR` en el mismo test para demostrar que el canal de aviso funciona |
| **W-2** | Días con régimen operativo distinto y 0 ciclos **en el camino del runner** | `build_window_row(cycles=[], evidence={"marketRegime": …})` para 4 días con regímenes distintos ⇒ assert `row["regimes"] == []`, `gate["episodes"] == 0` y `INCONCLUSIVE`; control positivo: un ciclo con `regime` ⇒ `episodes == 1`. (No usar `_gate_row`: inyectaría los regímenes y el test sería vacuo) |
| **R-4** | Operador lanza el runner sin `AUTO_ENGINE_SIM_ENGINE_ID` | Worker sin la variable ⇒ assert fallo explícito de arranque (no `auto-sim` silencioso) |
| **P-3** | Un push verde no acredita el HALT durable | Mover `test_auto_v46_hardkill_recovery_pg.py` a un job por commit con guarda anti-skip, o declarar por escrito que la certificación del HALT es sólo del tag |

### 8.1 Qué queda cerrado (y con qué)

| Hueco | Cambio aplicado | Prueba que lo fija |
| --- | --- | --- |
| **R-1** | Latch de instancia `_projection_read_failed`, activado en el `except` de la lectura de proyección **y** en la del canónico; `_openings_vetoed` devuelve `True` para **cualquier** símbolo mientras esté activo. Se limpia sólo tras lectura + reconciliación válidas. **Corrección 2026-10-26:** si falla el canónico, la readopción **no se consume** (`_readopted` queda `False`): se adopta la fila propia para poder cerrar y se **reintenta** en el tick siguiente. Antes el `_readopted = True` se estampaba igualmente y el veto de aperturas quedaba permanente hasta reiniciar | `test_r1_*` en `test_auto_v2_audit_regressions.py`, incluido `test_r1_the_veto_does_not_depend_on_the_watch_being_enumerable` (watch vacío), `test_r1_a_valid_read_clears_the_latch` y `test_r1_a_transient_canonical_failure_retries_the_readoption` (canónico que falla una vez y luego converge a `OK`) |
| **R-2** | En `readopt_positions`, con más de una fila viva el motor **no** adopta el total de la cuenta: conserva la cantidad de **su** fila y declara `UNKNOWN` (aperturas vetadas). El camino de una sola fila (`REBUILT` + canónico) queda intacto. **Añadido 2026-10-26:** `live_row_invariant_report()` publica, **read-only**, `Σ filas vivas` por motor frente al canónico (`delta`, `consistent`, filas ilegibles declaradas) y el cierre de un símbolo con varios motores se **declara** como `position_row_unreconciled` sin vetarlo (reducir nunca empeora el riesgo). **No** auto-cura: una fila ya inflada sigue necesitando reconciliación explícita | `test_r2_a_sell_cannot_liquidate_another_engines_row`: con dos filas de 100 y canónico 200, `_open == 100` y una venta de 200 liquida **100**, no 200. `test_r2_the_invariant_report_declares_the_inflation_and_does_not_heal_it`: 150+150 frente a canónico 200 ⇒ `delta = 100`, `consistent = False` y las filas quedan intactas. `test_r2_the_multi_engine_symbol_is_flagged_for_declaration` |
| **P-2 (contable)** | `realized_price = settle_price si es válido, si no price`, calculado **una vez** y usado en el hecho aplicado, en `_sim_realized_pnl` y en `_v2_track_reduce` (estado final). Antes sólo lo usaba el settlement | `test_p2_intraday_low_through_the_stop_sells_at_the_stop`, `test_p2_overnight_gap_fills_at_the_open`, `test_p2_target_partial_books_realized_r_at_the_declared_price`, `test_p2_the_close_r_uses_the_declared_price` |
| **P-2 (MAE)** | `apply_position_mark` publica `source="bars"` cuando el peor adverso viene de un extremo de barra (no `close_proxy`); sin extremo, el camino anterior queda byte-idéntico | `test_p2_the_adverse_bar_extreme_feeds_the_mae_and_declares_its_source`, `test_p2_mae_from_the_bar_survives_in_the_durable_mirror` (el valor sobrevive en el espejo) y `test_p2_stop_wins_when_stop_and_target_share_the_bar` (doble toque) |
| **P-1** | Latch local `KILL_STATE_UNREADABLE` cuando el espejo de la parada no se puede leer: el proceso no puede publicar `RUNNING` sin poder afirmar que no hay un HALT persistido. Al volver la lectura se adopta el motivo/identidad durables. **Corrección 2026-10-26:** el placeholder se **libera** con una lectura válida que demuestre que no hay HALT (sin fila, o fila liberada con `reconciliation_id`), y **sólo** entonces; antes un fallo transitorio dejaba el proceso parado hasta reiniciarse. Además el **camino legacy** (`AUTO_ENGINE_SIM_V2=0`) consulta el latch durable para vetar BUY (SELL sigue permitido). Residual de permanencia en §8.3 | `test_p1_a_persistent_load_failure_blocks_every_tick`, `test_p1_a_transient_failure_adopts_the_durable_halt`, `test_p1_a_transient_failure_without_a_durable_halt_recovers`, `test_p1_a_valid_read_never_lifts_a_real_durable_halt`, `test_p1_the_legacy_path_cannot_open_with_a_durable_halt`, `test_p1_the_legacy_path_still_allows_a_protective_exit`, `test_p1_control_a_readable_store_still_lifts_nothing` |
| **W-1** | `MEDIDO` **sin** gate verificable (`gate` ausente, `None` o `{}`) pasa a `INCONCLUSIVE` con severidad `alert`; el motivo declara el caso (`gate_missing` si el bloque no existe o es `null`, `gate_inconclusive` si existe pero no acredita). Un gate con veredicto declarado o ciclos > 0 sigue siendo `OK` | `test_measured_without_a_gate_is_inconclusive`, `test_measured_with_a_null_or_empty_gate_is_inconclusive`, `test_measured_with_measurable_cycles_is_ok` |
| **R-4** | `EngineIdentityMissingError` (subclase de `RuntimeError`) en el arranque durable; `scheduler_worker._start_workers` la captura y **sólo** apaga AUTO, dejando arrancar el resto de workers. El arranque directo del worker sigue fallando de forma explícita | `test_auto_identity_failure_does_not_take_down_the_other_workers`, `test_r4_durable_start_requires_an_explicit_engine_identity` |

### 8.2 Cifras exactas del cierre contable (P-2)

Entrada 100 · cantidad 200 · stop declarado 95. El precio declarado es el que gobierna fill,
P&L y estado final; el `open` sólo decide.

| Escenario | Fill | P&L realizado | R de cierre | MAE |
| --- | --- | --- | --- | --- |
| `open 100 · low 80`, stop 95 | **95** | **−1.000** | **−1,0R** con `initialRisk=5` (stop sembrado a 95) · **−0,5R** con `initialRisk=10` (stop estructural 90) | **−4,0R** (`(80−100)/5`) |
| Gap: `open 90 · low 88`, stop 95 | **90** | **−2.000** | −1,0R con `initialRisk=10` | **−2,4R** (`(88−100)/5`) |
| `high 110` toca T1 | **110** (parcial) | — | **+0,6R** realizada (`2,0R · 30%`), `remaining = 140` | — |
| `low 96`, sin tocar el stop | sin venta | 0 | 0 | **−0,8R**, persistido en el espejo con `source="bars"` |

La fórmula del R de cierre es la de `apply_position_reduce`: `(exit − entry)/initialRisk` por la
fracción ejecutada. Con el `open` (100) el cierre habría contabilizado **0R** y la pérdida
materializada habría desaparecido del estado final.

**Semántica fijada (2026-10-26), no supuesta:**

1. **El MAE es la excursión adversa de la BARRA**, no una reconstrucción del orden intrabar. En
   la primera fila el MAE es `(80 − 100)/5 = −4,0R` aunque la salida sea a 95: con barras D1 no
   se sabe si el `low` ocurrió antes o después del fill, así que se declara la **cota
   conservadora** (el extremo completo). Es una cota superior del dolor, **no** el P&L: el P&L
   usa el precio declarado de cierre (95). La misma cota alimenta
   `is_thesis_invalidated`, que así cierra antes en caso de duda (fail-closed en esa dirección).
2. **El fill D1 es un precio DECLARADO de contabilidad, no ejecutable.** Usar `open(B)` con los
   extremos de la **misma** barra es un supuesto de replay con barras diarias: stop, objetivo y
   cierre pueden haber ocurrido en cualquier orden dentro de `B`. El contrato sólo garantiza que
   settlement, hecho aplicado, P&L y reducción de estado usan **el mismo** número; no convierte
   el relleno en realista.

### 8.3 Residuales declarados (no cerrados por este cambio)

1. **P-1 · permanencia.** La parada por latch ilegible (`KILL_STATE_UNREADABLE`) es **local**:
   no se persiste porque la escritura puede fallar por la misma causa que la lectura. Cada
   proceso nuevo la re-deriva (fail-closed en ambos casos), pero **no queda evidencia durable**
   del tramo en que el latch fue ilegible. Lo que **sí** queda cerrado es que el placeholder ya
   no es permanente: una lectura válida posterior lo libera, y el veto alcanza también al camino
   legacy.
2. **R-2 · no curado, ahora declarado.** Una fila ya inflada por el defecto anterior **no se
   cura sola**: `live_row_invariant_report()` **mide** `Σ filas vivas == canónico` pero no
   repara. La cantidad necesita reconciliación **explícita** de operador antes de dar por buena
   una cuenta que ya operó con el defecto, y mientras siga abierta el cierre se declara
   (`position_row_unreconciled`). Prohibida la reparación heurística: el reparto entre motores
   no es determinable desde el total.
3. **W-1 · `gate` ausente.** Tratar `MEDIDO` sin gate como `INCONCLUSIVE` es fail-closed, pero
   implica que **ningún día histórico sin gate puede re-certificarse como `OK`** desde el
   ledger: la acreditación exige que el runner publique el gate del día.
4. **P-2 · supuesto de replay.** El MAE por barra es una **cota conservadora** y el fill D1 con
   `open(B)` es un precio declarado, no ejecutable (ver §8.2). Ninguna de las dos cosas mejora la
   resolución intradía: para eso hacen falta barras más finas, no otra fórmula.

### 8.4 Estado de la evidencia de este cierre

- `apps/api-python/tests/test_auto_v2_audit_regressions.py` y este anexo pasan a estar
  **trackeados** en este cierre (commit separado del de motor). Antes no entraban en `git diff`
  ni en CI. `git add` no equivale a certificación: la certificación exige el run remoto verde.
- **Certificación remota (2026-10-26).** Run [`40314593833`](https://github.com/jvelasca/Bolsa_V1/actions/runs/40314593833)
  sobre `2fa7d33d` en `audit/c1-c4-integrity-fold-2026-10-25`: **5/5 jobs `success`**
  (`quality`, `paper-forward-pg`, `lifecycle-pg`, `grammar-discovery-pg`,
  `auto-v2-durable-pg`). Detalle de lo que acredita cada uno:
  - `quality`: **5405 passed, 50 skipped** (suite completa, `ruff` con la config **raíz**,
    `lint-imports` 4/4 y `mypy` full-tree).
  - `auto-v2-durable-pg`: **126 passed** en `test_auto_v46_hardkill_recovery_pg.py` con
    `AUTO_HARDKILL_PG_REQUIRED=1` y la guarda anti-skip en verde; además C-4 (3 passed) y la
    ruta REAL del productor (7 passed) y la cadena diaria (1 passed).
  - Este run **sí** ejecuta el fichero de regresión: el `git add` era la condición, no la
    certificación por sí mismo.
- Verificación **local** previa al push (misma máquina, sin PostgreSQL):
  - `pytest apps/api-python/tests/test_auto_v2_audit_regressions.py -q` ⇒ **29 passed**
    (22 del cierre declarado + 7 de recuperación/legacy/reconciliación añadidos hoy).
  - `pytest` sobre `test_auto_v44_exit_crash_matrix.py`, `test_a9_1_crash_battery.py`,
    `test_window_day_watch.py`, `test_scheduler_worker.py`, `test_operability_window.py` y
    `packages/py/analytics/tests` (excluido `test_vectorbt_optuna.py`, que el Control de
    aplicaciones de esta máquina bloquea por `llvmlite.dll`) ⇒ **1425 passed**.
  - `ruff check --config pyproject.toml` (config **raíz**, la del CI), `mypy` con el alcance
    del CI (570 ficheros) y `lint-imports --config packages/py/.importlinter` (4/4) ⇒ **sin
    hallazgos**.
  - **No ejecutado en local**: PostgreSQL (las suites PG crean/destruyen esquemas; se certifican
    en CI) y las suites completas de 5000+ pruebas (se certifican en el run remoto).
- Declarado en configuración: `AUTO_ENGINE_SIM_ENGINE_ID` en `.env.example` y en el runbook de
  la ventana forward (R-4). Sin él, el arranque durable falla y AUTO queda apagado con error.
- **No** cambian los estados operativos: AUTO sigue **OFF**, la operativa es **PAPER virtual** y
  la ventana sigue **`INCONCLUSIVE`**. Este cierre es de **integridad de código**, no de
  rentabilidad ni de certificación multi-día.


---

## 9. Lo que esta verificación **no** ha hecho

- **Ninguna** prueba PostgreSQL en local. Las suites PG crean y destruyen esquemas en la base del
  `.env`; la verificación es read-only. Su evidencia es la **publicada** en `b3456897` y en el tag.
- **Ningún** `run-day`, `window:*`, `v2_76`, `v2_80` ni ciclo diario: no se ha escrito en
  `operability_runs/` ni se ha mutado el estado durable.
- **Ninguna** consulta a la base de datos: los hechos de `PROJECT_STATE.md` (24 fills sin
  `cycle_id`, 0 reservas, 0 intents) se **citan**, no se han medido aquí.
- **Ningún** test nuevo, ningún cambio de código, CI, migraciones, `package.json`, PR, tag ni pin.
- La suite local (126 pruebas) demuestra que las suites herméticas **pasan**; **no** demuestra que
  cubran los huecos. De hecho se ha comprobado que **no** los cubren: R-1 (el test no ejecuta
  `auto_turn`), P-1 (ningún test hace fallar `KillSwitchStore.load()`), P-2 (el test que aparenta
  cubrir el breach intrabar usa un `price_script`, no OHLC) y W-1/W-2 (los helpers inyectan el
  estado y los regímenes, de modo que el caso real nunca se ejercita).

---

## 10. Cierre y estados diferenciados

| Estado | Veredicto de esta verificación |
| --- | --- |
| **C-4 (integridad PostgreSQL)** | **Cerrado y no reabierto.** Los tres escenarios de coste ambiguo se certifican en `b3456897` (run `40287111793`, `3 passed in 1.79s` + guarda anti-skip). R-2 es un hueco **adyacente de cantidad**, no una refutación del coste |
| **Readopción cantidad/coste** | **CERTIFICADO POR CI (`2fa7d33d`).** Coste y plan sólidos, con cura de `entry_price` ya existente. R-1 pasa a fail-closed con reintento (el veto de aperturas se libera sólo con lectura y reconciliación válidas). R-2 deja de estar ciego: no adopta el total de la cuenta, **declara** la discrepancia (`live_row_invariant_report`) y **no** la repara. Residual declarado: una fila ya inflada sigue exigiendo reconciliación de operador |
| **Estado parcial (T1, P&L, FSM V2)** | **PARCIAL.** `_t1_done` sin efecto con V2 ON; `_sim_realized_pnl` sin efecto con gobernador OFF; `_v2_positions` con adopción perezosa |
| **HALT durable** | **CERTIFICADO POR CI (`2fa7d33d`, job `auto-v2-durable-pg`, `AUTO_HARDKILL_PG_REQUIRED=1`).** Semántica normal sólida y ordenación probada. P-1 pasa a fail-closed en cada tick (`KILL_STATE_UNREADABLE`), el placeholder se libera sólo con lectura válida y el veto alcanza al camino legacy. Residual: durante un fallo **persistente** no hay evidencia durable del tramo ilegible (la prueba PG corre por commit, no sólo en el tag) |
| **Stop de posición** | **CERRADO CON SUPUESTO DECLARADO.** El motor ya evalúa el stop y los objetivos con `bar_low`/`bar_high` de la barra (no sólo `open(B)`) y liquida al precio declarado (`min(open, stop)` en long; `max(open, target)` en el objetivo), con el **mismo** precio en settlement, hecho aplicado, P&L y reducción. Supuesto declarado: en barras D1 no se conoce el orden intrabar, así que el fill es un precio **de contabilidad** y el MAE es la cota conservadora de la barra (§8.2) |
| **Ventana multi-día** | **NO CERTIFICADO.** `d=5 e=0 c=0 INCONCLUSIVE`; el gate cuenta 5 días pero sólo **3 ejecuciones completas**; los otros 2 tienen `forward` fallido sin fila de ledger (§4.1). El vigía ya **no** interpreta un `MEDIDO` sin gate como favorable (W-1: pasa a `INCONCLUSIVE` con `gate_missing`/`gate_inconclusive`), pero eso **no** convierte los días históricos en mediciones válidas |
| **Rentabilidad** | **NO CERTIFICADO.** `0/32` ciclos, `evidence_ready=false`. Un CI verde no es evidencia estadística |

**Límites del cierre.** Este anexo confirma la integridad funcional descrita, la **certifica en
CI** para el código de `2fa7d33d` y corrige **diez** imprecisiones de trazabilidad. Lo que el run
verde acredita es que los contratos se cumplen y las regresiones no vuelven; **no** acredita
rentabilidad, ni calidad de las señales, ni que una cuenta ya inflada esté reconciliada. **No**
autoriza el paso a dinero real: AUTO sigue **OFF**, la operativa es **PAPER virtual** y la ventana
sigue **`INCONCLUSIVE`**.

**Actualización 2026-10-26 (posterior a la verificación read-only).** Tras revisar el diff real,
R-1, R-2, P-2 (contable y MAE), W-1 y R-4 tienen cambio de código **y** prueba local (§8.1). Los
veredictos de la tabla anterior describen el estado **medido por la auditoría**, no el estado
posterior: siguen abiertos los tres residuales de §8.3 (permanencia de P-1, fila ya inflada de
R-2, días sin `gate` de W-1) y la certificación del HALT durable en CI (P-3, §8). Las pruebas
nuevas están en un fichero **sin trackear** y la verificación es local, sin CI remoto (§8.4).

**Cambios en el repositorio:** únicamente este fichero (untracked). El dictamen original queda
intacto; `PROJECT_STATE.md` y `evidencia-c4-coste-ambiguo-pg-2026-10-26.md` conservan sus
modificaciones preexistentes sin tocar; ramas, PR #76, tags y pin siguen en el baseline de la §1.
