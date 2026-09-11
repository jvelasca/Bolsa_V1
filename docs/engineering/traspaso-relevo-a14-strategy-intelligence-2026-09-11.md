# RELEVO — A14 · Strategy Intelligence (gramática controlada de Discovery) — 2026-09-11

> **Para el agente entrante (con sus subagentes).** Documento autocontenido: asume **cero
> contexto previo**. Léelo entero antes de tocar nada. Respeta el estilo del repo: español,
> fail-closed, sin LLM en hot path, LIVE congelado. **Esta tarea empieza por PLAN, no por código.**

---

## 0. Estado de partida (verificado en Git)

- **Base:** `main` · HEAD local **`61e613b1`** (`feat(hardening): H1+H2 ...`).
- **Ancestro inmediato:** `5fcd0224` (`feat(v2.33/A13): paper forward`) — A13 **cerrada**.
- **Alembic head:** `035_paper_forward_evidence` (head único). **A14 no debería necesitar migración**
  salvo que añadas persistencia de planes nuevos (ver §6).
- **Árbol:** limpio al cerrar esta sesión. `main` va **2 commits por delante de `origin/main`**
  (`5fcd0224`, `61e613b1`), **sin push** (paso del owner).
- **Versión:** `CHANGELOG.md` → `1.58.1-beta` (hardening H1+H2). A14 abrirá su propia entrada.

Comprobación rápida de arranque:

```bash
git log --oneline -3          # 61e613b1 (HEAD) → 5fcd0224 → f552716e
git status --short            # debe estar limpio
cd packages/py/infrastructure && uv run alembic heads   # 035_paper_forward_evidence (head)
```

---

## 1. Qué es A14 y por qué

Hoy Discovery parte de un **catálogo de Familias** técnicas (plantillas fijas con un espacio de
parámetros pequeño). A14 da el salto a una **gramática controlada**: componer una definición de
estrategia desde piezas acotadas, con un techo combinatorio duro.

```
REGIME + TREND FILTER + MOMENTUM + ENTRY TRIGGER + EXIT     (máx. 2–3 componentes)
```

**Reglas de alcance (no negociables):**

- **No** crear un segundo motor de trading ni un segundo FSM. Reutilizar el motor declarativo real.
- **No** romper los gates de promoción: **CPCV, PBO, DSR, WFE, OOS** siguen siendo la autoridad.
- La combinatoria debe estar **acotada por presupuesto** (extensión de `DiscoveryBudget`), nunca
  por un catálogo enumerado a mano.
- Determinismo total: mismos inputs ⇒ mismas candidatas, en el mismo orden.

---

## 2. Anclajes reales (rutas exactas y APIs)

### 2.1 Catálogo actual (lo que A14 amplía, no reemplaza)

`packages/py/application/src/bolsa_application/discovery_catalog.py`

- `DiscoveryFamily` (dataclass, `line ~58`) — `name`, `parent`, `param_space`, `template`,
  `min_bars_hint`, `tags`; `param_points()` (`~76`) y `iter_param_points()` (`~81`) generan los
  puntos de parámetros de forma determinista.
- Constructores de DSL de reglas: `_spec`, `_cross`, `_compare`, `_price_vs`, `_definition`.
- Plantillas actuales: `_tpl_ema_crossover` (trend), `_tpl_donchian_breakout`,
  `_tpl_supertrend_follow`, `_tpl_adx_di_trend`, `_tpl_sar_flip`, `_tpl_ichimoku_tk_cross`,
  `_tpl_rsi_reversion`, `_tpl_macd_signal_cross`, `_tpl_stoch_oversold`,
  `_tpl_stoch_rsi_reversion`, `_tpl_williams_r_reversion`, `_tpl_roc_momentum`,
  `_tpl_bb_reversion`, `_tpl_bb_breakout`.
- Ramas: `PARENT_TREND="trend"`, `PARENT_MOMENTUM="momentum"`, `PARENT_VOLATILITY="volatility"`.
- Catálogo: `DISCOVERY_FAMILIES` (`line ~479`); helpers `family_by_name`, `families_by_parent`.
- **Presupuesto:** `DiscoveryBudget` (`line ~671`) — `max_trials_total=48`, `max_per_family=8`,
  `max_candidates=24`, `min_bars=60`; `normalized()`.

### 2.2 Generador de candidatas

`packages/py/application/src/bolsa_application/strategy_discovery_engine.py`

- API pública: `discover_candidates`, `discover_for_instrument`, `discover_from_universe`.
- `discover_for_instrument(...)`: reparto **determinista** del presupuesto (recorre el catálogo en
  orden; cada familia aporta ≤ `max_per_family` hasta agotar `max_trials_total`/`max_candidates`);
  `bar_count` descarta familias cuyo `min_bars_hint` no quepa (anti «sin trials»).

### 2.3 Motor declarativo (el ÚNICO válido)

`packages/py/analytics/src/bolsa_analytics/optimize/rules_grid.py`

```python
_simulate_rules_strategy(bars, definition, *, initial_cash,
                         trade_from_index, attach_round_trips, execution_model="next_open")
```

- Causalidad estricta `index-1 → open(index)` (sin look-ahead).
- Fases que ya lo consumen: `strategy_lab_phase.py`, `strategy_shadow_phase.py`
  (`run_shadow_replay`), `paper_forward_phase.py` (`run_paper_forward`).

### 2.4 Gates de promoción (no tocar su semántica)

- Dominio: `packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`.
- Aplicación: `optimization_runs.py`, `optimize.py`, `research_evidence.py`,
  `paper_lab_evidence.py`, `strategy_lab_phase.py`, `strategy_top3_coach_phase.py`.
- El Promotion Gate exige **evidencia ejecutada** (shadow con hold-out estricto, ya inviolable
  tras H1) y **forward** (A13). A14 no relaja nada de esto.

### 2.5 Orquestador y wiring

- `packages/py/application/src/bolsa_application/auto_orchestrator.py` — `OrchestratorDeps`,
  `_make_discovery_runner`/`auto_orchestrator_loop`; flag `AUTO_ORCHESTRATOR_DISCOVERY` (default
  **OFF**) con presupuesto por env.
- `apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py` — `_make_discovery_runner`,
  `_default_orchestrator`, gates `AUTO_ORCHESTRATOR_*`.

### 2.6 Invariantes de hardening ya cerrados (NO regresar)

- **H1**: `AutoOrchestrator._run_shadow` fuerza `require_holdout=True`; `OrchestratorDeps` **no**
  tiene `shadow_require_holdout`; sin `lab_end` demostrable no hay replay (fail-closed).
- **H2**: `ShadowReplayConfig`/`PaperForwardConfig` llevan
  `instrument_id`/`timeframe`/`source`/`adjusted`; la identidad entra en el `bars_hash`
  (`_bars_hash(window, identity)` en ambas fases). Cualquier definición nueva que produzca
  evidencia debe propagar esta identidad.

---

## 3. Invariantes que NO se tocan (violarlos = fallo de la tarea)

- `AUTO ⇒ SIMULATED`. `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`
  (ambas false). **Cero caminos LIVE nuevos.**
- RiskGate / SimulationGate / Ledger / Reconciliation **deterministas**; **sin LLM en hot path**
  (la IA solo research/advisory).
- **Fail-closed:** ausencia de evidencia ≠ aprobación.
- Migraciones **aditivas/nullables, sin backfill**, con `downgrade()` completo.
- Long-only intacto. `PAPER_D_EXECUTE` off por defecto.
- Un solo motor de trading y un solo FSM.

---

## 4. Entregable de esta fase: PRIMERO EL PLAN

**No escribas código hasta que el owner apruebe el plan.** El plan (modo plan) debe cubrir:

1. **Alcance de la gramática**
   - Vocabulario de componentes (REGIME / TREND FILTER / MOMENTUM / ENTRY TRIGGER / EXIT).
   - Qué se combina con qué (compatibilidades y vetos), y el techo de **2–3 componentes**.
   - Cómo se representa la definición compuesta en el DSL existente (`_spec`/`_cross`/...): ¿es una
     composición de los bloques actuales o hacen falta primitivas nuevas? Justifícalo.
2. **Acotación de la combinatoria**
   - Extensión de `DiscoveryBudget` (o un `GrammarBudget` que lo envuelva) con techo duro y
     reparto determinista por componente.
   - Orden de enumeración estable y criterio de corte (nunca “explosión”, nunca aleatorio).
   - Estimación cuantitativa: nº de combinaciones por instrumento con el presupuesto por defecto.
3. **Integración sin segundo motor**
   - Cómo `discover_for_instrument`/`discover_candidates` emiten candidatas gramaticales sin
     romper las familias actuales (¿coexisten? ¿se sustituyen? ¿tras un flag?).
4. **Gates intactos**
   - Cómo fluyen las candidatas nuevas por LAB → gates (CPCV/PBO/DSR/WFE/OOS) → shadow → forward,
     reutilizando las fases existentes.
5. **Certificación por commit**
   - Qué test **PG** certifica A14 end-to-end (patrón de `test_a13_paper_forward_pg.py` y
     `test_a11_discovery_to_auto_sim_pg.py`), y si requiere migración.
   - Batería hermética mínima (unittest de la gramática, determinismo, techo combinatorio).

**Formato de entrega del plan:** el owner usa fases con **aprobación**. Presenta el plan y **para**.

---

## 5. Cómo verificar SIEMPRE (paridad con CI)

```bash
# 1) Calidad
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent

# 2) Offline: copia EXACTAMENTE el comando `uv run pytest ...` del job `quality`
#    de .github/workflows/python-ci.yml (incluye los --ignore). Si te los saltas,
#    verás ~126 fallos falsos de tests que necesitan PG.

# 3) PG de certificación (Postgres 16 local)
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
#    Copia los comandos de los jobs `lifecycle-pg` y `paper-forward-pg` (PAPER_FORWARD_PG_REQUIRED=1,
#    STRATEGY_LIFECYCLE_PG_REQUIRED=1, AUTO_ORCHESTRATOR_PG_REQUIRED=1, LIFECYCLE_PG_REQUIRED=1).
```

Baseline de referencia (última corrida verde de la sesión anterior):

- ruff **0**, lint-imports **4 KEPT / 0 broken**, mypy **469 files Success**.
- `apps/api-python` offline: **201 passed / 0 failed**.
- `packages/py`: **2276 / 2278** (los 2 que fallan son **preexistentes**, ver §7).
- PG certificación: verde sin skips.

**Reglas de honestidad del repo:**

- No declares verde sin haber corrido los tres bloques.
- Distingue fallos **preexistentes** (§7) de regresiones tuyas.
- No certifiques `main`/HEAD como si fuera un tag.
- Inspecciona el `git status` antes de commitear: hay caches/`__pycache__`/logs que **no** son tuyos.

---

## 6. Persistencia (solo si el plan la necesita)

Si A14 requiere persistir algo nuevo (p. ej. el plan gramatical o su procedencia), entonces:

- Migración **aditiva/nullable, sin backfill**, `down_revision = "035_paper_forward_evidence"`,
  con `downgrade()` completo.
- Añadir el modelo a `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`
  y el store a `strategy_lifecycle_store.py` (InMemory + Postgres).
- Actualizar el head esperado en CI/docs.

Si **no** hace falta persistencia, deja el head en `035` y dilo explícitamente en el cierre.

---

## 7. Deuda conocida (NO introducida por ti — no confundir)

Preexistente del baseline, ajena a A14 (confirmada fallando en `5fcd0224` y en `61e613b1`):

- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` (2 tests de carga 500+500;
  el invariante de orden por `(executed_at, id)` se rompe por empates de timestamp a alta
  concurrencia — el invariante contable Σ ledger == cash **sí** es correcto).

Ya **saldados** en `61e613b1` (no volver a “arreglarlos”): `test_scheduler_worker` (set con
`start_auto_orchestrator`), `test_queue_poll_worker::test_run_con_arq_es_noop` (raíz:
`alembic/env.py` con `disable_existing_loggers=False`), y el invariante de equity del test A9
(aporta `closed_pnl` desde el libro de fills `sim_fill_finance_context`).

---

## 8. Freeze (copiar en cualquier sesión)

`AUTO ⇒ SIMULATED` · LIVE bloqueado (`LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED` false) ·
`PAPER_D_EXECUTE` off · sin LLM en hot path · fail-closed (ausencia de evidencia ≠ aprobación) ·
migraciones aditivas sin backfill · long-only · **un solo motor/FSM** ·
Alembic head `035_paper_forward_evidence` · HEAD `61e613b1` (local, sin push) ·
hardening H1+H2 cerrado (no regresar).

**No hacer:** tocar las barreras LIVE · añadir un segundo motor de trading/FSM · crear un catálogo
enumerado en lugar de una gramática acotada · relajar los gates CPCV/PBO/DSR/WFE/OOS · certificar
sin correr los tres bloques · mezclar A14 con el hardening ya cerrado · editar el fichero de plan
`v2.33_a13_paper_forward_294d0834.plan.md`.

---

## 9. Primeros pasos concretos (orden sugerido)

1. `git log --oneline -3` y `git status --short` → confirmar `61e613b1` como HEAD y árbol limpio.
2. Leer `discovery_catalog.py` y `strategy_discovery_engine.py` **completos** (son el material de
   partida de la gramática).
3. Mapear cómo `strategy_lab_phase.py` consume las candidatas y dónde viven los gates.
4. Redactar el **plan de A14** (§4) y presentarlo al owner. **Parar y esperar aprobación.**
5. Solo tras aprobación: implementar por fases pequeñas, con la batería de §5 en cada commit.
