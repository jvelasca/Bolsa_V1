# Evidencia — `v2.88.110-beta` / **`§7` — endurecimiento RUNTIME de la barrera SIM**: permiso positivo + invariante derivado + negativo E2E

> **Base funcional:** `v2.88.109-beta` (commit `a98adbed`). Cierra el trío de medidas de `§7` de la auditoría profundizada (`Endurecimiento de la barrera SIM`).
> **Naturaleza:** sello **defensivo/aditivo**. **`Δ motor ≠ 0`** (hay código de producto: `simulated_finance.py` + el worker AUTO) pero **`Δ decisión = 0`**: no se toca motor de decisión/ejecución, umbrales, reparto, `TOP_N`/régimen/selección/protección. **SIN migración** (head `052_top3_opportunities`) · **contrato sin cambio**.

---

## 1. Qué cierra (el hueco de `§7`)

    10|La barrera `AUTO → SIMULATED ONLY` / `AUTO → NEVER REAL LIVE` ya era **estructural** (envs LIVE fail-closed + allowlist de venues + invariante AST), pero la auditoría dejó tres residuos declarados:

1. **Permiso por AUSENCIA, no por CAPACIDAD.** El movimiento de dinero se protegía con una **lista de denegación** (venues no-AUTO) y con envs apagadas. Nada *exigía* al llamante una declaración **afirmativa** de vía simulada.
2. **Censo de módulos AUTO fijo.** `test_a8_m0_auto_live_invariant.py` mantenía a mano la lista de módulos AUTO: un módulo nuevo que cablease el broker podía quedar fuera del censo.
3. **Negativo implícito.** Que `live_auto` dry-run no envíe órdenes estaba garantizado **por construcción**, no por una prueba explícita.

Este sello cierra los tres.

## 2. `§7-a` — Permiso POSITIVO SIM-only (capacidad sellada, no ausencia)

[`simulated_finance.py`](../../../../packages/py/application/src/bolsa_application/simulated_finance.py) introduce `SimOnlyScope`, una capacidad **afirmativa e intransferible**, y `require_sim_only_scope(source=...)` como su **único** constructor válido:

- El constructor está **sellado** sobre una clave privada del módulo: `SimOnlyScope(_key=..., source=...)` con una clave ajena levanta `TypeError`; un `source` vacío levanta `ValueError` (un permiso sin procedencia declarada no debe existir).
- `build_simulated_execute_trade_applier(..., *, scope: SimOnlyScope)` **exige** la capacidad: sin `scope=`, o con un objeto forjado (duck-typed), levanta `TypeError`. El **punto de movimiento de dinero no se construye** sin declarar la vía.
- `Scope.allows(venue)` cubre SOLO `{paper, simulated}`; el applier re-verifica el venue del fill contra la capacidad (`scope.allows`), de modo que la lista de venues y la capacidad se refuerzan mutuamente.
    20|- El **worker AUTO** (única ruta de producción que construye el applier) acuña su permiso explícitamente: `require_sim_only_scope(source="auto_simulation_worker")` ([`auto_simulation_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py)).

**Pruebas** ([`test_a8_m0_sim_only_permission.py`](../../../../packages/py/application/tests/test_a8_m0_sim_only_permission.py), **7 passed**): cobertura de venues de la capacidad; `source` obligatorio; constructor sellado (forja ⇒ `TypeError`); applier sin `scope` ⇒ `TypeError`; applier con `scope` forjado ⇒ `TypeError`; comportamiento (mueve dinero SOLO para venue SIM, con la key idempotente canónica); y **aserción estructural** de que el worker acuña la capacidad en su punto de dinero (`scope=` presente en todo `build_..._applier`).

## 3. `§7-b` — Invariante AST DERIVADO (censo del árbol + allowlist invertida)

[`test_a8_m0_auto_live_invariant.py`](../../../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) deja de mantener la lista fija de módulos AUTO y **deriva** el censo del árbol real:

- **Derivación por convención de nombre** (`*auto*`, `paper_d*`) + **spine AUTO por ROL** declarado (`execution_router`, `position_exit_evaluator`, `execute_gated_portfolio_trade`, `evaluate_exit_plan`), con aserción de que el spine **sigue presente** (un renombrado rota el test en vez de perder cobertura en silencio).
- **Allowlist INVERTIDA sobre todo el paquete:** se barre `bolsa_application/**/*.py`, se detecta todo módulo que importe/referencie el puerto LIVE **o llame a `.submit(...)`** —así se caza también lo que llega **por inyección** (`confirm/execution.py`, que nunca nombra el símbolo del puerto)— y se exige que el censo **coincida exactamente** con los cuatro módulos autorizados (`broker_adapter`, `fill_pending_order`, `confirm_recommendation`, `confirm/execution`). Un módulo nuevo que cablee el broker **rompe en CI sin que nadie lo añada a mano**.
- **Barrido de `apps/*/src`:** NINGÚN módulo de aplicación puede tocar la vía real (allowlist vacía). El barrido descubre las raíces `src` por sí mismo (sin escanear `node_modules`) y se **auto-verifica** cubriendo al worker AUTO.
- **Anti-podredumbre:** se comprueba que la allowlist no apunta a humo y que el puerto sigue **definiendo** sus tres símbolos (`IBrokerAdapter`, `resolve_broker_adapter`, `XtbBrokerAdapter`).

**Verificación** (**40 passed**, incluye los AUTO por nombre/rol, el spine sin adapter y el barrido de apps).

## 4. `§7-c` — Negativo END-TO-END del dry-run (barreras LIVE arriba)

[`test_a8_m0_live_dry_run_never_submits.py`](../../../../packages/py/application/tests/test_a8_m0_live_dry_run_never_submits.py) recorre `_evaluate_live_dry_run` —el único punto donde AUTO "roza" el modo LIVE— con la vía real **minada** (`resolve_broker_adapter` y los `*.submit` de `Xtb`/`Mock`/`Paper` sustituidos por trampas que registran y explotan) y **en las dos posiciones de las barreras LIVE**: apagadas **y** abiertas a la vez (`LIVE_EXECUTION_AUTHORIZED=1` + `LIVE_EXECUTION_UNLOCKED=1`).

- Resultado: PASS o VETO (contrato dry-run), y **CERO** toques a la vía real: `hits == []` y `ExecuteTrade` sin llamadas (`trade.calls == []`). Es la afirmación fuerte: **ni con la vía real armada**, el dry-run de AUTO alcanza el broker o el libro.
- En PASS se exige `transaction_id is None` y el motivo «sin orden real».
- **Complemento estructural:** el módulo `execution_router.py` no contiene `.submit(` ni `resolve_broker_adapter`.

**Verificación** (**2 passed**).

## 5. Verificación (local, PostgreSQL real)

    50|- **Batería hermética EXACTA del job `quality`** (reproducida con el parser del propio censo `scripts/ci/test_selection.py`) → **`4789 passed, 1 skipped`** (0 fallos).
- **Ficheros nuevos `§7`** → **49 passed** (`test_a8_m0_auto_live_invariant` **40** · `test_a8_m0_sim_only_permission` **7** · `test_a8_m0_live_dry_run_never_submits` **2**).
- **Finanzas AUTO contra PG REAL** [`test_simulated_finance_pg.py`](../../../../apps/api-python/tests/test_simulated_finance_pg.py) (el fichero que consume el applier modificado) → **2 passed** (`AUTO_M5_FIN_PG_REQUIRED=1`).
- **Guardián de censo de tests** → **5 passed** (los 3 ficheros nuevos entran por el pase de directorio de `packages/py/application/tests`: sin fichero invisible, `0` declarados).
- **Guardián DÍA-D** [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed** (`2.11.110-beta`).
- **Estilo/estructura:** `ruff check` **All checks passed** · `lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken** · `mypy` (domain/market/infrastructure/application + api-python, `--follow-imports=silent`) → **544 source files, no issues**.
- **CI de tag:** sin cambio de workflow. Los tres ficheros nuevos viven en `packages/py/application/tests`, que el job `quality` recolecta por pase de directorio; el fichero PG modificado ya corre en `release-tag-ci`.

## 6. Límites declarados (sin fabricar)

- **No es una barrera criptográfica.** El sello de `SimOnlyScope` es de **identidad** (clave privada del módulo) dentro del mismo proceso Python: disuade el cableado accidental y hace el permiso **explícito y ruidoso**, pero un actor con capacidad de ejecutar código arbitrario en proceso puede importar la clave. La defensa en profundidad sigue siendo la allowlist de venues, las dos envs humanas y el invariante AST.
- **`Δ decisión = 0`:** no se toca ningún umbral, reparto, `TOP_N`, régimen, selección ni protección. El cambio es de contrato **interno** (firma del applier) y de pruebas.
- **`Scope.allows` es un segundo cierre, no un segundo umbral:** opera sobre el mismo conjunto `AUTO_SETTLE_VENUES` que la guarda de venues; no añade criterio de negocio.
- **El dry-run sigue sin broker por diseño** (F6-broker pendiente): `§7-c` **certifica** la ausencia, no la sustituye por una implementación.
- **Tag `unsigned`** (limitación de certificación, no defecto).

## 7. Cita POST-TAG

Tag anotado **`v2.88.110-beta`** (objeto `b08bbff2` → commit `d868ea40`) sellado y publicado.

- `Release tag CI` [**38136552355**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38136552355) → **`success`**: **11 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado), **sin reintentos** en los obligatorios.
- **`python`** (ruff/imports/mypy/pytest offline) → **`success`**: el permiso positivo, el invariante **derivado** y el negativo E2E quedan **certificados en CI**, no solo en local. **`lifecycle-pg`** (Alembic + auth + golden restart) → **`success`**.
- `replay-repro` → **VEREDICTO `REPRODUCIDO`**: `sha256` `1E3ADAC2…929A37E7` **idéntico** a los sellos previos ⇒ **`Δ decisión = 0`** confirmado por CI.
- Tag **unsigned** (limitación de certificación, no defecto).
