# Audit-pack `AUTO-8` Adaptive AUTO · slice 1 — `1.73.0-beta` (2026-09-21)

**Punto de partida:** tag **`v2.47-beta`** (`1.72.0-beta`, HEAD `cd5e3863`).
**Migración:** **NO** — Alembic head sigue en **`044_auto_cycle_trace`**.
**Bump:** `1.72.0-beta` → **`1.73.0-beta`**.
**Sonda de mutaciones:** [`apps/api-python/scripts/v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py)
(la matriz de la línea AUTO, extendida en esta pasada con M19–M21; ver §10).
**Sello:** tag anotado **`v2.48-beta`** (ver §12).

Este documento sigue la convención del repo: **lo que se midió, con el artefacto que lo produjo**. Donde algo no
se pudo medir, se declara **no medido** (no se rellena con un cero). El plan de la fase es
[`plan-v2-48-auto-8-adaptive-auto-2026-09-21.md`](./plan-v2-48-auto-8-adaptive-auto-2026-09-21.md)
y el relevo,
[`traspaso-relevo-post-v2-48-auto-8-adaptive-auto-2026-09-21.md`](./traspaso-relevo-post-v2-48-auto-8-adaptive-auto-2026-09-21.md).
Si el plan y este pack se contradicen, **manda el pack**.

---

## 0. Resumen: qué cierra esta pasada

| #   | Hallazgo / deuda                                                         | Estado  | Evidencia (medida)                                                              |
| --- | ------------------------------------------------------------------------ | ------- | ------------------------------------------------------------------------------- |
| 1   | No había capa que recomiende rotación/asignación por estrategia (AUTO-8) | CERRADO | `auto_adaptive.py` (puro) + `test_auto_adaptive.py` (17)                        |
| 2   | La recomendación Adaptive podía "decidir" en vez de recomendar           | CERRADO | `plan_v2_tick(adaptive=…)` consume como entrada; gates duros intactos (5 tests) |
| 3   | El flag OFF debía ser byte-idéntico (trampa del roadmap §10)             | CERRADO | gate 1 (`test_flag_off_payload_is_byte_identical_to_v47`)                       |
| 4   | Las mutaciones nuevas debían morder                                      | CERRADO | **M19/M20/M21** (rotación × salud, rotación × régimen, asignación monótona)     |

---

## 1. La capa pura — `auto_adaptive.py`

`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py` es **puro y read-only**: no importa
`application`, no produce órdenes, y su contrato es `AdaptivePlan.read_only = True`. Deriva la salud de la
self-evaluation de AUTO-7 (`StrategySelfEvaluation`, fills-only) y produce una **recomendación** que el motor
determinista consume.

- `StrategyHealth.from_evaluation` proyecta **solo** lo que Adaptive lee: `strategy_version`, `trades`,
  `decisive`, `expectancy_currency`, `profit_factor`, `win_rate`. Es un contrato explícito (frozen) para que la
  semántica de "salud" no se disperse entre dos shapes.
- `recommend_rotation` (reglas **deterministas y declarativas**, patrón tabla del gobernador):
  1. `adaptive_strategy_unhealthy` — salud **probadamente** negativa: `decisive` y
     (`expectancy_currency <= 0` o `profit_factor < 1`).
  2. `adaptive_strategy_regime_risk` — régimen adverso (`TREND_DOWN`/`HIGH_VOL`) y `not decisive` y
     (`win_rate is not None and win_rate < win_rate_floor`).
  3. El resto `ACTIVE`. **Sin dato ⇒ no se rota** (el desconocido no es un defecto).
- `recommend_allocation`: proporcional a la expectancy **positiva** si hay al menos una activa decisoria con
  `expectancy_currency > 0`; **uniforme `1/n`** en caso contrario. Multiplicador `share * n` acotado a `[0, 1]`
  (`_clamp_unit`: un no-número o no-finito colapsa a `0.0`).

**Disciplina de medición (lo que hace que esto valga):** una estrategia sin muestra no es "mala", es
desconocida; una pausa exige **evidencia**, no ausencia de evidencia. La asignación **solo estrecha** (techo
`1.0`) y una versión ausente del mapa equivale a `1.0` (sin estrechamiento), nunca a una pausa.

---

## 2. Flag OFF ⇒ byte-identidad

`adaptive_enabled: bool = False` en `V2Tunables`, leído de `AUTO_ENGINE_SIM_V2_ADAPTIVE` (opt-in). Con OFF:

- `plan_v2_tick(adaptive=None)` y el filtrado/asignación **no se ejecutan** (el bloque entero está tras
  `if adaptive is not None`).
- El worker **no** llama a `_v2_build_adaptive_plan` (cero I/O nuevo).
- El journal **no** publica ninguna clave `adaptive`; `V2TickPlan.adaptive` es `None`.

El gate 1 (`test_flag_off_payload_is_byte_identical_to_v47`) lo fija: con el flag OFF el payload del tick es
idéntico al de `AUTO-7`, y pasar `adaptive=None` explícitamente recorre el **mismo** camino (payloads idénticos).

---

## 3. Consumo determinista (rotación + asignación)

### 3.1 Rotación — antes del ranking

En `plan_v2_tick`, tras `entry_signals = eligible` y **antes** del ranking, las candidatas de estrategias
pausadas se descartan con el no-trade observable **`ADAPTIVE_STRATEGY_PAUSED`** (motivo nuevo en
`auto_reason_codes.py`) y el motivo de la pausa en el **detalle** del journal
(`adaptiveReason` + `adaptive` completo). Cada pausa también deja su fila de embudo `OPPORTUNITY_REJECTED`.

### 3.2 Asignación — estrechamiento del techo de riesgo

`PortfolioDecisionConfig.adaptive_risk_multiplier` (opcional) se aplica en `decide_portfolio` **solo** cuando es
`< 1.0`, sobre `max_risk_per_trade_pct` de `RiskAllocatorConfig` (`min` con el techo escalado del gobernador).
El `RiskAllocator.compute_allocation` (camino duro de sizing) y `portfolio_decision_engine.py` (vetos fail-closed)
**no se tocan**.

---

## 4. Gates del roadmap §10 (medidos)

| Gate                                                                 | Test                                                                                    |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| 1. flag OFF ⇒ byte-idéntico a AUTO-7                                 | `test_flag_off_payload_is_byte_identical_to_v47`                                        |
| 2. Adaptive no salta los gates duros (kill switch / régimen UNKNOWN) | `test_adaptive_cannot_bypass_kill_switch`, `test_adaptive_cannot_bypass_unknown_regime` |
| 3. rotación con régimen sintético                                    | `test_rotation_synthetic_regime_pauses_then_activates`                                  |
| (extra) estrechamiento del risk cap                                  | `test_allocation_narrows_risk_cap`                                                      |

`test_auto_adaptive.py` (**17**) cubre el módulo puro: reglas de rotación (salud y régimen sintético), asignación
monotónica y fallback uniforme, y proyección de `StrategyHealth`.

---

## 5. Verificación local medida (árbol final)

Comandos **exactos** de la casa. Los dos bloques offline usan el runner versionado
(`scripts/verify/offline_ci_run_yaml.py`), que **extrae los targets del YAML** y mide por **JUnit XML**.

| Comprobación                | Comando                                                                                                                        | Resultado                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| Estático (invocación de CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                                        | **All checks passed!**                          |
| Tipos                       | `uv run mypy … --follow-imports=silent`                                                                                        | **491 ficheros, 0 issues**                      |
| Fronteras                   | `uv run lint-imports --config packages/py/.importlinter`                                                                       | **4 kept / 0 broken** (610 ficheros, 3256 deps) |
| Evidencia del gobernador    | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py`                                                             | **exit 0** y `git diff` **vacío**               |
| Bloque `quality` de CI      | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                | **2200 passed, 0 failed, 0 skipped**            |
| Bloque `python` del tag     | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`            | **2211 passed, 0 failed, 0 skipped**            |
| Suites nuevas               | `uv run pytest packages/py/analytics/tests/test_auto_adaptive.py packages/py/application/tests/test_auto_adaptive_entry.py -q` | **22 passed**                                   |
| Matriz de mutaciones        | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`                                                      | **exit 0** (M19/M20/M21 muerden, árbol intacto) |

### 5.1 El delta `+22`/`+22` es la comprobación de cobertura

`quality` pasa de **2178** (`v2.47`) a **2200**; el job `python` del tag, de **2189** a **2211**. El delta es
**exactamente 22 en los dos bloques**, y su reparto es:

| Fichero                                                     | Nuevos | Vía de entrada        |
| ----------------------------------------------------------- | ------ | --------------------- |
| `packages/py/analytics/tests/test_auto_adaptive.py`         | 17     | pase de directorio    |
| `packages/py/application/tests/test_auto_adaptive_entry.py` | 5      | **registrado a mano** |
| **Total**                                                   | **22** |                       |

El fichero "registrado a mano" (`test_auto_adaptive_entry.py`) **no** entra por ningún pase de directorio: los
jobs `quality` y `python` enumeran `packages/py/application/tests` **fichero a fichero**. Se registró en **ambos**
(§8) para que el delta de los dos bloques quede **igual** (`+22/+22`), que es la comprobación de que ningún
fichero nuevo se quedó fuera de una de las dos listas.

---

## 6. Mutaciones nuevas (M19–M21) — MEDIDAS

**Sonda:** [`v2_44_mutation_audit.py`](../../apps/api-python/scripts/v2_44_mutation_audit.py), extendida con tres
mutaciones sobre `auto_adaptive.py`. Patrón de la casa: **copia en memoria**, restauración **sin** `git checkout --`,
y huella `git status --porcelain` de los ficheros tocados verificada **antes/después**.

| #       | Mutación aplicada (revertir el fix)                  | Rojos observados (medido)                                                                                                                                                                                                                   |
| ------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M19** | la estrategia probadamente negativa deja de pausarse | **4**: `test_rotation_pauses_decisive_negative_expectancy`, `test_rotation_pauses_decisive_profit_factor_below_one`, `test_build_adaptive_plan_combines_rotation_and_allocation`, `test_rotation_plan_exports_pause_reason_code_vocabulary` |
| **M20** | la pausa en régimen adverso deja de aplicarse        | **2**: `test_rotation_pauses_thin_sample_in_adverse_regime`, `test_rotation_synthetic_regime_pauses_then_activates`                                                                                                                         |
| **M21** | el multiplicador deja de acotarse a `[0, 1]`         | **2**: `test_allocation_multipliers_are_monotonic_and_bounded`, `test_allocation_proportional_to_positive_expectancy`                                                                                                                       |

**Balance: 3 de 3 mutaciones nuevas muerden**; la línea base (sin mutación) queda **verde** en todos los grupos,
cada mutación se **restaura byte a byte** (`restaurado byte a byte: si`) y la huella `git status` de los ficheros
mutados es **idéntica** antes y después (**la sonda no alteró el árbol**).

### 6.1 Nota de método: el teardown de `apps/api-python/tests` puede colgar sin PG

La mutación **M7** (pre-existente de `AUTO-4`, corre el test hermético del worker
`test_v2_optimizer_on_without_an_economic_producer_is_fail_closed`) reportó **una vez** un
`<TIMEOUT 600s>` en la corrida completa de la sonda. La causa no es el código: el teardown de
`apps/api-python/tests/conftest.py` (`purge_all_residuals`) intenta conectar a Postgres y, sin PG levantado, el
`connect` puede tardar del orden de minutos (la `FAST_FAIL_DSN` de la sonda apunta a un puerto local cerrado, pero
el `connect` no es instantáneo en todas las máquinas). La corrida **aislada** de la mutación M7 confirmó que
**muerde con 4 rojos en ~130 s** (los mismos 4 que el pack de `v2.47`), y el resto de la matriz quedó intacto. Es
un flake ambiental documentado en la propia cabecera de la sonda, **no** un defecto de esta pasada.

---

## 7. Cómo verificarlo (para el auditor)

```bash
# Estático, tipos y fronteras (invocaciones EXACTAS de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió (byte-identidad + su self-check sigue gobernando)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py   # vacío
uv run python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Los dos bloques offline de CI (targets e ignores EXTRAÍDOS del YAML, medida por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
#   => 2200 y 2211 passed, 0 skipped (base 2178/2189 → +22 en AMBOS)

# Las suites que muerden la recomendación Adaptive
uv run pytest packages/py/analytics/tests/test_auto_adaptive.py \
              packages/py/application/tests/test_auto_adaptive_entry.py -q   # 22 passed

# La matriz de mutaciones (restaura desde memoria y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # 21 mutaciones, exit 0

# La migración NO cambió (Alembic head sigue 044)
uv run alembic -c packages/py/infrastructure/alembic.ini heads        # => 044_auto_cycle_trace
```

---

## 8. Registro en CI (delta simétrico)

`test_auto_adaptive_entry.py` se registró **explícitamente** en los dos jobs, en la misma posición (entre
`test_auto_self_evaluation_feed.py` y `test_decision_journal_studies.py`):

- `.github/workflows/python-ci.yml` (`quality`)
- `.github/workflows/release-tag-ci.yml` (`python`)

El puro `test_auto_adaptive.py` entra por el pase de directorio `packages/py/analytics/tests` (presente en ambos
jobs). El **delta simétrico** `+22/+22` (ver §5.1) es la comprobación de cobertura.

---

## 9. Límites declarados (no silenciosos)

- **Salud solo de fills**: no hay migración ni backfill; lo no medido es `UNKNOWN` y una estrategia sin muestra
  **no** se rota.
- **La asignación solo estrecha** (`[0, 1]`): nunca ensancha el riesgo por operación por encima del techo del
  gobernador.
- **Sin productor de régimen nuevo**: `to_market_regime` mapea el `MarketRegime` que el worker ya calcula; un
  régimen no reconocido es `UNKNOWN` (no adverso).
- **Sin UI**: la recomendación solo es observable vía el detalle del journal.
- **`allow_distinct_strategies` y el resto de flags previos siguen como estaban** (default OFF): Adaptive no
  cambia la forma de competir dos estrategias.
- **`governor.json` sin trackear** (generado por la evidencia del gobernador).

---

## 10. Matriz de mutaciones — balance completo (21 mutaciones)

La matriz `v2_44_mutation_audit.py` conserva M1–M18 (de `AUTO-4`/`AUTO-6`/`AUTO-7`) y añade M19–M21. En la corrida
de esta pasada **M19/M20/M21 muerden** (ver §6) y la línea base queda verde; M1–M18 siguen mordiendo como en
`v2.47` (M7 con la nota de método del §6.1). La huella `git status` de los ficheros tocados es **intacta** antes y
después (`intacto: la sonda no altero el arbol`, `exit 0`).

---

## 11. Freeze (congelado, no tocar sin motivo)

- **Comportamiento de `AUTO_ENGINE_SIM_V2=0`**: debe seguir siendo `v2.39.x`.
- **Comportamiento de `AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual** y su `"bump"` se queda en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: **no** se tocan.
- **`v2.47-beta` y anteriores no se mueven**: `v2.48-beta` es **nueva y aditiva**.
- **Sin SHORT**: `entry_direction` devuelve `None` para `SELL`; ninguna ruta nueva permite entrada corta.
- **Sin migración ni backfill**: Alembic head sigue `044_auto_cycle_trace`; `NULL` en `cycle_id` = fila anterior.
- **`RiskAllocator.compute_allocation`** y **`portfolio_decision_engine.py`** (vetos fail-closed): **no** se tocan.

---

## 12. Sello

Producido localmente (2026-09-21). `package.json` → **`1.73.0-beta`**, `CHANGELOG.md` con la entrada de la fase,
docs `plan`/`pack`/`traspaso` en `docs/engineering/` y el freeze declarado (§11). El commit de fase y el tag
anotado **`v2.48-beta`** se producen al integrar el árbol; la **CI real** (Python CI + Release tag CI) se observa
entonces con `gh` (patrón del repo: el código certificado en el tag y la guía de lectura en el tip de `main`).
