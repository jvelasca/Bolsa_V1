# RELEVO — post V2.35/A15 · Observabilidad y gobernanza de la gramática de Discovery — 2026-09-11

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume
> **cero contexto previo** más allá de lo que aquí se dice. Léelo entero antes de tocar nada.
> Respeta el estilo del repo: español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-11 · **Base:** `main` · HEAD local **`4fdf108d`** (sello A14) sobre
> `e6fbab83` (fase A14) → `61e613b1` (hardening H1+H2) → `5fcd0224` (cierre A13).
> **Alembic head:** `035_paper_forward_evidence` (SIN migración nueva en A15).
> **Veredicto:** A15 **IMPLEMENTADA y VERIFICADA**; pendiente únicamente de su commit de fase,
> tag anotado `v2.35-beta` y cierre documental (los ejecuta el coordinador/propietario).

---

## 0. Estado en una frase

La gramática controlada de Discovery (A14) deja de ser un rollout **a ciegas**: el motor emite
un **resumen determinista de procedencia** (catálogo vs gramática, presupuesto y cupos), el
orquestador **cuenta** qué candidatas llegan de verdad al LAB y al shadow, y el worker AUTO
traza todo por **logs estructurados** y contadores de proceso. Todo es **observabilidad de
solo lectura**: no cambia decisiones, presupuestos, gates ni el reparto catálogo↔gramática.
Sin segundo motor, sin segundo FSM, sin migración.

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa. Relevante para esta continuación:

- `packages/py/domain` — dominio puro (entidades del ciclo de vida, promoción, salud).
- `packages/py/application` — fases del orquestador (LAB, shadow, forward, vigilancia), stores,
  Discovery (catálogo + motor + gramática) y `optimize.py`.
- `packages/py/analytics` — motor de reglas/backtest determinista (`rules_grid`, `rules_engine`,
  `indicators/compute.py`).
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL).
- `apps/api-python` — workers de fondo (AUTO), API, y los E2E de certificación PG.

### 1.2 Ciclo estratégico actual (lo que YA existe, no reimplementar)

```
ESTUDIO → DISCOVERY (catálogo + gramática A14, con resumen A15) → LAB (CPCV/PBO/DSR/WFE/OOS)
        → TOP3 → COACH → FINALISTA
        → SHADOW (hold-out histórico, V2.32/A12, evidencia EJECUTADA)
        → PROMOTION (gate cuantitativo + coach + evidencia shadow)
        → ACTIVE
        → PAPER FORWARD (mercado nuevo post-promoción, V2.33/A13)
        → VIGILANCIA → (degradación) → re-LAB
```

Puntos de anclaje reales (rutas exactas):

- **Único motor declarativo**: `packages/py/analytics/src/bolsa_analytics/optimize/rules_grid.py`
  → `_simulate_rules_strategy(...)` y `run_rules_grid_search`.
- **Evaluador de señales/FSM**: `packages/py/analytics/src/bolsa_analytics/signals/rules_engine.py`
  (`evaluate_rules_signals`, `_series_for_spec`).
- **Catálogo de Discovery**: `packages/py/application/src/bolsa_application/discovery_catalog.py`
  (`DiscoveryFamily`, `DISCOVERY_FAMILIES`, `DiscoveryBudget`, `family_by_name`).
- **Gramática A14**: `packages/py/application/src/bolsa_application/discovery_grammar.py`
  (`GrammarBudget`, `enumerate_grammar_plans`, `grammar_variants_for_plan`; techo anti-explosión
  fijado por test: **1784 planes** con el presupuesto por defecto).
- **Motor de Discovery (A15 amplía)**: `packages/py/application/src/bolsa_application/strategy_discovery_engine.py`
  (`discover_for_instrument` / `discover_candidates` / `discover_from_universe`, y **nuevo**
  `discover_for_instrument_with_summary` + `DiscoveryEmissionSummary`).
- **Orquestador (A15 amplía)**: `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  (`OrchestratorDeps`, `OrchestratorResult`, `_candidate_provenance`).
- **Worker AUTO (A15 amplía)**: `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  (`_make_discovery_runner`, `grammar_counters`, `GrammarObservabilityCounters`, `auto_orchestrator_loop`).
- **LAB**: `packages/py/application/src/bolsa_application/optimize.py` y
  `orchestrator_lab_runner.py`.
- **Shadow**: `strategy_shadow_phase.py`; **Forward**: `paper_forward_phase.py`.
- **Store del ciclo**: `strategy_lifecycle_store.py`.

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  (ambas false). **Cero caminos LIVE nuevos.**
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**.
- **Fail-closed**: ausencia de evidencia ≠ aprobación.
- **H1 — `require_holdout=True` inviolable** en la ruta de promoción; sin `lab_end` no hay replay.
- **H2 — identidad de dataset en `bars_hash`** (`instrument_id`/`timeframe`/`source`/`adjusted`).
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo.
- Long-only intacto. `PAPER_D_EXECUTE` off por defecto.
- Gates intactos: **CPCV, PBO, DSR, WFE, OOS** + coach. No se relaja ningún umbral.

---

## 2. Qué se acaba de hacer (V2.35/A15)

**Ficheros modificados (9, sin migración):**

- `packages/py/application/src/bolsa_application/strategy_discovery_engine.py`
- `packages/py/application/src/bolsa_application/auto_orchestrator.py`
- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
- `packages/py/application/tests/test_discovery_grammar.py`
- `packages/py/application/tests/test_auto_orchestrator.py`
- `apps/api-python/tests/test_auto_orchestrator_worker.py`
- `CHANGELOG.md`
- `docs/engineering/PROJECT_STATE.md`
- `docs/engineering/engineering-index-2026-08-03.md`

### 2.1 Hallazgo que A15 resuelve

Tras A14, la gramática era **funcional pero opaca**: con `AUTO_ORCHESTRATOR_GRAMMAR` OFF no había
forma de saber cuántas candidatas habría aportado, y con ON no había traza de la **procedencia**
(catálogo vs gramática) ni de cuántas llegaban de verdad al LAB y al shadow. Gobernar el rollout
exigía medirlo, y medirlo no debía cambiar ninguna decisión.

### 2.2 Cambios, por pieza

**a) Resumen determinista de emisión** (`strategy_discovery_engine.py`)
Nuevo `@dataclass(frozen=True, slots=True) DiscoveryEmissionSummary` con `catalog_candidates`,
`grammar_candidates`, `total_candidates`, `trials_used`, `catalog_cap`, `grammar_cap`,
`grammar_enabled` y `bar_count_ok` (warm-up). Nueva API aditiva
`discover_for_instrument_with_summary(...) -> (candidatas, resumen)`. El conteo se deriva de lo ya
emitido (el prefijo `GRAMMAR_FAMILY_PREFIX = "grammar:"` es la fuente de verdad): **no añade
estado al motor**. `discover_for_instrument` delega y descarta el resumen, conservando firma y
salida **byte-idénticas** con gramática OFF (test de regresión A13).

**b) Procedencia en el orquestador** (`auto_orchestrator.py`)
`OrchestratorResult` gana campos aditivos al final: `catalog_candidates`, `grammar_candidates`,
`lab_grammar_evaluated`, `shadow_started`, `shadow_grammar_started`. `lab_grammar_evaluated` se
cuenta sobre las evaluaciones reales del LAB (no sobre la mera emisión);
`shadow_started`/`shadow_grammar_started` reflejan si el finalista que entró al replay era
gramatical. **Sin provider de barras no hay replay ⇒ `shadow_started = 0`** (fail-closed honesto:
no se inventa evidencia).

**c) Logs estructurados + contadores de proceso** (`auto_orchestrator_worker.py`)
`_make_discovery_runner` usa la nueva API y emite **una línea por instrumento** (procedencia,
presupuesto y cupos). `auto_orchestrator_loop` amplía el log de ciclo y añade un **`cycle_summary`
agregado por ciclo**. Nuevos `GrammarObservabilityCounters` + `grammar_counters()` (acumulado por
proceso, para tests/inspección). **Solo `logging`**: nada se persiste en DB (sin migración).

### 2.3 Verificación reproducible (a repetir antes de elevar)

```bash
# Bloque 1: estático (verde)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# Bloque 2: quality offline (usa EXACTAMENTE los --ignore del job `quality` de python-ci.yml)
#   → 1243 passed (único fallo: flake ambiental de test_a9_scheduler_process_pg_zero_human
#     sobre BD local sucia; pasa en aislamiento. Ver §3.)

# Bloque 3: PG de certificación (Postgres 16 en localhost:5432)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
A14_GRAMMAR_PG_REQUIRED=1 PAPER_FORWARD_PG_REQUIRED=1 AUTO_ORCHESTRATOR_PG_REQUIRED=1 \
uv run pytest apps/api-python/tests/test_a14_grammar_discovery_pg.py \
  apps/api-python/tests/test_a13_paper_forward_pg.py \
  apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py -q
# → 6 passed (sin skips)
```

### 2.4 Tests

- `packages/py/application/tests/test_discovery_grammar.py` — resumen OFF (0 gramática) / ON
  (gramática > 0), cuadre `catálogo + gramática == total`, determinismo, warm-up y regresión A13.
- `packages/py/application/tests/test_auto_orchestrator.py` — procedencia del orquestador en LAB
  y shadow (con y sin provider de barras).
- `apps/api-python/tests/test_auto_orchestrator_worker.py` — contadores OFF/ON, monotonía entre
  llamadas y emisión del `cycle_summary`; los contadores se resetean por test (fixture autouse).

No hay job de CI nuevo: la observabilidad queda cubierta por los jobs existentes (`quality`,
`lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`).

---

## 3. Deuda conocida (NO introducida por A15 — no confundir)

Fallos **preexistentes** del baseline:

- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` — fallos de carga
  preexistentes (ruido de entorno de alta concurrencia). **No se toca.**
- `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` — flake **ambiental**
  documentado (falla con `MultipleResultsFound` sobre una BD local sucia; ver
  `audit-pack-v2.32.1-2026-09-11.md`). **Pasa en aislamiento** con y sin los cambios de A15.
  No es una regresión.

---

## 4. TRABAJO PENDIENTE — en orden

### Tarea 0 — Cierre/elevación de A15 (patrón A14)

1. Commit de fase A15 (9 ficheros, sin migración).
2. Push a `main` y tag anotado **`v2.35-beta`**.
3. Cierre documental (este relevo + `PROJECT_STATE` + entrada 104 del `engineering-index`).
4. Verificar el **Release tag CI** (run del tag, job `certify` success) y el `Python CI` del push.

### Tarea 1 — Gobernanza con datos reales (opcional, siguiente)

Con A15 ya observable, el owner puede decidir el rollout de `AUTO_ORCHESTRATOR_GRAMMAR` con
evidencia: cuánto aporta la gramática frente al catálogo y cuántas candidatas gramaticales
sobreviven al LAB y al shadow. Posible refinamiento: promover a producción un presupuesto concreto
(`AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS` / `_MAX_VARIANTS`) y observar ratios.

### Tarea 2 — Refinamiento del vocabulario (opcional, con cuidado)

Añadir variantes por bloque sube el techo combinatorio: el test anti-explosión
(`len(plans) == 1784`) obliga a revisar el coste de multiple testing de forma consciente y a
actualizar ese test de forma explícita.

---

## 5. Cómo verificar SIEMPRE antes de decir «hecho»

Orden mínimo (paridad con CI):

```bash
# 1) Calidad
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Offline (usa EXACTAMENTE los --ignore del job `quality` de python-ci.yml)

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
#    Copia los comandos de los jobs `lifecycle-pg`, `paper-forward-pg` y `grammar-discovery-pg`.
```

Reglas de honestidad del repo:

- No declares verde sin haber corrido los tres bloques.
- Distingue fallos **preexistentes** (§3) de regresiones tuyas.
- No certifiques `main`/HEAD como si fuera un tag.

---

## 6. Uso sugerido de subagentes

- **explore** (medium): mapear `strategy_discovery_engine` / `auto_orchestrator` / worker AUTO
  antes de tocar nada del discovery o de la observabilidad.
- **generalPurpose**: cambios que cruzan varios módulos manteniendo semántica.
- **best-of-n-runner**: solo si hace falta comparar dos diseños de observabilidad en paralelo.
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente.
- **ci-investigator**: si un check del tag A15 falla y hay que diagnosticarlo.

---

## 7. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -3` → comprobar la posición de `main` respecto al commit de fase A15 y al
      cierre documental; el tag `v2.35-beta` debe apuntar al cierre.
- [ ] `git status --short` → el commit de fase agrupa 9 ficheros modificados; hay
      caches/`__pycache__`/logs que **no** son tuyos; no los metas en commits.
- [ ] Leer `docs/engineering/PROJECT_STATE.md` (columna viva).
- [ ] `cd packages/py/infrastructure && uv run alembic heads` → debe salir
      `035_paper_forward_evidence (head)`.
- [ ] Preguntar al owner: ¿**Tarea 1** (gobernar el rollout con los datos de la observabilidad) o
      **Tarea 2** (refinar el vocabulario con revisión del techo combinatorio)?

---

## 8. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed (ausencia de evidencia ≠ aprobación) ·
migraciones aditivas sin backfill · long-only · Alembic head `035_paper_forward_evidence` ·
gramática A14 tras `AUTO_ORCHESTRATOR_GRAMMAR` (OFF por defecto) ·
A15 añade **observabilidad de solo lectura** (procedencia catálogo/gramática en discovery, LAB y
shadow; logs estructurados + contadores de proceso) **sin cambiar ninguna decisión**.

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · certificar sin
correr los tres bloques de verificación · mezclar A14/A15 en un commit · editar el fichero de plan
`a15_grammar_observability_4f2fbfdd.plan.md` · persistir métricas en DB (A15 no tiene migración).
