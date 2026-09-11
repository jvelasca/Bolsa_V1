# Audit Pack — V2.33 / A13 (Paper Forward)

> **Para el auditor externo.** Punto de entrada para auditar la fase **Paper Forward**
> desde Git, sin acceso al entorno de desarrollo. Fecha: 2026-09-11. Tag:
> **`v2.33.0-beta`**.

## 0. Qué auditar y dónde

| Elemento                | Referencia                                                                                       |
| ----------------------- | ------------------------------------------------------------------------------------------------ |
| Tag certificado         | **`v2.33.0-beta`**                                                                               |
| Base (HEAD anterior)    | Tag `v2.32.1-beta` → `0d4c39c2`                                                                  |
| Doc de cierre (detalle) | [`cierre-v2.33-a13-paper-forward-2026-09-11.md`](./cierre-v2.33-a13-paper-forward-2026-09-11.md) |
| Fase previa (contexto)  | [`audit-pack-v2.32.1-2026-09-11.md`](./audit-pack-v2.32.1-2026-09-11.md)                         |

El **diff a revisar** es:

```
git diff v2.32.1-beta..v2.33.0-beta
```

## 1. Cómo reproducir la verificación

Requisitos: `uv` + Python 3.12. Postgres 16 **solo** para las suites de certificación.

```bash
git fetch --tags origin
git checkout v2.33.0-beta

# --- Calidad (no requiere DB) ---
uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed
uv run lint-imports --config packages/py/.importlinter                  # 4 kept, 0 broken
uv run mypy packages/py/domain/src packages/py/market/src \
           packages/py/infrastructure/src packages/py/application/src \
           apps/api-python/src --follow-imports=silent                 # Success (469 files)

# --- Tests puros del forward + worker (sin DB) ---
uv run pytest \
  packages/py/domain/tests/test_strategy_lifecycle.py \
  packages/py/application/tests/test_paper_forward_phase.py \
  apps/api-python/tests/test_auto_orchestrator_worker.py -q

# --- Certificación PG del forward (skip = fallo) ---
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
PAPER_FORWARD_PG_REQUIRED=1 \
uv run pytest apps/api-python/tests/test_a13_paper_forward_pg.py -q
# → 2 passed (sin skips)
```

Smoke de la migración aditiva:

```bash
cd packages/py/infrastructure
uv run alembic heads          # → 035_paper_forward_evidence (head)
uv run alembic upgrade head
uv run alembic downgrade -1   # → vuelve a 034; downgrade() completo
uv run alembic upgrade head
```

## 2. Matriz afirmación → punto de código → test

| ID     | Afirmación de A13                                      | Punto de código                                                          | Test que lo bloquea                                                                                                                                                     |
| ------ | ------------------------------------------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A13-01 | Forward solo sobre barras nuevas post-promoción        | `paper_forward_phase.split_forward`; `PaperForwardConfig.promoted_at`    | `test_paper_forward_phase.py::test_split_forward_keeps_only_bars_after_promotion`, `::test_paper_forward_only_uses_bars_after_promotion`                                |
| A13-02 | Sin barras nuevas ⇒ sin evidencia (fail-closed)        | `run_paper_forward` (`forward_sin_barras`)                               | `test_paper_forward_phase.py::test_paper_forward_without_new_bars_is_fail_closed`; E2E `test_a13_forward_requires_new_bars_pg`                                          |
| A13-03 | Señal desde la definición de la ACTIVE (un solo motor) | `extract_active_executable` + `rules_grid._simulate_rules_strategy`      | `test_paper_forward_phase.py::test_extract_active_executable_none_when_missing`, `::test_paper_forward_produces_contable_evidence`                                      |
| A13-04 | Guarda de muestra en round-trips cerrados              | `PaperForwardPolicy.min_closed_round_trips`                              | `test_strategy_lifecycle.py::test_paper_forward_fails_closed_without_sample`                                                                                            |
| A13-05 | DD fail-closed (métrica ausente ≠ sin riesgo)          | `PaperForwardPolicy.evaluate`                                            | `test_strategy_lifecycle.py::test_paper_forward_fails_closed_when_drawdown_missing`                                                                                     |
| A13-06 | Evidencia reproducible (fingerprint)                   | `paper_forward_phase._fingerprint_kwargs`/`_bars_hash`                   | `test_strategy_lifecycle.py::test_paper_forward_result_carries_reproducible_fingerprint`; `test_paper_forward_phase.py::test_paper_forward_fingerprint_is_reproducible` |
| A13-07 | Persistencia aditiva, sin backfill                     | migración `035_paper_forward_evidence`; `PaperForwardResultRow`          | `alembic heads`/`downgrade`; `test_strategy_lifecycle_pg.py::test_paper_forward_result_persistence_pg`                                                                  |
| A13-08 | Evidencia atribuida a la `version_id` de la ACTIVE     | store `save_forward_result`/`list_forward_results`                       | `test_a13_paper_forward_pg.py` (round-trip persistido)                                                                                                                  |
| A13-09 | Wiring AUTO OFF por defecto (reversible)               | `auto_orchestrator_worker.forward_enabled`/`_make_forward_runner`        | `test_auto_orchestrator_worker.py::test_forward_defaults_off`, `::test_forward_enabled_truthy`, `::test_start_does_not_wire_forward_when_disabled`                      |
| A13-10 | Forward tras el ciclo y antes de la vigilancia         | `auto_orchestrator_loop(forward_runner=...)`                             | `test_auto_orchestrator_worker.py::test_loop_runs_forward_between_cycle_and_watch`                                                                                      |
| A13-11 | Certificación PG obligatoria por commit (skip = fallo) | `.github/workflows/python-ci.yml` job `paper-forward-pg`                 | CI `paper-forward-pg` con `PAPER_FORWARD_PG_REQUIRED=1`                                                                                                                 |
| A13-12 | Cero caminos LIVE                                      | (invariante) `LIVE_EXECUTION_AUTHORIZED` + `LIVE_EXECUTION_UNLOCKED`     | `test_a13_paper_forward_pg.py` (0 eventos de venue LIVE)                                                                                                                |
| A13-13 | El forward no rompe el ciclo ni inventa evidencia      | `auto_orchestrator_worker._make_forward_runner` (try/except fail-closed) | `test_auto_orchestrator_worker.py` (forward runner opcional); E2E negativo                                                                                              |

## 3. Checklist de auditoría (sugerido)

- [ ] `git checkout v2.33.0-beta` y confirmar la cadena de commits respecto a
      `v2.32.1-beta`.
- [ ] Revisar `git diff v2.32.1-beta..v2.33.0-beta` fichero a fichero contra §2.
- [ ] Verificar el **fail-closed** del forward: `promoted_at` en el futuro ⇒
      `forward_sin_barras`, `passed=False`, `trades=0`; sin definición ejecutable ⇒
      `forward_sin_definicion_ejecutable`.
- [ ] Confirmar que la ventana forward **solo** usa barras con
      `timestamp > promoted_at` y que un no-fill hace **fallar** el E2E.
- [ ] Confirmar que la migración `035` es aditiva/nullable, sin backfill, con
      `down_revision = "034_shadow_dataset_fingerprint"` y `downgrade()` completo.
- [ ] Confirmar que el forward **reutiliza** `rules_grid._simulate_rules_strategy` (no
      hay un segundo motor de trading).
- [ ] Confirmar que el wiring es **OFF por defecto** y que con OFF no se persiste
      evidencia forward.
- [ ] Correr la verificación de §1 (calidad + puros + PG).
- [ ] Confirmar invariante **LIVE congelado**: 0 caminos nuevos; `AUTO ⇒ SIMULATED`.
- [ ] Revisar que el job `paper-forward-pg` usa el gate `PAPER_FORWARD_PG_REQUIRED=1`
      (un skip es fallo duro).

## 4. Invariantes congelados (no se tocan en A13)

- `AUTO ⇒ SIMULATED`; `LIVE` bloqueado por `LIVE_EXECUTION_AUTHORIZED` +
  `LIVE_EXECUTION_UNLOCKED` (ambas false). **Cero caminos LIVE nuevos.**
- COACH advisory; RiskGate / SimulationGate / Ledger / Reconciliation deterministas.
- Sin LLM en el hot path. Long-only intacto.
- Migración aditiva/nullable, sin backfill; `downgrade()` completo.

## 5. Fuera de alcance (no imputable a A13)

- Las dos mejoras de _hardening_ señaladas por la auditoría V2.32.1 y no incluidas aquí:
  (a) hacer `require_holdout=True` **inviolable** en toda ruta de promoción productiva,
  y (b) ampliar `bars_hash` con `instrument_id`/`timeframe`/`source`/`adjusted`. Se
  abordan como commit de hardening aparte.
- A14 — Strategy Intelligence (gramática controlada de Discovery). Fase posterior.

> Cierre: [`cierre-v2.33-a13-paper-forward-2026-09-11.md`](./cierre-v2.33-a13-paper-forward-2026-09-11.md)
