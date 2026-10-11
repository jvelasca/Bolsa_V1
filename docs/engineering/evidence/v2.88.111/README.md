# Evidencia — `v2.88.111-beta` / **`§8` — validación OOS financiera por `(estrategia × instrumento)`**: dinero con costes, sensibilidad y banda

> **Base funcional:** `v2.88.110-beta` (commit `d868ea40`). Abre el hueco `§8` (Validación OOS por valor, P3) de la [auditoría profundizada](../../auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md).
> **Naturaleza:** sello **aditivo**. `Δ motor ≠ 0` (módulo puro nuevo + costura **opt-in** del CLI OOS) pero **`Δ decisión = 0`**: sin motor de decisión, sin umbrales, sin Alembic (head `052_top3_opportunities`) y **contrato sin cambio**.
> **Alcance ratificado (D-§8.A):** `§8-a` (módulo puro) + `§8-b` (costura opt-in + evidencia). `§8-c` (banda `K` medida) queda **declarado pendiente** — no se fabrica un punto.
> **Plan:** [`plan-v2-88-111-oos-validacion-financiera-2026-10-11.md`](../../plan-v2-88-111-oos-validacion-financiera-2026-10-11.md).

---

## 1. Qué cierra (el hueco de `§8`)

La auditoría profundizada §8 lo enuncia sin matices: **«ocupar el puesto #1 de Finalistas NO demuestra rentabilidad»**. El scorer OOS del replay AUTO ([`replay_oos.ScoreReport`](../../../../packages/py/application/src/bolsa_application/replay_oos.py)) mide **R** —múltiplos del riesgo al nacer— y es **coste-ciego**: no publica retorno de dinero, ni drawdown, ni Sharpe, ni profit factor, ni una dimensión `(estrategia, instrumento)`. Este sello incorpora esa evidencia de **dinero**.

## 2. `§8-a` — módulo PURO del reporte financiero por `(estrategia × instrumento)`

[`oos_finance.py`](../../../../packages/py/application/src/bolsa_application/oos_finance.py) (puro: sin DB, red ni reloj). Entra una secuencia de filles (`symbol`, `strategy_version`, `side`, `quantity`, `price`) y un **overlay de coste**; sale un reporte por grupo `(strategy_version, symbol)` + agregado:

- `grossReturnPct` / `netReturnPct` — retorno sobre el **capital comprometido**, bruto y **neto de costes** (`net ≤ gross`, con costes `0` son iguales).
- `maxDrawdownPct` — máxima caída de la curva de equity realizada, sobre el neto.
- `hitRate` — fracción de round-trips con PnL **neto** positivo.
- `profitFactor` — ganancias brutas / pérdidas brutas del neto; **`None`** (nunca `∞`) sin pérdidas.
- `sharpe` — media/desviación de los retornos por operación, **cuando proceda** (`n ≥ min_trades` **y** desviación `> 0`); si no, `None`.
- `commissionPaid` / `slippagePaid` — coste **modelado** aplicado (overlay explícito).
- `netReturnPctAtStress` — neto bajo costes escalados (sensibilidad, **monótona**).
- `trades` — número de round-trips cerrados.

**Contabilidad FIFO por grupo** (no mezcla símbolos) y **agregado = unión** de los round-trips en orden de clave estable. El exceso de una venta se ignora (no se fabrica un corto).

**Contrato de honestidad** (doctrina «Sin dato todavía», `UNKNOWN ≠ 0`): con `< min_trades` round-trips, **todos** los ratios del grupo son `None` — **jamás `0`** — y el grupo se declara en `unmeasured`.

**Banda, no punto.** El reporte fija `pointCitable = false` con su razón citada: mientras la banda de `K` sorteos del venue cruce el cero ([`v2.88.16.3`](../v2.88.16.3/README.md)), el punto **no** es una propiedad del motor. Se cita la banda, no el punto.

**Costes sin doble contabilización.** El overlay (comisión + deslizamiento, bps) es el coste **modelado**. Los filles del SIM ya llevan **embebida** la fricción del venue ([`applied_cost`](../../../../packages/py/application/src/bolsa_application/applied_cost.py) / `reference_mid`): esa fricción **medida** se reporta aparte y **no** se suma aquí.

**Pruebas** ([`test_oos_finance.py`](../../../../packages/py/application/tests/test_oos_finance.py), **12 passed**): neto ≤ bruto (y = con coste 0); sensibilidad monótona; `None` bajo `min_trades` (nunca `0`); PF `None` sin pérdidas; PF = ganancias/pérdidas con mezcla; Sharpe `None` con varianza nula y valor con muestra válida; agrupación `(versión, símbolo)`; determinismo y orden estable (agregado invariante al reordenar grupos); `cost overlay` rechaza bps negativos; adaptación/skip de filas ilegibles; venta sin compra previa ignorada.

## 3. `§8-b` — costura **OPT-IN** del CLI OOS (sello congelado intacto)

[`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py) gana el flag **`--finance-report PATH`** (**apagado por defecto**): reúne los `fill_rows` ya materializados por el motor y escribe el JSON del reporte en un fichero **aparte**, **sin tocar** el payload.

Restricción DURA respetada: `replay-repro` regenera el artefacto del sello y **asserta su `SHA-256` byte a byte**; el reporte **no** entra en el payload, así que el sello **no** puede moverse. El patrón es el mismo que la costura inerte ya probada de `capture_cycle_detail`.

**Pruebas** ([`test_replay_oos_cli_renderers.py`](../../../../apps/api-python/tests/test_replay_oos_cli_renderers.py), **6 passed**, +3): la costura agrupa por `(versión, símbolo)` y tolera un tick sin fills; descarta filles ilegibles sin fabricar; y una guarda **estructural** (`inspect.signature`) exige que `finance_report_path` sea `None` por defecto ⇒ la costura es inerte salvo que se pida.

## 4. Bump y sin migración

`2.11.110-beta` → **`2.11.111-beta`**: `package.json` + `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97`, guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**. **SIN migración** (head `052_top3_opportunities`); **contrato sin cambio**.

## 5. Verificación (local)

- `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed**.
- `lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken**.
- `mypy` (las 5 raíces `src`) → **545 source files, no issues** (+1 por el módulo nuevo).
- `pytest packages/py/application/tests -q` → **2656 passed**.
- `pytest` de los guardianes y ficheros tocados (bump + censo CI + renderers + `oos_finance`) → **24 passed**.

## 6. Límites (declarados, no disfrazados)

- **Validación de EDGE, no de RENTABILIDAD afirmada.** El reporte **calcula** las métricas exigidas; **no** afirma que la estrategia sea rentable. `pointCitable = false` lo declara.
- **`§8-c` PENDIENTE:** la banda `K` **medida** (re-ejecuta el replay `K` veces, no reproducible sin PG) merece su propio sello. Aquí solo se **declara** la cita de banda.
- **Costes MODELADOS.** El overlay es un modelo declarado; la fricción **medida** del SIM se reportaría aparte (fuera de este sello).
- **Cita POST-TAG pendiente:** el objeto del tag, el commit y el run de `Release tag CI` se añaden en §7 tras publicar.

## 7. Cita POST-TAG

Tag anotado **`v2.88.111-beta`** (objeto `ab02f934` → commit `a530dc93`) sellado y publicado.

- `Release tag CI` [**38141710304**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38141710304) → **`success`**: **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado), **sin reintentos** en los obligatorios.
- **`python`** (ruff/imports/mypy/pytest offline) → **`success`**: el módulo puro y la costura opt-in quedan **certificados en CI**, no solo en local. **`lifecycle-pg`** → **`success`**.
- **`replay-repro`** → **`REPRODUCIDO`**: `sha256` `1E3ADAC2…929A37E7` **idéntico** a los sellos previos ⇒ **prueba directa** de que la costura opt-in **no** movió el artefacto congelado (`Δ decisión = 0` confirmado por CI).
- Tag **unsigned** (limitación de certificación, no defecto).
