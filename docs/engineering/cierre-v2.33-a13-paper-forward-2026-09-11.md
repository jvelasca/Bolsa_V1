# Cierre V2.33 / A13 — Paper Forward (ACTIVE → forward P&L → vigilancia) (2026-09-11)

Version: `v2.33.0-beta`. Alcance: cerrar el salto de **validación histórica** (shadow sobre
hold-out del LAB, V2.32/A12) a **validación forward** (mercado nuevo posterior a la
promoción). No hay P0. La arquitectura no cambia, `LIVE` permanece **congelado** (no se
toca `LIVE_EXECUTION_AUTHORIZED` ni `LIVE_EXECUTION_UNLOCKED`, ni se añade camino LIVE) y
`AUTO` sigue **SIM-only**. Se reutiliza la infraestructura paper existente; no se crea un
segundo motor de trading.

---

## 0. Qué problema cierra A13

V2.32/A12 dejó la evidencia de una estrategia en su forma **histórica**:

    FINALISTA ──▶ SHADOW sobre hold-out del LAB ──▶ PROMOTION ──▶ ACTIVE

Eso responde a «¿habría funcionado con datos que no vio?», pero NO a «¿cómo se comporta
de verdad, con mercado nuevo, después de promocionarla?». A13 añade esa segunda pregunta:

    ACTIVE ──▶ barras NUEVAS (post-promoción) ──▶ señal propia ──▶ fills paper
           ──▶ posición ──▶ SL/T1/T2/trail ──▶ P&L FORWARD ──▶ VIGILANCIA

Sin dinero real: la ejecución permanece en el carril paper/SIM.

---

## 1. Forward paper determinista y fail-closed

`packages/py/application/src/bolsa_application/paper_forward_phase.py` (nuevo):

- `run_paper_forward(active=..., bars=..., policy=..., config=...)` ejecuta la
  **definición ejecutable de la ACTIVE** con el **mismo** motor declarativo que el
  LAB/shadow (`_simulate_rules_strategy` sobre `StrategyDefinitionV1`, causalidad
  `index-1 → open(index)`, `attach_round_trips=True`). No hay un motor paralelo: la señal
  del forward es exactamente la que ejecutaría el AUTO.
- `split_forward(bars, promoted_at=...)` deja pasar SOLO barras con
  `timestamp > promoted_at`. Un timestamp ausente no se asume mercado nuevo.
- `PaperForwardConfig(initial_cash, window_bars, min_bars, promoted_at, config_hash)`.
- Motivos explícitos de denegación: `forward_sin_definicion_ejecutable`,
  `forward_sin_barras`, `forward_replay_fallido`.

Fail-closed: sin definición ejecutable, sin barras nuevas o sin operaciones ⇒
`passed=False`. Nunca se lanza por falta de evidencia (un fallo del forward es un
resultado, no una excepción que rompa el ciclo).

---

## 2. Dominio

`packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py`:

- `PaperForwardResult`: métricas forward (trades, `round_trips`, `fills`, retorno, DD,
  win-rate), veredicto `passed`/`reasons`, vetos de gates y fingerprint reproducible
  (`forward_start`/`forward_end`/`bars_hash`/`strategy_definition_hash`/
  `engine_version`/`config_hash`/`data_snapshot_id`) más la barrera temporal
  `promoted_at`.
- `PaperForwardPolicy`: guarda de muestra `min_closed_round_trips` (operaciones
  **cerradas**, misma semántica que el shadow), `min_bars`, `min_return_pct` (mínimo) y
  `max_drawdown_pct` (techo). Fail-closed: con techo de DD configurado y métrica ausente
  ⇒ `forward_drawdown_ausente` (no se asume «sin riesgo»).

---

## 3. Persistencia

- Nueva migración
  `packages/py/infrastructure/alembic/versions/035_paper_forward_evidence.py`
  (`down_revision = "034_shadow_dataset_fingerprint"`): tabla `paper_forward_results`,
  **aditiva**, sin tocar tablas previas, sin backfill (no había evidencia forward), con
  `downgrade()` completo y guards idempotentes offline-safe.
- `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py`:
  `PaperForwardResultRow`.
- `packages/py/application/src/bolsa_application/strategy_lifecycle_store.py`:
  `save_forward_result`/`list_forward_results` en el Protocol, el doble InMemory y el
  store Postgres. La evidencia queda **atribuida** a la `version_id` de la ACTIVE.

`alembic heads` ⇒ `035_paper_forward_evidence` (head único).

---

## 4. Wiring del AUTO (default OFF, reversible)

`apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py`:

- `AUTO_ORCHESTRATOR_FORWARD=1` (default **OFF**) habilita el forward en el bucle:
  tras `run_cycle` y antes de `watch_active` se ejecuta y persiste la evidencia forward
  de la ACTIVE (`AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS`, default 400).
- Con OFF, el comportamiento es **idéntico** a V2.32.1: ni se lee ni se persiste
  evidencia forward.
- Un fallo del forward (lectura o persistencia) **no** tumba la vigilancia: se loguea y
  el ciclo continúa (fail-closed, sin inventar evidencia).

---

## 5. Certificación PostgreSQL por commit

- `apps/api-python/tests/test_a13_paper_forward_pg.py` (nuevo E2E, PG real):
  1. Promociona una ACTIVE por el camino A12 real (reutiliza el orquestador con shadow).
  2. **Caso negativo**: sin barras nuevas post-promoción ⇒ `forward_sin_barras` y
     `passed=False` (nunca un P&L inventado).
  3. Siembra mercado **nuevo** posterior a la promoción y ejecuta el forward: exige
     `trades > 0`, `round_trips > 0`, `forward_start > promoted_at`, `bars_hash`, y
     `engine_version == "paper-forward/2.33.0"`. Un no-fill es un **FALLO** duro.
  4. Persiste y relee la evidencia (atribución a la `version_id`).
  5. La vigilancia sigue operando y **cero** publicaciones al bridge LIVE.
- `.github/workflows/python-ci.yml`: nuevo job **`paper-forward-pg`** (per-commit) con
  `postgres:16-alpine`, `alembic upgrade head` y gate `PAPER_FORWARD_PG_REQUIRED=1`
  (un skip es fallo duro). El E2E se `--ignore`d en el job offline (sin PG), igual que
  el A11 E2E.

---

## 6. Invariantes que NO se tocan

- `AUTO ⇒ SIMULATED`; LIVE bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- COACH advisory; RiskGate / SimulationGate / Ledger / Reconciliation deterministas.
- Sin LLM en el hot path. Long-only intacto.
- Fail-closed: sin barras nuevas no hay evidencia forward; sin fill no se declara P&L.
- Migración aditiva/nullable, sin backfill; `downgrade()` completo.

---

## 7. Verificación (reproducible)

```
uv run ruff check packages/py apps/api-python --config pyproject.toml   → All checks passed
uv run lint-imports --config packages/py/.importlinter                  → 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 → Success (469 files)
```

Tests puros/herméticos nuevos:

- `packages/py/domain/tests/test_strategy_lifecycle.py` (V2.33):
  `test_paper_forward_policy_passes_with_evidence`,
  `test_paper_forward_fails_closed_without_bars`,
  `test_paper_forward_fails_closed_without_sample`,
  `test_paper_forward_fails_closed_when_drawdown_missing`,
  `test_paper_forward_result_carries_reproducible_fingerprint`,
  `test_paper_forward_result_records_vetoes`.
- `packages/py/application/tests/test_paper_forward_phase.py` (11 tests): extracción,
  partición temporal, fail-closed, evidencia contable, determinismo, fingerprint.
- `apps/api-python/tests/test_auto_orchestrator_worker.py` (V2.33):
  `test_forward_defaults_off`, `test_forward_enabled_truthy`,
  `test_forward_window_bars_default_and_override`,
  `test_loop_runs_forward_between_cycle_and_watch`,
  `test_start_does_not_wire_forward_when_disabled`.

Suite de certificación PG (`paper-forward-pg`), local contra Postgres:

```
PAPER_FORWARD_PG_REQUIRED=1 \
uv run pytest apps/api-python/tests/test_a13_paper_forward_pg.py -q
→ 2 passed (sin skips)
```

Round-trip del store (incluido en `test_strategy_lifecycle_pg.py`):
`test_paper_forward_result_persistence_pg` → evidencia persistida y releída sin pérdida.

---

## 8. Por qué esto cierra A13

Antes: la única evidencia de una estrategia era histórica (shadow). Ahora existe también
evidencia **forward**: la ACTIVE se mide sobre mercado nuevo posterior a la promoción,
con fills paper reales, P&L atribuido a su `version_id` y fingerprint reproducible, y
todo ello se certifica en cada push contra PostgreSQL real sin skips. El sistema sigue
SIM-only, con LIVE intacto.
