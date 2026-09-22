# Plan de fase — `V2.50` / `AUTO-9`: `strategy × regime` y `net expectancy_R`

**Fecha:** 2026-09-22 · **Estado:** EN EJECUCIÓN — pasos 1–9 (§13) · **Bump objetivo:** `1.74.0-beta` → `1.75.0-beta`
**Fase previa:** [`v2.49-beta` / `AUTO-8.1`](./traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md)
**Informe que lo motiva:** [`audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md`](./audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md) §11 y §12

> **Aviso de numeración.** El [roadmap AUTO](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) llega hasta
> `AUTO-8` (`V2.48+`, `1.73.0-beta`) y reservaba la etiqueta interna `AUTO-9` para `V2.49`. `V2.49` se
> consumió en `AUTO-8.1` (corrección de `AUTO-8`), así que esta fase toma la etiqueta **`AUTO-9`** sobre
> **`V2.50` / `1.75.0-beta`**. Es una decisión de rotulado, no un hecho: **RATIFICADA el 2026-09-22 por
> el propietario** (ver §13).

---

## 1. Objetivo

Cerrar el gate declarado en `v2.49`: convertir `net_expectancy_r` y `strategy × regime` de **forma
declarada** (`None` / `UNKNOWN`) en **medida real**, y con ello dar a `Adaptive` el denominador que hoy
le falta (R, no moneda bruta) y la dimensión de régimen que la política ignora.

**Lo que NO es este objetivo.** No se añaden estrategias, ni indicadores, ni capas de gramática, ni
«IA que prediga compras». No se toca el camino duro de riesgo. `Adaptive` sigue **recomendando**, no
decidiendo.

## 2. Invariante que instala

> _Adaptive recomienda sobre una economía **medida y normalizada**, no sobre una moneda sin escala._

```
fills durables ─┐
reservas durables ─┼─→ PRODUCTOR read-only (join por cycle_id) ─→ R por ciclo, régimen por ciclo
journal durable ─┘                                                   │
                                                                     ↓
                                          StrategySelfEvaluation (expectancy_R, net_expectancy_R)
                                                                     │
                                              StrategyHealth (regime, decisive) → AdaptivePlan
                                                                     │
                                        ── HARD RISK GATES ──→ motor determinista (sin cambios)
```

Dos consecuencias medibles y exigibles:

1. **Ningún dato medido puede empeorar la calidad de lo declarado.** Un ciclo al que le falte la
   reserva o el coste mantiene su hueco (`UNKNOWN`), no se rellena con `0`.
2. **La decisión no cambia por tener más datos.** Con el flag OFF (y con política neutral) el payload
   del tick y el `AdaptivePlan` siguen siendo **byte-idénticos** a `v2.49`.

## 3. Alcance

**Dentro:**

1. `r_multiple` **por ciclo** (`pnl / reserved_risk`), medido desde fuentes durables ya existentes.
2. `expectancy_r` **por estrategia** (agregado adimensional), que hoy siempre sale `None`.
3. `net_expectancy_r` **por estrategia** (R descontando coste), con su **estado de medición**
   (`COMPLETE` / `PARTIAL` / `UNKNOWN`) porque el coste disponible es **estimado**, no realizado (§6.3).
4. `regime` **por ciclo** → agregación `strategy × regime` y `StrategyHealth.regime` poblado.
5. Alimentar `Adaptive` con R: la asignación pasa a poder usar `net_expectancy_r` cuando esté medido,
   con la **misma** política explícita de «sin evidencia» ya sellada en `v2.49`.
6. Publicar la evidencia nueva en el journal y en la ruta de self-evaluation.

**Fuera (declarado):**

- Coste **realizado** (la atribución por fill exigiría tocar el spine de settlement y la clave de
  idempotencia financiera). Se entrega coste **estimado** y se etiqueta como tal.
- UI nueva. El consumo de los campos nuevos por la superficie móvil es una fase aparte.
- Broker real: sigue SIM.
- SHORT: sigue sin habilitarse por la puerta de atrás.

## 4. Estado de partida verificado (lo que YA existe)

Esta es la parte que cambia el plan respecto a lo que se escribió el 2026-09-21 (se creía que exigía
migración). **Los tres productores existen y son durables.**

### 4.1 `portfolio_reservations` — el denominador de R

`PortfolioReservationRow` ya persiste, **por ciclo**:

| Columna (modelo)                                               | Significado para AUTO-9                                                          |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `cycle_id`                                                     | la costura del join (`portfolio_reservations_cycle_id_idx`, migración `044`)     |
| `entry`, `stop`, `quantity`, `side`, `direction`               | geometría de la operación                                                        |
| `reserved_risk`                                                | **el `riskAmount` comprometido** ⇒ denominador de `r_multiple`                   |
| `cost` (JSONB)                                                 | `TradingCost.to_dict()`: comisión / spread / slippage / gap + pérdidas derivadas |
| `strategy_version_id`, `instrument_id`, `sector`, `account_id` | atribución                                                                       |
| `status`, `created_at`                                         | ciclo vivo vs cerrado                                                            |

Referencias: `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:2617-2652`,
índice en `:2608-2609`, y el alta desde el motor en
`packages/py/application/src/bolsa_application/auto_v2_entry.py:1966-1973`
(`reserved_risk=allocation.get("riskAmount")`, `cost=coerce_trading_cost(allocation.get("tradingCost"))`,
`cycle_id=cycle_id`). El mapeo fila→dominio ya lleva `cycle_id`:
`packages/py/application/src/bolsa_application/reservation_store.py:277`.

### 4.2 `sim_fill_finance_context` — el numerador de R

Ya persiste `cycle_id`, `strategy_version_id`, `side`, `quantity`, `price`, `account_id`
(`tables.py:2239-2253`; índices por `cycle_id` en `:2236-2237`). El PnL realizado por ciclo ya se
reconstruye en `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:117-152`.

### 4.3 `decision_journal_entries` — el régimen por ciclo · **PREMISA CORREGIDA**

> **Corrección del 2026-09-22 (paso 7). Lo que este apartado afirmaba era falso para el camino que
> produce los ciclos, y se deja escrito en lugar de borrado.**
>
> El payload de la decisión **sí** lleva `cycleId` (`auto_v2_entry.py:2259-2262`) y **las tres
> dimensiones del gobernador** (`marketRegime`, `riskRegime`, `operationalState`) en
> `auto_v2_entry.py:2296-2302`, y la tabla **sí** es durable y append-only (`tables.py:720-732`).
> La premisa fallida es la conjunción: **ese** journal es el del camino `plan_v2_tick`, y quien
> ejecuta el ciclo en el motor AUTO simulado —`auto_simulation_worker`— escribe en `_v2_journal`,
> que es una **lista en memoria**. Comprobado contra la base real: en `decision_journal_entries` no
> hay ninguna fila de decisión AUTO con `cycleId` (solo `human_confirm`, `contract_verified`, …), y
> `portfolio_reservations.cycle_id` / `sim_fill_finance_context.cycle_id` están a `NULL` en lo ya
> sembrado.
>
> **Consecuencia para el alcance:** el régimen por ciclo **no** es legible de ninguna fuente durable
> hoy. El plan deja de prometerlo: el productor lo declara `regime_not_durable` (hueco explícito,
> **no** un `UNKNOWN` inventado) y la costura queda lista —`regime_by_cycle`— para el día que exista
> un productor durable. Lo que sí se puede medir hoy, y es lo que el paso 7 entrega, es el
> **denominador** (`portfolio_reservations.reserved_risk`) y el **coste estimado** (`cost`), atados
> por `cycle_id`: es exactamente lo que convierte el `expectancy_r` de `None` permanente en un dato
> medido o declarado ausente.
>
> La fila durable que falta es trabajo del **worker** (hacer que su journal sea el de
> `decision_journal_entries`), no de este adaptador read-only: se declara como deuda con nombre, no
> se rodea.

### 4.4 El contrato puro que hay que rellenar

- `_Cycle` ya tiene hueco para `r_multiple`, `mfe_r`, `mae_r`, `slippage`
  (`packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py:168-179`) y los **lee**
  si llegan (`:207`), pero **nadie se los manda**.
- `StrategySelfEvaluation` ya expone `expectancy_r` (`:425`) y `AutoSelfEvaluation` ya agrega
  `r_values` (`:776`).
- `StrategyHealth` ya tiene `expectancy_r`, `net_expectancy_r` y `regime`, declarados `None`/`UNKNOWN`
  con su comentario de por qué (`auto_adaptive.py:176-184`), y `from_evaluation` **no** mapea los dos
  últimos (`:186-196`).
- `cycles_from_fills` emite **solo** `cycleId` / `strategyVersion` / `pnl`
  (`auto_self_evaluation_feed.py:120-152`), por diseño declarado en su docstring (`:16-20`).

**Conclusión del inventario:** falta **productor**, no **esquema**. El plan es un adaptador read-only
y una agregación nueva, no una migración.

## 5. Diseño

### 5.1 Productor por ciclo (read-only, puro en el cálculo)

Adaptador nuevo junto al de `AUTO-7` (mismo patrón que `make_auto_self_evaluation_provider`):

```
make_cycle_risk_provider(session_factory, account_id) -> cycle_risk(cycle_ids) -> dict[cycle_id, _CycleRisk]
```

- **Entrada:** los `cycle_id` de un conjunto de fills (ya los tiene el feed).
- **Lectura:** reservas **de ENTRADA** de esos ciclos (`side = 'buy'`, `cycle_id IN (…)`) y el
  `marketRegime` del journal de ese ciclo.
- **Salida:** `risk_amount` (`reserved_risk`), `entry`, `stop`, `cost_estimate`, `regime`,
  `closed_at` — con `None` explícito cuando el dato no existe.
- **Fail-closed:** fallo de lectura ⇒ informe con `errors=["cycle_risk_read_failed"]` y
  `decisive = False`; jamás métricas fabricadas.

**Decisión de forma que hay que tomar en la implementación (declarada aquí, no resuelta):** un ciclo
con **varias** reservas (entrada + salidas) debe elegir **una** como denominador. Criterio propuesto:
la reserva de entrada (`side='buy'`) **más antigua** del ciclo; si no hay ninguna identificable, el
ciclo queda `UNKNOWN` en riesgo. Se prohíbe repartir el riesgo entre varias.

### 5.2 Cálculo puro

En `auto_self_evaluation.py`, sin I/O:

```
r_multiple      = pnl / risk_amount                     (adimensional; None si risk_amount ≤ 0)
net_r_multiple  = (pnl − cost_estimate) / risk_amount   (None si falta el coste)
```

Reglas duras:

- `risk_amount ≤ 0` o ausente ⇒ `r_multiple = None` (**nunca** `0`, nunca `inf`).
- `cost_estimate` ausente ⇒ `net_r_multiple = None` y la estrategia baja a `PARTIAL` (§6.3).
- El redondeo es a 4 decimales, como el resto del módulo (`_round4`).

### 5.3 Agregación `strategy × regime`

Agregar por `(strategy_version, regime)` con la **misma** maquinaria de `_dedupe_cycles` (un ciclo
repetido cuenta **una vez** y se declara) y la misma guarda de muestra (`min_trades`). El régimen
`UNKNOWN` es un cubo **propio**: no se reparte ni se suma a otro.

`StrategyHealth.regime` se puebla con el régimen **dominante** de la estrategia **solo si es único y
decisorio**; si la estrategia opera en dos regímenes, queda `UNKNOWN` y el detalle va al desglose
`strategy × regime` (la política lo ignora, como hoy). **No se inventa el cruce.**

### 5.4 Consumo por `Adaptive`

- `StrategyHealth.from_evaluation` pasa a mapear `net_expectancy_r` y `regime`.
- La asignación usa `net_expectancy_r` **si está medido**; si no, cae a `expectancy_currency` (bruta)
  **declarándolo**, o al multiplicador neutral de la política. La política de «sin evidencia» **no
  cambia**.
- `adaptivePolicyVersion` sube a **`auto9-v1`** (el contrato de evidencia cambia ⇒ la versión debe
  cambiar; es lo que la hace reproducible).

## 6. Decisiones y límites que este plan declara

### 6.1 Sin migración

Alembic head sigue en **`044_auto_cycle_trace`**. No hay tabla nueva: los tres productores existen.
Si la implementación demuestra que el `payload->>'cycleId'` sin índice es inaceptable (§6.4), la
respuesta es una migración **aditiva de índice** (`045`), no de esquema — y se declarará entonces.

### 6.2 Ciclos sin reserva

Los ciclos anteriores a `v2.47` (sin `cycle_id`) y los que no tengan reserva de entrada identificable
quedan **`UNKNOWN` en riesgo**: cuentan en `trades` pero **no** en `expectancy_r`. El informe declara
cuántos son (`cycles_without_risk`), porque un R calculado sobre un subconjunto silencioso sería una
medida sesgada.

### 6.3 El coste es **estimado**, no realizado

`reserved_risk` y `cost` son **del instante de la decisión**. Por tanto:

- `net_expectancy_r` se publica etiquetado como **`estimatedCost`** en su estado de medición.
- **No** se presenta como «R neto realizado». Si el negocio exige el realizado, eso es otra fase
  (tocaría el spine de settlement) y queda **explícitamente fuera**.

### 6.4 Coste de la consulta de régimen

`marketRegime` vive en el **JSONB** del journal. Sin índice sobre `payload->>'cycleId'`, la lectura es
un `scan` filtrado por `decision_id`/`created_at`. Dos salidas admitidas: (a) resolver por el
`decision_id` del ciclo si el vínculo existe en un campo indexado; (b) índice de expresión aditivo.
**Debe medirse antes de elegir**: el plan no asume que sea barato. **RESUELTO (medido) en §13.3**: se
adopta (a) + confirmación obligatoria, **sin** migración `045`.

### 6.5 `mfe_r` / `mae_r`

`mfe_mae` ya vive en el JSONB de `position_state` (heredado de `AUTO-5`). Poblar `mfe_r`/`mae_r`
exige el mismo `risk_amount` como denominador ⇒ es **barato** una vez hecho §5.1 y se incluye como
**extensión opcional** (no bloquea el criterio de salida).

## 7. Gate (criterio de salida)

Se considera cerrada **solo** si todo esto es demostrable:

1. **Byte-identidad con el flag OFF**: el payload del tick y el `AdaptivePlan` con
   `AUTO_ENGINE_SIM_V2_ADAPTIVE=0` son idénticos a `v2.49`.
2. **Neutralidad con datos nuevos**: con la política neutral, medir R **no** cambia ninguna decisión
   (`ON-neutral ≡ OFF`), igual que se selló en `v2.49`.
3. **Hard gates intactos**: gobernador, kill switch, `RiskGate`/`Simulation Gate`, régimen y sizing
   (`portfolio_decision_engine.py`) no cambian de veredicto. Test explícito.
4. **Honestidad del hueco**: un ciclo sin reserva / sin coste **no** produce `0.0` en ninguna
   superficie; produce `None` + motivo. Test que lo fija.
5. **`strategy × regime` declarado**: una estrategia en dos regímenes no recibe un régimen inventado.
6. **Reproducibilidad**: mismo conjunto de fills/reservas ⇒ mismo informe, con independencia del
   orden de las filas (golden, como en `v2.49`).
7. **`adaptivePolicyVersion = auto9-v1`** sellado en `AdaptivePlan`, `as_dict()` y journal.

## 8. Plan de trabajo (orden de ejecución)

| #   | Tarea                                                         | Criterio de hecho                                                         |
| --- | ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 1   | Medir el coste de la lectura de régimen (§6.4)                | Decisión (a)/(b) **escrita** con la medición delante                      |
| 2   | Lector read-only de reservas por `cycle_id`                   | Tests PG (in-memory + PG), fail-closed declarado                          |
| 3   | Cálculo puro `r_multiple` / `net_r_multiple`                  | Tests unitarios con `risk_amount` ausente, `0`, negativo, y coste ausente |
| 4   | Agregación `strategy × regime` con `UNKNOWN` como cubo propio | Test de estrategia multi-régimen                                          |
| 5   | Mapear `net_expectancy_r` + `regime` en `StrategyHealth`      | `auto_adaptive` con `policyVersion = auto9-v1`                            |
| 6   | Consumo en asignación (R medido > moneda bruta)               | Test de que con R no medido **no** cambia nada                            |
| 7   | Evidencia en journal (por ciclo y por estrategia)             | Campos nuevos con su estado de medición                                   |
| 8   | Goldens, gate de byte-identidad, invariante de hard gates     | §7 entero                                                                 |
| 9   | Mutaciones `M28…`                                             | Cada mutación puesta en rojo por las suites                               |
| 10  | Docs (`plan`/`pack`/`traspaso`), `CHANGELOG`, bump y sello    | CI real 10/10 y tag                                                       |

## 9. Verificación (comandos, patrón del repo)

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/analytics/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

uv run pytest packages/py/analytics/tests/test_auto_self_evaluation.py \
              packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/application/tests/test_auto_adaptive_entry.py \
              packages/py/application/tests/test_auto_self_evaluation_feed.py -q

# Los dos bloques offline, con los targets EXTRAÍDOS del YAML (nunca a mano)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # …+ M28…
```

Base esperada: `quality` **2218** y job `python` del tag **2229** (`v2.49`) ⇒ el delta nuevo debe ser
**el mismo en AMBOS** (es la comprobación de que ningún test quedó fuera de una de las dos listas).

## 10. Freeze (no tocar sin motivo)

- `AUTO_ENGINE_SIM_V2=0` ⇒ sigue comportándose como `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_GOVERNOR=0` ⇒ byte-idéntico a `v2.43.1` sin parada dura.
- `v2_43_governor_evidence.py` ⇒ **byte a byte igual**, `"bump"` en `1.68.0-beta`, exit 0.
- Tabla del gobernador y sus umbrales ⇒ **no** se tocan.
- `v2.49-beta` y anteriores ⇒ **no se mueven**.
- Sin SHORT.
- `RiskAllocator` / `portfolio_decision_engine.py` ⇒ **no** se tocan (el borde `pct == 0.0` se queda
  como se selló en `v2.49`).
- `adaptivePolicyVersion` anterior (`auto8-v2`) ⇒ no se reescribe: los planes ya emitidos siguen
  siendo auditables con la política que los produjo.

## 11. Riesgos (y su mitigación declarada)

| Riesgo                                                          | Mitigación                                                       |
| --------------------------------------------------------------- | ---------------------------------------------------------------- |
| El coste estimado se lee como «R neto real»                     | Etiqueta `estimatedCost` **en el dato**, no en el doc            |
| R medido sobre un subconjunto sesgado (solo ciclos con reserva) | `cycles_without_risk` publicado y `PARTIAL` si la cobertura baja |
| La lectura de régimen encarece el informe                       | §6.4: medir **antes** de elegir                                  |
| `net_expectancy_r` mueve posiciones sin querer                  | Gate §7.2: con R no medido, **nada** cambia                      |
| Varias reservas por ciclo                                       | §5.1: criterio único declarado; sin reparto                      |

## 12. Sello previsto

`package.json` → **`1.75.0-beta`**; `CHANGELOG.md` con la entrada de la fase; docs
`plan`/`pack`/`traspaso` en `docs/engineering/`; **sin migración** (Alembic head sigue `044`); tag
anotado **`v2.50-beta`** y CI real observada con `gh` — **empujando el tag de uno en uno**, lección
medida en `v2.49` (§13 del pack).

---

## 13. Estado de ejecución (2026-09-22)

### 13.1 Rotulado

La etiqueta **`AUTO-9` sobre `V2.50` / `1.75.0-beta`** queda **ratificada** por el propietario el
2026-09-22. El aviso de numeración de la cabecera deja de ser una pregunta abierta.

### 13.2 Paso 2 — lector read-only por `cycle_id` · **HECHO**

`ReservationStore` gana `list_by_cycle_ids(account_id, cycle_ids, *, limit=500)` en el Protocol y en
las **dos** implementaciones (`InMemoryReservationStore`, `PostgresReservationStore`).

Decisiones que el lector **declara** en su contrato, no que asume:

| Situación                                       | Respuesta del lector           | Por qué                                                    |
| ----------------------------------------------- | ------------------------------ | ---------------------------------------------------------- |
| Ciclo con reserva de entrada **y** de salida    | **todas** las filas del ciclo  | elegir el denominador de R es del llamante, no del store   |
| Ciclo desconocido                               | `[]`                           | un hueco se declara (`cycles_without_risk`), no se rellena |
| `cycle_ids` vacío / en blanco                   | `[]` **sin consultar la base** | un conjunto vacío no es "todos los ciclos"                 |
| Fila sin ciclo (`cycle_id IS NULL`, pre-`2.47`) | **nunca** casa un ciclo        | "anterior a 2.47" no es un ciclo                           |
| `limit <= 0`                                    | `[]`                           | techo declarado, no "sin techo"                            |
| `account_id=None`                               | sin filtro de cuenta           | el fail-closed de cuenta lo aplica el llamante             |

La consulta de `Postgres` va por el índice que **ya existía** (`portfolio_reservations_cycle_id_idx`,
migración `044`), con el `IN` saneado y desduplicado. No hay migración.

Verificación (batería **exacta** de los jobs afectados, patrón del repo):

- `ruff check` limpio; `mypy` **gate de CI** (el real del YAML, que **no** incluye `analytics/src`)
  **0 errores** en 491 ficheros; `import-linter` **4/4**.
- Bloques offline con los targets extraídos del YAML: `quality` **2218 → 2222** y job `python` del tag
  **2229 → 2233**, **0 fallos**, ⇒ **delta simétrico +4** (los 4 tests in-memory viven en
  `test_auto_v47_cycle_trace.py`, registrado en **ambas** listas, así que ninguno quedó fuera de una).
- 1 test PG gated en `test_portfolio_reservation_pg.py` (registrado en los jobs con Postgres e
  `--ignore` d en los offline), **ejecutado en local contra PostgreSQL 16.14 real** (head `044`):
  **5 passed, 0 skipped** con el gate fail-if-skipped `AUTO_RESERVATION_PG_REQUIRED=1`.

### 13.3 Paso 1 — coste de la lectura de régimen · **MEDIDO Y DECIDIDO: (a)**, sin migración

El plan (§6.4) prohíbe asumir baratura y exige decidir con la medición delante. La sonda
`apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py` entrega las dos mitades:

**Mitad offline (corre, y prueba que (a) es _posible_).** `entry_decision_id` y `auto_cycle_id` hashean
la **misma** clave (`cuenta \x1f signal_id`) con el mismo `sha256` y solo cambian el prefijo:

```
cycle_id  = "cyc-" + sha256(cuenta \x1f signal_id)[:12]
decision_id = "dec-" + sha256(cuenta \x1f signal_id)[:12]      ⇒ decision_id = "dec-" + cycle_id[4:]
```

Y `decision_journal_entries.decision_id` **está indexado** (`index=True`). Ninguna de las tres tablas
que llevan `cycle_id` (`portfolio_reservations`, `sim_fill_finance_context`, `auto_exit_orders`) guarda
un `decision_id`, de modo que la vía (a) es hoy **la única que no exige índice nuevo**.

**Su límite, medido en la propia sonda.** El fallback sin identidad de señal acuña el ciclo con `uuid4`
y tiene **exactamente la misma forma** (`cyc-` + 12 hex): la forma **no** prueba origen. Por eso adoptar
(a) obliga a **confirmar la fila leída** (`payload->>'cycleId' == cycle_id`). Con la confirmación, una
derivación equivocada **no puede leer el régimen de un ciclo ajeno**: solo deja el hueco declarado
(`UNKNOWN`). Sin ella, (a) sería un invento.

**Mitad online: MEDIDA.** PostgreSQL 16.14 con Alembic head `044`. Inventario real de
`decision_journal_entries`: cuatro índices (`decision_id`, `account_id + created_at`, `session_id`,
`pkey`) y **ningún** índice de expresión sobre `payload->>'cycleId'` — el ciclo vive solo dentro del
JSONB y la tabla **no** tiene columna `cycle_id`.

Se midió en dos escalas: la tabla de desarrollo (1 118 filas reales, 0 con `cycleId`) y una BD
**scratch** sembrada a volumen (200 000 filas, 100 000 con `cycleId`, `ANALYZE` hecho), resolviendo
**el mismo ciclo** por las dos vías en ambos casos ⇒ misma cardinalidad de salida. La diferencia es la
senda de acceso, no el resultado:

| Filas   | (a) `decision_id` derivado                              | (b) `payload->>'cycleId'`                                       | Ratio    |
| ------- | ------------------------------------------------------- | --------------------------------------------------------------- | -------- |
| 1 118   | `Index Scan` · 2 buffers · **0,023 ms**                 | `Seq Scan` · 48 buffers (tabla entera) · **0,127 ms**           | ~5,5×    |
| 200 000 | `Bitmap Index Scan` + heap · 203 buffers · **0,163 ms** | `Parallel Seq Scan` (2 workers) · 3 332 buffers · **10,997 ms** | **~67×** |

Lo que decide no es el ratio de hoy sino su **deriva**: al pasar de 1 118 a 200 000 filas (×179),
(a) va de 0,023 a 0,163 ms (**×7**, sublineal: es un índice) y (b) de 0,127 a 10,997 ms (**×87**,
lineal: recorre la tabla entera, con 2 workers para poder hacerlo antes). (b) **no puede mejorar sin
un índice que hoy no existe**; (a) ya tiene el suyo.

**DECISIÓN (cierre de §6.4): se adopta (a)** — resolver el régimen por el `decision_id` **derivado** del
`cycle_id` contra el índice `decision_journal_entries_decision_id_idx` — y **la confirmación
`payload->>'cycleId' == cycle_id` forma parte del contrato, no es opcional**. **No se crea la migración
`045`**: Alembic head sigue en `044_auto_cycle_trace`.

Lo que la confirmación obliga a declarar (y el informe del paso 7 debe publicar): el fallback aleatorio
—ciclo sin identidad de señal— **no** es resoluble por (a). Su consecuencia no es un error ni un dato
falso, es **cobertura perdida**, así que el productor declara cuántos ciclos quedaron `UNKNOWN` en
régimen (`cycles_without_regime`), igual que ya declara `cycles_without_risk`. La confirmación es
_necesaria_ además porque una futura mudanza de la clave de identidad no rompería ningún dato: solo
perdería cobertura en silencio, y eso hay que poder verlo.

Medición reproducible: `uv run --no-sync python apps/api-python/scripts/a9_cycle_regime_read_cost_probe.py`
(la mitad online exige `DATABASE_URL`). La BD scratch se crea, siembra y borra con
`apps/api-python/scripts/a9_scratch_db.py` y **no sobrevive a esta fase**.

### 13.4 Paso 3 — cálculo puro `r_multiple` / `net_r_multiple` · **HECHO**

En `auto_self_evaluation.py` (puro: sin I/O, sin reloj, sin estado) nace el contrato público
`cycle_r(*, pnl, risk_amount, cost=None) -> CycleR`:

```
r_multiple     = pnl / risk_amount
net_r_multiple = (pnl − coste_estimado) / risk_amount        (los dos a 4 decimales)
```

Reglas duras, cada una con su caso límite cubierto:

| Entrada                                                | Resultado                  | Medición   | Nota              |
| ------------------------------------------------------ | -------------------------- | ---------- | ----------------- |
| `risk_amount` ausente, `0` o **negativo**              | **los dos** R = `None`     | `UNKNOWN`  | `risk_unmeasured` |
| `pnl` ausente                                          | los dos R = `None`         | `UNKNOWN`  | `pnl_unmeasured`  |
| `cost` ausente, ilegible o con `total` sin cuantificar | neto = `None`; el bruto sí | `PARTIAL`  | `cost_unmeasured` |
| `pnl = 0` **medido** (con riesgo y coste)              | `0.0` en los dos           | `COMPLETE` | —                 |

Decisiones que el código **declara** y que conviene no volver a discutir:

- **Nunca `0` donde no hay medida, nunca `inf`.** Un `risk_amount` no positivo no se
  sustituye por un cero: un R de `0` afirmaría "no pasó nada", que es una conclusión que
  nadie midió; y dividir sin guarda habría publicado "riesgo gratis".
- **Un `pnl = 0` medido SÍ es una medida** (`0.0`, `COMPLETE`). Es la otra mitad del mismo
  principio: un resultado plano es un dato; un hueco no, y el informe no puede confundirlos.
- **El coste es `TradingCost.total`** — comisión + spread + slippage. El `gap` **no** entra en
  `total` por diseño del modelo (es una cola de pérdida si el stop no retiene, no una
  fricción), así que no se le añade aquí. Y ojo con el matiz: que el `measurement` del coste
  sea `PARTIAL` porque falten `gap`/`stop_loss` **no** bloquea el R neto — esos componentes
  gobiernan las estimaciones de **pérdida**, no el total de fricción, que solo existe cuando
  sus tres sumandos existen.
- **Ausente ≠ incompleto ≠ cero.** Un `cost` ilegible no se lee como coste `0` (eso sería
  regalar R) y un coste medido de `0.0` sí produce un neto medido.
- **El coste es el estimado en la decisión, no el realizado** (§6.3): queda escrito en el
  docstring que quien publique `net_r_multiple` debe etiquetarlo como estimado.
- `CycleR` publica `risk_amount` y `cost_estimate` junto a los dos R porque son el **rastro de
  la división**: un R sin su denominador no es auditable.

Verificación: `test_auto_self_evaluation.py` **16 → 24** (_+8_), `ruff` limpio, `mypy` gate de CI
**0 errores / 491 ficheros**, `import-linter` **4/4**, y los dos bloques offline **`quality` 2222 →
2230** y job `python` del tag **2233 → 2241**, 0 fallos ⇒ **delta simétrico +8**. La simetría aquí es
**estructural**, no una comprobación: los tests viven en `packages/py/analytics/tests`, que ambos jobs
incluyen **por directorio**.

### 13.5 Paso 4 — agregación `strategy × regime` · **HECHO**

`auto_self_evaluation.py` publica el cruce con el material que ya tenía: `AutoSelfEvaluation.by_regime`
(tupla de `StrategyRegimeEvaluation`) y `cycles_without_regime`; el cálculo puro vive en
`aggregate_by_regime(cycles, *, min_trades)` y la consulta en `declared_regime(cells, version)`.

| Situación                                   | Respuesta del cruce                                 | Por qué                                                                  |
| ------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------ |
| Ciclo sin régimen declarado                 | cubo **propio** `UNKNOWN`                           | no se reparte ni se hereda: ese cruce nadie lo declaró                   |
| `unknown` / `UNKNOWN` / `Unknown` / ausente | **el mismo** cubo                                   | el valor se normaliza; el hueco no se multiplica                         |
| Ciclo repetido (misma identidad)            | cuenta **una vez**                                  | misma maquinaria `_dedupe_cycles` que el informe                         |
| Ciclo sin versión de estrategia             | **no** entra en el cruce                            | el cajón `unattributed` ya lo declara el informe                         |
| Celda por debajo de `min_trades`            | `decisive = False`                                  | `min_trades` es **por celda**: 90 ciclos en 3 regímenes son celdas de 30 |
| Celda con algún ciclo sin R                 | `decisive = False`, `rMeasurement = PARTIAL`        | una celda decisoria exige el R medido en **todos** sus ciclos            |
| Coste ausente en algún ciclo                | neto promediado sobre lo medido + `netRMeasurement` | `decisive` **no** cubre el neto: el consumidor exige `COMPLETE` (§5.4)   |

Decisiones que el código **declara** y que conviene no volver a discutir:

- **El cruce no se apropia del embudo.** `traded`/`rejected`/… no tienen dimensión de régimen en el
  dato durable, así que la celda **no** los publica y el informe añade
  `funnel_not_dimensioned_by_regime`. El embudo sigue en `byStrategy`, donde sí está medido.
- **Una `UNKNOWN` decisoria no asciende a régimen.** `declared_regime` devuelve `(régimen, None)`
  solo si hay **exactamente una** celda decisiva **con** régimen; en cualquier otro caso devuelve
  `(None, regime_undetermined)`. Publicar el par obliga a publicar el motivo del hueco: elegir un
  régimen entre dos candidatos sería inventar el cruce.
- **Orden canónico.** Las celdas se emiten ordenadas por `(strategyVersion, regime)`, así que el
  cruce no depende del orden en que lleguen las filas (golden de ida y vuelta en los tests).
- **El R declarado manda.** Si el ciclo ya trae su `r_multiple`, el cruce **no** lo recalcula: solo
  calcula lo que falta. Así el mismo módulo sirve al informe AUTO-7 (que recibe el R medido) y al
  productor del `v2.50` (que solo tiene el material en crudo), sin duplicar la aritmética.
- **La ruta API no cambia** (§3, «fuera: UI nueva»): el DTO de `auto/self-evaluation` construye sus
  campos explícitamente, de modo que el payload gana `byRegime` / `cyclesWithoutRegime` y la
  respuesta HTTP sigue siendo la misma. Sus tests pasan sin tocarlos.

Verificación: `test_auto_self_evaluation.py` **24 → 37** (_+13_), `ruff` limpio, `mypy` gate de CI
**0 errores / 491 ficheros**, `import-linter` **4/4**, y los dos bloques offline **`quality` 2230 →
2243** y job `python` del tag **2241 → 2254**, 0 fallos ⇒ **delta simétrico +13**.

### 13.6 Paso 5 — `net_expectancy_r` + `regime` en `StrategyHealth` · **HECHO**

`StrategyHealth` gana `net_r_measurement` y su `regime` deja de ser un literal: lo **deriva** del
cruce `strategy × regime` del **mismo** informe con `declared_regime`. `from_evaluation` acepta
`regime_cells`, `build_strategy_health` y `recommend_rotation` lo hilan y `AdaptivePlan.evidence_for`
publica `netExpectancyR` / `netRMeasurement` junto al resto de la evidencia.

| Situación                            | `StrategyHealth.regime` | Por qué                                       |
| ------------------------------------ | ----------------------- | --------------------------------------------- |
| Una celda decisiva **con** régimen   | ese régimen             | el cruce lo determina: no hay nada que elegir |
| Dos celdas decisivas (dos regímenes) | `UNKNOWN`               | elegir uno sería inventar el cruce            |
| Solo la celda `UNKNOWN` decisiva     | `UNKNOWN`               | la `UNKNOWN` **no** asciende a régimen        |
| Sin celdas (informe sin cruce)       | `UNKNOWN`               | el hueco se declara, no se hereda de la fila  |

Lo que este paso **no** hace es lo que mantiene vivo el gate §7.2: mapear evidencia no puede mover
una decisión. `test_regime_cells_alone_do_not_move_rotation_or_allocation` fija que añadir el cruce
deja rotación y asignación **idénticas**; el paso 6 es, por eso, el que sí toca la asignación — y
solo la asignación. La versión de política sube a **`auto9-v1`**: el contrato de evidencia cambió, y
el sello viaja en `as_dict()` y en el journal (`policyVersion`).

Verificación: `test_auto_adaptive.py` **29 → 36** (_+7_) y `test_auto_self_evaluation.py` **37 → 38**
(_+1_) ⇒ **+8**; `test_auto_adaptive_entry.py` **9 → 9** (solo se ajustó el helper `_row`, ningún caso
nuevo). `ruff` limpio, `mypy` gate de CI **0 errores / 491 ficheros**, `import-linter` **4/4**.

### 13.7 Paso 6 — consumo en la asignación: **eje de evidencia** · **HECHO**

El reparto pesaba con `expectancy_currency`. Desde aquí pesa con el **R neto medido** cuando ese eje
está medido para **todo** el grupo que compite, y con la moneda bruta cuando no — que es exactamente
el comportamiento anterior, así que «con R no medido **no** cambia nada» es una propiedad, no una
promesa. La decisión estructural es que el eje se elige por **pool** y **nunca** por fila:
`expectancy_currency` es absoluta y `net_expectancy_r` es adimensional, de modo que mezclar pesos de
los dos en el mismo reparto sería aritmética sin sentido.

| Situación                                  | Eje                   | Por qué                                                  |
| ------------------------------------------ | --------------------- | -------------------------------------------------------- |
| Todo el pool con R `COMPLETE` y positivo   | `net_expectancy_r`    | es la evidencia mejor normalizada disponible             |
| Alguna del pool sin R medido (o `PARTIAL`) | `expectancy_currency` | un hueco de medición **no** saca a nadie del reparto     |
| R medido y **≤ 0** en alguna del pool      | `expectancy_currency` | un R no positivo no es peso; y menos aún si rompe el eje |
| Sin decisorias positivas en ningún eje     | `expectancy_currency` | todas neutrales: no hay reparto al que cambiarle el eje  |

El eje se **declara** en `AllocationPlan.evidence_axis` y viaja en `as_dict()`, así que aparece en el
detalle de pausa del journal (`adaptive.as_dict()`) sin campos añadidos a mano. El default del campo
es el eje histórico: construir un `AllocationPlan` a mano —como hace el test de gates duros— sigue
significando lo mismo. La exigencia de R medido es `is_complete(net_r_measurement)`, es decir
`COMPLETE` estricto (§6.3: el coste es **estimado** y un `PARTIAL` promedia solo los ciclos con
coste).

Verificación: `test_auto_adaptive.py` **36 → 44** (_+8_), `ruff` limpio, `mypy` de los dos módulos
tocados **0 errores**, `import-linter` **4/4**, suite `analytics` **973 passed** (sin
`test_vectorbt_optuna.py`, que en esta máquina no importa por el bloqueo de DLL de `numba`) y
`application` **1779 passed**. Los dos tests que fijan el paso:

- `test_measuring_the_net_r_moves_the_allocation_but_never_the_rotation` — medir R mueve el reparto
  (`0.5 → 2/3`) y deja la rotación **byte-idéntica**, que es la prueba de que el paso 6 no puede
  tocar nada más que la asignación.
- `test_allocation_with_unmeasured_net_r_is_identical_to_the_historical_axis` — compara
  `multipliers` **y** `as_dict()` completos contra el eje histórico, sin R y con R `PARTIAL`.

### 13.8 Verificación de los dos bloques offline (pasos 5–6) · **RE-BASELINE DECLARADO**

El criterio del plan (§9) pide los dos bloques con los targets **extraídos del YAML** y delta
**simétrico**. Medido en esta máquina, con PostgreSQL local levantado:

| Bloque (targets del YAML)                       | Total | Pasan | Rojos | Delta de la fase |
| ----------------------------------------------- | ----- | ----- | ----- | ---------------- |
| `quality` (49 targets, `python-ci.yml`)         | 2500  | 2498  | 2     | **+16**          |
| job `python` del tag (58, `release-tag-ci.yml`) | 2511  | 2509  | 2     | **+16**          |

- **El delta es +16 y simétrico**, y es el medible: `packages/py/analytics/tests` entra por
  **directorio** en los dos bloques, y en esa carpeta los tests pasan de **66 a 82** exactos
  (`test_auto_adaptive.py` **29 → 44** y `test_auto_self_evaluation.py` **37 → 38**), repartidos
  **+8** (paso 5) y **+8** (paso 6). El `+11` estructural entre los dos bloques se conserva
  (2500 + 11 = 2511), igual que en las entradas anteriores de §13.
- **Los 2 rojos NO son de esta fase y no son de código**: `test_tax_report_after_round_trip_trade` y
  `test_workspaces_crud` fallan **por orden de ejecución** (cada uno pasa en aislamiento, y se
  reproducen corriendo solo ficheros que este plan **no** toca). Van en `apps/api-python/tests`, el
  último target de directorio de ambos bloques.
- **Discontinuidad declarada de la serie.** Los totales absolutos de esta tabla **no** son
  comparables con los de §13.2–§13.5 (2243 / 2254): ambos miden **+257** exactos, un desplazamiento
  **simétrico** que no puede venir de los tests añadidos (+16) y que **no se ha podido reproducir**
  con la misma extracción. Se deja declarado en lugar de atribuirlo a una causa no medida; lo
  comparable —y lo que el criterio exige— es el **delta**, que sí está medido dos veces.

### 13.9 Paso 7 — evidencia en el journal · **HECHO CON HUECOS DECLARADOS**

El paso 7 pedía evidencia «por ciclo y por estrategia, con su estado de medición». Al abrirlo, la
verificación de la premisa (§4.3) tumbó la mitad del alcance previsto: **el régimen por ciclo no es
legible de ninguna fuente durable** en el camino que produce los ciclos. En vez de rellenarlo con un
`UNKNOWN` que parecería medido, se entrega lo que **sí** se puede medir y se declara el resto.

**Lo entregado.** Un productor read-only (`packages/py/application/src/bolsa_application/cycle_risk.py`)
que ata por `cycle_id` el **denominador** de R (`portfolio_reservations.reserved_risk`) y el **coste
estimado** (`cost`), y una costura en el worker que lo inyecta en el informe AUTO-7
(`build_auto_self_evaluation(..., cycle_risk=…)`). Con eso el `expectancy_r` deja de ser un `None`
permanente: pasa a ser un dato **medido** o **declarado ausente**, ciclo a ciclo.

**Las cuatro reglas duras del productor** (cada una con su test):

| Regla                                       | Por qué                                                                                                                        |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Denominador **uno**: la entrada más antigua | varias reservas (entrada + salidas) ⇒ repartir el riesgo sería una media de denominadores, no una razón                        |
| Las reservas **liberadas** cuentan          | un ciclo CERRADO ya no tiene reserva viva: filtrar por viva dejaría el denominador en `None` justo en los ciclos con resultado |
| La ausencia **se declara** (`None` + nota)  | un riesgo `0` daría `inf`, y un `0` de relleno sería un número falso                                                           |
| El régimen **no se inventa**                | se publica `None` + `regime_not_durable`; la costura (`regime_by_cycle`) queda lista para el productor durable que falta       |

**El fail-closed cambia de forma, y se declara.** §5.1 preveía `errors=["cycle_risk_read_failed"]` +
`decisive = False`. Lo implementado **degrada sin afirmar**: una lectura rota devuelve `None`, el
informe recupera exactamente su forma AUTO-7 (los ciclos quedan sin R, que es el hueco que el módulo
ya declaraba) y la salud de los fills sigue mandando. Es más honesto que marcar `decisive = False`,
que confundiría «no pude leer el riesgo» con «la muestra no es decisoria», y no puede estrechar ni
rotar a ciegas en ningún caso. Una lectura **saturada** (tope de `list_by_cycle_ids`) tampoco veta:
los ciclos que no cupieron quedan declarados **sin** denominador — nunca con el de otro ciclo — y el
hecho se registra con un `warning`.

**Lo que este paso NO hace** (y por qué no es un olvido): no escribe ninguna fila durable. El journal
del worker es una lista **en memoria**, así que `cycleId` y `marketRegime` no llegan a
`decision_journal_entries` para los ciclos AUTO. Convertir ese journal en el durable es trabajo del
**worker**, no de un adaptador read-only, y se declara como deuda con nombre en §4.3. Mientras tanto,
la evidencia **sí** viaja al journal en la forma que el camino ya soporta: por **estrategia**
(`adaptiveEvidence` con `expectancyR` / `netExpectancyR` / `netRMeasurement` / `regime` y su
`policyVersion`) y por **ciclo** en el propio informe (`by_regime`, `cycles_without_regime`,
`cycles_without_cost`).

**Verificación.**

- `packages/py/application/tests/test_cycle_risk.py` (**21 tests**, nuevo): denominador único,
  reserva liberada, ausencia declarada, riesgo `0`, ciclos pedidos sin reserva, orden estable,
  régimen hueco/declarado, `to_cycle_fields` sin campos no medidos, costura identidad sin evidencia,
  los tres casos del informe (R medido, neto sin coste, cruce de régimen abierto), y los cuatro del
  gate §7 (invariancia al orden de reservas, reproducibilidad del payload, `None` —nunca `0.0`— en
  toda la superficie, y el ciclo sin medida).
- `apps/api-python/tests/test_auto_v50_auto9_cycle_risk_seam.py` (**7 tests**, nuevo): el worker mide
  el R del ciclo, sin reservas recupera la forma AUTO-7, no se presta el denominador de otro ciclo,
  sin ciclo no se mide, lectura rota degrada declarando, sin store sigue decidiendo por fills, y
  lectura saturada avisa.
- `packages/py/analytics/tests` **975 passed** (sin `test_vectorbt_optuna.py`, bloqueo de DLL de
  `numba` en esta máquina) · suites de `application` afectadas **58 passed** · `ruff` limpio sobre los
  ficheros tocados · `mypy` gate de CI **0 errores / 492 ficheros** · `import-linter` **4/4**.
- **Registro en CI simétrico.** `test_cycle_risk.py` va **explícito** en los dos jobs
  (`quality` de `python-ci.yml` y `python` del tag): vive en `packages/py/application/tests`, que no
  tiene pase de directorio en ninguno de los dos. La costura del worker entra por el pase de
  directorio de `apps/api-python/tests`. Es la deuda que v2.47 cerró para
  `test_decision_journal_studies.py`, repetida aquí a propósito.

### 13.10 Gate §7 · **CERRADO**, punto por punto

| #   | Criterio (§7)                             | Test que lo fija                                                                                            | Estado              |
| --- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------- |
| 1   | Byte-identidad con `ADAPTIVE=0`           | `test_adaptive_on_neutral_is_byte_identical_to_off` (`test_auto_adaptive_entry.py`)                         | ya venía de `v2.49` |
| 2   | Neutralidad: medir R no cambia decisiones | `test_allocation_with_unmeasured_net_r_is_identical_to_the_historical_axis`                                 | paso 6              |
| 3   | Hard gates intactos                       | `test_adding_evidence_never_moves_rotation_or_allocation` + el de gates duros                               | pasos 5–6           |
| 4   | Honestidad del hueco (nada de `0.0`)      | `test_no_surface_publishes_a_zero_where_the_gap_is_declared` + `…unmeasured…` (**nuevos**)                  | paso 7              |
| 5   | `strategy × regime` declarado             | `declared_regime` con dos celdas / una `UNKNOWN` decisiva                                                   | paso 4              |
| 6   | Reproducibilidad e invariancia al orden   | `test_the_producer_is_invariant_to_the_order_of_the_reservations` + `…report_is_reproducible…` (**nuevos**) | paso 7              |
| 7   | `adaptivePolicyVersion = auto9-v1`        | `test_the_policy_version_seals_the_auto9_evidence_contract`                                                 | paso 5              |

Subconjunto del gate corrido de una vez (`-k "byte_identical or neutral or hard or invariant or
reproducible or policy_version or gate"`): **11 passed, 101 deselected**. Los puntos 4 y 6 son los
únicos que el paso 7 tuvo que añadir; el resto ya estaba sellado por los pasos anteriores, y se
verifica que sigue estándolo.

### 13.11 Paso 9 (mutaciones) y verificación de los dos bloques · pasos 8–9 **HECHOS**

**Mutaciones: 33/33 muerden y el árbol queda intacto.** La matriz completa (`M1…M33`) se corrió de
una vez: **33 detectadas, 0 no detectadas, 0 restauraciones fallidas**, con la huella
`git status --porcelain` de los ficheros tocados **idéntica** antes y después (`intacto: la sonda no
altero el arbol`). Las seis nuevas de `AUTO-9`:

> **ENMIENDA (2026-09-22, medida en `AUTO-10` paso 5):** el `33/33` era **sobrestimado**. Al correr la
> matriz en `V2.51` se midió que `M25`, `M26` y `M33` **ya no aplicaban** desde el commit de código
> `df2002e7` (sus fragmentos habían derivado con el reformateo y la sonda **seguía** en vez de fallar),
> así que aplicaban **30/33**. En `V2.51` se reescribieron los cuatro fragmentos (`+M30`, roto por el
> paso 3 de `AUTO-10`) y la sonda pasa a **fallar** si un fragmento no existe, con el mismo criterio con
> el que ya abortaba si aparecía más de una vez. El producto de `V2.50` **no** cambia por esto: se
> corrige la afirmación, no el código. Detalle en `plan-v2-51-auto-10-…-2026-09-22.md` §3.3.

| #   | Qué rompe                                          | Rojos | Test que la caza (muestra)                                                       |
| --- | -------------------------------------------------- | ----- | -------------------------------------------------------------------------------- |
| M28 | el denominador pasa a ser la reserva **más nueva** | 2     | `test_the_oldest_entry_reservation_wins_and_the_rest_are_declared`               |
| M29 | una **venta** (riesgo `0`) entra como denominador  | 3     | `test_a_zero_risk_is_not_a_denominator`, `…entry_reservation_is_the_denominator` |
| M30 | un ciclo sin reservas **desaparece** del mapa      | 4     | `test_every_requested_cycle_appears_even_without_reservations`                   |
| M31 | el coste ausente se publica como **clave nula**    | 1     | `test_apply_cycle_risk_never_writes_an_unmeasured_field`                         |
| M32 | el informe **ignora** la evidencia que le llega    | 3     | `test_the_feed_measures_the_r_when_the_producer_gives_the_denominator`           |
| M33 | el worker **deja de leer** el riesgo por ciclo     | 3     | `test_the_worker_measures_the_r_from_the_cycle_reservation`                      |

**Dos hallazgos de la propia sonda, corregidos aquí** (una sonda que se cae dejando el mutante dentro
del árbol es peor que una que aborta):

1. **La restauración podía dejar el mutante puesto.** Con `M16` (que muta `auto_v2_entry.py`), el
   `write_bytes` de restauración falló de forma **reproducible** con `OSError [Errno 22]` de Windows —
   con el fichero **limpio** y con el mismo par escritura/restauración funcionando aislado —, y las
   dos primeras corridas **abortaron dejando `return best, ()` dentro del árbol** (se restauró a mano
   con `git checkout`). La sonda ya no puede hacer eso: `_restore` reintenta con pausa, prueba un
   reemplazo atómico con `os.replace` y, solo como último recurso, usa `git checkout`… **y solo si el
   fichero está limpio en git** (si tuviera cambios sin commitear, **aborta declarándolo** en vez de
   descartar trabajo ajeno). Con eso la matriz completa ya corre de principio a fin.
2. **La sonda admitía un filtro por rótulo** (`… M28 M29`): verificar un tramo no obliga a arrastrar
   las 30 corridas anteriores. Sin argumentos corre la matriz **completa**, como siempre.

**Bloques offline: verdes y simétricos, y la discontinuidad de §13.8 queda resuelta.** Con los
targets extraídos del YAML (`--with-pg-ignores`) y PostgreSQL local levantado:

| Bloque (targets del YAML)                       | Total | Pasan | Rojos | Delta de la fase |
| ----------------------------------------------- | ----- | ----- | ----- | ---------------- |
| `quality` (50 targets, `python-ci.yml`)         | 2287  | 2287  | **0** | **+69**          |
| job `python` del tag (59, `release-tag-ci.yml`) | 2298  | 2298  | **0** | **+69**          |

- **El delta es +69 en AMBOS** y es la cuenta exacta de la fase: **+4** (paso 2) **+8** (paso 3)
  **+13** (paso 4) **+8** (paso 5) **+8** (paso 6) **+21** (`test_cycle_risk.py`) **+7** (costura del
  worker) = **69**, sobre las bases `v2.49` de **2218** y **2229**. El `+11` estructural entre los dos
  bloques se conserva (2287 + 11 = 2298).
- **Los 2 rojos de §13.8 no reaparecen**: ambos bloques van **0 rojos / 0 skipped**. Aquella medición
  los atribuyó a contaminación de orden; aquí no se manifiestan.
- **La discontinuidad declarada en §13.8 queda cerrada, y a favor del dato.** Aquella tabla midió
  **2500 / 2511** y no se pudo reproducir; esta corrida, **con la misma extracción**, da **2287 /
  2298**, que es exactamente la serie de §13.2–§13.5 (`2243 / 2254`) más el delta de los pasos 5–7
  (**+44**). Es decir: los totales absolutos de §13.8 eran el artefacto (una recolección de más), no
  la serie. Se sustituyen por estos, que cierran la aritmética sin residuo.

### 13.12 Hallazgo operativo del tooling · **`ruff format` NO es un invariante del repo**

Ocurrió al cerrar el paso 9 y se deja escrito porque es un hazard real, no una anécdota.

La compuerta de CI es **`ruff check … --config pyproject.toml`** (lint, incluido el orden de imports).
**`ruff format` no está en ningún job.** La consecuencia es que el repo tiene _drift_ de formato
respecto a la config de la raíz: al ejecutar `uv run ruff format packages/py apps/api-python --config
pyproject.toml` para "dejar todo formateado", ruff **reescribió 608 ficheros** que no eran míos (y sí
lo estaban mis dieciséis, que ya cumplían la config). Es decir: el formato del repo **no** es la
config de la raíz, y formatear en masa mete 600 ficheros ajenos en el diff de la fase.

**Lo que se hizo, y por qué el criterio es exacto.** No se descartó nada a ciegas: para cada fichero
tocado se reconstruyó `HEAD`, se reformateó con **la misma invocación** que causó el daño y se comparó
con el contenido en disco. Si coincidían, el contenido era _solo_ `HEAD` reformateado (ruido) y se
restauró con `git checkout`; si no, había cambio semántico y se conservó. Resultado: **610 ficheros
analizados → 597 restaurados (ruido), 13 conservados (los míos)**, y el `git status` volvió a las
**24 entradas** de la fase. El paso dejó además un fallo útil de entorno (el mismo que mordió a la
sonda de mutaciones): escribir muchos `.py` seguidos dispara `OSError [Errno 22]` de Windows, así que
toda restauración masiva va con reintento y `os.replace`.

**Regla para la próxima fase:** usar `ruff check --config pyproject.toml` como compuerta (que es lo
que CI mira) y `ruff format` **solo** sobre los ficheros que uno ha tocado, nunca en masa.
