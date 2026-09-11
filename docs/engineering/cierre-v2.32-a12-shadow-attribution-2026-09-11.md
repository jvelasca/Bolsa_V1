# Cierre V2.32 / A12 — Shadow Validation & Autonomous Attribution (2026-09-11)

Version: `v2.32-beta`. Alcance: **los dos P2 diferidos a V2.32 por la auditoría V2.31**
(§6 de `cierre-v2.31-a11-discovery-engine-2026-09-10.md`).

1. **Shadow real**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` certificaba un **flag humano**,
   no una ejecución. No existía entidad, tabla ni cálculo de evidencia shadow.
2. **Atribución tras crash**: `strategy_version_id` solo vivía en
   `sim_fill_finance_context`; tras `readopt` los cierres de posiciones readoptadas
   quedaban con `NULL` y salían de las métricas observadas de la vigilancia.

`LIVE` permanece **congelado** en todo momento: no se toca `LIVE_EXECUTION_AUTHORIZED`
ni `LIVE_EXECUTION_UNLOCKED`, ni se añade ningún camino LIVE.

---

## 1. Pipeline (antes → después)

```
ANTES
  FINALISTA ──▶ VALIDACION(gates) ──▶ PROMOCION ──▶ ACTIVE
                       ▲
                       └── AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1 (flag humano, sin ejecución)

  crash ──▶ readopt posición (qty/entry/high-watermark) ──▶ cierre con strategy_version_id = NULL

DESPUÉS
  FINALISTA ──▶ SHADOW REPLAY (sobre barras reales, ventana separada del LAB)
            ──▶ ShadowValidationResult (trades/retorno/drawdown/win-rate) ──▶ PROMOCION
            ──▶ ACTIVE (enlazada a la evidencia: shadow_validation_id)

  crash ──▶ readopt posición + strategy_version_id (migración 033) ──▶ cierre ATRIBUIDO
```

---

## 2. Dominio — evidencia shadow (puro)

`packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`

- `ShadowValidationResult`: `version_id`, `trades`, `passed`, `reasons`, `instrument_id`,
  `return_pct`, `max_drawdown_pct`, `win_rate`, `bars_used`, `as_of`.
- `ShadowPolicy`: umbrales deterministas (`min_trades`, `min_return_pct`,
  `max_drawdown_pct`) con `evaluate(...) -> ShadowValidationResult`. `min_trades` es la
  guarda de muestra; el retorno es MÍNIMO y el drawdown es TECHO.
- `evaluate_promotion(...)`: la autoridad es `shadow: ShadowValidationResult | None`. El
  booleano `shadow_validated` se conserva como **override explícito del operador**
  (`None` por defecto ⇒ manda la evidencia). Sin evidencia que pase ⇒
  `shadow_validation_requerida`.
- `can_transition(..., shadow=...)`: en `VALIDACION` exige evidencia (`shadow.passed`).
- `StrategyPromotion` gana `shadow_validation_id` (enlace auditable); `ActiveStrategy`
  gana `shadow_validated`/`shadow_validation_id`.

## 3. Aplicación — motor de shadow replay

Nuevo `packages/py/application/src/bolsa_application/strategy_shadow_phase.py`:

- `run_shadow_replay(finalist, bars, policy, config, as_of)`: replay **determinista** de
  la definición ejecutable del finalista con el motor real de reglas
  (`evaluate_rules_signals`, modo `gated`, causalidad `index-1 → open(index)`, sin
  look-ahead), reutilizando la contabilidad de `rules_grid._simulate_rules_strategy`.
- `extract_executable(finalist)`: definición `definition["executable"]`; los finalistas H0
  sin ella no producen evidencia.
- Fail-closed: sin definición, sin barras suficientes o sin operaciones ⇒ `passed=False`
  con motivo explícito (`shadow_sin_definicion_ejecutable`,
  `shadow_barras_insuficientes`, `shadow_replay_fallido`). **Nunca lanza**: un fallo del
  replay es no-evidencia, no una excepción que rompa el ciclo.

## 4. Orquestador — Promotion Gate con evidencia

`packages/py/application/src/bolsa_application/auto_orchestrator.py`

- `OrchestratorDeps` gana `shadow_bars: ShadowBarsProvider | None`, `shadow_policy`,
  `shadow_config` y `shadow_override: bool | None`.
- `run_cycle` inserta la fase **SHADOW** entre `save_finalist` y `decide_promotion`:
  lee las barras del instrumento, ejecuta `run_shadow_replay`, persiste el resultado
  (`store.save_shadow_result`) y lo pasa a `decide_promotion(shadow=...)`.
- Sin `shadow_bars` no hay evidencia ⇒ queda fail-closed (no promociona).
- `strategy_promotion_phase.decide_promotion` propaga `shadow` y `shadow_override`.

Composition root (`apps/api-python/.../auto_orchestrator_worker.py`):

- `shadow_bars` se cablea desde el repositorio OHLCV real (una sesión por llamada;
  un fallo de lectura devuelve vacío ⇒ sin evidencia).
- `AUTO_ORCHESTRATOR_SHADOW_VALIDATED` **deja de ser la autoridad** y pasa a
  `shadow_override` explícito (solo si el operador lo fija; queda auditado como
  `shadow_override_operador`). Nuevo `AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS` (default 250).

## 5. Persistencia — evidencia y atribución

- **Migración `032_shadow_validation`**: tabla `strategy_shadow_validations` + columna
  `strategy_promotions.shadow_validation_id` (nullable). `StrategyShadowValidationRow`;
  `save_shadow_result`/`list_shadow_results` en el `LifecycleStorePort` (PG + InMemory).
- **`save_active` corregido**: la fila-localizador de la ACTIVE ya **no** escribe
  `shadow_validated=True` sin evidencia; propaga la evidencia real
  (`active.shadow_validated`/`shadow_validation_id`).
- **Migración `033_position_strategy_attr`**: `sim_auto_positions.strategy_version_id` y
  `ledger_entries.strategy_version_id` (nullable, con índices).
- `sim_durable_store.py`: `SimPositionProjection` y `PostgresSimAutoPositionStore.upsert`
  propagan/restauran la versión; `rebuild_sim_position_projection` la conserva.
- `auto_simulation_worker.py`: `_persist_position` escribe `_position_version[symbol]` en
  el espejo; `readopt_positions` lo **restaura** ⇒ los cierres post-crash vuelven a
  atribuirse.
- **Ledger**: `ExecuteTrade.execute(..., strategy_version_id=...)` (aditivo) estampa la
  versión en `append_trade`/`append_fee`; el applier SIM la propaga desde
  `SimulatedFillFinance`. La atribución deja de depender en exclusiva de
  `sim_fill_finance_context`. No toca importes, balances ni idempotencia.

## 6. Test E2E de certificación A11 (PG)

Nuevo `apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py`:

```
ESTUDIO → DISCOVERY → LAB → TOP3 → COACH → FINALISTA → SHADOW
        → PROMOTION → ACTIVE → SIGNAL → SIM BUY → FILL → LEDGER → VIGILANCE
```

- Con discovery real en el orquestador, LAB real sobre PG (migración → head **033**).
- Asserts: >1 candidata; evidencia shadow persistida (`trades > 0`); promoción con
  `shadow_validation_id` enlazado; fill SIM atribuido a la versión; readopt conserva
  `_position_version`; snapshot de vigilancia por versión; **LIVE bridge posts = 0**.
- Caso negativo: sin `shadow_bars` ⇒ `no_promocionada` con `shadow_validation_requerida`.
- Gate de honestidad: `AUTO_ORCHESTRATOR_PG_REQUIRED=1` ⇒ un skip es fallo duro.

## 7. CI

- `.github/workflows/release-tag-ci.yml`:
  - job `lifecycle-pg`: añade `test_a11_discovery_to_auto_sim_pg.py` con
    `AUTO_ORCHESTRATOR_PG_REQUIRED=1` (ya presente).
  - job `python`: añade `test_strategy_shadow_phase.py` y los tests de discovery
    (asimetría detectada en V2.31: el job diario no los listaba) + `--ignore` del E2E PG.
- `.github/workflows/python-ci.yml`: replica discovery + shadow (misma simetría).

## 8. Invariantes que NO se tocan

- `AUTO ⇒ SIMULATED`; LIVE bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). Cero caminos LIVE nuevos.
- COACH sigue advisory; RiskGate / SimulationGate / Ledger / Reconciliation
  deterministas.
- Sin LLM en el hot path. Long-only intacto.
- Fail-closed: sin evidencia shadow ⇒ no promoción; sin atribución ⇒ no se inventa versión.

## 9. Verificación

- `uv run ruff check packages/py apps/api-python --config pyproject.toml` → limpio.
- `uv run lint-imports --config packages/py/.importlinter` → **4 contratos KEPT**.
- `uv run mypy packages/py/{domain,infrastructure,application}/src apps/api-python/src`
  → Success, sin issues.
- Tests nuevos: `test_strategy_shadow_phase.py` (6, puro) + dominio shadow en
  `test_strategy_lifecycle.py` (5) → verdes.
- `test_a11_discovery_to_auto_sim_pg.py` contra Postgres local (`ensure_migrated()` a
  head 033) — job `lifecycle-pg` del tag.
- Migraciones `032`/`033` aditivas/nullable con `downgrade()` completo.

---

## 10. Por qué esto cierra los dos P2

Antes: la promoción se autorizaba con un booleano humano y la atribución de la serie
observada se truncaba en cada crash. Ahora: la promoción exige **evidencia ejecutada y
persistida** (contable y auditable, reproducible) y la atribución de la versión
**sobrevive al crash** en la proyección durable y en el ledger. El sistema sigue
SIM-only, con LIVE intacto.
