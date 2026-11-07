# Cierre de la medición sellada `2026-11-06` — `2.11.185-beta`

- **Corrida:** lanzada `2026-11-06T22:12:35Z` desde el árbol sellado (`31c2d3cd`, pin `apps e9486e12`
  / `packages 2de53cda`), motor `auto-window-1484e253`, `--max-ticks 400`.
- **Cierre:** **terminación prematura** a las `2026-11-07T22:12:31Z` tras **292** ticks durables.
  No hubo `forward.json`, no hubo señal, no hubo reinicio.
- **Veredicto:** **`PAPER INCONCLUSIVE`** · `episodes 0/2` · `measurable_cycles 0/32` ·
  **0 ciclos cerrados**. Y, desde esta medición, `days 4/4` **con un día que no fue de mercado** (§5).
- **Herramienta de este cierre:** [`scripts/ops/final_package.py`](../scripts/ops/final_package.py)
  (`--declare-termination`), read-only (`default_transaction_read_only = on`).
- **Predecesor:** [auditoria-paper-vivo-2026-11-06.md](./auditoria-paper-vivo-2026-11-06.md)
  (§11 documenta el relanzamiento sellado; este expediente lo cierra sin reescribirlo).

## 0. Dictamen

| Medida | Valor | Lectura |
| --- | --- | --- |
| Ticks ejecutados | **292 / 400** | **faltan 108**: la corrida no llegó a su tope |
| Ticks con barra `B` | **29** | `22:14:46Z → 23:40:09Z`, 2 273 vetos, `hold_no_op, trail` |
| Ticks ciegos | **263** | `07:40:53Z → 22:12:31Z`, `idle`, 0 vetos, 0 propuestas |
| Cobertura de barra al arrancar | **62 / 181** | el motor nació con la barra parcial |
| Cobertura de barra en la frontera | **84 / 181** | lo ingerido antes de medianoche UTC |
| Cobertura de barra del día (hoy) | **180 / 181** | llegó **después** de la frontera: ya no podía decidir |
| Barra del día siguiente en la frontera | **0** | sábado sin sesión: el tramo ciego era inevitable |
| Fills | **4** | BAS, `MARKET_CLOSE`, un solo ciclo `cyc-7e7921c7424f` |
| Reservas | **3** | 1 `RELEASED_BY_FILL` + 2 `RELEASED_BY_CANCEL` |
| Posiciones abiertas del motor | **4** | `updated_at` sin cambios desde el 5/11 |
| Órdenes de salida del día | **0** | — |
| `paper_forward_results` | **0** (día y total) | **cero ciclos cerrados** |
| Linaje | fills **4/4** con ciclo · reservas **3/3** | el material es trazable; lo que falta es el cierre |
| `alembic_version` | `066_account_evidence_policy` | coherente con el árbol sellado |
| Freeze | `apps`/`packages` = pin | `appsMatchesPin = True`, `packagesMatchesPin = True` |
| Dinero real | **No** | `venue = paper`, ejecución simulada |

**H-1 sigue confirmado** y ahora con el árbol del sello. Lo que este cierre **no** hace es convertir
la corrida en una certificación de rendimiento: no hay ciclos cerrados y la mayor parte de los ticks
se ejecutó sin barra.

## 1. Cómo terminó la corrida (y por qué no hay `forward.json`)

| Hecho medido | Valor |
| --- | --- |
| Último tick durable | `2026-11-07T22:12:31.684Z`, `seq 859` |
| PID del lock (`22708`) | **no existe** (`lockPidAlive = False`) |
| `forward.json` canónico y copia | **no existen** |
| Fila del ledger de esta corrida | **no existe** |
| `.run.lock/lock.json` | presente y obsoleto (escrito `22:12:35Z` del 6/11) |
| `manifest.json` del día | **sigue siendo el del intento abortado de 19:40Z** |
| Traceback en `forward.err.txt` | **ninguno** (solo `INFO httpx`) |

**Diagnóstico.** Un error de Python habría dejado traceback **y** habría escrito la fila del ledger
—así ocurrió al detener el intento de 19:40Z, que sí quedó registrado como `HARD_ERROR`—. Sin rastro
y sin fila, lo que desapareció fue el **proceso `node` del runner**, no su hijo. El corte externo a
las 24 h ya había registrado este mismo desenlace en
[auditoria-paper-vivo-2026-11-06.md](./auditoria-paper-vivo-2026-11-06.md) §11.3; este expediente lo
cierra con el paquete que lo declara y añade la causa por energía (§1.1).

### 1.1 Causa observada (energía)

**Registro de energía (`Microsoft-Windows-Kernel-Power`), en UTC:**

```text
19:53:01Z  506  entra en espera moderno
22:14:55Z  507  sale de la espera
22:15:20Z  506  entra OTRA VEZ en espera
```

El proceso murió a las `22:12:31Z`, **2 m 49 s antes** de esa última entrada en espera. La suspensión
de la máquina es la explicación compatible con todos los hechos; no se afirma como causa certificada.

**Consecuencia formal:** el día **no tiene fila propia en el ledger**. La fila `20261106` del
`ledger.jsonl` sigue siendo la del intento abortado (`HARD_ERROR / FORWARD_ERROR`, `19:40:53Z` →
`22:11:44Z`, freeze `0c64a560`). Leer el ledger por día sin mirar `startedAt` atribuye a esta corrida
un veredicto que no es suyo.

## 2. Los siete puntos del dictamen, respondidos

### 2.1 ¿Los 400 ticks son 400 ejecuciones efectivas del motor?

**No hubo 400.** Hay **292** ticks durables (`seq 568-859`). El contador del bucle del runner llegó a
`290` en su última línea de progreso (`22:08:27Z`) y el ledger durable tiene 292: los dos contadores
no son el mismo y el durable es el que se puede auditar.

Sobre "efectivas": **`NO_ACTIVITY = 0`** en los 292, y `activity = ANALYZING` en todos. Ningún tick
fue un bucle no recorrido. Pero un tick recorrido **sin precio de ejecución** no es un tick con
turno: el motor visitó los 80 símbolos y no decidió ninguno. Esa distinción es la de §2.2.

### 2.2 ¿Cuántos ticks con barra `B` y con qué cobertura?

| Tramo | Ticks | `activity` | `proposals` | `vetoes` | `reason` |
| --- | --- | --- | --- | --- | --- |
| Con barra `B` (`22:14:46Z → 23:40:09Z`) | **29** | `ANALYZING` | 0 | **2 273** | `hold_no_op, trail` |
| Ciego (`07:40:53Z → 22:12:31Z`) | **263** | `ANALYZING` | 0 | **0** | `idle` |

La cobertura **del tramo que decidía** no fue 96 ni 180:

- **62 / 181** instrumentos tenían barra `2026-11-06` **al arrancar** (`22:12:35Z`);
- **84 / 181** en la **frontera de medianoche** — el máximo que pudo usar el motor;
- **180 / 181** hoy, con la ingesta terminando **después** de la frontera
  (`+83 barras a las 08:00Z`, `+9 a las 18:00Z`), cuando ya no había barra del día corriente.

**96/180 no era una foto del tramo con barra.** El número del expediente previo describe la
estabilización de la cola a las `08:13Z` del 7/11, no lo que el motor tenía delante en `22:14Z`. La
diferencia no cambia el diagnóstico (frontera de barra), pero sí la lectura de la cobertura: el
tramo útil se midió con **62-84 instrumentos**, no con 96.

### 2.3 ¿El tramo posterior a medianoche está identificado como no evaluable?

**Sí, y es el 90 % de la corrida.** 263 de 292 ticks. Con `barsForNextDay = 0` (sábado sin sesión) y
el contrato fail-closed de `OhlcvPriceSource.execution()`, el bucle se recorre y no se decide nada.
Ese tramo **no cuenta como medido** y así viaja en el paquete (`bar_frontier.blind`).

### 2.4 ¿Los 4 fills y las 3 reservas se corresponden con registros persistidos?

**Sí, con identificador.** Los cuatro fills son del **mismo ciclo** y del **mismo símbolo**, con
procedencia `MARKET_CLOSE`:

| `execution_id` | Símbolo | Lado | Cantidad | Precio | `cycle_id` | Instante |
| --- | --- | --- | --- | --- | --- | --- |
| `…20763…1#1` | BAS | buy | 180.589400 | 55.348900 | `cyc-7e7921c7424f` | `20:05:12.837Z` |
| `…20763…1#2` | BAS | buy | 84.877018 | 55.364600 | `cyc-7e7921c7424f` | `20:05:12.843Z` |
| `…20763…1#3` | BAS | buy | 42.113448 | 55.384700 | `cyc-7e7921c7424f` | `20:05:12.847Z` |
| `…20763…1#4` | BAS | buy | 53.598934 | 55.403900 | `cyc-7e7921c7424f` | `20:05:12.852Z` |

Y las reservas, todas con `tick_id = 2026-11-06T20:05:11Z`:

| `reservation_id` | Estado / motivo | `cycle_id` |
| --- | --- | --- |
| `RES-dec-7e7921c7424f` | `RELEASED_BY_FILL` / `fill` | `cyc-7e7921c7424f` |
| `RES-dec-668b1a77105c` | `RELEASED_BY_CANCEL` / `cancel` | `cyc-668b1a77105c` |
| `RES-dec-fa41785acf4b` | `RELEASED_BY_CANCEL` / `cancel` | `cyc-fa41785acf4b` |

**Cuatro fills no son cuatro operaciones.** Son tramos de **una** entrada (escalado), y las tres
reservas se escribieron y resolvieron en **el mismo tick**. Las dos canceladas son reintentos de la
misma decisión sobre una fila que es *upsert*: la tabla **no** conserva cuántos intentos hubo.

### 2.5 ¿Sigue habiendo cero ciclos cerrados?

**Sí.** `paper_forward_results = 0` (del día y del total). `linaje fills 4/4`, `linaje reservas 3/3`:
lo que falta no es trazabilidad, es **un cierre de posición completa**. Las 4 posiciones abiertas del
motor siguen sin tocarse desde el 5/11.

Prueba independiente: `paper_cycles_export.py` **se niega a emitir** (`exit 2`,
`# BLOQUEADO: no hay ciclos cerrados con fill durable para esas versiones/cuenta`). El fichero de
stdout queda vacío **a propósito** y no es un resultado.

### 2.6 ¿El manifiesto acredita el árbol, la 066 y los hashes del freeze?

**El manifiesto del día NO.** Y es correcto que no: es el del intento abortado.

| Comprobación | Resultado |
| --- | --- |
| `package.json version` | `2.11.185-beta` |
| `HEAD:apps` vs `pin.appsHash` | `e9486e12…` = `e9486e12…` **True** |
| `HEAD:packages` vs `pin.packagesHash` | `2de53cda…` = `2de53cda…` **True** |
| `alembic_version` | `066_account_evidence_policy` |
| `manifest.freeze.apps` | `0c64a560…` (**≠ pin**) |
| `manifestFreezeMatchesPin` | **False** |

Falta la atestación **de la corrida**: sin `forward.json` no hay `windowProvenance`, ni `sha256` del
`window.json` del día, ni `gate`, ni `turnTotals`. El freeze del **árbol** sí está acreditado por el
pin y por `window:pin --check` (`freeze OK`), que es una comprobación independiente del manifiesto.

### 2.7 ¿La certificación conserva `INCONCLUSIVE` y el motivo `no closed cycles`?

| Instrumento | Resultado | Motivo |
| --- | --- | --- |
| `v2_98` | `INCONCLUSIVE` | `missingCriterionIds = [episodes, measurable_cycles]` |
| `paper_cycles_export` | `exit 2` **BLOQUEADO** | no hay ciclos cerrados con fill durable |
| `v2_100` | `P4` cerrado · `P1/P2/P3` abiertos | `P1` `INCONCLUSIVE`; `P2` 6 ciclos, 0 completos; `P3` 0 de 6 con DÍA-D |

`v2_98` → `verdict = INCONCLUSIVE`, `missingCriterionIds = [episodes, measurable_cycles]`,
`days 4/4`, `episodes 0/2`, `measurableCycles 0/32`, `ready = false`.
`v2_100` → `closedPendings = [P4]`, `openPendings = [P1, P2, P3]`.
`P4` cerrado significa `venue = paper`, envs LIVE ausentes y **0** trazas con venue LIVE: es un
invariante de **mantenimiento** y **no acredita** la operación PAPER.

Ningún umbral se ha tocado: `minDays 4`, `minEpisodes 2`, `minCycles 32`.

## 3. Desviaciones que quedan en el expediente

1. **Terminación prematura** (nueva, §1): 292/400 ticks, sin `forward.json`, sin fila de ledger, con
   `.run.lock` obsoleto y el `manifest.json` del intento abortado. La corrida **no cerró**.
2. **Cruce de medianoche**: 263 de 292 ticks sin barra del día corriente. No es evidencia de
   comportamiento en mercado abierto.
3. **Cobertura parcial en el arranque**: 62/181 instrumentos con barra al empezar; 84/181 en la
   frontera. Los símbolos sin barra quedaron fail-closed por diseño.
4. **Suspensión de la máquina**: hueco `23:40:09Z → 07:40:53Z` (8 h 0 m) sin ticks y la entrada en
   espera de `22:15:20Z` que coincide con la muerte del runner. Rompe la continuidad temporal.
5. **Worktree sellado estaba en `.184`**: `BolsaV1_WindowForward` hace `cd` a
   `.cursor\worktrees\window-seal-183` **por diseño** (mide un árbol clavado, no la raíz que avanza). El
   `7/11` a las `18:23:52Z` ejecutó con `apps = 0c64a560` (árbol de `.184`). Escribió `NON_MARKET_DAY`
   (correcto para un sábado), pero la medición diaria habría seguido midiendo el árbol pre-sello.
   **Re-anclado en este cierre** (§7): ahora `HEAD = 31c2d3cd`, `apps = e9486e12`.
6. **Avisos de los vigías**: benignos y ya superados; **no** son prueba de cobertura completa.

**Dos conceptos que no se intercambian:** cobertura de la **barra** (62→84 de 181 en el tramo útil,
180 hoy) y cobertura **operativa** del preflight (**60/80** operables). No se ha comprobado la
intersección de ambos conjuntos, así que **no** se presenta una como la otra.

## 4. Lo que este cierre certifica y lo que no

**Certifica:**

- El árbol sellado (`2.11.185-beta`, `066_account_evidence_policy`, freeze = pin) ejecutó **292**
  ticks con `state = RUNNING`, sin kill switch y sin corrupción de estado.
- **H-1** con el código del sello: 29 ticks con barra producen 2 273 vetos y motivos; 263 sin barra
  producen `idle` y cero vetos, con el bucle recorrido en ambos casos.
- El material es trazable hasta el fill (4/4 y 3/3) y **no** hay ciclos cerrados.
- `P4` (aislamiento LIVE) se mantiene.

**No certifica:**

- Rendimiento, eficacia ni rentabilidad de AUTO: **0 ciclos cerrados**.
- Que la corrida completara su ventana: **no completó** 400 ticks.
- La cobertura completa de la barra: **nunca** la hubo durante el tramo que decidía.
- Nada del tramo ciego: 263 ticks sin sesión no son medición.

## 5. Hallazgo nuevo: el criterio `days` cuenta días sin sesión

`v2_98` declara `days 4/4` y eso **parece** un avance hacia la ventana. No lo es, y no debe leerse
como tal.

`v2_80_market_window._collect` construye los días así:

```text
days = set(días_con_fill) | set(días_con_ciclo_cerrado) | set(días_con_entrada_de_journal)
```

El journal recibe una entrada **por tick**. Por tanto **cualquier día en que el motor haya tiqueado
cuenta como día de ventana**, aunque no haya habido sesión, ni barra, ni decisión:

| Día del `dayList` | Barra del día | Fills | Ticks | Motivos |
| --- | --- | --- | --- | --- |
| `2026-10-30` | 181 | 0 | 130 | `hold_no_op` (10 400 vetos) |
| `2026-11-05` | 180 | 179 | 724 | mixto (cierres, `time_stop`, `cycle_claimed`) |
| `2026-11-06` | 180 | 4 | 366 | `idle` 311 + `hold_no_op` 55 |
| **`2026-11-07`** | **0** | **0** | **263** | **`idle` 263** |

El **sábado 7/11** entra en el `dayList` con barra cero, cero fills y 263 ticks `idle`. Los
`days 4/4` se cumplen **incluyendo un día que no fue de mercado**.

El veredicto no cambia —`ready = false` porque `episodes` y `cycles` siguen en 0—, pero la lectura
del criterio sí: **`days 4/4` no significa cuatro días operables**. Corregirlo (que un día sin sesión
o sin decisión no cuente como día de ventana) es deuda de producto con su propio sello, **no** algo
que se arregle durante una medición.

## 6. Secuencia ejecutada en este cierre

| # | Paso | Resultado |
| --- | --- | --- |
| 1 | Espera del final natural | **no ocurrió**: terminación prematura (§1) |
| 2 | `final_package.py --day 20261106 --expected-ticks 400 --cycles-export-exit 2 --declare-termination` | paquete emitido, `PREMATURE_TERMINATION` declarado |
| 3 | `node scripts/window-certify.mjs` (`v2_98`) | `INCONCLUSIVE` · `days 4/4` · `episodes 0/2` · `cycles 0/32` |
| 4 | `paper_cycles_export.py` | `exit 2` **BLOQUEADO** (sin ciclos cerrados) |
| 5 | `v2_100_operational_certification_evidence.py` | `P4` cerrado · `P1/P2/P3` abiertos |
| 6 | `window:pin --check` | `freeze OK` |
| 7 | Re-anclaje del worktree sellado | **ejecutado y verificado** (§7) |

## 7. Re-anclaje del worktree sellado (ejecutado)

`task:install` **no** era el remedio: re-registra la misma `.cmd`, que hace `cd` al worktree por
diseño. Lo que estaba mal era el **árbol del worktree**. Ejecutado, en los dos pasos que documenta el
propio `.cmd`:

```text
git -C .cursor\worktrees\window-seal-183 checkout --detach 31c2d3cd
node scripts/window-pin.mjs --write --note "re-anclaje 2026-11-07: sello 2.11.185-beta (066) ..."
```

| Comprobación | Antes | Después |
| --- | --- | --- |
| `HEAD` del worktree | `05926dc8` (`.184`) | **`31c2d3cd`** (`.185`) |
| `HEAD:apps` | `0c64a560…` | **`e9486e12…`** = pin |
| `HEAD:packages` | `2de53cda…` | `2de53cda…` = pin |
| `window-pin --check` (desde el sello) | `freeze OK (05926dc8)` | **`freeze OK (31c2d3cd)`** |
| `.venv` del sello | — | resuelve `bolsa_application` **dentro del sello** |
| `uv.lock` / `pyproject.toml` entre `.184` y `.185` | — | **sin cambios**: no hace falta `uv sync` |
| Tarea `BolsaV1_WindowForward` | `.cmd` de la raíz → `cd` al sello | **sin cambios**: ya era correcto |

El lunes `2026-11-09` la tarea medirá `2.11.185-beta` / `066`, no el árbol de `.184`.

## 8. Deuda operativa abierta

- **`.run.lock` del `20261106` obsoleto**: no se ha borrado (no se tocó nada durante la medición). El
  siguiente `run-day` del mismo día exigiría `--force`, y **no debe lanzarse**: el día no tiene barra
  del día corriente.
- **`days` cuenta días sin sesión** (§5).
- **PR #104** se cerró **sin fusionar** (`2026-11-07T22:14:22Z`) al consolidarse en el PR #105; este
  expediente va en esa misma rama.

## 9. Invariantes de este cierre

- `Δ motor = 0`: no se modificó `auto_simulation_worker.py` ni ningún umbral.
- Sin DDL, sin `ensure_migrated`, sin `run-day`, sin señales a ningún proceso **durante la medición**.
- El paquete y los certificados son **read-only** (`default_transaction_read_only = on`).
- El script nuevo vive en `scripts/` ⇒ **freeze-neutral**: `HEAD:apps` y `HEAD:packages` no se movieron.
- El re-anclaje del sello es posterior al cierre y sólo movió el **worktree** (`scripts/`, fuera del
  freeze) y su pin; el árbol del repo de desarrollo sigue en `b0f1ba2f` con `freeze OK`.
- Un hueco se declara, no se rellena: ausencias en `null`, nunca en `0`.
- **AUTO OFF** · **PAPER INCONCLUSIVE**.
