# Plan de fase — `V2.50` / `AUTO-9`: `strategy × regime` y `net expectancy_R`

**Fecha:** 2026-09-22 · **Estado:** PLAN (no implementado) · **Bump objetivo:** `1.74.0-beta` → `1.75.0-beta`
**Fase previa:** [`v2.49-beta` / `AUTO-8.1`](./traspaso-relevo-post-v2-49-auto-8-1-adaptive-correcto-2026-09-21.md)
**Informe que lo motiva:** [`audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md`](./audit-pack-v2.49-auto-8-1-adaptive-correcto-2026-09-21.md) §11 y §12

> **Aviso de numeración.** El [roadmap AUTO](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) llega hasta
> `AUTO-8` (`V2.48+`, `1.73.0-beta`) y reservaba la etiqueta interna `AUTO-9` para `V2.49`. `V2.49` se
> consumió en `AUTO-8.1` (corrección de `AUTO-8`), así que esta fase toma la etiqueta **`AUTO-9`** sobre
> **`V2.50` / `1.75.0-beta`**. Es una decisión de rotulado, no un hecho: **pendiente de ratificar**.

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

### 4.3 `decision_journal_entries` — el régimen por ciclo

El payload de la decisión ya lleva `cycleId` (`auto_v2_entry.py:2259-2262`) y **las tres dimensiones
del gobernador** (`marketRegime`, `riskRegime`, `operationalState`) en `auto_v2_entry.py:2296-2302`.
La tabla es durable y append-only (`tables.py:720-732`).

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
**Debe medirse antes de elegir**: el plan no asume que sea barato.

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
