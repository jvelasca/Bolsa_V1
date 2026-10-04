# Evidencia `v2.88.46-beta` — `AUTO · DÍA-D-3e`: **condición de la invalidación del `THESIS_EXIT`** (el nivel congelado ES el stop inicial), sin tocar motor

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.46-beta` · **Package:** `2.11.46-beta` · **AsOf:** 2026-10-04 · **Nature:** `INVESTIGACION` · **Fase:** `V2.98 DIA-D AUTO THESIS CONDITION` · **Δ motor = 0**.

**Schemas:** `dia-d-thesis-exit-v2` (`KIND = "DIA_D_AUTO_THESIS_EXIT"`) y `dia-d-multi-cycle-ledger-v4` (aditivo sobre `-v3`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración** (leer no escribe esquema). **Contrato HTTP:** sin cambios (todo es Python puro; no viaja por OpenAPI).

**Padres:** [`v2.88.45`](../v2.88.45/README.md) (dónde viven los `38` ciclos `THESIS_EXIT`) → [`v2.88.44`](../v2.88.44/README.md) (de dónde nace la pérdida: mecanismo × coste × entrada) → [`v2.88.43`](../v2.88.43/README.md) (bootstrap de ciclos) → [`v2.88.42`](../v2.88.42/README.md) (venue).

**Packages de evidencia (no versionados, `.gitignore`):**

- `operability_runs/dia-d-auto-band/draw-00…draw-11/multi-cycles.json` — `12` ledgers `dia-d-multi-cycle-ledger-v4` (con la geometría de la invalidación), `92–137 KB` cada uno.
- `operability_runs/dia-d-auto/multi-band-detail-2021_2026.json` — el plegado `v2_94` con `--cycle-detail` (`45 205 B`).
- `operability_runs/dia-d-auto/thesis-exit-2021_2026.json` — el artefacto `dia-d-thesis-exit-v2` (`81 454 B`).

---

## 0. Qué añade este sello (y qué NO)

`v2.88.45` declaró una deuda: el `THESIS_EXIT` es el mecanismo que carga el `R` bruto negativo, pero el journal sólo publica el token **colapsado** `thesis_exit` (`rawReasonTokens = {thesis_exit: 38}`), así que *por qué se invalidó la tesis* **no** llegaba al artefacto. Este sello **mide la condición** —sin inventarla— desde el estado CONGELADO de la posición que la **costura inerte** ya sellada (`v2_87.capture_cycle_detail`) recogía, la persiste en un **ledger aditivo v4** y la pliega en un nuevo bloque `invalidation` del quirófano.

**NO** toca el motor, los umbrales, `TOP_N` ni la allocation. **NO** introduce contrafactuales. **NO** reconcilia la discrepancia de base de R que sí **mide** (`stopBasisMismatchR`): se declara, no se arregla.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **La capa v4 es ADITIVA:** los `38` ciclos `THESIS_EXIT` y su `expectancyR` bruta `-0.7087` son idénticos a `v2.88.45`. | Que el global difiera del sello anterior. | `global.realizedRGross.expectancyR.mean = -0.7087` (`total -2.3462`), `cycles = 38`, `coverage.cyclesTotal = 38`, `hitRate = 0.0833`. |
| **2** | **El nivel de invalidación ES el stop inicial en TODOS los ciclos:** ningún productor declara un `invalidationPrice` distinto ⇒ un `THESIS_EXIT` es **estructural**. | Que `levelEqualsInitialStop` no sea `38/38`. | `global.invalidation.levelEqualsInitialStop = {count: 38, measured: 38, share: 1.0}`; `condition = {nivel_igual_stop: 38}`; `invalidationLevelR` media/mediana `-1.0000`. |
| **3** | **El nivel se normaliza con los anclajes de la POSICIÓN, no del round trip:** con `actualEntry`/`initialRisk` el nivel cae a `-1R` exacto. | Que `invalidationLevelR` no sea `-1.0` usando el riesgo al nacer. | `invalidationLevelR = {mean: -1.0000000000000002, median: -1.0000000000000002, measured: 38}`. |
| **4** | **El trailing apretó el stop por encima del nivel en una minoría de ciclos:** el `stop` vigente al cierre **subió** por encima del nivel congelado sólo en parte de la muestra. | Que `stopAboveLevelR` sea `0` en TODOS o negativo. | `stopAboveLevelR = {mean: +0.4236, median: 0.0}`; `currentStopAtExitR = {mean: -0.5764, median: -1.0}`. |
| **5** | **El peor adverso reconstruido alcanzó el nivel en la mayoría:** `35/38` ciclos con MAE D1 cruzando el nivel (aproximación declarada del persistido). | Que `maeReachedLevel` sea `~0`. | `maeReachedLevel = {count: 35, measured: 38, share: 0.9211}`; `maeVsLevelR = {mean: +0.4029, median: +0.3499}`. |
| **6** | **La base de R del ledger discrepa del stop de la posición en `4/38` ciclos, y se declara (no se reconcilia).** | Que `stopBasisMismatchR.shareNonZero` sea `0`. | `stopBasisMismatchR = {mean: 0.1699, median: 0.0, measured: 38, shareNonZero: 0.1053}` (`4/38`). |
| **7** | **Cobertura total de la geometría:** los `38` ciclos traen el estado capturado (ningún hueco). | Que `invalidation.measured < 38` o algún anclaje sea `None`. | `coverage.detailCaptured = true`; `invalidation.measured = 38`; `condition` sin `sin_geometria`. |
| **8** | **Sin la costura la geometría es un hueco declarado, nunca `0`:** con `--cycle-detail` apagado, `invalidation.measured = 0`. | Que aparezca un `0.0` donde falta el dato. | Regla dura del código (`None`/`NOT_MEASURED`) + test `test_ledger_v4_without_capture_declares_the_gap_never_zero`. |
| **9** | **Determinismo:** dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**. | Que dos corridas difieran. | `sha256 766B8997B2A8A93682D8A5C092ED0CFA4E05D608B162A50AB6049AC6A5865A56`, `81 454 B` (reproducido). |
| **10** | **`Δ motor = 0`:** ningún fichero de motor cambia; la capa v4 es aditiva y la costura `capture_cycle_detail` sigue inerte por defecto. | Que el árbol del motor cambie o que la costura altere el replay con `capture_cycle_detail=False`. | `git status` del motor vacío; la costura sólo añade LECTURA del estado ya producido; `v2_95` sigue leyendo `realizedR/year/regime`. |

---

## 2. Medición real (`PostgreSQL`, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` ciclos `THESIS_EXIT` · `38` con fricción `COMPLETE` (`0` `PARTIAL`, `0` `UNKNOWN`) · `detailCaptured = true` · `11/12` sorteos con celda · **una** estrategia (`v283-window-a`) y **una** dirección (`long`).

### 2.1 Global (idéntico a `v2.88.45`: la capa v4 es aditiva)

| Métrica | Valor |
| --- | --- |
| R bruto total (por sorteo, media) | `-2.3462` |
| Expectancy bruta (entre sorteos) | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| HitRate | `0.0833` |
| R neto total (por sorteo, media) | `-2.5012` (medido) |
| Expectancy neta | `-0.7525` |
| Fricción media por sorteo | `0.0438 R` |
| MAE media / mediana | `-1.4029 R` / `-1.3499 R` |
| MFE media / mediana | `+0.6672 R` / `+0.3689 R` |
| Captura del MFE (media / mediana) | `0.0449` / `0.0` (medida en `34` ciclos) |
| `leftOnTableR` media / mediana | `+0.6269 R` / `+0.3979 R` |
| Excursión adversa temprana (D1, 3 barras) | media `-0.9505 R`; `< -0.5R` `76,3 %`; `< -1.0R` `52,6 %` |
| Slippage señal→ejecución | media `10,56 bps` / mediana `10,51 bps` |

### 2.2 Condición de la invalidación (nuevo, capa v4)

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `levelEqualsInitialStop` | `38/38` (`share 1.0`) | el nivel congelado **ES** el stop inicial: **THESIS_EXIT estructural** |
| `condition` | `{nivel_igual_stop: 38}` | ningún `nivel_distinto_stop` (nadie declara un nivel de tesis) |
| `invalidationLevelR` media / mediana | `-1.0000` / `-1.0000` | el nivel vive a `-1R` del nacimiento (por construcción) |
| `currentStopAtExitR` media / mediana | `-0.5764` / `-1.0000` | en ≥ la mitad de los ciclos el stop NO se movió; la media recoge el ratchet |
| `stopAboveLevelR` media / mediana | `+0.4236` / `0.0` | el trailing apretó el stop **por encima** del nivel en una minoría |
| `maeReachedLevel` | `35/38` (`92,1 %`) | el peor adverso D1 reconstruido cruzó el nivel (aprox. declarada) |
| `maeVsLevelR` media / mediana | `+0.4029` / `+0.3499` | cuánto sobrepasó el nivel el MAE reconstruido |
| `stopBasisMismatchR` | media `0.1699`; mediana `0.0`; `shareNonZero 10,5 %` (`4/38`) | la base de R del round trip **discrepa** del stop de la posición en `4` ciclos (declarado, no reconciliado) |

### 2.3 Por edad, año y régimen (sin cambios: idénticos a `v2.88.45`)

| Dimensión | Cubo | Sorteos | Ciclos | Expectancy bruta |
| --- | --- | --- | --- | --- |
| Edad | `1-3` | `1/12` | `1` | `-0.8236` |
| Edad | `4-10` | `10/12` | `20` | `-0.8153` |
| Edad | `11-30` | `8/12` | `14` | `-0.8767` |
| Edad | `>30` | `3/12` | `3` | `+0.7375` |
| Año | `2022` | `10/12` | `19` | `-0.7800` |
| Año | `2023` | `1/12` | `2` | `-0.5783` |
| Año | `2024` | `2/12` | `2` | `-0.5251` |
| Año | `2025` | `9/12` | `15` | `-0.7091` |
| Régimen | `high_vol` | `11/12` | `34` | `-0.6819` |
| Régimen | `trend_down` | `3/12` | `4` | `-0.7727` |

Todos los cubos siguen `fragile` (`few_cycles_per_draw`; `1-3` y `2023` además `insufficient_draws`). **Concentración:** `9` símbolos distintos, top símbolo `26,3 %`, top semana `2025-W12` `21,1 %`.

### 2.4 Lectura honesta

- **El `THESIS_EXIT` es estructural.** El nivel de invalidación **ES** el stop inicial en los `38` ciclos (`share 1.0`): no hay ninguna subpoblación donde un productor declare un nivel de tesis distinto. El hallazgo **corrige** la intuición de que el token colapsado escondía una condición "blanda": la condición es **el propio stop**, y el `THESIS_EXIT` se distingue del `STOP_EJECUTADO` por la **ruta de evaluación** (`is_thesis_invalidated` sobre el peor adverso persistido + mark), no por un nivel distinto.
- **El stop casi nunca se apretó por encima del nivel.** `stopAboveLevelR` mediana `0.0` y `currentStopAtExitR` mediana `-1.0`: en al menos la mitad de los ciclos el stop vigente al cierre **seguía en el nivel**. La media (`+0.42` / `-0.58`) recoge la minoría con trailing.
- **El peor adverso cruzó el nivel en el `92 %`** de los ciclos (`maeReachedLevel 35/38`), con un sobrepaso medio de `+0.40 R` — **aproximación** declarada: se calcula con el MAE **D1 reconstruido**, no con el MAE persistido por el motor.
- **Discrepancia declarada (no reconciliada).** En `4/38` ciclos (`10,5 %`) la base de R del round trip (`stop`) difiere del stop congelado de la posición (`stopBasisMismatchR`, media `0.17 R`, hasta `~1.08 R`): la normalización del `realizedR` de esos ciclos NO es la del riesgo al nacer. Se **mide y se declara**; arreglarlo tocaría el replay (fuera de este sello, `Δ motor = 0`).

---

## 3. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest` DÍA-D (`test_dia_d_*.py` + `test_dia_d_bump_guard.py`) | **144 passed** (v2.88.45 selló `135`; `test_dia_d_multi_sampling.py` `21`, `test_dia_d_thesis_exit.py` `18`, `test_dia_d_bump_guard.py` `1`) |
| `test_dia_d_multi_sampling.py` (capa v4) | **21 passed** (nivel/stop al cierre, ratchet, nivel distinto, anclajes de la posición + discrepancia de base, hueco sin captura) |
| `test_dia_d_thesis_exit.py` (bloque `invalidation`) | **18 passed** (plegado, nivel distinto + discrepancia, hueco medido vs `0` medido, determinismo) |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros, `3 608` dependencias) |
| `mypy` (gate real, `--follow-imports=silent`) | limpio (`531` ficheros) |
| `contract:check` | OK (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| `test_dia_d_bump_guard.py` | OK (`meta.bump` alineado a `2.11.46-beta` en `v2_89…v2_97`) |
| Determinismo `v2_97` | byte a byte idéntico (`sha256 766B8997…`, `81 454 B`) |
| `Δ motor = 0` | `git status` vacío sobre los ficheros de motor; la costura sólo **lee** estado ya producido; la capa v4 del ledger es aditiva |

---

## 4. Límites declarados (NO se cierran aquí)

- **El nivel congelado ES hoy el stop inicial** (deuda declarada): ningún productor emite un `invalidationPrice` de tesis distinto, así que la capa v4 **confirma** que el `THESIS_EXIT` es estructural; *por qué* el motor elige la ruta de invalidación (mark/MAE) frente al stop puro sigue **sin** capturarse aquí.
- **`maeReachedLevel` es una APROXIMACIÓN:** usa el MAE **D1 reconstruido** (barras entre días), no el peor adverso persistido por el motor (`mfeMae.maeR`). No son el mismo número y no se presentan como tal.
- **`stopBasisMismatchR` se declara y NO se reconcilia:** la normalización de R del ledger (`stop` del round trip) puede diferir del stop congelado de la posición; arreglarlo sería tocar el replay.
- **La capa v4 es OPT-IN:** exige la costura `--cycle-detail`; sin ella `invalidation.measured = 0` y los anclajes quedan hueco declarado (nunca `0`).
- **Edad en días naturales:** el replay es `D1` (`step_day_clock`); no son barras efectivas ni intradía.
- **`n` pequeño:** `38` ciclos en `11/12` sorteos ⇒ **todos** los cubos `fragile`; ninguna celda se cita como fuerte.
- **Contrafactual fuera de alcance:** `Δ motor = 0` estricto; no se re-simulan ni salidas ni niveles alternativos.
- **Bootstrap no-IID** (`block`/`regime-aware`) sigue **P3**; aquí sólo se declara.
- **REPLAY/OOS ≠ PAPER:** no sustituye la ventana PAPER real (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Regenerar los 12 sorteos con detalle v4 (geometría de la invalidación)
uv run --no-sync python apps/api-python/scripts/v2_94_dia_d_multi_band.py \
  --reuse --cycles --cycle-detail \
  --from-year 2021 --to-year 2026 \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/multi-band-detail-2021_2026.json

# 2) Plegar los 38 THESIS_EXIT al artefacto del quirófano (schema v2, bloque invalidation)
uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \
  --out-dir operability_runs/dia-d-auto-band \
  --out operability_runs/dia-d-auto/thesis-exit-2021_2026.json

# 3) Dos corridas deben dar el mismo sha256 (determinismo)
```

> **Nota de re-ejecución:** `v2_94._DETAIL_LEDGER_SCHEMA = "dia-d-multi-cycle-ledger-v4"` obliga a re-correr
> un sorteo cuyo ledger no sea v4. La capa v4 **redefinió campos** durante la fase (sin cambiar el string
> del esquema), así que al regenerar hay que **borrar** los `draw-XX/multi-cycles.json` previos o correr sin
> `--reuse`: si no, `--reuse` reutilizaría un ledger v4 antiguo con la semántica anterior.

---

## 6. Sello

- **Añadidos:** `docs/engineering/evidence/v2.88.46/README.md`.
- **Modificados:** `dia_d_multi_sampling.py` (ledger `-v4`: geometría de la invalidación + normalización por anclajes de la posición + `stopBasisMismatchR`), `dia_d_thesis_exit.py` (`dia-d-thesis-exit-v2`: bloque `global.invalidation` + eje `invalidation` + límites), `v2_87_replay_oos_durable_cycle.py` (costura inerte: `cycleDetail.invalidationByCycle`), `v2_93_dia_d_multi.py` (acumula y pasa la captura), `v2_94_dia_d_multi_band.py` (`_DETAIL_LEDGER_SCHEMA` exige v4), `v2_97_dia_d_thesis_exit.py` (docstring v4), `v2_89`/`v2_90`/`v2_91`/`v2_92`/`v2_93`/`v2_94`/`v2_95`/`v2_96`/`v2_97` (`meta.bump`), `test_dia_d_bump_guard.py`, `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `package.json`, `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`.
- **`Δ motor = 0`:** ningún fichero de motor tocado (la costura `capture_cycle_detail` sólo lee estado ya producido y su default sigue `False`).
- **Tag:** `v2.88.46-beta` → objeto `b728fd33`, commit `9658a5cb`.
- **Commits:** funcional `20a77ded` → re-anclaje del freeze `5ebd85aa` → docs `9658a5cb`.
- **`Release tag CI` run [`37202334330`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37202334330) VERDE:** `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4503 passed / 45 skipped` (**+9** sobre `v2.88.45`); `replay-repro` `REPRODUCIDO` `1E3ADAC2…` (`3 340 728 B` LF / sello `3 445 622 B` CRLF) ⇒ el artefacto congelado no se movió.
- **Re-sello autocontenido:** [`v2.88.46.1-beta`](../v2.88.46.1/README.md) — `DOCS-ONLY` + bump de metadatos (`Δ motor = 0`). Este fichero, **dentro** del tag `v2.88.46-beta`, dejaba la cita de arriba como `PENDIENTE` (el commit que la escribe es POST-TAG); el re-sello entrega el mismo objeto **con** la cita dentro del tag. Auditoría externa: [`entrega-auditoria-externa-mia-v2.88.46-2026-10-04.md`](../../entrega-auditoria-externa-mia-v2.88.46-2026-10-04.md).
