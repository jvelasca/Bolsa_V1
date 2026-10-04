# Entrega a auditoría externa (MIA) — `v2.88.48-beta` · AUTO · **DÍA-D-3g: correlación DECISIÓN↔CICLO del `THESIS_EXIT` (huella de decisión intra-tick por `cycle_id`)**

> **Fecha:** 2026-10-04 · **Producto:** V2.88.48-beta · **Package:** `2.11.48-beta` · **Alembic head:** `048_journal_entry_dedupe_key` (**sin migración**).
> **Base:** `v2.88.47-beta` (desambiguación `THESIS_EXIT` vs `STOP`: `structuralStopCandidate 38/38` **medido desde `D1`**). **Este sello cierra la deuda que aquél declaró:** *qué hizo el decider en el tick del toque*.
> **Unidad:** el **ciclo**. **Regla del hueco:** un valor sin muestra es `None`/`NOT_MEASURED`, **nunca** `0`; el **neto** sólo se afirma con fricción `COMPLETE` (si no, es un **suelo** declarado, jamás el bruto disfrazado de neto).
> **`Δ decisión motor = 0`.** Ningún fichero de motor tocado; la costura inerte sigue apagada por defecto. **`Δ motor = 0` DEMOSTRADO LOCALMENTE:** el artefacto congelado de `replay-repro` **se reproduce byte a byte** contra el fixture sellado (§4).
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.48/README.md`](./evidence/v2.88.48/README.md).
> **Nota de auditabilidad:** como en `v2.88.46`/`v2.88.47`, la cita del `Release tag CI` de este sello **no puede** viajar dentro del propio tag (el job sólo corre al empujar el tag): se escribe en un commit **POST-TAG**; el sello previo `v2.88.47-beta` sí lleva la suya publicada.

---

## 1. Qué se entrega (y qué NO)

**Se entrega** la **huella de decisión intra-tick** de los `38` ciclos `THESIS_EXIT`, **leída** —no re-ejecutada— del estado que el worker ya produce tras `auto_turn()`:

1. **Los motivos disparados del tick** (`decisionReasons`: `STRUCTURAL_STOP`, `THESIS_INVALIDATION`, …) y la **etiqueta** del día (`decisionLabel`).
2. **Si la posición sobrevivió** el tick (`survived`) y **cuánto se llenó** del ciclo (`filledQty`, por `contexts.order` con `cycle_id`), más la señal de **DÍA** `dayOrders`/`dayFills` (delta de `report.orders`/`report.fills`), **declarada NO por ciclo**.
3. **La clasificación del toque** (`decisionRoute` ∈ {`materializado`, `stop_evaluado_sin_materializar`, `stop_no_evaluado`, `sin_toque`, `sin_traza`}, tupla **cerrada**), con `stopEvaluatedOnTouch`, `deciderRanOnTouch`, `stopFiredNotFilled` y `stopTouchDays`.
4. **La frontera declarada** de la secuencia (`timelineStartsAt = "first_full_tick_after_entry"`, **D47-01**).
5. La **asociación** de cada fila `managementRows` a su `cycleId` (`(instrument_id, day)`).
6. Todo ello en un **ledger aditivo v6** y en un **bloque `decisionCorrelation`** del artefacto `dia-d-thesis-exit-v4`.

**No se entrega**, y se declara:

- **NO** se separa el caso **A** (el stop se evaluó y **no** generó orden) del caso **C** (el stop generó orden y **no** se llenó aguas abajo): desde la costura inerte ambos colapsan en `stop_evaluado_sin_materializar`; `dayOrders`/`dayFills` son señal de **DÍA** y **no** se usan para separarlos.
- **D47-01 SÓLO se DECLARA:** el día de entrada **no** tiene fotograma; no se captura (la secuencia empieza en el primer tick `D1` completo post-entrada).
- **`decisionRoute` NO es contrafactual:** no se re-simula la decisión ni se afirma qué *habría* pasado.
- La capa v6 es **OPT-IN** (`--cycle-detail`): sin la costura, `decisionRoute = sin_traza` y los booleanos quedan *hueco declarado*, nunca `0`.
- **El nivel congelado SIGUE siendo hoy el stop inicial** (deuda de `v2.88.45`/`v2.88.46`/`v2.88.47`).
- `n` pequeño (`38` ciclos `pooled` / `32` identidades únicas) ⇒ **todos** los cubos `fragile`.
- **Sin contrafactuales.** **REPLAY/OOS ≠ PAPER** (`P3-2`/`P3-3` **ABIERTAS**); `CONFIRMED` **reservado**.

---

## 2. Cambios verificables (todo puro, todo con test)

| Pieza | Fichero | Qué hace |
| --- | --- | --- |
| Ledger v6 | `dia-d-multi-cycle-ledger-v6` | campos **aditivos** sobre `-v5` (compatibles con `-v1`…`-v5`): huella de decisión (`decisionReasons`/`decisionLabel`/`filledQty`/`survived`/`dayOrders`/`dayFills`) y clasificación (`decisionRoute`, `stopEvaluatedOnTouch`, `deciderRanOnTouch`, `stopFiredNotFilled`, `stopTouchDays`, `timelineStartsAt`). Token `STRUCTURAL_STOP` comparado **case-insensitive** (`structural_stop`). Un hueco es `None`, nunca `0`. |
| Módulo puro | `packages/py/application/src/bolsa_application/dia_d_thesis_exit.py` | `SCHEMA_VERSION="dia-d-thesis-exit-v4"`; nuevo bloque `global.decisionCorrelation` + eje `byDecisionRoute` en `axes`; límites actualizados (D47-01, A/C agrupados). |
| Costura inerte | `v2_87_replay_oos_durable_cycle.py` | escribe en el **mismo fotograma del día**, tras `auto_turn()`, `decisionReasons`/`decisionLabel`/`survived`/`filledQty`/`dayOrders`/`dayFills` (leídos de `_v2_last_exit_reasons`/`_v2_last_exit_label` y del delta de `report.orders`/`report.fills`) y anota `managementRows` con `cycleId`; **sólo** con `capture_cycle_detail=True`; con la costura apagada el replay es **idéntico** (un `if`). |
| Acumulador | `v2_93_dia_d_multi.py` | acumula `managementByCycle` y lo pasa a `build_cycle_ledger`. |
| Sellado de esquema | `v2_94_dia_d_multi_band.py` | `_DETAIL_LEDGER_SCHEMA = "dia-d-multi-cycle-ledger-v6"`: con `--cycle-detail` un ledger antiguo se **re-corre** (no se mezclan esquemas). |
| CLI | `v2_97_dia_d_thesis_exit.py` | claves de secuencia + impresión `CORRELACIÓN DECISIÓN↔CICLO` (consola UTF-8 en Windows). |
| Guardián | `apps/api-python/tests/test_dia_d_bump_guard.py` | `meta.bump == package.json.version` en `v2_89`…`v2_97` (`2.11.48-beta`). |
| Tests | `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `test_v2_87_release_log.py` | **163 passed** DÍA-D en total (`32` + `23` + `9` + `1`). |

---

## 3. Medición real (PostgreSQL, `K = 12` sorteos, años `2022-2025`)

**Cobertura:** `38` observaciones `THESIS_EXIT` `pooled` (`32` identidades de ciclo únicas) · `38` con fricción `COMPLETE` · `detailCaptured = true` · **una** estrategia (`v283-window-a`) y **una** dirección (`long`) · `9` símbolos.

### 3.1 Global (idéntico a `v2.88.45`…`v2.88.47`: la capa v6 es ADITIVA)

| Métrica | Valor |
| --- | --- |
| Expectancy bruta | `-0.7087` (`[min -1.2274, max -0.2095]`, `var 0.1056`) |
| Expectancy neta | `-0.7525` |
| HitRate | `0.0833` |
| `levelEqualsInitialStop` | **`38/38`** (`share 1.0`) |
| `disambiguation.route` (v5) | `{ruta_ambas: 34, ruta_mae: 4}` (`ruta_mark = 0`) |
| Concentración | `9` símbolos; top símbolo `26,3 %`; top semana `2025-W12` `21,1 %` |

### 3.2 Correlación DECISIÓN↔CICLO (el hallazgo de esta fase)

| Métrica | Valor | Lectura |
| --- | --- | --- |
| `route` | `{materializado: 19, stop_evaluado_sin_materializar: 19}` | **mitad y mitad**; `stop_no_evaluado = 0`, `sin_toque = 0`, `sin_traza = 0` |
| `routeByStructuralStopCandidate` | `candidate 38/38` | reproduce `v2.88.47` (el nivel **fue tocado** en todos) |
| `stopEvaluatedOnTouch` | **`38/38` (`share 1.0`)** | en **todos** los toques `STRUCTURAL_STOP` está en los motivos ⇒ **`stop_no_evaluado = 0`** |
| `deciderRanOnTouch` | **`38/38` (`share 1.0`)** | el decider dejó huella en todos los toques |
| `stopFiredNotFilled` | `22/38` (`0.5789`) | los `19` sin materializar **+** `3` `materializado` con un toque que no llenó |
| `stopTouchDays` media / mediana | `2.0789` / `1.0` | días con `mark ≤ currentStop` por ciclo |
| `timelineStartsAt` | `first_full_tick_after_entry` | **D47-01** declarado |

### 3.3 Eje `byDecisionRoute`

| Cubo | Sorteos | Ciclos | Expectancy bruta | HitRate | MAE | MFE | `stopFiredNotFilled` | `touchBeforeExit` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `materializado` | `10/12` | `19` | `-0.7936` | `0.1167` | `-1.3836` | `+0.9234` | `3/19` | `10/19` |
| `stop_evaluado_sin_materializar` | `9/12` | `19` | `-0.6938` | `0.0000` | `-1.4222` | `+0.4111` | `19/19` | `3/19` |

Ambos cubos son `fragile` (`few_cycles_per_draw`). **Ninguna celda se cita como fuerte.**

### 3.4 Lectura honesta

- **La pregunta A/B/C de `v2.88.47` CIERRA.** El sello anterior midió que el stop **fue tocado** (`38/38`) pero no podía decir si se **evaluó**. La huella intra-tick lo responde: `stopEvaluatedOnTouch 38/38` y `deciderRanOnTouch 38/38` ⇒ **`stop_no_evaluado = 0`**. **No** hay ningún caso de "toque sin evaluación".
- **Mitad materializa, mitad no.** `materializado 19` = el stop disparó **y** el tick produjo fill (caso **B**); `stop_evaluado_sin_materializar 19` = disparó **sin** fill (casos **A/C agrupados**).
- **El cubo que materializa conserva más recorrido favorable:** `hitRate 0.1167` / `MFE +0.9234` frente a `hitRate 0.0000` / `MFE +0.4111` del que no materializa. Es una **correlación medida**, no una causa.
- **El `3` de diferencia:** `stopFiredNotFilled 22/38` = `19` sin materializar `+` `3` que sí materializaron en otro tick — es la misma semántica ("disparó y no llenó") aplicada **por día**.

### 3.5 Determinismo

Dos corridas de `v2_97` sobre el mismo `--out-dir` ⇒ JSON **byte a byte idéntico**
(`sha256 thesis-exit-v4 = A4CECDAA…`, `176 912 B`; `sequences = 742ADBED…`, `259 280 B`).

---

## 4. Gates (comandos exactos, re-ejecutados)

| Comando | Resultado |
| --- | --- |
| `uv run pytest … (DÍA-D completo) -q` | **163 passed** |
| `uv run pytest packages/py/application/tests/test_dia_d_multi_sampling.py -q` | **32 passed** |
| `uv run pytest packages/py/application/tests/test_dia_d_thesis_exit.py -q` | **23 passed** |
| `uv run pytest packages/py/application/tests/test_dia_d_loss_origin.py -q` | **9 passed** |
| `uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | **1 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (`659` ficheros) |
| `uv run mypy … application/src apps/api-python/src --follow-imports=silent` | sin errores (`531` source files) |
| `pnpm window:test` | **25/25** |
| Determinismo `v2_97` / `v2_97 --sequences` | byte a byte idéntico (`A4CECDAA…` / `742ADBED…`) |
| **`Δ motor = 0` (`replay-repro` LOCAL)** | **`REPRODUCIDO`** `240662250347A2AAD0F8E9F0101185D8ACC80C1D4BD1B4BBFF02D4766D9F54F0` (`3 445 622 B` CRLF) / `1E3ADAC2…` (`3 340 728 B` LF) = **idéntico al sello**; 2 corridas byte a byte |

---

## 5. Límites declarados (no se cierran aquí)

1. `Δ motor = 0`; sin migración; no se mueve ningún umbral ni allocation; sin contrafactuales.
2. **A vs C agrupados** en `stop_evaluado_sin_materializar`: la costura inerte no los separa (`dayOrders`/`dayFills` son señal de DÍA). Deuda declarada.
3. **D47-01 SÓLO se declara:** el día de entrada no tiene fotograma.
4. La capa v6 es **OPT-IN** (`--cycle-detail`); sin ella `decisionRoute = sin_traza`.
5. La huella de decisión **se lee**, no se re-ejecuta (`Δ motor = 0`).
6. **El nivel congelado SIGUE siendo hoy el stop inicial** (deuda de la serie `v2.88.45`…`v2.88.47`).
7. Edad en **días naturales**; `n` pequeño ⇒ **todos** los cubos `fragile`.
8. **REPLAY/OOS ≠ PAPER**; `CONFIRMED` **NO** se emite; `P3-2`/`P3-3` **ABIERTAS**.

---

## 6. Sello

- **Producto:** `V2.88.48-beta`. **Package:** `2.11.48-beta`. **Sin migración.**
- **Ficheros añadidos:** `docs/engineering/evidence/v2.88.48/README.md`, esta entrega.
- **Ficheros modificados (sello funcional):** `dia_d_multi_sampling.py` (ledger `-v6`), `dia_d_thesis_exit.py` (artefacto `-v4`), `v2_87` (costura inerte: huella de decisión + `managementRows` con `cycleId`), `v2_93`/`v2_94`/`v2_97`, `meta.bump` `v2_89`…`v2_97`, `test_v2_87_release_log.py`, `test_dia_d_multi_sampling.py`, `test_dia_d_thesis_exit.py`, `test_dia_d_loss_origin.py`, `package.json`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze), `CHANGELOG.md`, `CURRENT_SYSTEM.md`, `versioning.md`.
- **Tag:** `v2.88.48-beta` → tag object `1e344391`, commit `149d5886` (funcional `814c9392`, freeze `ba8ee8e7`). **`Release tag CI` run [`37221439959`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37221439959) VERDE** (`attempt 1`, `17:41:00Z` → `17:49:22Z`): `11 jobs success` + `playwright` integrado `skipped` por diseño; `certify` `success`; `python` `4521 passed / 45 skipped` (**+10** sobre `v2.88.47`; `ruff` `All checks passed!`, `imports` `4 kept, 0 broken`, `mypy` `531` ficheros); `replay-repro` `REPRODUCIDO` `1E3ADAC2…` (`3 340 728 B` LF / sello `3 445 622 B` CRLF) ⇒ el artefacto congelado no se movió (**`Δ motor = 0`** confirmado por CI). **GitHub Release** `v2.88.48-beta` publicado.
