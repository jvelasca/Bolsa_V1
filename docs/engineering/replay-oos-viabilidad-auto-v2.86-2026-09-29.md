# Replay OOS de viabilidad del motor AUTO — `AUTO-MATERIAL-14` / `v2.86`

> **AsOf:** 2026-09-29 · **Fase:** instrumento de investigación (read-only + cuarentena en memoria)
> **Tipo de entrega:** código de instrumento (`packages/` + `apps/api-python/scripts/`) + informe.
> **Bump:** **SIN bump** (`2.10.2-beta` sin mover) · **SIN migración** (Alembic head sigue en `046_fill_reference_mid`).
> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) · **Deuda:** [deuda-p3-post-auditoria-v2.70-2026-09-26.md](./deuda-p3-post-auditoria-v2.70-2026-09-26.md)
> **Relevo de esta fase:** este documento hace también de relevo (ver §8).
>
> **[NOTA DE CONTEXTO POSTERIOR — 2026-09-29.]** Esta fase viaja dentro del tag **`v2.88-beta`** del
> **sello conjunto** (`AUTO-MATERIAL-14` + `AUTO-MATERIAL-15` + cierre de `OBS-14` / `AUTO-MATERIAL-16`).
> Su cabecera dice «SIN tag» porque describe el **estado al autorarla**: `v2.86` se autoró y **no** se
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

Consecuencia dura: **`P3-2`/`P3-3` siguen ABIERTAS.** Este replay **no las cierra ni las mueve**: los
buckets de calendario del forward se construyen con `created_at = datetime.now(UTC)`, así que un replay
con reloj simulado **no puede** acreditar una ventana de días reales. Cualquier lectura que presente este
informe como «la validación» es **incorrecta**.

## 2. Qué se implementó (y con qué garantías)

### 2.1 Módulo puro `bolsa_application.replay_oos`

`packages/py/application/src/bolsa_application/replay_oos.py` — sin I/O, sin reloj de pared:

- `bar_day` / `clamp_bars_as_of` — **no-lookahead**: ninguna barra con `timestamp > as_of` es visible.
- `make_as_of_bar_loader` — loader con la **misma firma** que `make_bar_snapshot_loader`, acotado por
  `as_of`. El recorte es **fail-closed**: una barra sin fecha se **descarta**, nunca se asume «del día».
- `make_day_price_script` / `ReplayCursor` / `step_day_clock` — **un día por tick**. El cursor es la
  **única autoridad** de fecha, `as_of` y precio de apertura: la entrada se sirve al **open del día
  siguiente** (`days[index+1]`), de modo que **el motor no ve nada del día que va a operar**.
- `census_operable_days` — censo de días operables *long* con el régimen del propio día (barras `<= D`),
  reutilizando `DiscoveryRegimeSource` + `aggregate_trial_regime`. Publica además
  `operable_by_operational()` (ver §4.1: es la diferencia entre leer «318 días» y «318 días alcistas»).
- `score_replay` — puntuación contra los fills **ya materializados** (nunca mira el futuro).

### 2.2 CLI orquestador `v2_86_replay_oos_viability.py`

`apps/api-python/scripts/v2_86_replay_oos_viability.py`: Paso 0 (censo) → Paso 2b (replay) → Paso 3
(puntuación), con `--no-replay` para ejecutar **solo** el censo.

**Cuarentena (hermético por construcción):** el motor se instancia con
`InMemorySimFillFinanceContextStore`, `InMemorySimAutoPositionStore`, `InMemorySimConsumedSignalStore`,
`InMemoryExecutionEventStore`, `InMemoryReservationStore`, un `_ConfirmingFinanceApplier` en memoria y un
port de barras `_ReadOnlyBarPort`. **Ninguna escritura a PostgreSQL** en el camino del replay (la entrada y
la salida del CLI sí leen, read-only, el catálogo y el histórico).

**Continuidad de identidad:** cuenta fija `1484e253d2d54645945a6b1d7`, venue `paper`, versión
`v283-window-a` y el **mismo watch** de la ventana real (A y B), leídos del material durable. Un replay con
otra cuenta/versión no sería comparable.

### 2.3 Scorer: la unidad es el CICLO, no el fill

El motor liquida en **fills parciales** (varias filas por entrada y por salida). Contar una ida y vuelta
por fila repetiría la misma R `k` veces e inflaría el censo; por eso `score_replay` agrega por símbolo:

- **entrada** = VWAP de las compras, con el **stop del tick en que nació** la posición (el denominador de R
  no se re-media);
- **salida** = VWAP de las ventas; cuando la cantidad llega a **cero** se emite **una** `RoundTrip`;
- lo que sigue vivo se publica como `OpenPosition` con su **R no realizado**, marcado;
- **huecos**: una salida sin entrada previa, o un ciclo con `entry == stop` (riesgo no medible), **no**
  producen R. Se declaran (`n/d`); **nunca** se rellenan con un `0`.

### 2.4 Verificación

- **18 tests puros** en `packages/py/application/tests/test_replay_oos.py` (no-lookahead, recorte de barras
  fail-closed, bloqueo del censo en `trend_down`, `high_vol` operable **y declarado**, cursor de
  calendario, script de precios fail-closed, agregación de parciales, ciclo vivo, VWAP, huecos).
- **6 mutaciones nuevas `M234`–`M239`** en `apps/api-python/scripts/v2_44_mutation_audit.py` (matriz
  **233 → 239**), todas **verificadas mordiendo** (`6/6`), con el árbol restaurado byte a byte.
- Guardarraíles vecinos sin regresión: **71 passed**
  (`test_replay_oos.py`, `test_auto_forward_deciders.py`, `test_auto_v2_partial_fills.py`,
  `test_auto_v2_worker_integration.py`); `ruff` limpio.

## 3. Hipótesis a refutar

> «El motor AUTO, ¿habría operado si lo hubiésemos puesto a andar sobre la historia?»

El censo del Paso 0 responde **antes** de gastar el replay, y el replay mide el caudal real.

## 4. Medición

### 4.1 Paso 0 — censo de días operables (read-only, 1 284 días)

Ventana: **historia completa** de las barras D1 del watch (20 símbolos), `2021-12-07 → 2026-09-29`.

| | |
| --- | --- |
| Días censados | **1 284** |
| **Días operables (long)** | **318** (24.8 %) |
| Racha operable máxima | **205 días** |
| Agregado | `trend_down` 907 · `high_vol` 310 · `sin_regimen` 59 · `range` 8 |

**Desglose por eje operativo (lo que impide leer «318» como «318 días alcistas»):**

> `operableByOperational = { HIGH_VOLATILITY: 310, SIDEWAYS: 8 }`

El gate `regime_allows_entry_for` **no** veta `HIGH_VOLATILITY`, así que 310 de los 318 días operables lo
son **por volatilidad**, no por tendencia. **Días `BULL_TREND` operables: 0** en los 1 284.

Días operables por año (operables / total):

| 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
| --- | --- | --- | --- | --- | --- |
| 0 / 77 | **218 / 257** | 36 / 255 | 4 / 254 | 23 / 253 | 37 / 188 |

La operabilidad **no está uniformemente repartida**: se concentra en **2022** (68 % de todos los días
operables). Es un hecho del histórico, no del instrumento.

El **gate** del plan («si ~0 días, no seguir al harness») **pasa**: 318 > 0 ⇒ el replay aporta.

### 4.2 Paso 2b — replay (1 224 ticks, días con precio de apertura siguiente)

`2021-12-07 → 2026-09-28`.

| Métrica | Valor |
| --- | --- |
| Decisiones | 24 480 |
| Propuestas | 35 |
| Órdenes | 31 |
| **Fills** | **118** |
| Vetos | 24 449 |
| Días con fills | 16 |

**Motivos de veto (journal de entrada, familias):**

| Familia | Conteo |
| --- | --- |
| `top_n_excluded` | 4 827 |
| `regime_invalid` | 4 530 |
| **`risk_budget_exceeded`** | **1 400** |
| `risk_measurement_partial` | 160 |
| `approved` | 24 |
| `concentration_exceeded` | 2 |

Los dos primeros son **estructurales y esperados** (véase §6): `TOP_N` es un tope de **evaluación** que
corre **antes** del gate de régimen, y 906 de los 1 224 ticks son `BEAR_TREND` (veto legítimo de longs).

### 4.3 Paso 3 — puntuación OOS

**13 ciclos cerrados**, todos de `v283-window-a`:

| Métrica | Valor |
| --- | --- |
| R realizado total | **−11.816** |
| R medio | **−0.909** |
| R mediano | **−1.239** |
| Signo positivo (R > 0) | **15.4 %** (2/13) |
| Huecos declarados (`n/d`) | **0** |
| Posiciones abiertas al cierre | 1 (R no realizado, marcado) |

Distribución: `≤ −1R` **11** · `(−1, 0)` **0** · `[0, 1)` **1** · `≥ +1R` **1**.

Ciclos por mes de salida: `2022-02`: 1 · `2022-03`: 8 · `2022-04`: 3 · `2022-05`: 1.

## 5. Hallazgo principal — el replay se TRUNCA, y el instrumento lo declara

**El motor deja de proponer tras `2022-05-06`** (el último fill), pese a que quedan **266 días
`HIGH_VOLATILITY`** con régimen operable por delante.

Medido, no interpretado: en esos 266 días hábiles operables el journal registra **0 propuestas y
~20 vetos/día**, y la familia dominante es **`risk_budget_exceeded`** (1 400) con
**`risk_measurement_partial`** (160).

**Causa raíz (instrumento, no mercado):** el libro de compromisos pendientes
(`_v2_refresh_open_orders`: reservas + trazas de `execution_events` no-`APPLIED`) **no se retira** en un
replay sin el ciclo durable completo de dinero y reservas. El motor, correctamente, deja de abrir cuando
el riesgo comprometido le parece agotado. Se probaron **dos** configuraciones herméticas y **ninguna**
sostiene el replay multi-anual:

| Configuración hermética | Familia dominante | Efecto |
| --- | --- | --- |
| Sin `InMemoryReservationStore` | `open_orders_unmeasurable` | El libro pendiente queda **INMEDIBLE** ⇒ veta aperturas |
| Con `InMemoryReservationStore` (+ applier) | `risk_budget_exceeded` | El libro pendiente se **infla** ⇒ agota el presupuesto |

Añadir un `finance_applier` confirmador **no** cambia el resultado (idéntico: 118 fills / 13 ciclos).

**Lectura honesta:** un replay multi-anual del motor congelado **no es viable hoy** como instrumento
completo; lo que produce es el **primer episodio** del motor (~13 ciclos) más un censo de operabilidad
fiable. **No** se ha degradado ninguna compuerta para estirar la muestra, y **no** se presenta el tramo
truncado como representativo de los 5 años.

## 6. Hallazgos colaterales (estructurales, medidos)

1. **El cuello de botella del AUTO es el agregado conservador + `TOP_N`.** `aggregate_trial_regime` toma
   el veredicto **más conservador** presente (un solo `trend_down` de 20 veta **todos** los longs) y el
   régimen se pasa como **valor único por tick**; con `TOP_N=5` y `|watchA|=10` salen
   `5 top_n_excluded + 5 regime_invalid` por tick. El `5/5` es **coincidencia de conteo**, no una
   clasificación por símbolo (ya declarado en `OBS-13`).
2. **`high_vol` cuenta como operable.** Es un hecho del gate, no un error; se publica desglosado para que
   nadie lea «318 días operables» como «318 días de tendencia».
3. **La operabilidad histórica se concentra en 2022.** 2023–2026 suman 100 días operables de 950.

## 7. Límites declarados (lo que este informe NO afirma)

- **NO** cierra `P3-2`/`P3-3` ni sustituye la ventana PAPER real.
- **NO** afirma que el motor «pierda dinero»: la muestra es de **13 ciclos**, de un **único episodio**
  (`2022-02 → 2022-05`), en un régimen `HIGH_VOLATILITY`, y **sin** los cubos de calendario reales.
  `15.4 %` de signo positivo con `n=13` **no es** concluyente.
- **NO** mide edge, ni `expectancy_R`, ni drawdown de la estrategia: mide R realizado de los ciclos que el
  motor **decidió** abrir, truncado por el instrumento.
- **NO** hay conteo instrumentado de escrituras a PostgreSQL (la cuarentena es **por construcción**: stores
  en memoria). Queda como límite, no como acreditación.
- Los artefactos `operability_runs/*.json` viven en un directorio **gitignoreado** (`.gitignore:102`): el
  resumen viaja en `docs/engineering/evidence/v2.86/`, el JSON completo se regenera con el comando de §8.
- **Paso 4 parcial:** la actualización de los registros (`PROJECT_STATE`, `engineering-index`, deuda P3) se
  hace en esta fase; cualquier re-sello/tag es **decisión del propietario** y no se ejecuta aquí.

## 8. Reproducción (PowerShell)

```powershell
# Paso 0 solo (censo read-only, ~1 min)
uv run --no-sync python apps/api-python/scripts/v2_86_replay_oos_viability.py --no-replay --json `
  --out operability_runs/replay-oos-census-20260929.json

# Censo + replay + puntuación (~80 s, hermético)
uv run --no-sync python apps/api-python/scripts/v2_86_replay_oos_viability.py --json `
  --out operability_runs/replay-oos-viability-20260929.json

# Tests puros del instrumento
uv run --no-sync python -m pytest packages/py/application/tests/test_replay_oos.py -q

# Matriz de mutaciones (bloque del instrumento)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py --only M234,M235,M236,M237,M238,M239
```

**Requisito medido:** PostgreSQL arriba y alcanzable en `127.0.0.1:5432` (Docker Desktop iniciado). Una
caída de Docker mata el paso read-only con `psycopg.errors.ConnectionTimeout`.

## 9. Artefacto y evidencia cruda

- JSON completo (2 054 030 B, gitignoreado):
  `operability_runs/replay-oos-viability-20260929.json`
  **SHA-256** `91A871FBD5B43335C1197DA74D5D91663730A12FD0929FB8A3CB3F4C35143A90`
- Resumen versionado y verificable: [evidence/v2.86/README.md](./evidence/v2.86/README.md)

## 10. Relevo — estado tras esta fase

- **Hecho:** módulo puro + 18 tests + CLI + **`M234`–`M239`** (6/6 muerden) + censo + replay + puntuación
  + este informe.
- **Causa declarada del siguiente intento:** el libro de compromisos pendientes del replay hermético
  (reservas/`execution_events`) **no se retira**. Para un replay multi-anual haría falta reproducir el
  **ciclo durable completo** de reserva→fill→liberación (no un parche en el harness).
- **Deuda abierta (NO se cierra por este informe):** `P3-2`, `P3-3` (ventana PAPER real ≥4 días **con
  material**), `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`.
- **Cerrado:** nada. Este informe **no** cierra deuda; clasifica evidencia.
