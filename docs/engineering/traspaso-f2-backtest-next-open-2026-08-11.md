# Traspaso — F2 Rigor científico del backtest (fill next_open) (2026-08-11)

> **Padre único:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) §16 (sub-entrada de la Auditoría consolidada, junto a F1).
> **Fuentes de verdad (leer primero):** plan F2 (`.cursor/plans/f2_rigor_cientifico_backtest_next_open_8b76de60.plan.md`, micro-cambios A–F) · `audit-consolidado-internas-externas-2026-08-11.md` (P0.1/P0.2 + D0–D5) · [traspaso-f1-integridad-financiera-2026-08-11.md](./traspaso-f1-integridad-financiera-2026-08-11.md) (cierre F1).
> **Rama de ejecución:** `stage/f2-backtest-next-open-2026-08-11`, creada desde `3c59dc8` (HEAD/corte de F1, decisión del usuario). Rama `stage/f1-*` se mantiene como base (no fusionar/borrar por ahora).
> **Regla del hilo:** NO tocar código fuera de F2. Cada micro-cambio A–F atómico se valida con la batería (ruff+mypy+pytest) antes de commit. Los commits quedan **pendientes de aprobación** del usuario (norma F1 §8: aprobación previa a cada commit).
> **Estado:** F2 **IMPLEMENTADO 2026-08-11** ✅ (A–F, working tree verde). **Commits sin crear todavía — pendientes de aprobación del usuario.** Ver §7.

---

## 1. Objetivo de F2

Eliminar el **look-ahead/same-bar** en los 5 simuladores (P0.1) aplicando fill en `open[t+1]` (`next_open`) como execución inmutable para 1D con un `execution_model` explícito; reforzar el fingerprint OHLCV completo (P0.2); añadir el test anti-lookahead; y un script de recálculo idempotente de trials/resultados históricos (CORE-R · Finalistas · Lista AUTO · DÍA D). Cero features (D5).

## 2. Diagnóstico confirmado en código (FASE 1)

Los 5 simuladores llenaban con el **cierre de la misma barra** donde nace la señal (señal en `t` usa datos hasta `t`, pero ejecuta a `t`) → sesgo `next_open`. Se corrige en: `run_backtest`, grids H0 SMA/RSI/MACD (`_simulate_*`), `vectorbt_sma`, `optuna_sma`.

## 3. Decisiones pactadas (no renegociar)

- **D0** orden F1 → F2 → F3b → F5a → (F3a+F4+F5b); F2 es la fase ya ejecutada.
- **D1** `next_open` inmutable para 1D; único valor explícito `next_open` cubre el scope F2; **MOC queda fuera** (F3+/F5+).
- **D5** solo F1–F5, **cero features**: los contratos FE/BE (F5a), Alembic (F3b), auth (F5b) y el ciclo analytics↔market (F4) quedan fuera.
- **D2** autoridad BD: Prisma versionado (decidido en F1; no hubo migración en F2).

## 4. Implementación (A–F)

| #     | Fichero(s)                                                                          | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ----- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | `packages/py/analytics/src/bolsa_analytics/backtest.py`                             | `execution_model: Literal["next_open"]="next_open"` en `run_backtest`. La señal en `t` se llena a `open[t+1]` (el loop mira `signal_by_index.get(i-1)` y ejecuta con `open[i]`); si no hay `i+1` no se ejecuta. `BacktestTradeResult.timestamp` = barra de ejecución real; `price=fill(open[i+1])`. Equity curve valora al close (mark-to-close), el fill al open. Fallback `open=close` para callers que solo pasan close (documentado).                     |
| **B** | `optimize/sma_grid.py` · `rsi_grid.py` · `macd_grid.py` · `application/optimize.py` | Misma regla next*open en `_simulate_sma_crossover`, `_simulate_rsi_mean_reversion`, `_simulate_macd_signal_cross` (señal en `index-1` → fill `open[index]`; `price` ya no es `bar.close`). `execution_model` añadido a cada simulador y a `run*\*\_grid`, propagado a `RunSmaGridOptimize.execute` y los caminos CPCV/WF/hold-out (`\_simulate_family_metrics`, `\_baseline_for_family`, `\_run_sma/rsi/macd/cpcv/walk_forward/h0_partial`).                  |
| **C** | `optimize/vectorbt_sma.py` · `optimize/optuna_sma.py`                               | `entries`/`exits` calculados sobre `close` y **desplazados +1** con shift numpy (no `.shift()` de pandas: produce dtype `object` y rompe numba). `vbt.Portfolio.from_signals(open, entries_fill, exits_fill, ...)` → fill en `open[t+1]`. `execution_model` añadido y expuesto; threadings en `optimize.py` para optuna/vectorbt.                                                                                                                             |
| **D** | `research/data_snapshot.py` · `research/manifest.py` · `application/backtests.py`   | `BarFingerprint` gana `open/high/low/volume` opcionales (defaults `None`, no rompe callers solos con `close`). `compute_data_version` hashea los 5 campos OHLCV con `:.8f` (fallback `open=high=low=close`, `volume=0`). `RUN_MANIFEST_VERSION` 1.0→**1.1**, `ENGINE_VERSION` 0.3.0→**0.4.0** (invalida manifests viejos → fuerza recálculo). `backtests.py` aporta OHLCV completo al fingerprint.                                                            |
| **E** | `tests/test_no_lookahead.py` (nuevo)                                                | Motor: señal en `t` → `trades[0].timestamp == bars[t+1]` y `price == open[t+1]`, ningún fill en la barra de señal. Caso límite: señal en última barra → `trade_count==0`. Grids SMA/RSI/MACD: invariant — con `close` idéntico pero `open` distinto, los resultados cambian ⟹ el fill usa `open` (no el close de la barra de señal).                                                                                                                          |
| **F** | `scripts/research/recalc_trials_next_open.py` (nuevo)                               | Recálculo idempotente por instrumento de los presets/trials existentes con `next_open`. `--dry-run` cuenta y lista las combinaciones que recalcularían sin escribir; `--apply` re-ejecuta vía `RunAndSaveBacktest` (ya default `next_open`) insertando run+trial nuevos; salta si existe run con `data_version` y `engine.version` actuales (idempotencia). `--symbol`, `--campaign`, `--timeframe`, `--limit`, `--initial-cash`, `--reset`, `--mark-legacy`. |
| —     | `tests/test_research_manifest.py`                                                   | Actualizado: `manifestVersion=="1.1"`; añadido `test_compute_data_version_detects_ohlcv_changes` (P0.2).                                                                                                                                                                                                                                                                                                                                                      |

## 5. Batería (por micro-cambio y cierre)

- **A–E:** `ruff check` + `mypy` (ficheros tocados) + `pytest` (analytics; application si toca `backtests.py`/`optimize.py`) — **todo verde** por micro-cambio.
- **Mypy:** grids H0 y `data_snapshot`/`manifest` **0 errores**. `backtest.py` y `optimize.py` muestran errores **pre-existentes** (verificado contra `git show HEAD:`) fuera del gate CI (el gate mypy CI es `domain/market/infrastructure/api`; analytics/application NO están en él). `vectorbt`/`optuna` → `import-untyped` preexistente por faltar stubs de vectorbt (fuera del gate).
- **pytest cierre:** analytics **323 ✓** · application **222 ✓** · api-python offline **9 ✓** (total **554 ✓**, 0 fallos).
- **Cierre global pendiente:** `pnpm test` + CI green (se hará tras aprobar commits y crear/push del estado).

## 6. Deuda / fuera de alcance (registrado, NO resuelto)

- **`--mark-legacy` no-op:** `research_trials` y `backtest_runs` **no tienen columna de marca de época/legacy**. Requiere contrato + columna (Alembic/Prisma, F3b fuera de alcance). El script lo informa y queda como deuda. Los trials antiguos quedan identificables por `manifest.engine.version` / `data_version` (nuevo-theme vs old-theme).
- **MOC / market-on-close:** `execution_model` queda solo con `next_open` (F3+/F5+).
- **Alembic** (F3b), **auth** (F5b), **ciclo analytics↔market** (F4), **contratos FE/BE** (F5a), `ensure_migrated` (F3b): no tocados.
- **TS `RUN_MANIFEST_VERSION` (`research-platform.ts`)** se mantiene en `'1.0'` (declaración tipo standalone, sin validación runtime; contrato FE/BE F5a fuera de alcance). El bump 1.1 es del lado analytics e invalida la caché de manifests para el recálculo.
- **`optimize.py`** (application) acumula 2 errores mypy pre-existentes (`int(latest["done"]...)`); no son del gate CI ni regresión de F2.

## 7. Registro

| Fecha      | Acción                                                                                                                                                                                                                                                                                                                        |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-08-11 | Traspaso F2 creado. Rama `stage/f2-backtest-next-open-2026-08-11` creada desde `3c59dc8` (estado F1, decisión del usuario).                                                                                                                                                                                                   |
| 2026-08-11 | **A** implementado en `backtest.py` (motor next_open). Ruff✓ · pytest backtest 7✓ · mypy sin errores nuevos (el único es pre-existente, fuera del gate CI).                                                                                                                                                                   |
| 2026-08-11 | **B** grids H0 + `optimize.py` (propagación `execution_model`). Ruff✓ · pytest analytics 317✓ · application 222✓ · mypy grids 0.                                                                                                                                                                                              |
| 2026-08-11 | **C** vectorbt+optuna (shift numpy + open). Fix: `.shift()` de pandas daba dtype `object` y rompía numba → shift con `np.zeros_like`+asignación. `test_vectorbt_optuna` 4✓ · analytics 317✓ · application 222✓.                                                                                                               |
| 2026-08-11 | **D** fingerprint OHLCV completo + bump 1.1/0.4.0 + **E** test anti-lookahead (`test_no_lookahead.py`). analytics **323✓** · api offline 9✓.                                                                                                                                                                                  |
| 2026-08-11 | **E** afianzado: motor llena en `open[t+1]` sin fill en barra de señal; última barra no ejecuta; grids usan `open` (invariante open-vs-close). [`test_research_manifest` actualizado a 1.1 + test OHLCV].                                                                                                                     |
| 2026-08-11 | **F** script `recalc_trials_next_open.py` (idempotente, dry-run/apply, campañas). ruff✓ · py_compile✓ · smoke import✓. No ejecutable e2e sin Postgres: queda listo para `--apply`.                                                                                                                                            |
| 2026-08-11 | **CIERRE F2 (working tree)** — ruff 0 nuevos en ficheros F2 · mypy sin errores nuevos (pre-existentes fuera del gate CI) · pytest analytics 323✓ + application 222✓ + api offline 9✓ = **554✓ · 0 fallos**. **Commits A–F pendientes de aprobación del usuario** (norma F1 §8). Siguiente fase: **F3b** (u orden pactado D0). |

---

## 8. Protocolo recurrente (obligatorio en TODOS los hilos)

> Norma permanente del proyecto (establecida en el traspaso F1 §8). Se reproduce por referencia al traspaso F1 §8. Al cerrar cualquier hilo: preparar el siguiente con su `traspaso-*` (estado+decisiones+deuda), entrada única en `engineering-index-2026-08-03.md`, y entregar en el chat **el texto exacto** para pegar en el próximo.

---

## 9. Texto exacto de traspaso — siguiente hilo (F3b / continuación)

> IMPORTANTE: F2 quedó IMPLEMENTADO en working tree pero **sin commits** (pendientes de aprobación). El próximo hilo debe, PRIMERO, decidir y aprobar los commits A–F y crear el push; después seguir con la siguiente fase (D0: F3b → F5a → F3a+F4+F5b). Aprobar cada commit. No renegociar D0–D5.

```text
Texto de traspaso → nuevo chat (CONTINUACIÓN — commits F2 + fase siguiente)

CONTEXTO INMEDIATO: En working tree está IMPLEMENTADO F2 (Rigor científico del backtest, fill
next_open) con los micro-cambios A–F VERDES (ruff✓ · mypy sin errores nuevos fuera del gate CI ·
pytest: analytics 323✓ + application 222✓ + api offline 9✓ = 554✓, 0 fallos). NO se crearon los
commits ni se pusheó aún. Rama actual: stage/f2-backtest-next-open-2026-08-11 (desde 3c59dc8).

Lee PRIMERO: docs/engineering/traspaso-f2-backtest-next-open-2026-08-11.md (§4 implementación A–F,
§5 batería, §6 deuda, §7 registro) y su fuente plan F2 (.cursor/plans/f2_rigor_cientifico_backtest_next_open_8b76de60.plan.md).
NO toques código fuera del alcance de la fase que se declare.

TAREA INMEDIATA (pendiente de aprobación del usuario): aprobar los 6 commits atómicos F2
(orden del plan y del traspaso §4 A,B,C,D,E,F), hacer push a origin/stage/f2-backtest-next-open-2026-08-11,
y validar CI green (pnpm test global). Ruta de ficheros tocados por A–F (no perderse):
  A packages/py/analytics/src/bolsa_analytics/backtest.py
  B packages/py/analytics/src/bolsa_analytics/optimize/{sma_grid,rsi_grid,macd_grid}.py + packages/py/application/src/bolsa_application/optimize.py
  C packages/py/analytics/src/bolsa_analytics/optimize/{vectorbt_sma,optuna_sma}.py
  D packages/py/analytics/src/bolsa_analytics/research/{data_snapshot,manifest}.py + packages/py/application/src/bolsa_application/backtests.py
  E packages/py/analytics/tests/test_no_lookahead.py (nuevo) + packages/py/analytics/tests/test_research_manifest.py
  F scripts/research/recalc_trials_next_open.py (nuevo)

DECISIONES Y ESTADO git (verificar): rama stage/f1-integridad-financiera-2026-08-11 se mantiene como
base (no fusionar/borrar). HEAD cortado = 3c59dc8 (M5 F1). F2 alive colgando en stage/f2-*. Checkpoint
de retroceso global: tag audit-checkpoint-2026-08-11 (2683c49).

Decisiones pactadas (NO renegociar): D0 orden F1→F2→F3b→F5a→(F3a+F4+F5b); D1 next_open inmutable 1D
(MOC fuera); D5 cero features (contratos FE/BE F5a, Alembic F3b, auth F5b, ciclo analytics↔market F4,
ensure_migrated F3b FUERA). Deuda registrada en F2 §6: --mark-legacy no-op (falta columna), versiones
TS sin tocar, mypy pre-existentes en backtest.py/optimize.py fuera del gate CI, numba/vectorbt sin stubs.

BATERÍA OBLIGATORIA: ruff check + mypy (ficheros tocados) + pytest (analytics/application/api-python).
Al cerrar cualquiera: preparar el siguiente traspaso-* + entrada única en engineering-index + texto
exacto en el chat (norma permanente del proyecto).
```
