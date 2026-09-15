# Audit Pack — V2.40.1 / AUTO Safety Hardening · fail-closed real + fuentes reales (2026-09-15)

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.40.1** sobre `v2.40-beta` — cierra los **siete P0** de la auditoría de esa versión en el
> pipeline de decisión de AUTO 2.0 y **cablea en producción** las fuentes que lo alimentan (sector,
> liquidez, edge, régimen).
>
> **Base auditada:** `v2.40-beta` (`1.65.0-beta`).
> **Bump:** `1.65.0-beta` → **`1.65.1-beta`**.
> **Alembic head:** `040_auto_v2_durable_state` (**sin migración nueva**).
> **Flags:** `AUTO_ENGINE_SIM_V2` (**OFF por defecto**). Con el flag sin activar, AUTO se comporta
> exactamente como `v2.39.3-beta`: el endurecimiento vive entero dentro del camino V2.
> **Breaking declarado (en beta):** se elimina el env `AUTO_ENGINE_SIM_V2_DEFAULT_EDGE` y el campo
> `V2Tunables.default_edge` (ver §3). Cualquier despliegue que dependiera de ese valor por defecto
> deja de tener edge ⇒ **NO ENTRY** hasta que exista un `EdgeReport` persistido o la propuesta
> declare `memo edge=`.
> **Sello CI:** esta fase **no** reclama un run de GitHub (patrón honesto del repo: no se afirma CI
> de un commit aún no publicado). La evidencia de ejecución es **local** y está en §7, con la
> batería **exacta** de los jobs afectados.

---

## 0. Resumen ejecutivo

La auditoría de `v2.40-beta` fue consistente en un diagnóstico: **AUTO 2.0 tenía el modelo operativo
correcto y la disciplina de datos equivocada**. Los vetos existían, pero varios de ellos **se
aprobaban por ausencia de dato** (correlación `None` ⇒ "sin conflicto", liquidez `None` ⇒ 1.0,
edge ausente ⇒ 0.9, `signal_id` vacío ⇒ se decide igual, plan de posición sin sector ⇒ todas las
posiciones caían al centinela `<unknown>`), y el motor **no acumulaba** el riesgo comprometido
dentro del tick, así que N candidatas del mismo tick se evaluaban contra la **misma** foto inicial.
A eso se sumaba un gap de producción: el runtime real construía el worker **sin** fuentes de
régimen, sector ni liquidez, de modo que AUTO V2 en producción era `UNKNOWN` ⇒ exit-only ⇒ nunca
abría nada (un sistema ciego que parecía prudente).

Esta fase **no cambia el modelo**, cambia su **aritmética de verdad**:

| Eje                   | Antes (`v2.40-beta`)                                                    | Ahora (`v2.40.1-beta`)                                                                 |
| --------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Correlación           | `None` ⇒ no hay conflicto (fail-open)                                   | Gate activo ⇒ solo `CALCULATED` pasa; el resto veta `correlation_unknown`              |
| Sector                | snapshot sin `sector` ⇒ todo `<unknown>`; el candidato se medía solo    | snapshot con sectores **conocidos**; posición opaca ⇒ `sector_exposure_unverifiable`   |
| Riesgo intra-tick     | `_committed_position()` sin `risk_amount` ⇒ `risk_used` no subía        | foto de trabajo acumulativa: A → reserva → B → reserva → C                             |
| Edge                  | `default_edge = 0.9` si no se declara                                   | `None` ⇒ componente 0 ⇒ `edge_below_threshold`; edge real del `EdgeReport` persistido  |
| Liquidez              | `None` ⇒ `liquidity = 1.0`                                              | `None` ⇒ veto `liquidity_unknown`; notional real del catálogo (`advUsd`)               |
| Identidad de señal    | `signal_id` opcional; dedupe por `setdefault` (depende del orden)       | `signal_id` obligatorio; dedupe por clave canónica (determinista ante cualquier orden) |
| `EXIT_ONLY`           | solo ganaba si `order_action == "hold"`                                 | **precedencia absoluta**: liquida y anula `REDUCE`/`TAKE_PROFIT`/trailing              |
| Fuentes en producción | ninguna inyectada en `AutoSimRuntime` ⇒ régimen `UNKNOWN` ⇒ sin entrada | régimen + sector + ADV + edge cableados sobre la sesión viva del tick                  |

**Veredicto:** tras esta fase, "no tengo el dato" **no puede** producir una entrada, y el motor real
de producción tiene los datos que necesita para decidir. La contrapartida operativa está
documentada y es deliberada: AUTO queda en **NO ENTRY** si el catálogo no tiene sector/ADV frescos o
si la versión ACTIVE no tiene un `EdgeReport` vigente.

---

## 1. P0-1 · Correlación fail-open

**Afirmación:** con el gate de correlación configurado (`max_correlation`), una correlación
**desconocida** veta la entrada en vez de aprobarse.

**Antes:** `_correlation_conflict()` devolvía `False` cuando `correlation is None`: la ausencia del
dato se interpretaba como "sin conflicto de correlación". Es el patrón fail-open clásico: el veto
existía en el código pero **no podía dispararse** si el dato faltaba.

**Ahora:** el chequeo es **por estado**. `TradeContext.correlation_status` distingue `CALCULATED` de
`STALE`/`UNAVAILABLE`/`CONFLICTING`; con el gate activo solo `CALCULATED` pasa y el resto emite
`correlation_unknown`, que está en `_NO_TRADE_REASONS`. Con `max_correlation is None` (gate apagado
de forma explícita) el comportamiento no cambia: no se inventa un gate que nadie pidió.

**Código:** `packages/py/analytics/src/bolsa_analytics/cognitive/trade_context.py` (tri-estado y
resolución) · `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`
(`correlation_unknown`, `_NO_TRADE_REASONS`).
**Test:** `packages/py/application/tests/test_portfolio_decision_engine.py::test_correlation_unknown_blocks_when_gate_enabled` ·
`packages/py/application/tests/test_auto_v2_entry.py::test_plan_v2_tick_unknown_correlation_blocks_when_gate_on`.

---

## 2. P0-2 · Concentración sectorial medida sobre cajas opacas

**Afirmación:** la exposición sectorial del libro se calcula con los sectores **reales** de las
posiciones abiertas, y si algún sector no es fiable el motor **veta** nuevas entradas en vez de
asumir que la cartera está limpia.

**Antes:** `build_worker_snapshot()` **no transmitía `sector`** de las posiciones abiertas, así que
todas caían al sentinel `<unknown>` de `portfolio_fit.py`. Consecuencia: el sector del candidato se
medía **solo contra sí mismo** y el gate de concentración no podía violarse nunca. Además
`_concentration_violates()` no vetaba sin snapshot o sin `max_sector_pct`.

**Ahora:** el snapshot lleva los sectores **conocidos** (`_v2_open_sectors()` sólo publica lo que
resuelve a `KNOWN`; el resto **no se publica a propósito**, la posición queda OPACA) y
`decide_portfolio` veta con `sector_exposure_unverifiable` si alguna posición abierta tiene sector
no verificable: **no se aumenta exposición sobre estado opaco**. Para el candidato, el gate es
explícito por estado: `sector_unknown` / `sector_conflicting` (el `memo sector=` y
`instruments.sector` difieren tras normalizar) / `sector_stale` (`fetchedAt` de fundamentales
supera `sector_max_age_days`, 30 por defecto), todos en `_NO_TRADE_REASONS`.

**Código:** `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`
(`_sector_exposure_unverifiable`, `_SECTOR_REJECTION_CODE`) ·
`packages/py/application/src/bolsa_application/auto_v2_entry.py` (`build_worker_snapshot` con
`sectors`, `_context_for_signal`) · `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
(`_v2_open_sectors`).
**Test:** `test_portfolio_decision_engine.py::test_sector_unknown_blocks` /
`::test_sector_conflicting_blocks` / `::test_sector_stale_blocks` /
`::test_sector_exposure_unverifiable_blocks` / `::test_unknown_sector_sentinel_is_unverifiable` ·
`test_auto_v2_entry.py::test_plan_v2_tick_unknown_sector_is_rejected` /
`::test_plan_v2_tick_sector_conflict_with_catalog_is_rejected` /
`::test_plan_v2_tick_stale_observation_is_rejected` /
`::test_plan_v2_tick_open_position_without_sector_blocks_new_entries` /
`::test_build_worker_snapshot_carries_open_position_sectors`.

---

## 3. P0-3 · Sobre-gasto de riesgo dentro del tick

**Afirmación:** cada aprobación **reserva** riesgo y exposición antes de evaluar la siguiente
candidata del mismo tick.

**Antes:** `_committed_position()` no propagaba `risk_amount`, así que `risk_used` no subía dentro
del tick: N candidatas con presupuesto 6 % y riesgo 1 % podían aprobarse todas evaluando cada una
contra la **misma** foto inicial (6 % comprometido ≠ 6 % medido).

**Ahora:** se reconstruye una **foto de trabajo** por aprobación (`_working_snapshot`) que suma el
riesgo comprometido (`snapshot.risk_used + Σ risk_amount`) y recalcula `exposure` y
`exposure_by_sector` con las posiciones comprometidas incluidas. El orden de evaluación pasa a ser
A → reserva → B → reserva → C, nunca "las tres contra la misma foto".

**Invariante certificado:** 6 candidatas de riesgo 1 % con presupuesto 6 % ⇒ **exactamente 6**
aprobadas, `risk_remaining == 0` y la **7ª** veta por `risk_budget_exceeded`. La misma lógica se
certifica para la exposición sectorial intra-tick.

**Código:** `packages/py/application/src/bolsa_application/auto_v2_entry.py`
(`_working_snapshot`, `_committed_position` con `risk_amount` y `sector`).
**Test:** `packages/py/application/tests/test_auto_v2_entry.py::test_plan_v2_tick_reserves_risk_intra_tick` ·
`::test_plan_v2_tick_reserves_sector_exposure_intra_tick`.

---

## 4. P0-4 · Edge y liquidez inventados (fail-open por defecto)

**Afirmación:** el motor **no** inventa edge ni liquidez; su ausencia se propaga como ausencia y el
tick queda en NO ENTRY.

**Antes:** `V2Tunables.default_edge = 0.9` (env `AUTO_ENGINE_SIM_V2_DEFAULT_EDGE`) convertía "la
estrategia no declara edge" en una puntuación de oportunidad excelente, y `_score_from_signal()`
asignaba `liquidity = 1.0` cuando `liquidity_notional is None`. Dos fail-open del mismo tipo: el
componente ausente puntuaba como el mejor valor posible.

**Ahora (breaking, en beta):** se **eliminan** `default_edge` y su env; `edge_from_package(pkg)`
devuelve `None` si la propuesta no declara `edge`, y `_score_from_signal()` propaga `None` (el
ranker puntúa 0 el componente ausente). Resultado honesto: sin `memo edge=` y sin `EdgeReport` ⇒
`edge = 0` ⇒ por debajo de `min_edge` ⇒ **NO ENTRY**. El edge deja de ser un supuesto del motor y
pasa a ser un **dato persistido y auditable**: `EdgeReportRow.edge_score` de la versión de
estrategia, leído por `EdgeReportSource` (prioridad `memo edge=` > `EdgeReport` > nada). La liquidez
tampoco se inventa: `None` con `require_liquidity` ⇒ `liquidity_unknown`; el veto preexistente
`<= 0` se mantiene.

**Código:** `packages/py/application/src/bolsa_application/auto_v2_entry.py` (`V2Tunables` sin
`default_edge`, `edge_from_package`, `_score_from_signal`, `EdgeReportSource`) ·
`packages/py/application/src/bolsa_application/portfolio_decision_engine.py` (`liquidity_unknown`,
`PortfolioDecisionConfig.require_liquidity`).
**Test:** `test_auto_v2_entry.py::test_edge_from_package_has_no_default` /
`::test_plan_v2_tick_low_edge_blocks` / `::test_plan_v2_tick_unknown_liquidity_is_rejected` ·
`test_portfolio_decision_engine.py::test_liquidity_unknown_blocks` /
`::test_require_flags_can_be_disabled_explicitly`.

---

## 5. P0-5 · Identidad de señal opcional y deduplicación dependiente del orden

**Afirmación:** sin identidad de señal **no hay entrada**, y el conjunto aprobado de un tick es
**independiente del orden** de las señales de entrada.

**Antes:** `_signal_rejection()` no descartaba una señal sin `signal_id` (la rama permisiva estaba
comentada como tal), y la deduplicación usaba `deduped.setdefault(...)`: con dos señales del mismo
instrumento, el ganador dependía de por cuál se iteraba primero.

**Ahora:** `signal_id` vacío ⇒ `SIGNAL_IDENTITY_MISSING` ⇒ NO ENTRY (y el worker, si el timeframe no
se entiende, produce `signal_id=""`, de modo que un `AUTO_ENGINE_SIM_V2_TIMEFRAME` ilegible es
**fail-closed auditado en journal**, no una vía libre para repetir la señal). La selección usa
`canonical_candidate_key` (`edge` desc → `strategy_version` → `bar_timestamp` → `signal_id` →
`instrument_id`) con `min(...)` por instrumento: la **misma** señal, en cualquier orden, produce el
**mismo** conjunto aprobado. Cuando la propuesta no declara versión, la identidad usa el centinela
explícito `unversioned` (una estrategia que no se identifica sigue sin poder repetir la MISMA señal
sobre la MISMA barra).

**Código:** `packages/py/application/src/bolsa_application/auto_v2_entry.py`
(`_signal_rejection`, `canonical_candidate_key`, `_dedupe_candidates`, `signal_identity_for_bar`).
**Test:** `test_auto_v2_entry.py::test_plan_v2_tick_without_identity_is_rejected` (inverso del
antiguo `..._still_decides`) · `::test_plan_v2_tick_dedupe_is_order_independent` ·
`::test_canonical_candidate_key_prefers_higher_edge` ·
`::test_plan_v2_tick_consumed_signal_of_other_bar_still_decides`.

---

## 6. P0-6 · `EXIT_ONLY` no era absoluto

**Afirmación:** cuando el régimen es exit-only, la posición se liquida **entera**, sin que
`REDUCE`/`TAKE_PROFIT`/trailing puedan quedarse con parte del riesgo.

**Antes:** `manage_position()` sólo forzaba la venta total por régimen si
`order_action == "hold"`: una estrategia que pedía `REDUCE` o un objetivo T1 alcanzado **ganaban**
al exit-only y la posición sobrevivía a un régimen que exigía salir.

**Ahora:** `regime_is_exit_only(regime)` tiene **precedencia absoluta**: fija
`order_action = "sell"` con la cantidad remanente, anula el stop update y registra `REGIME_EXIT`
como motivo, ignorando el resto de vías de decisión.

**Nota de revisión (decisión consciente, no un olvido):** **no** se añade la excepción "salvo
`RECONCILIATION_CRITICAL`" que sugería el informe. El invariante del repo y su test
(`test_v2_recon_status_never_blocks_protective_exit`) exigen que la reconciliación **nunca** bloquee
una salida protectora; bajo reconciliación crítica la salida se emitirá con la cantidad **canónica**
del lector canónico, no con la proyección divergente. Si el auditor prefiere la excepción literal,
el cambio es local (una condición) y arrastra el ajuste de ese test.

**Código:** `packages/py/application/src/bolsa_application/position_manager.py`.
**Test:** `packages/py/application/tests/test_position_manager.py::test_regime_exit_only_overrides_take_profit`
(exige `"target_1" not in result.exit_reasons`) y la batería `test_v2_recon_status_never_blocks_protective_exit`.

---

## 7. P0-7 · AUTO V2 ciego en producción (fuentes reales cableadas)

**Afirmación:** en el camino real de producción, el tick de AUTO 2.0 recibe **régimen, sector, ADV y
edge reales** leídos de la base de datos viva, no valores inyectados por tests.

**Antes:** `AutoSimRuntime` construía el worker **sin** `regime_source` ni `sector_source` (solo los
tests los inyectaban) y **no existía** `liquidity_source`. En producción, por tanto, el régimen era
`UNKNOWN` ⇒ exit-only ⇒ AUTO **nunca abría nada**: el sistema parecía prudente cuando en realidad
estaba ciego.

**Ahora:** el runtime compone los lectores sobre la **misma sesión del tick** y los pasa por
`real_turn(...)`:

- **Régimen:** `DiscoveryRegimeSource` con `bars_provider` (`make_bar_snapshot_loader`) sobre
  `SqlAlchemyOhlcvRepository`; un fallo de lectura deja `NO_REGIME` ⇒ `UNKNOWN` ⇒ exit-only. El
  override `AUTO_ENGINE_SIM_V2_REGIME` conserva la prioridad.
- **Contexto de cartera (sector + liquidez + frescura):** `CatalogTradeContextSource` sobre una
  lectura **nueva y única** del catálogo, `list_trade_context_by_ids(instrument_ids)` →
  `{sector, adv_usd, observed_at}` leyendo `instruments.sector` y
  `profile_snapshot.fundamentals` (`advUsd`, `fetchedAt`). El mapa responde por `id` **y** por
  `symbol` (el worker se keya por símbolo) y **omite** los instrumentos sin fila.
- **Edge:** `EdgeReportSource` sobre `SqlAlchemyCognitiveRepository.latest_edge_report(...)`.

Los `refresh()` son **async y una vez por tick**; el hot path lee de caché **síncrona**, así que
decidir no depende de I/O y un fallo de lectura deja el dato **ausente** (nunca inventado).

**Código:** `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
(`_compose_regime_source`, `_compose_trade_context_source`, `_compose_edge_source`,
`_v2_refresh_trade_context`, `_v2_context`, `_v2_liquidity`, `_v2_edge`, `_v2_sector`,
`_v2_open_sectors`, `AutoSimRuntime.run_tick`, `start_auto_sim_worker`) ·
`packages/py/domain/src/bolsa_domain/repositories/instrument_repository.py`
(`InstrumentTradeContext`, `list_trade_context_by_ids` en el Protocol) ·
`packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/instrument_repository.py`
(implementación en **una** query; dato ausente ⇒ `None`, nunca default).
**Test:** `apps/api-python/tests/test_auto_v2_worker_integration.py` (27 passed: el pipeline abre
con fuentes inyectadas, **no** abre sin ellas y la cascada de vetos
`liquidity_unknown` → `edge_below_threshold` → `sector_unknown` se observa en el journal) ·
`apps/api-python/tests/test_instrument_trade_context_pg.py::test_list_trade_context_by_ids_reports_sector_adv_and_freshness`
(PG real) · `apps/api-python/tests/test_auto_v2_durable_pg.py` (el reinicio real **exige** sector y
ADV frescos sembrados + un `EdgeReport` vigente para poder abrir: si el cableado se rompiera, el
test se pondría rojo por `sector_unknown`/`liquidity_unknown`/`edge_below_threshold`).

---

## 8. Matriz de gates y sus códigos de motivo

| Código de motivo               | Estado que lo dispara                                       | Config que lo activa                 |
| ------------------------------ | ----------------------------------------------------------- | ------------------------------------ |
| `sector_unknown`               | `SectorResolutionStatus = UNKNOWN`                          | `require_sector = True` (default)    |
| `sector_conflicting`           | `memo sector=` ≠ `instruments.sector` (normalizados)        | `require_sector = True`              |
| `sector_stale`                 | `fetchedAt` de fundamentales > `sector_max_age_days`        | `require_sector = True`              |
| `sector_exposure_unverifiable` | Alguna posición abierta con sector no-`KNOWN`               | `require_sector = True`              |
| `liquidity_unknown`            | `LiquidityStatus = UNKNOWN` con gate activo                 | `require_liquidity = True` (default) |
| `correlation_unknown`          | `CorrelationStatus ≠ CALCULATED` con gate activo            | `max_correlation` configurado        |
| `edge_below_threshold`         | `edge` ausente (0) o por debajo de `min_edge`               | `min_edge` de `V2Tunables`           |
| `SIGNAL_IDENTITY_MISSING`      | `signal_id` vacío (p. ej. timeframe ilegible)               | Siempre (fail-closed)                |
| `risk_budget_exceeded`         | Riesgo comprometido acumulado del tick agota el presupuesto | `risk_budget_pct` de `V2Tunables`    |

Todos los códigos están en `_NO_TRADE_REASONS`, se registran en el `DecisionJournalEntryRecord`
(`auto_entry_decision`) y se pueden auditar por tick.

---

## 9. Verificación (evidencia local; CI pendiente de publicación)

Batería **exacta** de los jobs afectados, ejecutada sobre el árbol de esta fase:

| Suite / comando                                                                                                       | Resultado                    |
| --------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `ruff check packages/py apps/api-python --config pyproject.toml`                                                      | **All checks passed**        |
| `mypy domain/market/infrastructure/application/apps-api-python --follow-imports=silent`                               | **0 errores** (482 ficheros) |
| `lint-imports --config packages/py/.importlinter`                                                                     | **4/4 contratos KEPT**       |
| Batería exacta del job `quality` de `python-ci.yml` (lista literal del workflow)                                      | **1616 passed**              |
| `packages/py/application/tests` + `packages/py/analytics/tests` + `packages/py/domain/tests`                          | **2347 passed**              |
| Job `auto-v2-durable-pg` (`AUTO_V2_DURABLE_PG_REQUIRED=1` + `INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED=1`, PG real, `-rs`) | **21 passed**                |
| `apps/api-python/tests/test_auto_v2_worker_integration.py`                                                            | **27 passed**                |

Nota de honestidad sobre el formateador: `ruff format --check` **no** es un gate de este repo (CI
sólo ejecuta `ruff check`) y el árbol tiene drift de formato **preexistente** con la versión de ruff
instalada; esta fase **no** reformatea ficheros ajenos para no inflar el diff. Lo que sí se
certifica es que `ruff check` (el comando del workflow) pasa sin incidencias.

**Verificación por mutación sugerida al auditor** (no se reclama como ejecutada): revertir
`_working_snapshot` (volver a `replace(snapshot, positions=...)`) debe poner rojo
`test_plan_v2_tick_reserves_risk_intra_tick`; reintroducir el fallback de `edge_from_package` debe
poner rojo `test_edge_from_package_has_no_default`; devolver la rama permisiva de
`_signal_rejection` debe poner rojo `test_plan_v2_tick_without_identity_is_rejected`; devolver la
condición `order_action == "hold"` en `position_manager` debe poner rojo
`test_regime_exit_only_overrides_take_profit`; vaciar `_v2_open_sectors` debe poner rojo
`test_plan_v2_tick_open_position_without_sector_blocks_new_entries`.

**En CI:** `test_instrument_trade_context_pg.py` se añade al job `auto-v2-durable-pg` de
`python-ci.yml` (PostgreSQL service + `INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED=1` + paso
_fail-if-skipped_ ya existente) y al job de certificación de `release-tag-ci.yml`; en el job
`quality` (sin PostgreSQL) queda **explícitamente ignorado**, como el resto de las suites
PG-gated, para que **no** pueda skipear en mudo dentro de la certificación.

---

## 10. Fuera de alcance (anotado, no tocado)

- **No** se toca el settlement, el ledger, la idempotencia por fill, el `RiskGate` ni la
  reconciliación.
- **No** se activa ninguna feature por defecto: `AUTO_ENGINE_SIM_V2` sigue **OFF**.
- **No** se aborda el `PortfolioReservation` **transaccional** completo (la reserva de esta fase es
  intra-tick, en memoria, dentro del tick; no un motor transaccional con persistencia).
- **No** se implementan `ProtectionPlan`/`ProtectionInstruction` durables, governor de
  drawdown/volatilidad, Portfolio Optimizer, Golden Day PG, NO TRADE Engine con outcome, **fuente
  real de correlación** (el gate sigue siendo fail-closed por estado, pero el dato lo aporta el
  llamante) ni la calibración del `OpportunityRanker`. Todo ello queda para V2.41.
- **No** se cambia ninguna firma HTTP ni DTO compartido ⇒ sin regeneración de OpenAPI.

---

## 11. Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada P0** de §1–§7,
con evidencia `archivo:línea`, y delta real `v2.40-beta` → `v2.40.1-beta`. Marca explícitamente lo
que **no** puedas verificar desde GitHub y requiera entorno local (en particular: las suites con
PostgreSQL y las verificaciones **por mutación** de §9).
