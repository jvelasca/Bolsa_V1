# Evidencia `v2.88.122-beta` — Verificación ejecutable AUTO/DÍA-D

> **Bump:** `2.11.121-beta` → **`2.11.122-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** sello de **VERIFICACIÓN** (no de producto). **`Δ motor = 0`** (solo `apps/api-python/tests/**`, `.github/workflows/**` y metadatos de versión) · **`Δ decisión = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`) · **SIN cambio de contrato**. Tag **unsigned**.

Cierra, con evidencia **ejecutable gated contra PostgreSQL real**, la parte verificable de los dos frentes funcionales que quedaron abiertos tras `v2.88.121`:

1. **La lane AUTO recorre TODO el universo ESTUDIO** (y no depende del reloj de máquina).
2. **La cadena DÍA-D** (señal → ciclo → cierre) se reconstruye desde hechos durables **sin pasos `unknown` silenciosos** y su **P&L cuadra** con el libro aplicado.

Los huecos que **no** se cumplen se **declaran** aquí (no se cierran, no se toca el motor).

---

## 1. Qué se certifica (y con qué)

| # | Slice | Fichero | Gate (fail-if-skipped) | Rol |
|---|-------|---------|------------------------|-----|
| S1 | Cobertura del universo ESTUDIO | [`test_auto_estudio_universe_coverage_pg.py`](../../../../apps/api-python/tests/test_auto_estudio_universe_coverage_pg.py) | `AUTO_ESTUDIO_COVERAGE_PG_REQUIRED=1` | PG real (orquestador + bucle reales) + 3 herméticos |
| S2 | Acoplamiento del watch diario | [`test_auto_daily_watch_coupling.py`](../../../../apps/api-python/tests/test_auto_daily_watch_coupling.py) | — (hermético, corre en el job offline) | Fija y **declara** el hallazgo |
| S3 | Traza DÍA-D + P&L conciliado | [`test_auto_dia_d_trace_pg.py`](../../../../apps/api-python/tests/test_auto_dia_d_trace_pg.py) | `AUTO_DIA_D_TRACE_PG_REQUIRED=1` | PG real (proceso `scheduler_worker`) |

Reproducción local:

```bash
AUTO_ESTUDIO_COVERAGE_PG_REQUIRED=1 AUTO_DIA_D_TRACE_PG_REQUIRED=1 \
  uv run pytest \
    apps/api-python/tests/test_auto_estudio_universe_coverage_pg.py \
    apps/api-python/tests/test_auto_dia_d_trace_pg.py -q
uv run pytest apps/api-python/tests/test_auto_daily_watch_coupling.py -q
```

---

## 2. S1 — Cobertura del universo ESTUDIO (lane de orquestación)

Arnés: composición **REAL** del orquestador (`_default_orchestrator(session_factory)`) sobre PG real; el universo se siembra en la lista ESTUDIO (3 valores, cada uno con `InstrumentRow` + serie OHLCV con tendencia). El automotor se conduce con el **mismo `auto_orchestrator_loop`** de producción (no se reimplementa el bucle).

**Matriz de cobertura (cada valor de ESTUDIO deja evidencia DURABLE de ciclo):**

| Valor sembrado en ESTUDIO | Candidata durable | Evaluación LAB durable | `optimization_run_id` |
|---------------------------|-------------------|------------------------|-----------------------|
| `inst-estco-<suffix>-0` | ✅ | ✅ | ✅ |
| `inst-estco-<suffix>-1` | ✅ | ✅ | ✅ |
| `inst-estco-<suffix>-2` | ✅ | ✅ | ✅ |

**Asertos certificados:**

- `resolve_universe().status == "ok"` y el universo resuelto **incluye los 3 valores**.
- `_instruments_for_cycle(orchestrator, allowlist=())` (la función que usa el bucle) **incluye el lote completo**.
- El **bucle real** recorre cada valor y cada uno deja candidata + evaluación con `optimization_run_id` (no basta con aparecer en un informe por valor).
- **Allowlist solo intersecta:** `allowlist=(v0,)` ⇒ `(v0,)`; `allowlist` sin intersección con ESTUDIO ⇒ `()` (fail-closed).
- **Fail-closed sin ESTUDIO** (resolver REAL, hermético): puerto ausente ⇒ `unavailable` ⇒ `()`; lista vacía ⇒ `empty` ⇒ `()`; puerto que lanza ⇒ `unavailable` ⇒ `()`; nunca cae a la allowlist.
- **Independencia del reloj:** con `bar_tick`/`last_closed_bar_day` booby-trapeados, la cobertura **no cambia** (es pertenencia de lista, no consulta temporal). Se añade la estabilidad del ancla de barra cerrada dentro de la misma barra diaria (`bar_tick`/`last_closed_bar_day` constantes).

Resultado local: **4 passed** (1 PG + 3 herméticos).

---

## 3. S2 — Hallazgo DECLARADO: el watch diario NO deriva del universo ESTUDIO

**Hallazgo (no cerrado en este sello).** Las dos lanes AUTO nacen desacopladas:

| Lane | Fuente del instrumento | Evidencia (`file:line`) |
|------|------------------------|--------------------------|
| Estrategia/orquestación | lista **ESTUDIO** (universo canónico); el CSV `AUTO_ORCHESTRATOR_INSTRUMENTS` solo **intersecta** | [`auto_orchestrator_worker._instruments_for_cycle`](../../../../apps/api-python/src/bolsa_api/background/auto_orchestrator_worker.py) |
| Operación diaria | **CSV estático** `AUTO_ENGINE_SIMULATED_WATCH` / `AUTO_ENGINE_DRY_WATCH` (default `AAA,IBEX`); **no consulta ESTUDIO** | [`paper_auto_engine_worker._watch_symbols`](../../../../apps/api-python/src/bolsa_api/background/paper_auto_engine_worker.py#L104) |

**Consecuencia para el operador:** un valor que entra en ESTUDIO **no** entra solo en el día AUTO; el CSV y la lista ESTUDIO deben mantenerse **sincronizados a mano**.

`test_auto_daily_watch_coupling.py` **fija** esta conducta: (a) default `AAA,IBEX`; (b) el CSV (SIM preferido sobre el alias DRY) manda; (c) con el resolver ESTUDIO booby-trapeado el watch **no se inmuta** (prueba falsable de que hoy no hay acoplamiento); (d) guarda estática: el módulo de la lane diaria no importa `resolve_estudio_universe`/`ESTUDIO_LIST_ID`. Cualquier acoplamiento futuro **pondría el test rojo** y obligaría a actualizar esta declaración. Resultado local: **4 passed**.

---

## 4. S3 — Traza DÍA-D extremo a extremo + P&L conciliado

Arnés **reutilizado** de [`test_golden_day_v2_process_pg.py`](../../../../apps/api-python/tests/test_golden_day_v2_process_pg.py): el día lo conduce el **proceso real** `python -m bolsa_api.workers.scheduler_worker` con `AUTO_OPERATIONAL_AUDIT=1` sobre PG real (un instrumento, el mínimo para producir un ciclo cerrado). Régimen **SIM** (nunca bridge LIVE — verificado).

**Cadena canónica del ciclo CERRADO (reconstruida desde HECHOS DURABLES, no desde RAM):**

| Etapa | Estado |
|-------|--------|
| `SIGNAL` | `reached` |
| `TOP_N` | `reached` |
| `RISK` | `reached` |
| `RESERVATION` | `reached` |
| `ORDER` | `reached` |
| `FILL` | `reached` |
| `PROTECTION` | `reached` |
| `SETTLEMENT` | `reached` |
| `CYCLE_CLOSED` | `reached` |

Se **enumeran** los no-encendidos y el test exige `not_reached == {}`: **ningún `unknown`/`absent` silencioso**.

**Conciliación de P&L** (identidad de fuentes independientes):

- `CYCLE_CLOSED.pnl` (reconstrucción FIFO del **monitor**) == `realized_notional_from_applied_fills` (libro aplicado: `execution_events.status='APPLIED'` + `sim_fill_finance_context`) == `SETTLEMENT.pnl` (liquidación durable), **exacto al quantum del dinero** (`NUMERIC(18,6)`).
- El monitor reconstruye el realizado en **12 decimales** y el libro **cuantiza cada fill a 6**; por eso la identidad se exige al quantum representable del ledger (documentado en [`applied_fill_equity.py`](../../../../apps/api-python/tests/applied_fill_equity.py)). En la corrida local el valor coincidió (monitor `-26.022593080000` → quantum `-26.022593` == libro `-26.022593`): la coincidencia **no es vacua** (`gross_notional > 0`, ambos lados BUY/SELL presentes).
- Los hechos durables del overlay llevan identidad determinista: `nullKey == 0` y **cero** `dedupe_key` repetidas.

**Controles negativos:** un `cycleId` ajeno (`cyc-foreign-does-not-exist-000000`) se devuelve tal cual pero **no hereda** `SIGNAL` ni `SETTLEMENT` (asociación rechazada). La traza es **determinista** entre lecturas (mismo `cycleId` y mismo `pnl`).

Resultado local: **1 passed**.

---

## 5. Cableado CI y censo

- Los dos ficheros PG entran en el job **`lifecycle-pg`** de [`release-tag-ci.yml`](../../../../.github/workflows/release-tag-ci.yml) en **paso DEDICADO** con **guard anti-skip** (log + `grep` de `skipped`, como el Golden Day) y sus dos env-gates (`AUTO_ESTUDIO_COVERAGE_PG_REQUIRED`, `AUTO_DIA_D_TRACE_PG_REQUIRED`) en el `env:` del job.
- Ambos van al `--ignore` de los jobs **offline** (`python-ci.yml` y `release-tag-ci.yml`): sin PG skipearían en mudo dentro del pase de directorio.
- El fichero hermético S2 se recoge por el **pase de directorio** del job offline (no requiere PG).
- **Censo de selección** (`scripts/ci/test_selection.py`, guarda [`test_ci_test_selection_census.py`](../../../../apps/api-python/tests/test_ci_test_selection_census.py), `maxUndeclared: 0`): **616 / 616 ejecutados · 0 sin declarar · 0 obsoletos**. Ningún test nuevo queda invisible.

---

## 6. Huecos declarados (NO cerrados; sin tocar el motor)

1. **Desacoplamiento watch diario ↔ ESTUDIO (S2):** seguirá siendo responsabilidad del operador mantener CSV y ESTUDIO sincronizados. No se acopla en este sello.
2. **La conciliación de P&L certifica la IDENTIDAD de fuentes, no la RENTABILIDAD.** El sandbox corre precio plano inyectado y cierre por `time_exit`; la magnitud del resultado no se valida aquí.
3. **Ventana PAPER longitudinal (`P3-2`/`P3-3`, ADR-046) y `CONFIRMED`:** fuera de alcance.
4. **Olas 2..6 de auditoría UI:** abiertas.
5. **`v2_87` sella `2.11.0-beta` en un dict de evidencia interno** (segundo `"bump"`, distinto del `meta.bump` que vigila el guardián); **no** se toca — es histórico y ajeno a este bump.

---

## 7. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| `ruff check` (ficheros nuevos) | **All checks passed** |
| `mypy` (lista CI: `packages/py/*/src` + `apps/api-python/src`) | **Success: no issues found in 552 source files** |
| `import-linter` (`packages/py/.importlinter`) | **4 kept, 0 broken** |
| S1 + S2 + S3 con gates ON | **9 passed** (`16.19s`) |
| Censo de selección | **616/616 · 0 sin declarar** · 0 obsoletos |
| Guardián de bump + guarda de censo | **6 passed** |
| `pytest packages/py/application/tests` | **2715 passed** |
| `pytest apps/api-python/tests` (PG real, suite completa) | **1013 passed** (+9 respecto a `1003`+1ambiental de `v2.88.121`; el fallo **ambiental** de timing de `chaos/live_a7` **no** se reprodujo) |
| YAML de workflows | parsea (`python-ci` 5 jobs · `release-tag-ci` 13 jobs) |
| `alembic heads` | `053_dia_d_cycle_verifications` (**sin migración**) |

**`Δ motor = 0` verificado por diff:** `git diff --stat` del sello solo toca `.github/workflows/**`, `CHANGELOG.md`, `PROJECT_STATE.md`, los 10 `meta.bump` de los CLIs y `package.json`; **cero** cambios en `packages/py/*/src`, `apps/api-python/src` y migraciones.

**CI del sello (verde).** `Release tag CI` [**38392092094**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38392092094) — **success en 12m57s**: 12/12 jobs `success` (`playwright (integrated E2E, opt-in)` = `skipped` por diseño). El paso nuevo **`Pytest AUTO universe coverage + DÍA-D trace (PG, fail if skipped)`** se ejecutó con `AUTO_ESTUDIO_COVERAGE_PG_REQUIRED=1` y `AUTO_DIA_D_TRACE_PG_REQUIRED=1` y salió **`5 passed in 11.40s`** (S1 4 + S3 1), con el guard anti-skip **sin `::error`** (no hubo `SKIPPED`). Lo decisivo: **`replay-repro` success** con veredicto **`REPRODUCIDO`** (`Δ decisión = 0` confirmado por el artefacto congelado) y **`lifecycle-pg` sin migración**. CI de rama del commit de sello (`0ac2cf1c`): `Python CI` [38392089182](https://github.com/jvelasca/Bolsa_V1/actions/runs/38392089182) · `Frontend CI` [38392089088](https://github.com/jvelasca/Bolsa_V1/actions/runs/38392089088) · `Optimize lab` [38392089103](https://github.com/jvelasca/Bolsa_V1/actions/runs/38392089103) · `Gitleaks` [38392089491](https://github.com/jvelasca/Bolsa_V1/actions/runs/38392089491) — todos `success`.
