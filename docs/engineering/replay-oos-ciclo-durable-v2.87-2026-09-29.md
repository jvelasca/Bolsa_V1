# Replay OOS del ciclo durable reserva→fill→liberación — `AUTO-MATERIAL-15` / `v2.87`

> **AsOf:** 2026-09-29 · **Fase:** instrumento de investigación (read-only + cuarentena en memoria)
> **Tipo de entrega:** código de instrumento (`packages/` + `apps/api-python/scripts/` + tests) + informe + evidencia.
> **Bump:** **SIN bump** (`2.10.2-beta` sin mover) · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`) · **SIN tag**.
> **Padre:** [replay-oos-viabilidad-auto-v2.86-2026-09-29.md](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md) · **Índice:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
> **Relevo de esta fase:** este documento hace también de relevo (ver §10).
>
> **[NOTA DE CONTEXTO POSTERIOR — 2026-09-29.]** Esta fase viaja dentro del tag **`v2.88-beta`** del
> **sello conjunto** (`AUTO-MATERIAL-14` + `AUTO-MATERIAL-15` + cierre de `OBS-14` / `AUTO-MATERIAL-16`).
> Su cabecera dice «SIN tag» porque describe el **estado al autorarla**: `v2.87` se autoró y **no** se
> commiteó hasta ese sello. El texto sellado se conserva **verbatim**; esta nota es la única adición.

---

## 1. Qué clase de evidencia produce esto — y qué NO

**Es evidencia de INVESTIGACIÓN (viabilidad del instrumento), no evidencia de OPERACIÓN.**

| | Ventana PAPER real (`P3-2`/`P3-3`) | Este replay OOS |
| --- | --- | --- |
| Reloj | Pared (`datetime.now(UTC)`) | Simulado (cursor de calendario) |
| Cubos de calendario | Día/semana/año reales | **NO reproducibles** (dependen del reloj de pared) |
| Material durable | Escribe y lee PostgreSQL | **Cero escrituras** (cuarentena en memoria) |
| Sustituye a la ventana | — | **NO. Nunca.** |

Consecuencia dura: **`P3-2`/`P3-3` siguen ABIERTAS.** Este replay **no las cierra ni las mueve**.
Lo que cambia respecto de `v2.86` es **la capacidad del instrumento**: el replay multi-anual ya
**no se trunca**, y el artefacto **declara** su horizonte y la medición del libro en vez de contarlos
en una narración.

## 2. Qué se implementó (y con qué garantías)

### 2.1 Módulo puro `bolsa_application.replay_oos` (extendido)

Sobre el módulo de `v2.86` se añaden helpers **puros** (sin I/O, sin reloj de pared):

- `declare_book_measurement` / `book_is_declared_complete` — normaliza la medición del libro a
  `COMPLETE` / `PARTIAL` / `UNKNOWN`; una etiqueta ilegible es **`UNKNOWN`**, nunca `COMPLETE`.
- `BookSnapshot` / `snapshot_book` — congela la foto del libro (reservas vivas, `reservedRisk`,
  `reservedCash`, órdenes pendientes) a partir de las filas de reserva; una reserva no viva con
  `remaining_qty > 0` **no** cuenta como compromiso.
- `ReleaseTally` / `count_releases` / `release_deltas` / `tally_releases` — separa
  `RELEASED_BY_FILL` de `RELEASED_BY_CANCEL` y publica el **delta por día** (un pico de `CANCEL` es
  la firma del huérfano, ahora medida).
- `Horizon` / `declare_horizon` / `close_tick` — cierre de tick con reconciliación durable
  (ver §2.3) y declaración del horizonte; una truncación sin causa se declara
  **`undeclared_truncation`** (nunca se silencia).
- `ScoreReport.by_year()` — particiona los ciclos cerrados por **año de salida**.

### 2.2 CLI orquestador `v2_87_replay_oos_durable_cycle.py`

`apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py` reutiliza read-only los loaders de
`v2_86` (patrón `importlib`) y añade el ciclo durable. **Cuarentena hermética intacta:**
`InMemorySimFillFinanceContextStore`, `InMemorySimAutoPositionStore`, `InMemorySimConsumedSignalStore`,
`InMemoryExecutionEventStore`, `InMemoryReservationStore`, `_ConfirmingFinanceApplier` y un port de
barras `_ReadOnlyBarPort`; **se suman** `InMemoryExitOrderStore` y `InMemoryKillSwitchStore` para que
la identidad de salida y la parada dura existan también en el replay. **Ninguna escritura a PostgreSQL**
en el camino del replay.

**Identidad de la ventana:** cuenta fija `1484e253d2d54645945a6b1d7`, venue `paper`, versión
`v283-window-a` y el **mismo watch** (20 símbolos) leídos del material durable.

### 2.3 Reconciliación al cierre de tick — el arreglo del goteo

Tras cada `await worker.auto_turn()` el replay ejecuta la **misma** rutina que el arranque del motor
(no un parche): `_v2_reconcile_reservations(startup=False)`. En el motor SIM la orden se liquida
**dentro** del mismo tick, así que una reserva viva al cierre está muerta: reconciliar al cierre es
**fiel al motor**, no un atajo. Una reserva sin fill al cierre se libera como `RELEASED_BY_CANCEL`; si
su fill está capturado pero no aplicado, la regla `instrument not in in_flight` la **conserva**
(correcto). **No se baja ningún umbral ni se fuerza nada.**

`--no-durable-cycle` permite correr el **control A/B** (mismo harness, reconcile apagado) — ver §5.

### 2.4 Guardarraíl de horizonte (techo de 1000 fills `APPLIED`)

`_v2_reconcile_reservations` lee `read_applied_fill_facts(..., limit=1000)`; con `>= 1000` filas la
medición pasa a `UNKNOWN`, **no** libera y dispara `engage_kill_switch_durable("RECONCILIATION_FAILURE")`.
Un replay multi-anual puede superarlo. El instrumento lo resuelve con un **espejo de eventos con
retención declarada**: conserva las últimas `K = 900` filas `APPLIED` (por debajo del tope de lectura
del motor) y **archiva** las anteriores. Es honesto porque el store **realmente contiene eso** (no una
ventana devuelta como si fuese el libro entero), la reconciliación corre cada tick (solo importan los
fills recientes) y el replay no reinicia posiciones. En cada tick se comprueba la medición; si deja de
ser `COMPLETE` o la parada dura queda activa, el replay **se detiene y publica** `truncationReason` +
`lastDay`, nunca una truncación silenciosa.

### 2.5 Verificación

- **18** tests puros de `v2.86` (`test_replay_oos.py`) **+ 29 nuevos** en
  `packages/py/application/tests/test_replay_oos_durable_cycle.py` (medición del libro, foto del libro,
  transiciones de liberación y su conteo, horizonte declarado incl. `undeclared_truncation`, `by_year`).
- **7** tests de costura herméticos en `apps/api-python/tests/test_auto_v2_durable_cycle.py`
  (huérfana liberada `CANCEL` al cierre, libro que **no** gotea en N ticks, techo de 1000 `APPLIED`
  con retención activa, seguridad de in-flight).
- **5 mutaciones nuevas `M240`–`M244`** en `apps/api-python/scripts/v2_44_mutation_audit.py` (matriz
  **239 → 244**), todas **verificadas mordiendo 5/5** y restauradas byte a byte:
  - `M240` ciclo durable apagado · `M241` reconciliación a medias (solo fills) · `M242` retención
    invertida (archiva el fill del tick) · `M243` horizonte mudo · `M244` medición ilegible publicada
    `COMPLETE`.
- Guardarraíles vecinos sin regresión: **71 passed**
  (`test_replay_oos.py`, `test_auto_forward_deciders.py`, `test_auto_v2_partial_fills.py`,
  `test_auto_v2_worker_integration.py`); `ruff` limpio.

## 3. Hipótesis a refutar

> «El goteo de reservas huérfanas era lo que truncaba el replay multi-anual, **no** el mercado.»

La contraprueba A/B (§5) la responde de forma directa: mismo harness y ventana, **solo** con la
reconciliación de cierre apagada.

## 4. Medición — corrida con ciclo durable

### 4.1 Paso 0 — censo de días operables (read-only, 1 284 días)

Ventana: **historia completa** de las barras D1 del watch (20 símbolos), `2021-12-07 → 2026-09-29`.

| | |
| --- | --- |
| Días censados | **1 284** |
| **Días operables (long)** | **318** (24.8 %) |
| Racha operable máxima | **205 días** |
| Agregado | `trend_down` 907 · `high_vol` 310 · `sin_regimen` 59 · `range` 8 |

> `operableByOperational = { HIGH_VOLATILITY: 310, SIDEWAYS: 8 }`

El gate **no** veta `HIGH_VOLATILITY`, así que 310 de los 318 días operables lo son **por volatilidad**.
**Días `BULL_TREND` operables: 0** en los 1 284.

Días operables por año (operables / total): 2021 `0/77` · 2022 **`218/257`** · 2023 `36/255` ·
2024 `4/254` · 2025 `23/253` · 2026 `37/188`. La operabilidad se concentra en **2022 (68 %)**.

### 4.2 Paso 2b — replay (1 224 ticks, días con precio de apertura siguiente)

`2021-12-07 → 2026-09-28`.

| Métrica | Valor |
| --- | --- |
| Decisiones | 24 480 |
| Propuestas | 238 |
| Órdenes | **210** |
| **Fills** | **752** |
| Vetos | 24 283 |
| Días con fills | 141 |

**Motivos de veto (journal de entrada, familias):**

| Familia | Conteo |
| --- | --- |
| `regime_invalid` | 878 |
| `top_n_excluded` | 292 |
| `risk_measurement_partial` | 227 |
| `approved` | 86 |
| `concentration_exceeded` | 33 |
| **`risk_budget_exceeded`** | **11** |

Los dos primeros siguen siendo **estructurales y esperados** (≈906 ticks `BEAR_TREND` y `TOP_N` que
corre **antes** del gate de régimen). Lo que **cambia** es que `risk_budget_exceeded` cae de **1 400**
a **11**: el presupuesto ya no se agota.

### 4.3 Libro de compromisos (reserva → fill → liberación)

| | |
| --- | --- |
| Reservas vivas (máx.) | **1** |
| Reservas vivas (final) | **0** (`finalReservedRisk = 0.0`) |
| Días con retirada `CANCEL` | **1** (`2022-02-28`) |
| Retiradas acumuladas | `RELEASED_BY_FILL` **237** · `RELEASED_BY_CANCEL` **1** |
| Días con medición parcial / desconocida | **0 / 0** |
| Retención `APPLIED` | 900 (pico 752; archivadas 0; tope de lectura del motor 1000) |

`replay.horizon = {completed: true, lastDay: 2026-09-28, ticks: 1224, totalTicks: 1224, truncationReason: null}`.

### 4.4 Paso 3 — puntuación OOS

**62 ciclos cerrados**, todos de `v283-window-a`:

| Métrica | Valor |
| --- | --- |
| R realizado total | **−18.366** |
| R medio | **−0.296** |
| R mediano | **−1.053** |
| Signo positivo (R > 0) | **37.1 %** (23/62) |
| Huecos declarados (`n/d`) | **0** |
| Posiciones abiertas al cierre | 10 (R no realizado, marcado) |

`byYear` (bucket nuevo):

| Año | Ciclos | R medio | Signo positivo |
| --- | --- | --- | --- |
| 2022 | 50 | −0.504 | 30.0 % |
| 2023 | 7 | +0.227 | 57.1 % |
| 2024 | 2 | +1.876 | 100 % |
| 2025 | 3 | +0.501 | 66.7 % |

## 5. Hallazgo principal — el desbloqueo es el ciclo durable, medido con un control A/B

Se corrió el **mismo** harness y la **misma** ventana con la **única** diferencia de
`--no-durable-cycle` (reconciliación de cierre apagada). El control **reproduce exactamente el
comportamiento de `v2.86`**: congela toda la actividad tras `~2022-05` con **15 reservas huérfanas
vivas** que comprometen **todo** el presupuesto (`$6000`) ⇒ `risk_budget_exceeded` **1 400**.

| Métrica | Ciclo durable | Control (`--no-durable-cycle`) |
| --- | --- | --- |
| Órdenes | **210** | 31 |
| Fills | **752** | 118 |
| Ciclos cerrados | **62** | 13 |
| Reservas vivas (máx.) | **1** | **15** |
| Riesgo comprometido final | **0.0** | **5 999.9998** |
| `RELEASED_BY_FILL` / `_BY_CANCEL` | **237 / 1** | 29 / **0** |
| Días con fills | **141** | 16 |
| `risk_budget_exceeded` | **11** | **1 400** |
| R por año | 2022·2023·2024·2025 | solo 2022 |

**Lectura honesta.** El cuello de botella de `v2.86` era **de instrumento, no de mercado**: el motor
—correctamente— dejaba de abrir cuando el libro de compromisos le parecía agotado, y el libro se
agotaba porque las reservas huérfanas **nunca se retiraban** en un replay sin el ciclo durable. Con la
reconciliación de cierre (la **misma** rutina del arranque real), el libro se mantiene limpio y el
replay recorre las **4 temporadas**. **No** se degradó ninguna compuerta: los vetos estructurales
siguen contando, solo dejan de estar dominados por el goteo. El control se conserva como artefacto
(SHA-256 en §9) para que la afirmación sea **reproducible**, no narrada.

## 6. Hallazgos colaterales (estructurales, medidos)

1. **El cuello del AUTO sigue siendo el agregado conservador + `TOP_N`.** `aggregate_trial_regime`
   toma el veredicto **más conservador** (un solo `trend_down` veta todos los longs) y el régimen se
   pasa como **valor único por tick**; con `TOP_N` corriendo **antes** del gate de régimen, el `5/5`
   de `top_n_excluded`/`regime_invalid` es **coincidencia de conteo** (ya declarado en `OBS-13`).
   Ahora ese cuello **se ve sin el goteo encima**.
2. **`risk_measurement_partial` (227) supera a `risk_budget_exceeded` (11).** Con el libro limpio,
   el límite que más aparece ya no es el presupuesto agotado, sino el libro **parcialmente medible**
   en el tick — el motor ya lo veta de forma conservadora (fail-closed), pero es el próximo punto a
   mirar para estirar la muestra.
3. **La asimetría 2022↔2023-2025 también aparece en la puntuación.** 50 de los 62 ciclos son de
   2022 (la temporada `HIGH_VOLATILITY`); en 2023–2025 entra menos pero con R medio positivo. Es un
   hecho del histórico/censo, no un resultado del instrumento.

## 7. Límites declarados (lo que este informe NO afirma)

- **NO** cierra `P3-2`/`P3-3` ni sustituye la ventana PAPER real: el reloj es **simulado** y los cubos
  de calendario salen de `datetime.now(UTC)`.
- **NO** afirma edge. La muestra ya es multi-anual (**62 ciclos**) pero es **un solo instrumento**,
  **una sola cuenta/versión/watch** y `pairActive=false` (una sola versión puntuada); `37.1 %` de
  signo positivo con `n=62` **sigue sin ser concluyente** sobre el edge.
- **NO** hay conteo instrumentado de escrituras a PostgreSQL: la cuarentena es **por construcción**
  (stores en memoria).
- Los artefactos `operability_runs/*.json` viven en un directorio **gitignoreado** (`.gitignore:102`):
  el resumen viaja en `docs/engineering/evidence/v2.87/`, el JSON completo se regenera con §8.
- **Paso 4 parcial:** la actualización de registros (`PROJECT_STATE`, `engineering-index`, deuda P3
  con `OBS-14`) se hace en esta fase; cualquier re-sello/tag es **decisión del propietario**.

## 8. Reproducción (PowerShell)

```powershell
# Corrida completa con ciclo durable (~90 s, hermético, read-only)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json `
  --out operability_runs/replay-oos-ciclo-durable-20260929.json

# Contraprueba A/B (reconciliación de cierre APAGADA)
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --no-durable-cycle --json `
  --out operability_runs/replay-oos-ciclo-durable-20260929-control.json

# Tests puros + costura
uv run --no-sync python -m pytest packages/py/application/tests/test_replay_oos.py `
  packages/py/application/tests/test_replay_oos_durable_cycle.py `
  apps/api-python/tests/test_auto_v2_durable_cycle.py -q

# Matriz de mutaciones (bloque del instrumento)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M240 M241 M242 M243 M244
```

**Requisito medido:** PostgreSQL arriba y alcanzable en `127.0.0.1:5432` (Docker Desktop iniciado).
Una caída de Docker mata el paso read-only del censo con `psycopg.errors.ConnectionTimeout`.

## 9. Artefacto y evidencia cruda

- JSON corrida durable (3 165 540 B, gitignoreado):
  `operability_runs/replay-oos-ciclo-durable-20260929.json` —
  **SHA-256** `DC61B3B912C6C7CE6455837BF8E6E6BDD6C03CE6B900D6B73D7925B203C6C54F`
- JSON contraprueba A/B (2 949 320 B, gitignoreado):
  `operability_runs/replay-oos-ciclo-durable-20260929-control.json` —
  **SHA-256** `FE4CBF79E221A27E2A517A10976664FB6149BB4AAB8635851B5558A28378CCD1`
- Resumen versionado y verificable: [evidence/v2.87/README.md](./evidence/v2.87/README.md)

## 10. Relevo — estado tras esta fase

- **Hecho:** helpers puros + 29 tests puros + 7 tests de costura + CLI con reconciliación de cierre y
  guardarraíl de horizonte + **`M240`–`M244`** (5/5 muerden) + corrida durable completa **+ control A/B**
  + este informe + evidencia.
- **Resuelto (medido):** el goteo que truncaba `v2.86` **queda eliminado** con el ciclo durable
  (reservas vivas pico 1, final 0; horizonte `completed=true`; 62 ciclos en 4 temporadas).
- **Deuda nueva declarada (`OBS-14`, NO se arregla aquí — alcance replay-only):** el **motor real**
  ejecuta `_v2_reconcile_reservations` **solo al arranque**; entre reinicios retiene reservas muertas,
  igual que el replay hermético antes de esta fase. Cerrarla es **fase de código del motor**, no de
  instrumento. Registrada en [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
- **Deuda abierta (NO se cierra por este informe):** `P3-2`, `P3-3`, `OBS-14` (nueva), `OBS-13`,
  `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`.
- **Cerrado:** nada. Este informe **no** cierra deuda de datos; clasifica evidencia y deja el
  instrumento multi-anual **viable y declarativo**.
