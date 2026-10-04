# Entrega a auditoría externa (MIA) — `v2.88.46-beta` · AUTO · **DÍA-D-3e: condición de la invalidación del `THESIS_EXIT` (el nivel congelado ES el stop inicial)**

> **Fecha:** 2026-10-04 · **Producto:** V2.88.46-beta · **Package:** `2.11.46-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.45-beta` (quirófano del `THESIS_EXIT`: *dónde viven* los `38` ciclos). **Este sello cierra la deuda que aquél declaró:** *qué condición* invalidó la tesis.
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`, **nunca** `0`; el **neto** sólo se afirma con fricción `COMPLETE` (si no, es un **suelo** declarado, jamás el bruto disfrazado de neto).
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado; el artefacto congelado de `replay-repro` no se mueve (certificado por el propio job del CI: §6).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.46/README.md`](./evidence/v2.88.46/README.md).
> **Nota de auditabilidad:** el sello funcional `v2.88.46-beta` dejó su propia cita del CI como `PENDIENTE` dentro del tag (el commit que la escribe es POST-TAG). Para auditar el objeto **autocontenido**, usar el re-sello [`v2.88.46.1-beta`](./evidence/v2.88.46.1/README.md), que viaja **con** la cita (`Δ motor = 0`).

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la **condición de la invalidación** de los `38` ciclos `THESIS_EXIT`, medida —no inventada— desde el estado CONGELADO de la posición que la costura inerte ya sellada capturaba:

1. **El nivel congelado de invalidación** (`invalidationPrice`) y su normalización en `R` con los anclajes **propios de la posición** (`actualEntry`/`initialRisk`).
2. **El stop vigente al cierre** (`currentStopAtExit`) y si el trailing lo apretó **por encima** del nivel (`stopAboveLevelR`).
3. **La clasificación de la condición** (`thesisExitCondition` ∈ {`sin_geometria`, `nivel_igual_stop`, `nivel_distinto_stop`}).
4. **Si el peor adverso alcanzó el nivel** (`maeReachedLevel`, con aproximación declarada).
5. **La discrepancia de base de `R`** entre el round trip y el stop de la posición (`stopBasisMismatchR`), **medida y declarada**.
6. Todo ello en un **ledger aditivo v4** y en un **bloque `invalidation`** del artefacto `dia-d-thesis-exit-v2`.

**No se entrega**, y se declara:

- **NO** se captura *por qué* el motor elige la ruta de invalidación (mark/MAE) frente al stop puro: sólo se mide que el **nivel ES el stop**.
- `maeReachedLevel` usa el MAE **D1 reconstruido** (barras entre días), **no** el peor adverso persistido por el motor: es una **aproximación declarada**, no el mismo número.
- `stopBasisMismatchR` se **declara** (4/38 ciclos) y **no** se reconcilia: arreglarlo tocaría el replay.
- La capa v4 es **OPT-IN** (`--cycle-detail`): sin la costura, `invalidation.measured = 0` y los anclajes quedan *hueco declarado*, nunca `0`.
- Edad en **días naturales** (`D1`); `n` pequeño (`38` ciclos en `11/12` sorteos) ⇒ **todos** los cubos `fragile`.
- **Sin contrafactuales:** no se re-simulan niveles ni salidas alternativas. **REPLAY/OOS ≠ PAPER** (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **reservado**.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Ledger v4 | `dia-d-multi-cycle-ledger-v4` | campos **aditivos** sobre `-v3` (y compatibles con `-v1`/`-v2`): `invalidationPrice`, `initialStop`, `currentStopAtExit`, `invalidationLevelR`, `currentStopAtExitR`, `stopAboveLevelR`, `stopBasisMismatchR`, `maeVsLevelR`, `levelEqualsInitialStop`, `maeReachedLevel`, `thesisExitCondition`. Normaliza el `R` con los anclajes de la **posición**. |
| Módulo puro | `packages/py/application/src/bolsa_application/dia_d_thesis_exit.py` | `SCHEMA_VERSION="dia-d-thesis-exit-v2"`; nuevo bloque `global.invalidation` + eje `invalidation` en `axes`. |
| Costura inerte | `v2_87_replay_oos_durable_cycle.py` | publica `cycleDetail.invalidationByCycle` (estado congelado por `cycle_id`) **sólo** con `capture_cycle_detail=True`; con la costura apagada el replay es **idéntico** (un `if`). |
| Sellado de esquema | `v2_94_dia_d_multi_band.py` | `_DETAIL_LEDGER_SCHEMA = "dia-d-multi-cycle-ledger-v4"`: con `--cycle-detail` un ledger antiguo se **re-corre** (no se mezclan esquemas). |
| Guardián | `apps/api-python/tests/test_dia_d_bump_guard.py` | `meta.bump == package.json.version` en `v2_89`…`v2_97`. |
| Tests | `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py` | `144 passed` DÍA-D en total (`21` + `18` con nombre propio). |

---

## 3. Medición real (PostgreSQL, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` ciclos `THESIS_EXIT` · `38` con fricción `COMPLETE` · `detailCaptured = true` · `11/12` sorteos con celda · **una** estrategia (`v283-window-a`) y **una** dirección (`long`).

### 3.1 Global (idéntico a `v2.88.45`: la capa v4 es ADITIVA)

| Métrica | Valor |
| --- | --- |
| Expectancy bruta | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| Expectancy neta | `-0.7525` |
| HitRate | `0.0833` |
| MAE media / mediana | `-1.4029 R` / `-1.3499 R` |
| MFE media / mediana | `+0.6672 R` / `+0.3689 R` |
| Captura del MFE (media / mediana) | `0.0449` / `0.0` |
| `leftOnTableR` media / mediana | `+0.6269 R` / `+0.3979 R` |
| Concentración | `9` símbolos; top símbolo `26,3 %`; top semana `2025-W12` `21,1 %` |

### 3.2 Condición de la invalidación (el hallazgo de esta fase)

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `levelEqualsInitialStop` | **`38/38` (`share 1.0`)** | el nivel congelado **ES** el stop inicial ⇒ **`THESIS_EXIT` estructural** |
| `condition` | `{nivel_igual_stop: 38}` | **ningún** `nivel_distinto_stop`: nadie declara un nivel de tesis |
| `invalidationLevelR` media / mediana | `-1.0000` / `-1.0000` | el nivel vive a `-1R` del nacimiento (por construcción) |
| `currentStopAtExitR` media / mediana | `-0.5764` / `-1.0000` | en ≥ la mitad de los ciclos el stop **no** se movió |
| `stopAboveLevelR` media / mediana | `+0.4236` / `0.0` | el trailing apretó el stop por encima del nivel en una **minoría** |
| `maeReachedLevel` | **`35/38` (`92,1 %`)** | el peor adverso D1 reconstruido cruzó el nivel (**aprox. declarada**) |
| `maeVsLevelR` media / mediana | `+0.4029` / `+0.3499` | sobrepaso del nivel por el MAE reconstruido |
| `stopBasisMismatchR` | media `0.1699`; mediana `0.0`; **`shareNonZero 10,5 %` (`4/38`)** | la base de `R` del round trip **discrepa** del stop de la posición (**declarado, no reconciliado**) |

### 3.3 Lectura honesta

- **El `THESIS_EXIT` es estructural, no una condición "blanda".** El token colapsado `thesis_exit` no
  escondía un nivel distinto: el nivel **es** el stop inicial en los `38` ciclos. La diferencia con
  `STOP_EJECUTADO` está en la **ruta de evaluación** (`is_thesis_invalidated` sobre el peor adverso
  persistido + mark), **no** en un nivel distinto.
- **El stop casi nunca se apretó por encima del nivel** (`stopAboveLevelR` mediana `0.0`;
  `currentStopAtExitR` mediana `-1.0`): la media recoge la minoría con trailing.
- **El peor adverso cruzó el nivel en el `92 %`** de los ciclos, con un sobrepaso medio de `+0.40 R`
  (**aproximación** declarada: MAE D1 reconstruido).
- **Discrepancia de base de `R` declarada:** en `4/38` ciclos la base del round trip difiere del stop
  congelado de la posición; la normalización del `realizedR` de esos ciclos no es la del riesgo al nacer.

### 3.4 Determinismo

Dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**
(`sha256 766B8997B2A8A93682D8A5C092ED0CFA4E05D608B162A50AB6049AC6A5865A56`, `81 454 B`).

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `uv run pytest … (DÍA-D subset) -q` | **144 passed** |
| `uv run pytest packages/py/application/tests/test_dia_d_multi_sampling.py -q` | **21 passed** |
| `uv run pytest packages/py/application/tests/test_dia_d_thesis_exit.py -q` | **18 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (`659` ficheros) |
| `uv run mypy … application/src apps/api-python/src --follow-imports=silent` | sin errores (`531` source files) |
| `pnpm --filter @bolsa/web contract:check` | **OK** (sin cambios de DTO) |
| `pnpm window:test` | **25/25** |
| Determinismo `v2_97` | byte a byte idéntico (`sha256 766B8997…`, `81 454 B`) |
| `git status --porcelain -- <motor>` | **vacío** ⇒ `Δ motor = 0` |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral ni allocation; sin contrafactuales.
2. **El nivel congelado ES hoy el stop inicial:** ningún productor emite un `invalidationPrice` de tesis
   distinto ⇒ `THESIS_EXIT` **estructural**. *Por qué* el motor elige la ruta de invalidación sigue **sin**
   capturarse aquí.
3. `maeReachedLevel` es una **APROXIMACIÓN** (MAE D1 reconstruido, no el persistido por el motor).
4. `stopBasisMismatchR` se **declara** y **no** se reconcilia (`4/38`).
5. La capa v4 es **OPT-IN** (`--cycle-detail`); sin ella la geometría es *hueco declarado*.
6. Edad en **días naturales**; `n` pequeño ⇒ **todos** los cubos `fragile`.
7. **REPLAY/OOS ≠ PAPER**; `CONFIRMED` **NO** se emite; `P3-2`/`P3-3` **ABIERTAS**.

---

## 6. Sello

- **Producto:** `V2.88.46-beta`. **Package:** `2.11.46-beta`. **Sin migración.**
- **Ficheros añadidos:** `dia_d_thesis_exit.py` (v2, bloque `invalidation`), `evidence/v2.88.46/README.md`, esta entrega.
- **Ficheros modificados (sello funcional):** `dia_d_multi_sampling.py` (ledger `-v4`), `v2_87` (costura inerte `invalidationByCycle`), `v2_93`/`v2_94`/`v2_97`, `meta.bump` `v2_89`…`v2_97`, `test_dia_d_bump_guard.py`, `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `package.json`, `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.
- **Tag:** `v2.88.46-beta` → objeto `b728fd33`, commit `9658a5cb`.
- **Commits:** funcional `20a77ded` → re-anclaje del freeze `5ebd85aa` → docs `9658a5cb` (tag publicado) → cita POST-TAG `9ab04e60`.
- **`Release tag CI` run [`37202334330`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37202334330) VERDE** (`attempt 1`, `12:30:22Z` → `12:38:39Z`): `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4503 passed / 45 skipped` (**+9** sobre `v2.88.45`; `ruff` `All checks passed!`, `imports` `4 kept, 0 broken`, `mypy` `531` ficheros); `replay-repro` `REPRODUCIDO` `1E3ADAC2…` (`3 340 728 B` LF / sello `3 445 622 B` CRLF) ⇒ el artefacto congelado no se movió (**`Δ motor = 0`** confirmado por CI).
- **Re-sello autocontenido:** `v2.88.46.1-beta` → objeto `039eb6fd`, commit `ce0ffbf3` (package `2.11.46.1-beta`) — `DOCS-ONLY` + bump de metadatos, **`Δ motor = 0`**; lleva **dentro** del tag la cita del CI del sello funcional (§4 de [`evidence/v2.88.46.1/README.md`](./evidence/v2.88.46.1/README.md)). Su propio `Release tag CI` run [`37210471946`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37210471946) **VERDE** (`11 jobs success` + `playwright` integrado `skipped`; `python` `4503 passed / 45 skipped` = **idéntico** al sello funcional ⇒ `Δ = 0`; `replay-repro` `REPRODUCIDO` `1E3ADAC2…`). **GitHub Release** [`v2.88.46.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.46.1-beta) publicado.
