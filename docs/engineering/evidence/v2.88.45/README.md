# Evidencia `v2.88.45-beta` — `AUTO · DÍA-D-3d`: **quirófano del `THESIS_EXIT`** (dónde viven los 38 ciclos), sin tocar motor

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.45-beta` · **Package:** `2.11.45-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.97 DIA-D AUTO THESIS EXIT` · **Δ motor = 0**.

**Schemas:** `dia-d-thesis-exit-v1` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`) y `dia-d-multi-cycle-ledger-v3` (aditivo sobre `-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.44`](../v2.88.44/README.md) (de dónde nace la pérdida: mecanismo × coste × entrada) → [`v2.88.43`](../v2.88.43/README.md) (bootstrap de ciclos) → [`v2.88.42`](../v2.88.42/README.md) (venue) → [`v2.88.41`](../v2.88.41/README.md) (atribución multirregimen).

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-band/draw-00…draw-11/multi-cycles.json` — `12` ledgers `dia-d-multi-cycle-ledger-v3` (con estrategia, dirección, fricción y motivo de cierre).
- `operability_runs/dia-d-auto/multi-band-detail-2021_2026.json` — el plegado `v2_94` con `--cycle-detail`.
- `operability_runs/dia-d-auto/thesis-exit-2021_2026.json` — el artefacto `dia-d-thesis-exit-v1` (`63 551 B`).

---

## 0. Qué añade este sello (y qué NO)

`v2.88.44` aisló el hallazgo incómodo: el `STOP_EJECUTADO` domina en frecuencia (`93,4 %`) con expectancy bruta `~0`, y el grueso del `R` bruto negativo vive en pocos `THESIS_EXIT` (`38` ciclos, `expectancyR = -0.7087`, `hitRate = 8,3 %`). Este sello **abre quirúrgicamente esos 38 ciclos**: responde a *dónde viven* (estrategia, dirección, año/régimen, edad, geometría MAE/MFE/captura, entrada y coste).

**NO** responde a *por qué* se invalidó la tesis: el journal sólo publica el token **colapsado** `thesis_exit` (la traducción `THESIS_INVALIDATION → thesis_exit` de `auto_reason_codes._DAY_EXIT_REASON_BY_PRIMARY` borra la condición). Recuperarla exigiría capturar el contexto del plan, que hoy **no** llega al journal → fase futura, **no** esta. Se declara; no se finge.

**NO** toca el motor, los umbrales, `TOP_N` ni la allocation. **NO** introduce contrafactuales ("qué habría pasado con otra salida"): sólo descompone lo observado.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **El global reproduce `v2.88.44`:** los `38` ciclos `THESIS_EXIT` y su `expectancyR` bruta `-0.7087` son idénticos al sello anterior (la capa v3 es aditiva). | Que el global difiera del sello `v2.88.44`. | `global.realizedRGross.expectancyR.mean = -0.7087`, `total.mean = -2.3462`; `cycles = 38`; `coverage.cyclesTotal = 38`. |
| **2** | **Los 38 viven en UNA sola estrategia y UNA sola dirección:** no hay mezcla que esconda subpoblaciones. | Que `byStrategy`/`byDirection` tengan más de un cubo con ciclos. | `byStrategy = [v283-window-a (38)]`, `byDirection = [long (38)]`. |
| **3** | **La pérdida se concentra en ciclos de edad media:** los cubos `4-10` y `11-30` días son negativos; el `>30` es positivo pero `n = 3`. | Que la edad larga (`>30`) cargue la pérdida. | `byAgeBucket`: `4-10` `n=20` `-0.8153`; `11-30` `n=14` `-0.8767`; `>30` `n=3` `+0.7375` (`fragile`); `1-3` `n=1` `-0.8236`. |
| **4** | **La excursión adversa de estos ciclos es peor que la media global:** `MAE` media `-1.4029 R` (vs `-0.7115 R` de TODO el replay en `v2.88.44`). | Que la MAE de los `THESIS_EXIT` sea `~0` o mejor que la global. | `global.excursion.maeR.mean = -1.4029`, `median = -1.3499`; `entryQuality.adverseR.mean = -0.9505`, `shareBelowHalfR = 0.7632`, `shareBelowOneR = 0.5263`. |
| **5** | **Hubo MFE que no se capturó:** `leftOnTableR` medio `+0.6269 R` (acotado por el `MFE` `+0.6672 R`) y captura media del MFE `0.0449` (mediana `0.0`). | Que `leftOnTableR` sea `<= 0` (no había nada que capturar) o **supere** el MFE. | `excursion.mfeR.mean = +0.6672` (`measured = 38`); `excursion.leftOnTableR.mean = +0.6269`, `median = +0.3979`, `measured = 34`; `excursion.capture.mean = 0.0449`, `median = 0.0`, `measured = 34`. Misma semántica `capturedR = max(realizedR, 0)` que `capture_study` (`v2.88.40`, `A39-01`). |
| **6** | **El coste no invalida el neto:** los `38` ciclos tienen fricción `COMPLETE` (no hay suelo). | Un `netRealizedR` nulo o un `PARTIAL` en el cubo. | `coverage.cyclesWithCompleteFriction = 38`; `global.realizedRNet.cyclesUnmeasured = 0`; `net.expectancyR.mean = -0.7525`. |
| **7** | **El motivo crudo NO revela la causa:** los `38` traen el token colapsado `thesis_exit`. | Que aparezca un token distinto que sí describa la condición. | `rawReasonTokens = {thesis_exit: 38}`. |
| **8** | **Riesgo de concentración moderado:** `9` símbolos distintos, top símbolo `26,3 %`, top semana `2025-W12` `21,1 %`. | Que un solo símbolo/semana explique >50 %. | `concentration = {distinctSymbols: 9, topSymbolShare: 0.2632, topWeekShare: 0.2105}`. |
| **9** | **Determinismo:** dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**. | Que dos corridas difieran. | `sha256 09AC71BD63EA967C22D9869A1A6D6CD6ACCD53FDCCDED7538257C40E7984A71F`, `63 551 B` (reproducido). |
| **10** | **`Δ motor = 0`:** ningún fichero de motor cambia; la capa v3 es aditiva y la costura `capture_cycle_detail` sigue inerte por defecto. | Que el árbol del motor cambie o que la costura altere el replay con `capture_cycle_detail=False`. | `git status` del motor vacío; la capa v3 sólo añade dos campos por ciclo al ledger; `v2_95` sigue leyendo `realizedR/year/regime`. |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` ciclos `THESIS_EXIT` · `38` con fricción `COMPLETE` (`0` `PARTIAL`, `0` `UNKNOWN`) · `detailCaptured = true` · `11/12` sorteos con celda · **una** estrategia (`v283-window-a`) y **una** dirección (`long`).

### 2.1 Global

| Métrica | Valor |
| --- | --- |
| R bruto total (por sorteo, media) | `-2.3462` |
| Expectancy bruta (entre sorteos) | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| HitRate | `0.0833` |
| R neto total (por sorteo, media) | `-2.5012` (medido, **no** suelo) |
| Expectancy neta | `-0.7525` |
| Fricción media por sorteo | `0.0438 R` |
| MAE media / mediana | `-1.4029 R` / `-1.3499 R` |
| MFE media / mediana | `+0.6672 R` / `+0.3689 R` |
| Captura del MFE (media / mediana) | `0.0449` / `0.0` (medida en `34` ciclos; `4` con `mfeR <= 0` son hueco) |
| `leftOnTableR` media / mediana | `+0.6269 R` / `+0.3979 R` (acotada por el MFE; nunca lo supera) |
| Excursión adversa temprana (D1, 3 barras) | media `-0.9505 R`; `< -0.5R` `76,3 %`; `< -1.0R` `52,6 %` |
| Slippage señal→ejecución | media `10,56 bps` / mediana `10,51 bps` |

### 2.2 Por edad del ciclo (días naturales)

| Cubo | Sorteos | Ciclos | Expectancy bruta | MAE media | Frágil |
| --- | --- | --- | --- | --- | --- |
| `1-3` | `1/12` | `1` | `-0.8236` | `-1.3495` | sí (`insufficient_draws`) |
| `4-10` | `10/12` | `20` | `-0.8153` | `-1.3747` | `few_cycles_per_draw` |
| `11-30` | `8/12` | `14` | `-0.8767` | `-1.5709` | `few_cycles_per_draw` |
| `>30` | `3/12` | `3` | `+0.7375` | `-0.8247` | `few_cycles_per_draw` |

### 2.3 Por año y régimen

| Dimensión | Cubo | Sorteos | Ciclos | Expectancy bruta |
| --- | --- | --- | --- | --- |
| Año | `2022` | `10/12` | `19` | `-0.7800` |
| Año | `2023` | `1/12` | `2` | `-0.5783` |
| Año | `2024` | `2/12` | `2` | `-0.5251` |
| Año | `2025` | `9/12` | `15` | `-0.7091` |
| Régimen | `high_vol` | `11/12` | `34` | `-0.6819` |
| Régimen | `trend_down` | `3/12` | `4` | `-0.7727` |

### 2.4 Lectura honesta

- **No hay subpoblaciones que rescaten el bucket:** los `38` son una sola estrategia (`v283-window-a`) y una sola dirección (`long`). El `-0.7087` es la expectativa de TODO el cubo, no un promedio que mezcle un grupo bueno con uno malo.
- **La pérdida vive en la edad media:** los ciclos que duran `4-30` días cargan la expectativa negativa (`-0.8153`/`-0.8767`); los `>30` son positivos pero **sólo `3` ciclos** (declarados `fragile`). No se cita como evidencia fuerte.
- **La excursión adversa es severa:** `MAE` media `-1.4029 R` — **peor** que la media global del replay (`-0.7115 R` en `v2.88.44`) — con `76 %` de ciclos por debajo de `-0.5 R` en las primeras `3` barras D1.
- **Había MFE que no se capturó:** `leftOnTableR` `+0.63 R` sobre un `MFE` medio `+0.67 R`, con captura media del MFE `0.0449` (mediana `0.0`). La tesis se invalida cuando ya había ido a favor y se devuelve casi todo el premio medido. La captura se define sobre el resultado **NO negativo** (misma semántica sellada en `capture_study`, `v2.88.40`): nunca es negativa y `leftOnTableR` **no** supera el MFE.
- **El motivo exacto de la invalidación NO está capturado** (`rawReasonTokens = {thesis_exit: 38}`): esta fase dice *dónde* está la pérdida, no *qué condición* la disparó.

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` DÍA-D (`test_dia_d_*.py` + `test_dia_d_bump_guard.py`) | **135 passed** (`v2.88.44 = 120`; **+15**: `+14` de `test_dia_d_thesis_exit.py`, `+1` de la capa v3) |
| `pytest` `test_dia_d_thesis_exit.py` | **14 passed** (selección, dirección, captura acotada al MFE, **paridad con `capture_study`**, `PARTIAL→None`, cubos de edad, plegado, motivos, concentración, determinismo, huecos, no-import de motor) |
| `ruff check` | limpio |
| `lint-imports` (`import-linter`) | **4 kept / 0 broken** (`659` ficheros) |
| `mypy` | limpio (`531` ficheros) |
| `contract:check` | OK (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| `test_dia_d_bump_guard.py` | OK (incluye `v2_97`; `meta.bump` alineado a `2.11.45-beta`) |
| Determinismo `v2_97` | byte a byte idéntico (`sha256 09AC71BD…`, `63 551 B`) |
| `Bugbot` (auditoría **pre-sello**) | **1 hallazgo medium, corregido**: `_capture`/`_left_on_table` usaban `realizedR` en crudo (captura negativa posible y `leftOnTableR` inflado por `\|pérdida\|`, superaba el MFE). Ahora calcan `capture_study` (`A39-01`) y hay **test de paridad**; los números de §2 se re-midieron con el arreglo |
| `Security review` (pre-sello) | **sin hallazgos**: capa pura/read-only, sin secretos, sin deserialización insegura, sin ampliar frontera de confianza |
| `Δ motor = 0` | `git status` vacío sobre los ficheros de motor; la capa v3 del ledger es aditiva y `v2_95` sigue leyendo `realizedR/year/regime` |

---

## 4. Límites declarados (NO se cierran aquí)

- **La condición de invalidación NO está capturada:** `rawReasonTokens = {thesis_exit: 38}` es el token colapsado; recuperar el "por qué" exige capturar el contexto del plan, que hoy no llega al journal.
- **Edad en días naturales:** el replay es `D1` (`step_day_clock`); no son barras efectivas ni intradía.
- **Distancia al objetivo no medible:** el round trip no guarda el `target`; se aproxima con `MFE`/captura, no se presenta como distancia exacta.
- **Sector diferido:** requeriría plumbing nuevo y el catálogo no es `PIT` (ya declarado en sellos previos).
- **`n` pequeño:** `38` ciclos en `11/12` sorteos ⇒ **todos** los cubos `fragile` (`few_cycles_per_draw` y/o `insufficient_draws`); ninguna celda se cita como fuerte.
- **Contrafactual fuera de alcance:** `Δ motor = 0` estricto; no se re-simulan salidas alternativas.
- **`Σ` por mecanismo ≠ global:** sigue declarado (no se cuadra aquí); la reconciliación analítica (`GLOBAL = Σ buckets + unclassified`) queda **fuera** de este sello.
- **Bootstrap no-IID** (`block`/`regime-aware`) sigue **P3**; aquí sólo se declara.
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle v3 (estrategia/dirección + fricción + motivo)
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/multi-band-detail-2021_2026.json

# 2) Plegar los 38 THESIS_EXIT al artefacto del quirófano
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/thesis-exit-2021_2026.json

# 3) Dos corridas deben dar el mismo sha256 (determinismo)
```

---

## 6. Sello

- **Añadidos:** [`dia_d_thesis_exit.py`](../../../../packages/py/application/src/bolsa_application/dia_d_thesis_exit.py), [`v2_97_dia_d_thesis_exit.py`](../../../../apps/api-python/scripts/v2_97_dia_d_thesis_exit.py), [`test_dia_d_thesis_exit.py`](../../../../packages/py/application/tests/test_dia_d_thesis_exit.py), `docs/engineering/evidence/v2.88.45/README.md`.
- **Modificados:** `dia_d_multi_sampling.py` (ledger `-v3`: `strategyVersion`/`direction`), `v2_94` (`_DETAIL_LEDGER_SCHEMA` exige v3 ⇒ re-corre y no mezcla esquemas), `v2_89`/`v2_90`/`v2_91`/`v2_92`/`v2_93`/`v2_94`/`v2_95`/`v2_96` (`meta.bump`), `test_dia_d_bump_guard.py`, `test_dia_d_multi_sampling.py`, `test_dia_d_loss_origin.py`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado; la capa v3 del ledger es aditiva.
- **Tag:** `v2.88.45-beta` → objeto `369a6b9e`, commit `d3b42970`.
- **Commits:** funcional `a9ee8d25` → re-anclaje del freeze `023a1683` → docs `d3b42970`.
- **`Release tag CI` run [`37196539718`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37196539718) VERDE:** `11 jobs success` + `playwright` integrado `skipped`; `python` `4494 passed / 45 skipped` (**+15**); `replay-repro` `REPRODUCIDO` `1E3ADAC2…`.
