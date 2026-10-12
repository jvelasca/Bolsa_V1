# Evidencia `v2.88.114-beta` — `§8-c` BANDA `K` MEDIDA del reporte financiero OOS

> **Sello:** `v2.88.114-beta` (base `v2.88.113-beta`).
> **Bump:** `2.11.113-beta` → **`2.11.114-beta`** (`package.json` + `meta.bump` de los 9 CLIs `v2_89`…`v2_97`).
> **Naturaleza:** **aditivo** · **`Δ decisión = 0`** (no toca motor, umbrales, `TOP_N` ni reparto) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato SIN cambio**.
> **Cierra:** residuo **`R-4`/`§8-c`** de la [auditoría de `v2.88.113-beta`](../auditoria-v2.88.113-beta-2026-10-11.md).
> **Fecha de medición:** 2026-10-11.

---

## 1. Qué cambia (aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Módulo puro** | [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) | `build_finance_band(draws=…)`: pliega `K` reportes OOS por `(strategyVersion, symbol)` + agregado en `bands` (min/median/max/mean/stdev/n), `drawsWithCell`/`drawsTotal`, `validity` medida y `limits`. Determinista; `None` ≠ `0`. |
| **Costura OPT-IN** | [`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py) | flags `--finance-band K` (default `0` = OFF), `--finance-band-out PATH`, `--finance-band-seal SHA256`; `_build_parser()` extraído. Orquestador: parchea `_SEED_LINE` del worker, lanza subprocesos de sí mismo con `--finance-report`, **restaura byte a byte** (aborta si no) y pliega. |
| **Tests puros** | [`test_oos_finance_band.py`](../../../../packages/py/application/tests/test_oos_finance_band.py) | `None ≠ 0`, `drawsWithCell` con cubo ausente, `insufficient_draws` con `K=1`, `crossesZero`/`pointCitable` en ambos sentidos, determinismo. |
| **Guarda del CLI** | [`test_replay_oos_cli_renderers.py`](../../../../apps/api-python/tests/test_replay_oos_cli_renderers.py) | inercia por defecto, no-recursión del argv del sorteo, plegado de la costura `ticks → reporte → banda` sin PG. |

La fuente ÚNICA del criterio de banda (`MIN_DRAWS_FOR_BAND = 2`, `CI95_Z = 1.96`) se **importa** de
[`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py): no se re-declara.

---

## 2. Restricción dura respetada — sello `replay-repro` intacto

`replay-repro` regenera `replay-oos-durable-v2.88.7.json` y **asserta su `SHA-256` byte a byte**. En la medición, el **sorteo `k = 0`** (realización de producción, **sin** parchear el árbol) reprodujo exactamente:

```
sha256_lf = 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7
```

Verificado con `--finance-band-seal` (la sonda sale con código `2` si no cuadra): **exit `0`**. El payload por defecto **no** se movió; la banda vive en fichero aparte y con el flag **apagado por defecto**.

---

## 3. Medición `K = 12` (ventana `w32`, entrada congelada)

- **PostgreSQL:** `bolsa_v1_replay_w32` (fixture `v2.88.7`, `25 700` barras).
- **Watch:** el congelado del fixture (`replay_oos_input_fixture.py watch --fixture …v2.88.7/replay-input-fixture.ndjson`), 20 instrumentos.
- **Comando:**
  ```
  v2_87_replay_oos_durable_cycle.py --watch <WATCH> --finance-band 12 \
     --finance-band-out operability_runs/oos-finance-band/w32-band.json \
     --finance-band-seal 1E3ADAC2…929A37E7
  ```
- **Coste:** `12 × ~80 s` (≈ `965 s`). **Requisito:** PostgreSQL con la entrada sembrada ⇒ **no reproducible sin PG**.

### 3.1 Sorteos (SHA-256 del payload por sorteo, LF)

El **sorteo 0** = sello del tag. El **sorteo 1** reproduce la realización `k01` ya declarada por el
harness de robustez de semilla `v2.88.16.3` (`CD59FEB8…`), lo que **cruza** dos instrumentos independientes.

| k | sha256_lf | | k | sha256_lf |
| --- | --- | --- | --- | --- |
| 00 | `1E3ADAC26543…929A37E7` | | 06 | `5B4C7A29FE9C…22942D8` |
| 01 | `CD59FEB83D64…41537D6A` | | 07 | `E44D86B63B1A…E1D2DF59` |
| 02 | `7891A0327F9D…E1D595AF` | | 08 | `314980A17C93…60D7C5B9` |
| 03 | `1001E0D1D0DA…31715751` | | 09 | `DC7B128CF264…207A5529` |
| 04 | `F6F65AFC8A43…EC1EC2D8` | | 10 | `522EE3DDF768…A41F7CA6` |
| 05 | `C03443645488…FE3B460D` | | 11 | `D9C97343717B…73E49C9A` |

### 3.2 Banda del AGREGADO (`netReturnPct`, `K = 12`)

| métrica | min | median | max | mean | stdev | n |
| --- | --- | --- | --- | --- | --- | --- |
| `netReturnPct` | **−3.398126** | −0.702897 | **+0.515323** | −0.861316 | 1.019600 | 12 |
| `grossReturnPct` | −3.248126 | −0.552897 | +0.665323 | −0.711316 | 1.019600 | 12 |
| `netReturnPctAtStress` | −3.548126 | −0.852897 | +0.365323 | −1.011316 | 1.019600 | 12 |
| `maxDrawdownPct` | 0.461874 | 1.255984 | 3.623252 | 1.415661 | 0.855978 | 12 |
| `hitRate` | 0.491184 | 0.609903 | 0.679372 | 0.596166 | 0.047632 | 12 |
| `profitFactor` | 0.383374 | 0.810082 | 1.192960 | 0.807073 | 0.211712 | 12 |
| `sharpe` | 0.066817 | 0.263033 | 0.435189 | 0.265227 | 0.086448 | 12 |
| `committedCapital` | 686 979.81 | 1 231 358.71 | 1 695 800.91 | 1 201 006.21 | 282 582.00 | 12 |
| `trades` | 397 | 726.5 | 1095 | 715 | 180.657 | 12 |

**`validity` medida:**
`crossesZeroNetReturn = True` · `pointCitable = False` · `se = 0.294333` · `ci95HalfWidth = 0.576893`.

### 3.3 Banda por grupo (`10` grupos, `K = 12`)

| símbolo (prefijo) | min | max | mean | n (`drawsWithCell`) | `crossesZero` | `pointCitable` |
| --- | --- | --- | --- | --- | --- | --- |
| `0a5dc12fd5` | −4.321 | +1.581 | −0.829 | 10 | **True** | False |
| `0cf0907837` | −4.512 | +0.320 | −1.360 | 12 | **True** | False |
| `240a4ae01a` | −8.766 | +2.333 | −4.439 | 11 | **True** | False |
| `31f9a597d0` | −2.359 | +3.515 | −0.514 | 12 | **True** | False |
| `381dd3b069` | −9.412 | +1.219 | −2.261 | 10 | **True** | False |
| `49596ff25a` | −5.242 | +0.520 | −2.574 | 11 | **True** | False |
| `4d24ea0292` | −6.878 | +2.301 | −0.477 | 9 | **True** | False |
| `54283bcb54` | −4.836 | +3.228 | −0.453 | 11 | **True** | False |
| `5a130eea1a` | −12.323 | +7.900 | −2.033 | 11 | **True** | False |
| `5c34aaec14` | −5.708 | +8.474 | +0.046 | 10 | **True** | False |

**Resultado:** **`10/10`** grupos cruzan el cero y **`10/10`** son `pointCitable = False`; el **agregado también cruza** ⇒ **ningún punto es citable**. Es exactamente lo que `§8-c` quería **medir** en vez de narrar: el dinero OOS del replay AUTO es un **sorteo del venue con banda que cruza cero**, no una rentabilidad.

> **`drawsWithCell` < `K` (9, 10, 11) en varios grupos:** el overlay `min_trades = 10` descarta en algunos sorteos los grupos sin operaciones suficientes ⇒ el sorteo **baja `drawsWithCell`** y **no** rellena con `0` (regla respetada y ejercitada en la medición real).

### 3.4 Artefactos crudos

- [`finance-band-w32-k12.json`](./finance-band-w32-k12.json) — artefacto `oos-finance-band-v1` completo (`10` grupos + agregado + `coverage` + `limits`).
- [`finance-band-w32-k12.log`](./finance-band-w32-k12.log) — salida del orquestador (12 sorteos, sección `BANDA`).

---

## 4. Verificación

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `lint-imports --config packages/py/.importlinter` | ✅ `Contracts: 4 kept, 0 broken.` |
| `mypy <5 raíces src> --follow-imports=silent` | ✅ `Success: no issues found in 552 source files` |
| `pytest packages/py/application/tests -q` | ✅ `2681 passed, 5 skipped` |
| `pytest apps/api-python/tests/test_replay_oos_cli_renderers.py` | ✅ `9 passed` |
| `pytest test_dia_d_bump_guard + test_ci_test_selection_census + test_oos_finance` | ✅ `20 passed` |
| Medición `K = 12` con `--finance-band-seal` (autochequeo del sello) | ✅ exit `0`; `k=0` = `1E3ADAC2…929A37E7` |
| Árbol tras la matriz de re-sorteo (`auto_simulation_worker.py`) | ✅ limpio (`git status --porcelain` sin cambios) |

---

## 5. Límites declarados

- **Compone/observa, no decide:** `Δ decisión = 0`; no toca motor, umbrales, `TOP_N` ni reparto.
- **No sustituye PAPER** (`P3-2`/`P3-3` abiertas) ni emite `CONFIRMED`; la banda mide el **sorteo del venue**, no el futuro.
- **Costes modelados** (overlay `commission_bps=10`, `slippage_bps=5`, `stress=2×`); la fricción medida del SIM iría aparte, sin doble contabilización.
- **La banda medida NO es reproducible sin PostgreSQL** (el replay lee barras reales): se cita como **medición local**, no como gate de CI.
- **Determinismo ≠ validez:** reproducir el payload byte a byte no convierte el cero en un punto citable.

---

## 6. Residuos

| ID | Descripción | Estado |
| --- | --- | --- |
| `R-4`/`§8-c` | banda `K` medida del reporte financiero OOS | **✅ CERRADO por este sello** |
| `R-5` | cita POST-TAG de `113` en las evidencias | **✅ actualizada** ([`v2.88.113/README.md` §10](../v2.88.113/README.md)) |
| `R-2` | `origin/main` en `3d8e74ad`: los commits del tag `113` no corren `main` CI | **abierto (fuera de alcance)** |

---

## 7. Cita POST-TAG

Tag anotado **`v2.88.114-beta`** (objeto `bcb19cd40c4d8739519ed579575f10712a3884bc` → commit `743bb8df71cb8ef617bdf94a52eb08312086efce`) sellado y publicado en `origin`.

- `Release tag CI` [**38218516439**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516439) → **`success`** (`12m6s`): **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado).
- **`replay-repro`** → **`success`**: regenera el artefacto del sello desde el fixture **sin** mover el payload ⇒ la costura opt-in de la banda **no** tocó el sello congelado.
- Resto de workflows del tag: `Python CI` [**38218516436**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516436) `success` · `Frontend CI` [**38218516453**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516453) `success` · `Fase 2 scientific` [**38218516438**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516438) `success` · `Optimize lab` [**38218516459**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38218516459) `success`.
- **Distinción:** *estado comunicado* (implementado y verificado localmente) vs *verificación externa* (tag/commit/run resueltos en GitHub) — aquí **ambos** confirmados. El sello **no** demuestra rentabilidad ni bloquea por sí solo rutas reales de `XTB`.
