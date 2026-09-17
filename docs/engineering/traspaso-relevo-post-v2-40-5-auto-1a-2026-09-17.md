# RELEVO — post V2.40.5/AUTO-1A · Position Materialization & Partial-Fill Integrity — 2026-09-17

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume
> **cero contexto previo** más allá de lo que aquí se dice. Léelo entero antes de tocar nada.
> Respeta el estilo del repo: español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-17 · **Base:** `main` · HEAD local **`d7b77da3`** (sellado docs-only de
> `v2.40.4-beta`) · **precedente de versión:** tag `v2.40.4-beta` → `1127d010`.
> **Alembic head:** `041_unique_natural_keys` (**SIN migración nueva** en AUTO-1A).
> **Veredicto:** AUTO-1A **IMPLEMENTADO y VERIFICADO en local**; **pendiente** de commit de fase,
> push, tag anotado `v2.40.5-beta`, CI del tag y cierre documental (los ejecuta el
> coordinador/propietario). El árbol está **sin commitear**: **17 modificados + 9 nuevos = 26
> entradas** (§2.3), sin ruido (ni `logs/`, ni caches, ni `__pycache__/`).
>
> Origen de la fase: las **dos auditorías** de `v2.40.4-beta` (AUDITORIA 1 y AUDITORIA 2) señalaron
> el **P0** de contabilidad de posición; el [plan](./plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md)
> es el contrato implementado aquí y su **§8 es el arranque del auditor**.

---

## 0. Estado en una frase

La posición del AUTO **deja de ser la cantidad pedida** y pasa a ser **Σ fills `APPLIED`**
(`POSITION = Σ APPLIED BUY − Σ APPLIED SELL`), el exit se dimensiona contra la posición
**materializada** con invariante duro (`applied_qty <= held`), la cola de un llenado parcial queda
como **capital pendiente** (nunca como posición ni como realizado), la autoridad canónica tras un
reinicio se **reconstruye** desde el ledger `APPLIED`, y ningún skip de gestión de posición vuelve a
ser un `continue` mudo. El **flake del scheduler** que la auditoría midió **no era del test**: era un
bug de contabilidad real, y queda cerrado (30/30 con PG real).

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa personal (IBEX/Europa). Relevante para esta continuación:

- `packages/py/domain` — dominio puro.
- `packages/py/application` — casos de uso: orquestador del ciclo de estrategia, stores durables,
  ejecución/ledger, y toda la cadena **AUTO 2.0** (snapshot → ranker → decider → allocator →
  position manager).
- `packages/py/analytics` — motor determinista (reglas, backtest, indicadores) y el módulo
  `cognitive/` (estados/mediciones puras: `measurement`, `open_order`, **y ahora `position_ledger`**).
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL).
- `apps/api-python` — API, **workers de fondo AUTO** y los E2E de certificación con PG real.

### 1.2 La cadena que importa aquí

```
tick AUTO (auto_simulation_worker.auto_turn)
  → decide (TradePlan) → orden (venue_order_id + revenue namespaced)
  → SIM settlement: simulated_fill_schedule(...)  ← puede cortar ANTES del último chunk
      → sim_fill_finance_context (se persiste para TODOS los fills PLANIFICADOS, ANTES de mover dinero)
      → apply_finance(...) → execution_events.status = APPLIED | RETRY | FAILED | ...
  → contabilidad de posición (AQUÍ estaba el P0)
  → persistencia (positions / sim_auto_position / _v2_durable_plans)
  → gestión de posición (PositionManager: T1/T2/stop/trailing)
  → re-arranque: reconciliación contra la autoridad canónica
```

Puntos de anclaje reales (rutas exactas):

- **Worker AUTO (el foco del P0)**: `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  — `auto_turn`, `_settle` (~L872), `_Settlement` (~L385), `_record_applied_event`,
  `_compose_canonical_reader` (~L2192), `_reconcile_before_trusting`, `_v2_position_package`.
- **Ledger de posición (nuevo)**: `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py`
  (`AppliedFillFact`, `LedgerPosition`, `build_position_ledger`).
- **Lectura de fills aplicados (nuevo)**: `packages/py/application/src/bolsa_application/applied_fills.py`
  (`read_applied_fill_facts`, `CanonicalPositions`).
- **Stores ampliados**: `packages/py/application/src/bolsa_application/execution_event.py`
  (`list_applied`), `sim_durable_store.py` (`SimFillFinanceContextStore.get_many`).
- **Gestión de posición**: `packages/py/application/src/bolsa_application/position_manager.py`
  (`manage_position_outcome`, `PositionManagerSkip`); orquestación del ciclo en
  `auto_investment_system.py` (`run_auto_cycle`).
- **Reason codes (dueño único)**: `packages/py/application/src/bolsa_application/auto_reason_codes.py`.
- **Settlement del simulador**: `packages/py/application/src/bolsa_application/simulated_settlement.py`
  (`persist_fill_finance_context`), `simulated_broker.py` (`simulated_fill_schedule`).
- **Suites PG de la jornada completa**: `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`
  y `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` + helper compartido nuevo
  `apps/api-python/tests/applied_fill_equity.py`.

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  false). **Cero caminos LIVE nuevos.**
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación; libro no legible ⇒ aperturas vetadas y
  **salidas protectoras SIEMPRE permitidas**.
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo. **AUTO-1A no añade
  ninguna**: head sigue en `041_unique_natural_keys`.
- Long-only intacto. `PAPER_D_EXECUTE` off por defecto.
- **No editar** el fichero de plan de Cursor
  (`auto-1a_position_materialization_d314c0b6.plan.md`).

---

## 2. Qué se acaba de hacer (V2.40.5/AUTO-1A)

### 2.1 Causa raíz (lo pedido ≠ lo llenado ≠ lo materializado)

`simulated_fill_schedule` puede dejar una orden **parcialmente llena** (la cola queda en `RETRY`,
**dinero NO movido**), pero el worker contabilizaba la cantidad **pedida**:

- `_settle` descartaba los outcomes del apply (`result, _out = ...`) ⇒ devolvía **todas** las
  `FillObservation`, incluidas las `RETRY`, y `_record_applied_event` las daba por aplicadas.
- Consecuencia 1: `_open` / `_persist_position` / `_v2_track_entry` / `_v2_track_reduce` /
  `PositionState` (T1/stop/trailing) usaban la pedida ⇒ **posición inflada** (o deflactada) frente a
  Σ `APPLIED`.
- Consecuencia 2: el exit se clampaba contra `_open` inflado ⇒ un `SELL` podía exceder la posición
  real (medido en el plan: pedir 100 sobre una posición real de 73,5).
- Consecuencia 3: `_v2_known_fill_ids` derivaba de los "aplicados" ⇒ los `RETRY` entraban como
  **conocidos** y **desaparecían del libro de órdenes pendientes** (`reserved_cash` mentía).
- Consecuencia 4 (el **flake**): el helper de equity de las suites PG sumaba **todas** las filas de
  `sim_fill_finance_context`, que se persisten **antes** de mover dinero ⇒
  `equity != initial + realized + unrealized` de forma **intermitente**, según si el tick dejó cola.
  No era un test inestable: era el test **detectando** un bug de dinero.

### 2.2 Cambios, por pieza

**a) `PositionLedger` — read-model puro (`bolsa_analytics.cognitive.position_ledger`)**
`AppliedFillFact` (fila `APPLIED` con contexto legible), `LedgerPosition` (`quantity`, `realized_qty`,
`remaining_qty`, `average_entry`, `realized_pnl`, `violations`), `build_position_ledger(facts, rejected=…)`
con orden canónico `(applied_at, execution_id)`. Reglas de honestidad: **sobreventa aplicada** ⇒
violación explícita (`oversell_above_position` / `oversell_without_position`) y **nunca** un corto
inventado; una fila **no interpretable no se descarta en silencio**, baja el `measurement`
(`COMPLETE`/`PARTIAL`/`UNKNOWN`) — "no pude leer el libro" jamás se confunde con "el libro está plano".

**b) Lectura de fills `APPLIED` (application)**
`ExecutionEventStore.list_applied(account_id, *, limit)` (protocolo + in-memory + PG:
`WHERE status='APPLIED' ORDER BY applied_at, execution_id`) y `SimFillFinanceContextStore.get_many`
(batch, sin N+1). `read_applied_fill_facts` **declara** sus huecos (sin store, excepción, sin
contexto, `limit` agotado, descuadre evento↔contexto) en vez de devolver un libro plausible.
`CanonicalPositions` transporta las trazas que sustentan cada cantidad, con el **mismo contrato de
`dict`** del seam `canonical_positions_reader`.

**c) Contabilidad del worker (el P0)**
`_settle` devuelve `_Settlement(applied, unapplied, requested_qty)` con modo **structural** para el
camino sin `finance_applier` (no hay dinero que mover). `auto_turn` usa `applied_qty` en `_open`,
persistencia, `PositionState`, emits y `report.fills`; el emit `order` conserva la **pedida**. Nuevos
journal codes: `fill_not_materialized`, `fill_partially_materialized`, `fill_unapplied`
(**capital reservado**, visible en el libro de pendientes). Invariante duro `applied_qty <= held`
(defensa en profundidad) ⇒ si se violara, se aplana y se journaliza `exit_qty_over_position`.

**d) Autoridad canónica = ledger**
`_compose_canonical_reader` construye `{symbol: qty}` desde Σ `APPLIED` (no desde `position_state`).
Tras un reinicio con la RAM vacía, una proyección **inflada** se reescribe a la materializada
(`REBUILT`); libro ilegible ⇒ `None` ⇒ `POSITION_PROJECTION_UNKNOWN` ⇒ aperturas vetadas y salidas
permitidas.

**e) Observabilidad de skips (AUDITORIA 2)**
`manage_position_outcome` devuelve `PositionManagerResult` | `PositionManagerSkip` | `None` (los casos
benignos siguen siendo `None`; **`manage_position` mantiene el contrato antiguo** ⇒ retrocompatible).
`run_auto_cycle` journaliza `auto_position_skip` con `attention="high"` para `no_mark_data`,
`mark_rejected` y `decision_unavailable`; el worker propaga el motivo a `_v2_last_exit_reasons[symbol]`.

**f) CI (red de seguridad, cableado en esta misma sesión)**
Los jobs `quality` (`python-ci.yml`) y `python` (`release-tag-ci.yml`) corren una **lista explícita**
de ficheros: un test nuevo **no entra solo**. Se añadió
`packages/py/application/tests/test_applied_fills.py` a **ambos** (los otros dos ficheros nuevos ya
quedaban cubiertos por directorio: `packages/py/analytics/tests/**` y `apps/api-python/tests/**`).
Los comentarios nuevos van **fuera** del bloque plegado `run: >` (lección sellada en v2.40.2: un `#`
dentro de un bloque plegado se come el resto del comando). Verificado corriendo la batería **entera**
del job `quality` con el comando **extraído del propio YAML** ⇒ `exit 0` sin rojos (tabla §2.4).

### 2.3 Ficheros (sin commitear: 17 modificados + 9 nuevos)

**Modificados**

| Fichero                                                                        | Δ                                                      |
| ------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`           | +243/−56                                               |
| `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` | +107/−18                                               |
| `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`             | +5/−4                                                  |
| `packages/py/application/src/bolsa_application/position_manager.py`            | +100/−3                                                |
| `packages/py/application/src/bolsa_application/execution_event.py`             | +75                                                    |
| `packages/py/application/src/bolsa_application/auto_investment_system.py`      | +66/−7                                                 |
| `packages/py/application/src/bolsa_application/sim_durable_store.py`           | +60/−1                                                 |
| `packages/py/application/src/bolsa_application/auto_v2_entry.py`               | +41/−2                                                 |
| `packages/py/application/src/bolsa_application/auto_daily_journal.py`          | +1/−1 (docstring de `kind`: `fill_unapplied`)          |
| `packages/py/application/tests/test_execution_event.py`                        | +76                                                    |
| `packages/py/application/tests/test_auto_investment_system.py`                 | +72                                                    |
| `packages/py/application/tests/test_position_manager.py`                       | +56                                                    |
| `CHANGELOG.md`                                                                 | +83                                                    |
| `docs/engineering/roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`                  | +59/−13                                                |
| `package.json`                                                                 | `1.65.4-beta` → `1.65.5-beta`                          |
| `.github/workflows/python-ci.yml`                                              | +5 (cablea `test_applied_fills.py` en `quality`)       |
| `.github/workflows/release-tag-ci.yml`                                         | +5 (cablea `test_applied_fills.py` en el job `python`) |

**Nuevos (9)**

- `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py`
- `packages/py/analytics/tests/test_position_ledger.py`
- `packages/py/application/src/bolsa_application/applied_fills.py`
- `packages/py/application/src/bolsa_application/auto_reason_codes.py`
- `packages/py/application/tests/test_applied_fills.py`
- `apps/api-python/tests/applied_fill_equity.py` (helper compartido, **no** es un fichero de test)
- `apps/api-python/tests/test_auto_v2_partial_fills.py` (seam determinista de settlement)
- `docs/engineering/plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md`
- `docs/engineering/traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md` (este relevo)

> Los **8 primeros** son el slice; el **9º** es la documentación de relevo. Al hacer `git add`,
> revisa `git status --short` y añade **solo** estas 26 entradas: correr las suites deja
> `__pycache__/`, `.pytest_cache/` y a veces `logs/` que **no** deben entrar en el commit.

### 2.4 Verificación ejecutada (local, sobre el árbol final)

| Bloque                                                                         | Comando / gate                                                                                                                                         | Resultado                                          |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| Estático                                                                       | `ruff check packages/py apps/api-python --config pyproject.toml` (**invocación de CI**)                                                                | `All checks passed!`                               |
| Estático                                                                       | `mypy … --follow-imports=silent`                                                                                                                       | **485 ficheros, 0 issues**                         |
| Estático                                                                       | `lint-imports --config packages/py/.importlinter`                                                                                                      | **4 kept / 0 broken**                              |
| Paquetes (gate del plan)                                                       | `pytest test_execution_event, test_position_manager, test_simulated_settlement, test_position_ledger, test_applied_fills, test_auto_investment_system` | **80 passed**                                      |
| App (gate del plan)                                                            | `pytest test_auto_v2_worker_integration, test_auto_v2_partial_fills, test_a9_1_crash_battery, test_auto_simulation_worker`                             | **54 passed**                                      |
| Suite completa de paquetes                                                     | `pytest packages/py`                                                                                                                                   | **2729 passed**, 1 skipped, 1 xfailed (241 s)      |
| PG durable                                                                     | `AUTO_V2_DURABLE_PG_REQUIRED=1 … test_auto_v2_durable_pg.py`                                                                                           | **2 passed**                                       |
| PG jornada completa (bucle)                                                    | `AUTO_SCHEDULER_PG_REQUIRED=1 … test_auto_scheduler_real_pg_zero_human_intervention.py` ×30                                                            | **0 fallos** (2 tests por ejecución ⇒ 60 en verde) |
| PG proceso de scheduler                                                        | `AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 … test_a9_scheduler_process_pg_zero_human.py`                                                                    | **2 passed** (30,7 s)                              |
| Barrido amplio de la app (sin `chaos`)                                         | `pytest apps/api-python/tests --ignore=…/chaos`                                                                                                        | **477 passed**, 3 rojos **ajenos** (ver §3)        |
| **Job `quality` completo** (comando **extraído del YAML**, con la lista nueva) | `pytest <lista explícita de quality>`                                                                                                                  | **exit 0** (87 s), **0 rojos**                     |

### 2.5 Matriz de mutaciones (medida, no declarada)

| Mutación                                                        | Efecto medido                                                                                                                                                                      |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1 · `applied_qty = exec_qty` (volver a la cantidad **pedida**) | **6 rojos** en `test_auto_v2_partial_fills.py`                                                                                                                                     |
| M2 · `_record_applied_event` también con `settlement.unapplied` | **1 rojo** (la cola `RETRY` desaparece del libro de pendientes)                                                                                                                    |
| M4 · quitar el clamp `applied_qty <= held`                      | **1 rojo** (`test_protective_exit_never_exceeds_the_applied_position`)                                                                                                             |
| M5a · `manage_position_outcome` vuelve a `None` en los skips    | **2 rojos** (`test_manage_position_outcome_declares_rejected_mark`, `…_declares_decision_unavailable`)                                                                             |
| M3 · quitar el filtro `APPLIED` del helper de equity            | **1 rojo determinista** (`test_equity_realized_ignores_unapplied_fill_context`); en el bucle 30× de la jornada **no** se detecta (0/30) ⇒ el instrumento determinista es necesario |

### 2.6 Cambios observables y deuda declarada

- **Journal**: códigos nuevos `fill_not_materialized`, `fill_partially_materialized`, `fill_unapplied`,
  `exit_qty_over_position`, `auto_position_skip` (+ `no_mark_data`, `mark_rejected`,
  `decision_unavailable`). `report.fills` pasa a contar **fills aplicados**.
- **Breaking en beta**: ninguno de API pública relevante; `manage_position` conserva contrato.
- **Deuda declarada (no silenciosa)**: la cola no llena queda como **capital en `RETRY`** y su
  liberación explícita es `AUTO-1`; **sin índice parcial** `execution_events(account_id, status)`
  (lectura acotada por `limit`, migración asignada a `AUTO-1`); el `PositionLedger` es **read-model**
  sin tabla propia.

---

## 3. Deuda conocida (NO introducida por AUTO-1A — no confundir)

Fallos **preexistentes** del baseline, medidos con A/B (`git stash` + re-run) durante esta sesión:

- `apps/api-python/tests/integration/test_tax_report.py::test_tax_report_after_round_trip_trade`
  (**403** en el `SELL`): **falla igual con el árbol limpio**. Está en el `--ignore` de `quality`.
- `apps/api-python/tests/chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_c3b_…`:
  flake **2/6 con el cambio y 2/6 en baseline** (recuperación de órdenes LIVE; ajeno al slice).
  `chaos/live_a7` está en el `--ignore` de `quality` **y** del job `python` del tag ⇒ no rompe CI.
- `apps/api-python/tests/test_simulated_finance_pg.py::test_finance_auto_day_materializes_executetrade_exactly_once`
  y `apps/api-python/tests/test_workspaces.py::test_workspaces_crud`: rojos **solo** dentro del
  barrido completo; **pasan en aislamiento** (sensibilidad al orden/estado PG compartido). Ambos en
  el `--ignore` de `quality`.
- **`PROJECT_STATE.md` está desactualizado a propósito de esta fase**: en su entrada de `v2.40.4`
  declara el flake del scheduler como "criterio: re-ejecutar el job". AUTO-1A **lo cierra**: el flake
  era el síntoma de un bug de contabilidad. Hay que corregir esa frase al sellar (§4.0.6).
- La máquina de verificación es **Windows con política de control de aplicaciones**: el ejecutable
  `alembic` puede quedar bloqueado (`Failed to spawn`). Alternativa: `uv run python -m alembic`, o
  comprobar la head leyendo `packages/py/infrastructure/alembic/versions/041_unique_natural_keys.py`.
  **`mypy` sí funciona** en esta sesión (485 ficheros, 0 issues).

---

## 4. TRABAJO PENDIENTE — en orden

### Tarea 0 — Cierre y elevación de AUTO-1A (patrón `v2.40.4`)

1. **`git status --short`** y `git add` **explícito** de las **26 entradas** de §2.3 (17 M + 9 `??`).
   **No** meter ruido (`logs/`, `.pytest_cache/`, `__pycache__/`).
2. Commit de fase (mensaje sugerido:
   `feat(v2.40.5): posicion = suma de fills APPLIED, fills parciales y skips de gestion con rastro`,
   cuerpo con causa raíz, mutaciones medidas y deuda declarada).
3. Push a `main` y verificar **Python CI** verde (run del push). Nota: `python-ci.yml` tiene
   **path-filter** que incluye `.github/workflows/python-ci.yml`, así que este push **sí** dispara CI.
4. Tag anotado **`v2.40.5-beta`** apuntando al commit de fase.
5. Verificar **Release-tag CI** (job `certify` + `python` + `lifecycle-pg` + `auto-v2-durable-pg`).
   El job `python` del tag ejecuta `mypy` sobre el árbol completo y ahora también
   `test_applied_fills.py`.
6. **Cierre documental** (commit adicional **docs-only**, que **no** re-dispara `Python CI`):
   - `docs/engineering/PROJECT_STATE.md` — entrada de `V2.40.5/AUTO-1A` y **corregir** la frase del
     flake de `v2.40.4` (§3).
   - `CURRENT_SYSTEM.md` si su columna viva menciona el flake.
   - `docs/engineering/engineering-index-2026-08-03.md` — entrada nueva (la última es la **116**,
     `V2.39.3`; esta sería la **117**).
   - **Crear** `docs/engineering/audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md` y
     `docs/engineering/arranque-auditor-v2-40-5-auto-1a-2026-09-17.md` (patrón de `v2.40.4`: matriz
     afirmación→código→test, mutaciones medidas, cambios observables, límites declarados, y la
     declaración honesta de que **no** se afirma CI de un tag aún no publicado). **No existen aún**:
     son entregables de este paso.

### Tarea 1 — `AUTO-1` — Portfolio Reservation Engine (`V2.41` / `1.66.0-beta`)

Es la **siguiente fase del roadmap** y ya arranca sobre posición materializada. Alcance declarado en
`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md` §3: reservas explícitas `Decision + Reservation` con
rollback/release, ciclo de vida durable de la posición, y **la migración del índice parcial**
`execution_events(account_id, status)` que AUTO-1A dejó declarada como deuda.

### Tarea 2 — Auditoría externa del slice (cuando el owner la pida)

Punto de entrada: el `arranque-auditor` de §4.0.6. Las **tres preguntas** que dejó abiertas la
auditoría anterior están respondidas en el plan §8; el auditor debería atacar más bien:
¿el modo _structural_ de `_settle` puede enmascarar un `RETRY` en un camino con `finance_applier`
real?, ¿`CanonicalPositions` se reutiliza como fuente de verdad en **todos** los consumidores de
posición (riesgo, exposición, sizing) o queda alguno leyendo `_open`?, y ¿el `limit` de `list_applied`
es suficiente con la jornada real más larga medida?

---

## 5. Cómo verificar SIEMPRE antes de decir «hecho»

Orden mínimo (paridad con CI, **extrae los comandos del YAML**, no los reescribas de memoria):

```bash
# 1) Calidad (invocación EXACTA de CI: --config pyproject.toml y los mismos paths)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Offline del job `quality` (usa EXACTAMENTE su lista y sus --ignore)
uv run python -c "import yaml;print(yaml.safe_load(open('.github/workflows/python-ci.yml',encoding='utf-8'))['jobs']['quality']['steps'][-1]['run'])"
#   …y ejecuta esa cadena tal cual.

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q   # ×30
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q
```

Reglas de honestidad del repo:

- No declares verde sin haber corrido los bloques.
- Distingue fallos **preexistentes** (§3) de regresiones tuyas; mide con A/B (`git stash`).
- No certifices `main`/HEAD como si fuera un tag.
- Un test nuevo **no entra solo** en la red de CI: cablea el fichero en `quality` **y** en el job
  `python` del tag.

---

## 6. Uso sugerido de subagentes

- **explore** (medium): mapear `auto_simulation_worker` (`_settle` / `auto_turn` /
  `_compose_canonical_reader`) y `applied_fills` antes de tocar contabilidad de posición.
- **generalPurpose**: cambios que cruzan worker + application + analytics manteniendo semántica.
- **best-of-n-runner**: solo si hay que comparar dos diseños de reservas en `AUTO-1`.
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **ci-investigator**: si el run del tag `v2.40.5-beta` falla y hay que diagnosticarlo.

---

## 7. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -3` → ¿hay commit de fase? ¿hay tag `v2.40.5-beta`?
- [ ] `git status --short` → **26 entradas** (17 M + 9 `??`, §2.3); los `logs/`, caches y
      `__pycache__/` que aparezcan tras correr tests **no** son tuyos.
- [ ] `git stash list` → hay un stash **ajeno y antiguo** (`all-v170`, 2026-09-02). **No lo toques**;
      si haces A/B con `git stash`, verifica que el árbol vuelve a las **26** entradas de §2.3.
- [ ] Leer `docs/engineering/PROJECT_STATE.md` (columna viva) y
      `docs/engineering/plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md` §8.
- [ ] Comprobar la head de Alembic: `041_unique_natural_keys` (SIN migración nueva en esta fase).
- [ ] Preguntar al owner: ¿**Tarea 0** (sellado y elevación) o **Tarea 1** (`AUTO-1` Reservation
      Engine)?

---

## 8. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed (ausencia de evidencia ≠ aprobación; libro
ilegible ⇒ aperturas vetadas y salidas permitidas) · migraciones aditivas sin backfill · long-only ·
**Alembic head `041_unique_natural_keys` (AUTO-1A no migra)** ·
**`POSITION = Σ APPLIED` y `exit_qty <= materialized_qty`** · lo pedido, lo llenado y lo materializado
son tres números distintos y los tres son auditables · `RETRY`/`CAPTURED`/`APPLYING`/`FAILED` **nunca**
son posición ni realizado (son capital reservado) · ningún skip de gestión queda mudo.

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · leer `position_state`
como autoridad de posición · contabilizar la cantidad **pedida** · certificar sin correr los bloques
de §5 · editar el fichero de plan de Cursor
(`auto-1a_position_materialization_d314c0b6.plan.md`) · meter en el commit el ruido de `logs/` y
caches · declarar CI de un tag que aún no existe.
