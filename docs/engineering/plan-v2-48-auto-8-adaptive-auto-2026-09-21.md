# Plan de fase — `AUTO-8` Adaptive AUTO · slice 1 (`V2.48`, `1.73.0-beta`)

**Fecha:** 2026-09-21 · **Punto de partida:** tag **`v2.47-beta`** (`1.72.0-beta`), HEAD `cd5e3863`
(traspaso de `V2.47`). **Migración:** **NO** — Alembic head sigue en **`044_auto_cycle_trace`**.
**Bump:** `1.72.0-beta` → **`1.73.0-beta`**. **Sello:** tag anotado **`v2.48-beta`** (ver §8.2).

Este plan es la **orden de trabajo** de la fase; el pack de evidencia es
[`audit-pack-v2.48-auto-8-adaptive-auto-2026-09-21.md`](./audit-pack-v2.48-auto-8-adaptive-auto-2026-09-21.md)
y el relevo es
[`traspaso-relevo-post-v2-48-auto-8-adaptive-auto-2026-09-21.md`](./traspaso-relevo-post-v2-48-auto-8-adaptive-auto-2026-09-21.md).
Si el plan y el pack se contradicen, **manda el pack** (el plan dice lo que se iba a hacer; el pack, lo que se midió).

---

## 0. Decisiones del owner

1. **Adaptive recomienda, el motor determinista decide.** `AUTO-8` slice 1 es una capa **pura y read-only**
   que produce una **recomendación** (`AdaptivePlan`) consumida por `plan_v2_tick` como **entradas** — pausando
   candidatas antes del ranking y estrechando el techo de riesgo por estrategia. **Nunca `AI → BUY`.**
2. **Salud solo de fills** (`PnL realizado`, `expectancy`, `win rate`, `profit factor`, `drawdown`), reusando la
   self-evaluation de `AUTO-7` (fills-only). Lo no medido se declara `UNKNOWN`: una estrategia sin muestra no es
   "mala", es **desconocida**, y el desconocido **no se pausa a ciegas**.
3. **Flag OFF ⇒ byte-identidad.** `adaptive_enabled` default **OFF**; con OFF el payload del tick es idéntico a
   `AUTO-7` (cero I/O nuevo, cero claves `adaptive` en el journal). Es la misma disciplina que el resto de flags
   de la línea AUTO.
4. **Los gates duros son intocables.** La recomendación Adaptive **no** puede saltarse el gobernador, el kill
   switch, el `RiskGate`/`Simulation Gate` ni el sizing de `RiskAllocator`. El multiplicador solo **estrecha**
   (`[0, 1]`), nunca ensancha.

---

## 1. Invariante que instala

> _Adaptive recomienda — por salud de estrategia (solo fills) y régimen — qué versiones pausar y cuánto estrechar
> el riesgo por estrategia; el motor determinista decide si opera, con el gobernador, el kill switch y el sizing
> intactos. Con el flag OFF, el sistema es byte-idéntico al de la fase anterior._

---

## 2. Qué NO cambia (freeze)

- **`AUTO_ENGINE_SIM_V2=0`**: comportamiento `v2.39.x` intacto.
- **`AUTO_ENGINE_SIM_V2_GOVERNOR=0`**: byte-idéntico a `v2.43.1` **sin parada dura**.
- **`v2_43_governor_evidence.py`**: **byte a byte igual**, `exit 0`, su `"bump"` conservado en `1.68.0-beta`.
- **Tabla del gobernador y sus umbrales**: no se tocan.
- **`v2.47-beta` y anteriores no se mueven**: `v2.48-beta` es **nueva y aditiva**.
- **Sin SHORT**: ninguna ruta nueva permite entrada corta; `entry_direction` devuelve `None` para `SELL`.
- **Sin migración**: Alembic head sigue `044_auto_cycle_trace`; **sin backfill**.
- **`governor.json` sin trackear** (lo genera `v2_43_governor_evidence.py --out`; no se añade a ningún commit).

---

## 3. Piezas (qué se extiende, no qué se reinventa)

### 3.1 Módulo puro nuevo — `auto_adaptive.py`

`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py`, **puro y read-only** (no importa
`application`, no produce órdenes):

- `StrategyHealth` (frozen/slots): proyección de `StrategySelfEvaluation` con **solo** lo que Adaptive consume
  (`strategy_version`, `trades`, `decisive`, `expectancy_currency`, `profit_factor`, `win_rate`). `from_evaluation`
  es la única forma de construirlo.
- `recommend_rotation(by_strategy, regime) -> RotationPlan` — reglas **deterministas y declarativas**:
  1. `PAUSED` con `adaptive_strategy_unhealthy` si `decisive` y (`expectancy_currency <= 0` o `profit_factor < 1`).
  2. `PAUSED` con `adaptive_strategy_regime_risk` si `regime ∈ {TREND_DOWN, HIGH_VOL}` y `not decisive` y
     (`win_rate is not None and win_rate < win_rate_floor`).
  3. El resto `ACTIVE` (sin dato ⇒ no se rota).
- `recommend_allocation(active, by_strategy) -> AllocationPlan`: entre estrategias `ACTIVE`; proporcional a la
  expectancy positiva si hay al menos una decisoria con `expectancy_currency > 0`, y **uniforme `1/n`** en caso
  contrario (fail-safe). El multiplicador es `share * n` acotado a `[0, 1]` (**solo estrecha**).
- `build_adaptive_plan(by_strategy, regime) -> AdaptivePlan`: compone rotación + asignación + régimen.

### 3.2 Flag de configuración

- `adaptive_enabled: bool = False` en `V2Tunables` + `AUTO_ENGINE_SIM_V2_ADAPTIVE` en `tunables_from_env()`.
- `adaptive_win_rate_floor: float = 0.35` + `AUTO_ENGINE_SIM_V2_ADAPTIVE_WIN_RATE_FLOOR`, saneado **fail-closed en
  bloque** (`_adaptive_env_overrides`): solo se acepta un número finito en `(0, 0.5]`; cualquier otro valor
  descarta el env y queda el default declarado.

### 3.3 Cableado en `plan_v2_tick`

- Nuevo parámetro `adaptive: AdaptivePlan | None = None` (último, con default `None`).
- **Rotación**: tras `entry_signals = eligible` y **antes** del ranking, filtrar las candidatas cuyo
  `strategy_version` esté `PAUSED`; journalizar cada una con `adaptive_strategy_paused` (motivo nuevo en
  `auto_reason_codes.py`) y su fila de embudo `OPPORTUNITY_REJECTED`. Con `adaptive is None` no se ejecuta nada.
- **Asignación**: en el bucle de decisión, `PortfolioDecisionConfig.adaptive_risk_multiplier` estrecha el
  `max_risk_per_trade_pct` solo cuando el multiplicador es `< 1.0` (`min` con el techo del gobernador). El
  `RiskAllocator` (camino duro) sigue aplicando capital, buying power, stop y coste sin cambios.
- **Byte-identidad OFF**: `V2TickPlan.adaptive` default `None`; el journal solo añade claves `adaptive` cuando
  `adaptive is not None` **y** hay estrechamiento que declarar (mismo patrón que `optimizer`).

### 3.4 Worker pasa el `AdaptivePlan`

En `_v2_plan_tick`: si `cfg.adaptive_enabled`, construir la recomendación con `_v2_build_adaptive_plan` —lee los
fills de las versiones observadas con el `SimFillFinanceContextStore` que el worker ya usa, llama
`build_auto_self_evaluation(fills=...)` y luego `build_adaptive_plan`— y pasarla a `plan_v2_tick(adaptive=...)`.
Con el flag OFF (o sin store) se pasa `None` (**cero I/O nuevo**); un fallo de lectura devuelve `None`
(fail-closed: sin salud medible no se rota ni se estrecha nada).

### 3.5 Gates y tests

- `packages/py/analytics/tests/test_auto_adaptive.py` (puro, **17**): reglas de rotación (salud y régimen
  sintético), asignación monotónica y fallback uniforme, proyección de `StrategyHealth`.
- `packages/py/application/tests/test_auto_adaptive_entry.py` (**5**): los **tres gates del roadmap §10** —
  1. flag OFF ⇒ `plan_v2_tick` byte-idéntico a AUTO-7; 2. ninguna recomendación adaptativa salta los gates duros
     (kill switch / régimen UNKNOWN); 3. rotación con régimen sintético — más el estrechamiento del risk cap.
- **Registro explícito en CI**: `test_auto_adaptive_entry.py` en `.github/workflows/python-ci.yml` (`quality`) y
  `.github/workflows/release-tag-ci.yml` (`python`), con **delta simétrico**. Mutaciones **M19/M20/M21** en
  `apps/api-python/scripts/v2_44_mutation_audit.py`.

### 3.6 Versión, changelog y sello

- `package.json` línea 3 → `1.73.0-beta`; entrada nueva en `CHANGELOG.md`.
- Docs de fase `plan` + `audit-pack` + `traspaso-relevo` en `docs/engineering/`, con el freeze declarado.

---

## 4. Gate (lo que mide el roadmap)

| Roadmap                                               | Cómo se mide aquí                                                                                         |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| §10 `AUTO-8` — "Adaptive recomienda, el motor decide" | Flag OFF byte-idéntico + Adaptive no salta los gates duros + rotación con régimen sintético + M19/M20/M21 |

---

## 5. Criterios de salida

1. `ruff` / `mypy` / `lint-imports` limpios con las invocaciones **de CI**.
2. Los dos bloques offline (targets **extraídos del YAML**) verdes, con **delta simétrico** y los ficheros nuevos
   dentro de la red.
3. Matriz de mutaciones **medida** (incluye M19/M20/M21) y árbol **intacto** al terminar la sonda.
4. `v2_43_governor_evidence.py`: `git diff` vacío y `exit 0`.
5. Flag OFF ⇒ payload byte-idéntico (gate 1); Adaptive no salta los gates duros (gate 2); rotación sintética verde
   (gate 3).
6. Bump `1.73.0-beta` + CHANGELOG + docs de fase + sello con freeze declarado.

---

## 6. Límites previstos (declarar, no maquillar)

- **La recomendación no migra ni rellena huecos**: la salud se deriva **solo de fills**; lo no medido es
  `UNKNOWN` y una estrategia sin muestra **no** se rota.
- **La asignación solo estrecha**: el multiplicador vive en `[0, 1]`; una estrategia sin expectancy positiva
  recibe `0` (no compite por presupuesto de riesgo), y nadie se ensancha por encima del techo del gobernador.
- **No hay productor de régimen nuevo**: `to_market_regime` mapea el `MarketRegime` del gobernador que el worker
  ya calcula; un régimen no reconocido se trata como `UNKNOWN` (no adverso).
- **Sin UI** en esta fase (la recomendación es invisible salvo el detalle del journal).

---

## 7. Estado de ejecución (cerrado 2026-09-21)

| Pieza (id)     | Estado | Dónde se ve                                                                               |
| -------------- | ------ | ----------------------------------------------------------------------------------------- |
| `pure-module`  | HECHO  | `auto_adaptive.py` (rotación + asignación puras) + `test_auto_adaptive.py` (17)           |
| `flag`         | HECHO  | `adaptive_enabled` + `AUTO_ENGINE_SIM_V2_ADAPTIVE(_WIN_RATE_FLOOR)` con saneo fail-closed |
| `wire-entry`   | HECHO  | `plan_v2_tick(adaptive=…)` (filtrado pre-ranking + estrechamiento del risk cap)           |
| `worker`       | HECHO  | `_v2_build_adaptive_plan` desde fills; OFF ⇒ `None` (cero I/O)                            |
| `journal`      | HECHO  | `ADAPTIVE_STRATEGY_PAUSED` + fila de embudo; claves `adaptive` solo con Adaptive activo   |
| `tests`        | HECHO  | `test_auto_adaptive.py` (17) + `test_auto_adaptive_entry.py` (5) + CI + M19/M20/M21       |
| `version-seal` | HECHO  | `1.73.0-beta` + CHANGELOG + docs plan/pack/traspaso + freeze declarado                    |

### 7.1 Desviaciones declaradas frente a lo que este plan decía

1. **`recommend_allocation` firma sin `n_active`.** El plan (§1) describía
   `recommend_allocation(active, by_strategy, n_active)`; la implementación deriva `n = len(rows)` de las filas
   activas observadas (no de un parámetro externo), para que la asignación **no** dependa de un conteo que el
   llamante podría discrepar del conjunto real. El contrato resultante (multiplicador `share * n` en `[0, 1]`) es
   el mismo que pedía el plan.
2. **`adaptive_win_rate_floor` como tunable de `V2Tunables`** (no solo `_governor_env_overrides`): el suelo viaja
   en `V2Tunables.adaptive_win_rate_floor` y el saneo fail-closed vive en `_adaptive_env_overrides`. El patrón es
   el del gobernador, adaptado a un umbral único.
3. **El suelo de win rate se sanea a `(0, 0.5]`** (no `(0, 1]`): un suelo por encima de `0.5` pausaría casi todo
   en régimen adverso, y un suelo `0` o negativo pausaría muestras anecdóticas buenas; ambos se declaran
   incoherentes y descartan el env.

### 7.2 Límites (confirmados al ejecutar)

Los de §6. Además: `ADAPTIVE_STRATEGY_PAUSED` es el **no-trade observable** (el operador ve QUÉ se pausó) y el
motivo de la pausa (`adaptive_strategy_unhealthy`/`adaptive_strategy_regime_risk`) viaja en el **detalle** del
journal; la casa única del literal de pausa es `auto_reason_codes.py`. El multiplicador `risk_multiplier_for`
de una versión ausente del mapa es `1.0` (ausencia ≠ pausa: "no hubo nada que estrechar").

---

## 8. Verificación (cada cifra, con el artefacto que la produjo)

| Comprobación             | Comando (invocación de CI)                                                                                                     | Resultado                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------- |
| Estático                 | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                                        | **All checks passed!**                         |
| Tipos                    | `uv run mypy … --follow-imports=silent`                                                                                        | **491 ficheros, 0 issues**                     |
| Fronteras                | `uv run lint-imports --config packages/py/.importlinter`                                                                       | **4 kept / 0 broken**                          |
| Evidencia del gobernador | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py`                                                             | **exit 0** y `git diff` **vacío**              |
| Bloque `quality` de CI   | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`                | **2200 passed, 0 skipped**                     |
| Bloque `python` del tag  | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`            | **2211 passed, 0 skipped**                     |
| Suites nuevas            | `uv run pytest packages/py/analytics/tests/test_auto_adaptive.py packages/py/application/tests/test_auto_adaptive_entry.py -q` | **22 passed**                                  |
| Matriz de mutaciones     | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py`                                                      | **exit 0**, M19/M20/M21 muerden, árbol intacto |

### 8.1 Matriz de mutaciones

**MEDIDA**: sonda `v2_44_mutation_audit.py` extendida con **M19/M20/M21** (rotación por salud, rotación por
régimen, asignación monótona). Las tres muerden y la huella `git status` de los ficheros tocados queda **intacta**
(detalle por mutación en el §10 del pack).

### 8.2 Sello

Producido. `package.json` → **`1.73.0-beta`**, `CHANGELOG.md` con la entrada de la fase, docs `plan`/`pack`/
`traspaso` en `docs/engineering/` y el **freeze declarado** (§2). El commit de fase y el tag anotado
**`v2.48-beta`** se producen al integrar el árbol (ver el §12 del pack).
