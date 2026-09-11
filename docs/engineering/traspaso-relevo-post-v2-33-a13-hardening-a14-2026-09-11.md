# RELEVO — post V2.33/A13 → hardening + A14 (Paper Forward ya cerrado) — 2026-09-11

> **Para el agente entrante (con sus subagentes).** Este documento es autocontenido: asume
> **cero contexto previo**. Léelo entero antes de tocar nada. Respeta el estilo del repo:
> español, fail-closed, sin LLM en hot path, LIVE congelado.
>
> **AsOf:** 2026-09-11 · **Base:** `main` · HEAD local **`5fcd0224`** (commit de cierre de A13).
> **Alembic head:** `035_paper_forward_evidence` (head único).
> **Veredicto:** V2.33/A13 **CERRADA en código y verificada**; pendiente (a) el _push_ + tag por
> parte del owner, (b) dos ítems de _hardening_ del audit V2.32.1, (c) la fase A14.

---

## 0. Estado en una frase

El sistema ya tiene evidencia **histórica** (shadow, V2.32/A12) **y forward** (paper, V2.33/A13)
de una estrategia; `AUTO ⇒ SIMULATED` y `LIVE` doblemente bloqueado. Lo que queda es (1) _hardening_
barato de dos contratos del audit V2.32.1, (2) empujar/taggear A13, (3) abrir **A14 — Strategy
Intelligence** (gramática controlada de Discovery).

---

## 1. Contexto mínimo indispensable (verificado en código)

### 1.1 Qué es este proyecto

Monorepo de una plataforma de bolsa. Relevante para esta continuación:

- `packages/py/domain` — dominio puro (entidades del ciclo de vida, promoción, salud).
- `packages/py/application` — fases del orquestador (LAB, shadow, forward, vigilancia) y stores.
- `packages/py/analytics` — motor de reglas/backtest determinista (`rules_grid`, `rules_engine`).
- `packages/py/infrastructure` — SQLAlchemy + Alembic (PostgreSQL).
- `apps/api-python` — workers de fondo (AUTO), API, y los E2E de certificación.

### 1.2 Ciclo estratégico actual (lo que YA existe, no reimplementar)

```
ESTUDIO → LAB → TOP3 → COACH → FINALISTA
        → SHADOW (hold-out histórico, V2.32/A12, evidencia EJECUTADA)
        → PROMOTION (gate cuantitativo + coach + evidencia shadow)
        → ACTIVE
        → PAPER FORWARD (mercado nuevo post-promoción, V2.33/A13)
        → VIGILANCIA → (degradación) → re-LAB
```

Puntos de anclaje reales (rutas exactas):

- Motor declarativo reutilizado: `packages/py/analytics/src/bolsa_analytics/optimize/rules_grid.py`
  → `_simulate_rules_strategy(bars, definition, *, initial_cash, trade_from_index,
attach_round_trips, execution_model="next_open")`. Causalidad `index-1 → open(index)`.
- Shadow: `packages/py/application/src/bolsa_application/strategy_shadow_phase.py`
  (`split_holdout`, `ShadowReplayConfig`, `run_shadow_replay`).
- Forward: `packages/py/application/src/bolsa_application/paper_forward_phase.py`
  (`split_forward`, `PaperForwardConfig`, `run_paper_forward`, `_bars_hash`).
- Seam de la ACTIVE en el hot path:
  `packages/py/application/src/bolsa_application/auto_orchestrator.py`
  (`active_strategy_decider`, `OrchestratorDeps`).
- Worker AUTO: `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`
  (`auto_orchestrator_loop`, `_default_orchestrator`, `_make_forward_runner`, env-gates).
- Store del ciclo: `packages/py/application/src/bolsa_application/strategy_lifecycle_store.py`
  (Protocol + InMemory + `PostgresStrategyLifecycleStore`).
- Tablas: `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`.

### 1.3 Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en el hot path**
  (la IA solo en research/advisory).
- **Fail-closed**: ausencia de evidencia ≠ aprobación.
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo.
- Long-only intacto. `PAPER_D_EXECUTE` off por defecto.

---

## 2. Qué se acaba de hacer (V2.33/A13) — commit `5fcd0224`

16 ficheros, +2165/−2. Commit **local en `main`**, **sin push** (paso del owner).

**Código:**

- Dominio: `PaperForwardResult` + `PaperForwardPolicy` en
  `packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`.
- Fase: `packages/py/application/src/bolsa_application/paper_forward_phase.py` (nuevo).
- Store: `save_forward_result`/`list_forward_results` en `strategy_lifecycle_store.py`.
- Tabla + migración: `PaperForwardResultRow` en `tables.py` y
  `packages/py/infrastructure/alembic/versions/035_paper_forward_evidence.py`
  (`down_revision = "034_shadow_dataset_fingerprint"`).
- Wiring: `auto_orchestrator_worker.py` (`AUTO_ORCHESTRATOR_FORWARD`, default **OFF**;
  `AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS`, default 400).

**Tests:**

- Herméticos: `packages/py/domain/tests/test_strategy_lifecycle.py` (6 nuevos),
  `packages/py/application/tests/test_paper_forward_phase.py` (11),
  `apps/api-python/tests/test_auto_orchestrator_worker.py` (5 nuevos).
- Store PG: `apps/api-python/tests/test_strategy_lifecycle_pg.py::test_paper_forward_result_persistence_pg`.
- E2E de certificación: `apps/api-python/tests/test_a13_paper_forward_pg.py` (2 tests; sin fill =
  fallo duro; sin barras nuevas = fail-closed).
- CI: job `paper-forward-pg` en `.github/workflows/python-ci.yml` (skip = fallo).

**Docs:** `CHANGELOG.md` (`1.58.0-beta`),
`docs/engineering/cierre-v2.33-a13-paper-forward-2026-09-11.md`,
`docs/engineering/audit-pack-v2.33-2026-09-11.md`,
`docs/engineering/PROJECT_STATE.md`.

**Verificación reproducible (ya pasada en la sesión anterior):**

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed
uv run lint-imports --config packages/py/.importlinter                  # 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 # Success (469 files)

# PG de certificación (necesita Postgres 16 en localhost:5432):
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
PAPER_FORWARD_PG_REQUIRED=1 STRATEGY_LIFECYCLE_PG_REQUIRED=1 \
AUTO_ORCHESTRATOR_PG_REQUIRED=1 LIFECYCLE_PG_REQUIRED=1 \
uv run pytest apps/api-python/tests/test_a13_paper_forward_pg.py \
  apps/api-python/tests/test_strategy_lifecycle_pg.py \
  apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py \
  packages/py/application/tests/test_sim_strategy_attribution.py -q
# → 15 passed (sin skips)
```

---

## 3. Deuda conocida (NO introducida por A13 — no confundir)

Fallos **preexistentes** del baseline, documentados en
`docs/engineering/audit-pack-v2.32.1-2026-09-11.md` §5. **No** intentes arreglarlos como parte del
hardening salvo instrucción expresa; son ruido de entorno:

- `apps/api-python/tests/test_scheduler_worker.py::test_event_loop_starters_reunen_todos_los_workers_periodicos`
  (el set esperado es anterior a `start_auto_orchestrator`).
- `apps/api-python/tests/test_queue_poll_worker.py::test_run_con_arq_es_noop`.
- `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`.
- Par `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (requiere Postgres local
  **limpio**; falla con `MultipleResultsFound` sobre una BD sucia).

---

## 4. TRABAJO PENDIENTE — en orden

### Tarea 0 (owner, no agente): push + tag de A13

- Push de `main` (`5fcd0224`) y tag de la release A13.
- Después: verificar CI del tag (deben correr, como mínimo, `quality`, `lifecycle-pg`,
  `paper-forward-pg`, con skip = fallo).
- **No** hacer esto el agente salvo que el owner lo pida explícitamente.

### Tarea 1 — Hardening de contratos del audit V2.32.1 (pequeño, 1 commit)

Dos ítems que el audit V2.32.1 dejó como pendientes y que se acordó **no** mezclar con A13.

**H1 — `require_holdout=True` inviolable en la ruta de promoción productiva.**
Hoy `ShadowReplayConfig.require_holdout` tiene default `False`
(`strategy_shadow_phase.py:64`) y la docstring permite que el llamante entregue barras ya
recortadas. Es una API reutilizable válida, pero **para promoción** queremos una regla absoluta:
sobre la ruta de promoción, `require_holdout` debe ser **forzado a True** y `lab_end` obligatorio
(sin `lab_end` ⇒ `shadow_lab_end_ausente`, fail-closed). Nunca «confío en que el llamante ya
recortó».

- Dónde: `packages/py/application/src/bolsa_application/auto_orchestrator.py` (construcción de
  `ShadowReplayConfig` para la fase shadow) y/o el wiring del worker
  (`auto_orchestrator_worker.py`, ya pasa `shadow_require_holdout=True`).
- Criterio de hecho: existe un test que demuestra que **no hay ninguna ruta de promoción** que
  construya el replay con `require_holdout=False` ni sin `lab_end`; y que forzarlo no rompe el E2E
  A11 (`test_a11_discovery_to_auto_sim_pg.py`) ni el E2E A13.

**H2 — ampliar `bars_hash` con identidad de instrumento/timeframe/fuente.**
Hoy `_bars_hash` (`paper_forward_phase.py:262`) hashea solo `timestamp + OHLCV`. Para evidencia
institucional debe incluir además `instrument_id`, `timeframe`, `source` y `adjusted` (que dos
datasets D1 vs H1 no puedan compartir identidad de evidencia). El mismo criterio aplica al
fingerprint del shadow (`strategy_shadow_phase.py`, `_bars_hash`).

- Dónde: `paper_forward_phase.py` (`_bars_hash`, `split_forward`, `run_paper_forward`) y
  `strategy_shadow_phase.py` (hash análogo).
- Cuidado: la firma del hash cambia ⇒ **recalcular** los valores esperados en los tests de
  fingerprint existentes (`test_paper_forward_phase.py::test_paper_forward_fingerprint_is_reproducible`,
  `test_strategy_shadow_phase.py::test_shadow_replay_fingerprint_is_reproducible`). No cambies la
  semántica de «mismo dataset ⇒ mismo hash».
- Criterio de hecho: tests que demuestran que dos series con mismo OHLCV pero distinto
  `instrument_id`/`timeframe` producen `bars_hash` distinto.

> Nota: H1 y H2 pueden ir en **un solo commit** de hardening, o en dos. Mantén migraciones fuera
> (este hardening no necesita migración).

### Tarea 2 — A14 — Strategy Intelligence (fase grande)

Objetivo (del owner): ampliar Discovery desde un catálogo de familias técnicas hacia una
**gramática controlada** de definición de estrategias, evitando explosión combinatoria.

```
REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT   (máx. 2–3 componentes)
```

Requisitos duros:

- Mantener los gates antes de promocionar: **CPCV, PBO, DSR, WFE, OOS**.
- Reutilizar el motor declarativo (`rules_grid` / `rules_engine`) y el catálogo existente
  (`packages/py/application/src/bolsa_application/discovery_catalog.py`,
  `strategy_discovery_engine.py`); no crear un segundo motor ni un segundo FSM.
- Empezar por un **plan** (modo plan) antes de código: alcance de la gramática, cómo se acota la
  combinatoria (presupuesto global tipo `DiscoveryBudget`), y cómo se certifica en PG por commit.

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

# 2) Offline (usa EXACTAMENTE los --ignore del job `quality` de python-ci.yml;
#    si te los saltas, verás ~126 fallos falsos de tests que necesitan PG).
#    Copia el comando `uv run pytest ...` del job `quality`.

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
#    Copia el comando del job `lifecycle-pg` y del job `paper-forward-pg`.
```

Reglas de honestidad del repo:

- No declares verde sin haber corrido los tres bloques.
- Distingue fallos **preexistentes** (§3) de regresiones tuyas.
- No certifiques `main`/HEAD como si fuera un tag.

---

## 6. Uso sugerido de subagentes

- **explore** (medium/very thorough): mapear `discovery_catalog.py`,
  `strategy_discovery_engine.py` y el dispatch del LAB antes de diseñar A14.
- **generalPurpose**: para cambiar `_bars_hash` en **dos** módulos manteniendo semántica, o para
  redactar el plan de A14.
- **best-of-n-runner**: solo si hace falta comparar dos diseños de gramática en paralelo.
- **bugbot** / **security-review**: **solo** si el owner los pide explícitamente (en este repo se
  lanzan a petición, no por defecto).
- **ci-investigator**: si un check del tag A13 o del hardening falla y hay que diagnosticarlo.

Trabaja por **fases con aprobación** del owner (el repo commit-a-commit, con revisión). No mezcles
hardening y A14 en el mismo commit.

---

## 7. Checklist de arranque (haz esto primero)

- [ ] `git log --oneline -3` → confirmar que `5fcd0224` es HEAD o ancestro.
- [ ] `git status --short` → entender qué hay sin commitear (hay caches/`__pycache__`/logs que
      **no** son tuyos; no los metas en commits).
- [ ] Leer `docs/engineering/PROJECT_STATE.md` (columna viva) y
      `docs/engineering/audit-pack-v2.33-2026-09-11.md`.
- [ ] `cd packages/py/infrastructure && uv run alembic heads` → debe salir
      `035_paper_forward_evidence (head)`.
- [ ] Preguntar al owner: ¿Tarea 1 (hardening) o Tarea 2 (A14) primero? ¿Hay push/tag de A13?

---

## 8. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed (ausencia de evidencia ≠ aprobación) ·
migraciones aditivas sin backfill · long-only · Alembic head `035_paper_forward_evidence` ·
A13 en `5fcd0224` (local, sin push).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · certificar sin
correr los tres bloques de verificación · mezclar A13/hardening/A14 en un commit · editar el fichero
de plan `v2.33_a13_paper_forward_294d0834.plan.md`.
