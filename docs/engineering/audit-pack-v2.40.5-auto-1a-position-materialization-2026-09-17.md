# Audit pack — V2.40.5 / AUTO-1A · Position Materialization & Partial-Fill Integrity (`1.65.5-beta`)

> **Ámbito:** la posición del AUTO deja de ser la **cantidad pedida** y pasa a ser **Σ fills `APPLIED`**
> (`POSITION = Σ APPLIED BUY − Σ APPLIED SELL`), el exit se dimensiona contra la posición **materializada**
> (invariante duro `applied_qty <= held`), la cola de un llenado parcial queda como **capital pendiente**
> (nunca como posición ni como realizado), la autoridad canónica tras un reinicio se **reconstruye** desde
> el ledger `APPLIED`, y ningún skip de gestión de posición vuelve a ser un `continue` mudo.
> **Bump:** `1.65.4-beta` → `1.65.5-beta`. **Alembic head:** `041_unique_natural_keys` (**sin migración**).
> **Estado:** implementado y verificado en local; **sellado con CI real de GitHub**. Commit de fase
> `d15f0a18` (26 ficheros, `+3538/−120`), tag anotado **`v2.40.5-beta` → `d15f0a18`**. El commit
> **docs-only** de cierre que estás leyendo es posterior y **no** entra en el tag.
> **CI medida en esta sesión:**
> `Python CI` **GREEN** en `main` run [`35194186488`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194186488)
> (5/5: `quality`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`) y
> `Release-tag CI` **GREEN** en el tag run [`35194658271`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194658271)
> (10 jobs requeridos + `certify (aggregate + artifact)`; `playwright (integrated E2E)` `skipped` por ser opt-in).
>
> Plan de implementación: [`plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md`](./plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md).
> Relevo de continuidad (arranque del siguiente agente): [`traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md`](./traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md).
> Roadmap por fases: [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).

---

## 1. Punto de partida verificado (no se re-audita)

- El AUTO contabilizaba la cantidad **pedida**: `_settle` descartaba los outcomes del `apply`
  (`result, _out = ...`) y devolvía **todas** las `FillObservation`, incluidas las `RETRY`, así que
  `_record_applied_event` las daba por aplicadas.
- `simulated_fill_schedule` puede dejar una orden **parcialmente llena** (la cola queda en `RETRY`,
  **dinero NO movido**): lo pedido, lo llenado y lo materializado son **tres números distintos**.
- Consecuencias medidas en el plan: posición inflada/deflactada frente a Σ `APPLIED`; un `SELL` podía
  exceder la posición real (pedir 100 sobre una posición real de 73,5); `_v2_known_fill_ids` derivaba
  de los "aplicados" ⇒ los `RETRY` entraban como **conocidos** y **desaparecían del libro de pendientes**
  (`reserved_cash` mentía).
- El **«flake»** del scheduler (`test_auto_scheduler_real_pg_zero_human_intervention.py`, declarado en
  `V2.40.4` con «criterio: re-ejecutar el job») **no era del test**: el helper de equity sumaba **todas**
  las filas de `sim_fill_finance_context`, que se persisten **antes** de mover dinero ⇒
  `equity != initial + realized + unrealized` de forma intermitente según si el tick dejaba cola. Era el
  test **detectando** un bug de dinero. **Cerrado por este slice** (30/30 con PG real, §7.2).
- Invariante que **no** puede regresar: _la reconciliación puede vetar aperturas, nunca una salida
  protectora_; y una fila **no interpretable no se descarta en silencio** (baja el `measurement`).

---

## 2. Matriz afirmación → código → test

### a) `PositionLedger` — read-model puro

| Afirmación                                                                       | Código                                                            | Test                                                  |
| -------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------- |
| La posición es Σ fills `APPLIED` con orden canónico `(applied_at, execution_id)` | `bolsa_analytics.cognitive.position_ledger.build_position_ledger` | `packages/py/analytics/tests/test_position_ledger.py` |
| Una **sobreventa aplicada** es violación explícita, nunca un corto inventado     | `oversell_above_position` / `oversell_without_position`           | idem (`violations`)                                   |
| Una fila no interpretable **no** se descarta en silencio                         | `MeasurementStatus` `COMPLETE`/`PARTIAL`/`UNKNOWN`                | idem                                                  |
| El libro es determinista ante cualquier orden de entrada                         | orden canónico + agregación pura                                  | idem                                                  |

### b) Lectura de fills `APPLIED` (application)

| Afirmación                                                              | Código                                                                     | Test                                                    |
| ----------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------- |
| El ledger se lee por estado, no por posición pedida                     | `ExecutionEventStore.list_applied` (protocolo + in-memory + PG)            | `packages/py/application/tests/test_execution_event.py` |
| El contexto financiero se lee en **batch** (sin N+1)                    | `SimFillFinanceContextStore.get_many`                                      | `test_sim_durable_unit_of_work.py`, idem                |
| La lectura **declara sus huecos** en vez de devolver un libro plausible | `read_applied_fill_facts` (sin store / excepción / sin contexto / `limit`) | `packages/py/application/tests/test_applied_fills.py`   |
| La autoridad de posición transporta las trazas que la sustentan         | `CanonicalPositions` (mismo contrato `dict` del seam del worker)           | idem                                                    |

### c) Contabilidad del worker (el P0)

| Afirmación                                                                   | Código                                                                           | Test                                                                                   |
| ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `_settle` separa **aplicado** de **no aplicado** y declara la pedida         | `auto_simulation_worker._Settlement(applied, unapplied, requested_qty)`          | `apps/api-python/tests/test_auto_v2_partial_fills.py`                                  |
| El camino sin `finance_applier` es **structural** (no hay dinero que mover)  | modo `structural` de `_Settlement`                                               | idem                                                                                   |
| La posición, la persistencia, `PositionState` y los emits usan `applied_qty` | `auto_turn`                                                                      | idem                                                                                   |
| El emit `order` conserva la cantidad **pedida** (lo pedido es auditable)     | `auto_turn` (emits)                                                              | idem                                                                                   |
| La cola queda como **capital reservado**, visible en el libro de pendientes  | journal `fill_not_materialized`, `fill_partially_materialized`, `fill_unapplied` | `test_auto_v2_partial_fills.py`, `test_auto_investment_system.py`                      |
| El exit **nunca** excede la posición materializada                           | clamp `applied_qty <= held` ⇒ journal `exit_qty_over_position`                   | `test_protective_exit_never_exceeds_the_applied_position` (medido por mutación, §3 M4) |

### d) Autoridad canónica = ledger

| Afirmación                                                                    | Código                        | Test                                                                                                             |
| ----------------------------------------------------------------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Tras un reinicio con RAM vacía, la autoridad se reconstruye desde Σ `APPLIED` | `_compose_canonical_reader`   | `test_auto_scheduler_real_pg_zero_human_intervention.py` (PG real), `test_a9_scheduler_process_pg_zero_human.py` |
| Una proyección **inflada** se reescribe a la materializada                    | journal `REBUILT`             | idem                                                                                                             |
| Libro ilegible ⇒ `None` ⇒ aperturas vetadas y **salidas permitidas**          | `POSITION_PROJECTION_UNKNOWN` | idem                                                                                                             |

### e) Observabilidad de los skips de gestión (AUDITORIA 2)

| Afirmación                                                              | Código                                                       | Test                                                     |
| ----------------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| Ningún skip de gestión queda mudo                                       | `manage_position_outcome` → `PositionManagerSkip`            | `packages/py/application/tests/test_position_manager.py` |
| Los casos benignos siguen siendo `None` y `manage_position` no cambia   | contrato antiguo preservado (retrocompatible)                | idem                                                     |
| `no_mark_data`, `mark_rejected` y `decision_unavailable` se journalizan | `run_auto_cycle` ⇒ `auto_position_skip` (`attention="high"`) | `test_auto_investment_system.py`                         |
| El motivo se propaga al worker                                          | `_v2_last_exit_reasons[symbol]`                              | `test_auto_simulation_worker.py`                         |

### f) Red de seguridad de CI

| Afirmación                                                       | Código                                                            | Evidencia                                                                 |
| ---------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Un test nuevo **no entra solo**: se cablea con nombre propio     | `quality` (`python-ci.yml`) y job `python` (`release-tag-ci.yml`) | `test_applied_fills.py` en ambos (§7.1)                                   |
| Los comentarios nuevos van **fuera** del bloque plegado `run: >` | workflows                                                         | lección sellada en `v2.40.2` (un `#` dentro se come el resto del comando) |

---

## 3. Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite y se revirtió (no se declara
ninguna sin medir):

| #   | Mutación                                                   | Efecto medido                                                                                                                                                                          |
| --- | ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `applied_qty = exec_qty` (volver a la cantidad **pedida**) | **6 rojos** en `apps/api-python/tests/test_auto_v2_partial_fills.py`                                                                                                                   |
| M2  | `_record_applied_event` también con `settlement.unapplied` | **1 rojo** (la cola `RETRY` desaparece del libro de pendientes)                                                                                                                        |
| M3  | Quitar el filtro `APPLIED` del helper de equity            | **1 rojo determinista** (`test_equity_realized_ignores_unapplied_fill_context`); en el bucle 30× de la jornada **no** se detecta (0/30) ⇒ el instrumento determinista es **necesario** |
| M4  | Quitar el clamp `applied_qty <= held`                      | **1 rojo** (`test_protective_exit_never_exceeds_the_applied_position`)                                                                                                                 |
| M5a | `manage_position_outcome` vuelve a `None` en los skips     | **2 rojos** (`test_manage_position_outcome_declares_rejected_mark`, `…_declares_decision_unavailable`)                                                                                 |

**Sin mutación**: las mismas suites quedan verdes (la batería del §7.2 es la referencia).

---

## 4. Cambios observables y deuda declarada

1. **Journal (códigos nuevos)**: `fill_not_materialized`, `fill_partially_materialized`,
   `fill_unapplied`, `exit_qty_over_position`, `auto_position_skip` (con `no_mark_data`,
   `mark_rejected`, `decision_unavailable`). `report.fills` pasa a contar **fills aplicados**.
2. **`manage_position_outcome`** devuelve `PositionManagerResult | PositionManagerSkip | None`.
   `manage_position` conserva el contrato antiguo ⇒ retrocompatible. **Breaking en beta: ninguno de API
   pública relevante.**
3. **Posición**: la autoridad publicada (y persistida) es la materializada. Un consumidor que leyera la
   cantidad pedida como posición deja de tener razón por diseño.
4. **Deuda declarada, no silenciosa**: la cola no llena queda como **capital en `RETRY`** y su
   liberación explícita es **`AUTO-1`** (Portfolio Reservation Engine); **sin índice parcial**
   `execution_events(account_id, status)` (lectura acotada por `limit`, migración asignada a `AUTO-1`);
   el `PositionLedger` es **read-model** sin tabla propia.

---

## 5. Límites declarados (lo que este slice NO resuelve)

1. **La liberación de la cola `RETRY` no es explícita**: se reconoce como capital reservado, pero no
   existe todavía un ledger de reservas con `release`/`rollback`/`replay`. Eso es `AUTO-1`.
2. **Sin índice parcial** `execution_events(account_id, status)`: el libro de pendientes se acota con
   `LIMIT` + `ORDER BY`. Migración asignada a `AUTO-1`.
3. **`PositionLedger` no persiste**: es un read-model que se reconstruye desde `execution_events` +
   `sim_fill_finance_context`. No hay tabla de posición materializada.
4. **El `limit` de `list_applied`** es un suelo: agotarlo baja el `measurement` (no se publica un libro
   plausible), pero no se ha medido aún la jornada real más larga (pregunta abierta para el auditor).
5. **`CanonicalPositions` es la autoridad del worker**, no necesariamente la de **todos** los
   consumidores de posición (riesgo, exposición, sizing): el barrido de esos consumidores es una
   pregunta abierta declarada, no una afirmación de este pack.
6. **El antiguo «flake» del scheduler ya no se declara flake**: era el síntoma del bug de contabilidad que
   este slice cierra. Con la corrección, el bucle 30× con PG real da **0 fallos** (§7.2). La frase
   «criterio: re-ejecutar el job» de `PROJECT_STATE` (entrada `V2.40.4`) queda **corregida** en el commit
   docs-only de este sellado.

---

## 6. Cómo reproducir la verificación

```bash
# 1) Estático (invocación EXACTA de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
               packages/py/application/tests/test_applied_fills.py \
               packages/py/application/tests/test_execution_event.py \
               packages/py/application/tests/test_position_manager.py \
               packages/py/application/tests/test_simulated_settlement.py \
               packages/py/application/tests/test_auto_investment_system.py -q

# 3) Camino del worker (hermético, sin PG)
uv run pytest apps/api-python/tests/test_auto_v2_worker_integration.py \
               apps/api-python/tests/test_auto_v2_partial_fills.py \
               apps/api-python/tests/test_a9_1_crash_battery.py \
               apps/api-python/tests/test_auto_simulation_worker.py -q

# 4) Offline del job `quality` (usa EXACTAMENTE su lista y sus --ignore, extraída del YAML)
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"

# 5) PG real (certificación)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q
```

---

## 7. Evidencia de verificación

### 7.1 CI real de GitHub (medida en esta sesión con `gh`)

| Gate                                              | Run                                                                            | Resultado                                                                                                                                                                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Python CI` (push a `main`, `d15f0a18`)           | [`35194186488`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194186488) | **GREEN 5/5**: `quality`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`                                                                                                    |
| `Python CI` (push del tag, `d15f0a18`)            | [`35194658317`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194658317) | **GREEN 5/5** (misma batería)                                                                                                                                                                                 |
| `Release tag CI` (tag `v2.40.5-beta`, `d15f0a18`) | [`35194658271`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194658271) | **GREEN**: `security`, `shared`, `decision-spine`, `frontend`, `python`, `playwright (mock)`, `lifecycle-pg`, `dr-verify`, `a7-gate` + `certify`; `playwright (integrated E2E)` `skipped` (opt-in por diseño) |

**El commit de sellado NO entra en el tag y NO re-dispara `Python CI`.** El tag apunta a `d15f0a18`, el
commit **verde**; el commit docs-only de cierre toca solo `CHANGELOG.md`, `docs/**` y
`docs/engineering/**`, rutas que **no** están en el `paths` de `Python CI`, así que ese push no lanza
`Python CI` (solo `Gitleaks`). Patrón del repo: el **código y su evidencia CI** van en el tag; la
**guía de lectura** va en el tip de `main`.

### 7.2 Baterías locales (medidas en el árbol final del slice, antes de publicar)

| Batería                                                                                     | Resultado                                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ruff check packages/py apps/api-python --config pyproject.toml` (invocación de CI)         | `All checks passed!`                                                                                                                                                                                                     |
| `mypy … --follow-imports=silent`                                                            | **485 ficheros, 0 issues**                                                                                                                                                                                               |
| `lint-imports --config packages/py/.importlinter`                                           | **4 kept / 0 broken**                                                                                                                                                                                                    |
| Paquetes (gate del plan)                                                                    | **80 passed** (`test_execution_event`, `test_position_manager`, `test_simulated_settlement`, `test_position_ledger`, `test_applied_fills`, `test_auto_investment_system`)                                                |
| App (gate del plan)                                                                         | **54 passed** (`test_auto_v2_worker_integration`, `test_auto_v2_partial_fills`, `test_a9_1_crash_battery`, `test_auto_simulation_worker`)                                                                                |
| Suite completa de paquetes (`pytest packages/py`)                                           | **2729 passed**, 1 skipped, 1 xfailed (241 s)                                                                                                                                                                            |
| `AUTO_V2_DURABLE_PG_REQUIRED=1 … test_auto_v2_durable_pg.py`                                | **2 passed**                                                                                                                                                                                                             |
| `AUTO_SCHEDULER_PG_REQUIRED=1 … test_auto_scheduler_real_pg_zero_human_intervention.py` ×30 | **0 fallos** (2 tests por ejecución ⇒ 60 en verde) ⇒ el «flake» queda **cerrado**                                                                                                                                        |
| `AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 … test_a9_scheduler_process_pg_zero_human.py`         | **2 passed** (30,7 s)                                                                                                                                                                                                    |
| Barrido amplio de la app (sin `chaos`)                                                      | **477 passed**, 3 rojos **ajenos** (§3 del relevo: `integration/test_tax_report` 403, flake `chaos/live_a7`, `test_simulated_finance_pg`/`test_workspaces` sensibles al orden; los `--ignore` de `quality` los excluyen) |
| **Job `quality` completo** (comando **extraído del YAML**, con la lista nueva)              | **exit 0** (87 s), **0 rojos**                                                                                                                                                                                           |

**Lo que este pack afirma:** las cifras anteriores, medidas en local sobre el árbol del slice, y los tres
runs de CI de GitHub identificados por su `run id`. **Lo que NO afirma:** nada sobre un tag no
publicado; no hay en esta fase ninguna afirmación de CI que no corresponda a `d15f0a18`.
