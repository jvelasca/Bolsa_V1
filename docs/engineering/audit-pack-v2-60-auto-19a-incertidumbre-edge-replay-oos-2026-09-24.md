# Audit-pack `AUTO-19A` Incertidumbre del edge + Replay OOS — `1.85.0-beta` (2026-09-24)

**Fase:** `V2.60` / `AUTO-19A`. **Producto:** BETA / no producción (**el flag Adaptive sigue OFF**).
**Sin migración.** `_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`; el gobernador **no se toca**.
**El sello del reparto NO se mueve: sigue en `auto18-v1`.**

**Documentos de la fase:** [plan](./plan-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[relevo](./traspaso-relevo-post-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md).

---

## 0. Resumen: qué instala esta pasada

`AUTO-18` publicaba **cuánto** se había medido (`confidence`/`coverage`/`effective_N`) y una expectancy
**encogida**, pero **no** el **intervalo de incertidumbre** del número ni la **confianza de que haya edge**:
un punto sin intervalo es una **certeza disfrazada**. `AUTO-19A` cierra los dos huecos y añade un
instrumento de validación:

1. **Un intervalo de incertidumbre puro** (`auto_adaptive_uncertainty.py`, nuevo): `ExpectancyInterval`
   por **bootstrap de EPISODIOS** (`bootstrap_episodes_v1`), con semilla declarada, `lower ≤ point ≤ upper`
   por construcción y ausencia **declarada** (`no_cycles`/`insufficient_episodes`).
2. **`edgeConfidence` — un eje PROPIO** (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`), derivado del **signo del
   intervalo frente a cero** y modulado a la baja por cobertura, deterioro y base del neto. `UNKNOWN` es
   **no-medición**, nunca un `LOW` por defecto.
3. **Una batería de replay OOS estadístico** (`auto_adaptive_replay.py`, nuevo): parte cada estrategia en
   IS/OOS **cronológico**, re-aplica las estadísticas de decisión de `AUTO-18` sobre el IS y las compara
   con la expectancy **realizada** del OOS; responde con números y `sample` a las cuatro preguntas del
   auditor, con veredicto `supported`/`not_supported`/`inconclusive`.
4. **Cableado aditivo**: `StrategyHealth`/`AdaptivePlan` ganan los dos campos y un frame `uncertainty`;
   la evidencia gana `expectancyInterval`/`edgeConfidence`. **Sin `uncertainty`, el plan es byte-idéntico**
   a `AUTO-18` y el sello **no** se mueve.

## 1. El invariante: **ninguna lectura de edge se publica como certeza ni como permiso**

> La expectancy se publica con su **intervalo de incertidumbre**; la **confianza de medición**
> (`confidence`, ya existente) se separa de la **confianza de edge** (`edgeConfidence`); y **ninguna de
> las dos mueve el reparto** (que sigue siendo `auto18-v1`). El replay demuestra —o declara **inconcluso**—
> con datos si el shrinkage, el `effective_N`, la banda y la cobertura predicen mejor **fuera de muestra**.

Seis corolarios, con test y con mutación que los mata:

1. **La independencia se mide una sola vez.** El material del intervalo sale de `regime_episodes`
   (promovida a público en `auto_adaptive_confidence.py:434`); `measured_r` (`:407`), `regime_of` (`:417`)
   y `coverage_band` (`:503`) también se exponen. La incertidumbre **no** reimplementa la semántica de
   episodios: **un solo productor**. (M149 ⇔ remuestrear ciclos sueltos.)
2. **La ausencia no es un defecto, pero se declara.** Sin ciclos medidos ⇒ `point=None` + `no_cycles`; con
   menos de `min_episodes` rachas ⇒ solo el punto + `insufficient_episodes` y `edge=UNKNOWN`. **Nunca** se
   fabrica un intervalo que la muestra no sostiene. (M153 ⇔ publicar el percentil con una sola racha.)
3. **El intervalo contiene a su punto.** `lower ≤ point ≤ upper` **por construcción** (se ensancha si
   hiciera falta, `auto_adaptive_uncertainty.py:357-358`): contradecir su propio punto sería una
   contradicción publicada. (M150 ⇔ bootstrap sin semilla ⇒ deja de ser reproducible.)
4. **El eje del EDGE es propio.** `_edge_confidence` (`:375`) decide base por el **signo del intervalo**
   frente a cero y degrada un escalón (con suelo `LOW`, nunca a `UNKNOWN`) por `coverage LOW/UNCOVERED`,
   `decay SEVERE` y `basis DATA_DEGRADED`, cada uno con su nota. (M151 ⇔ deducirlo de la medición;
   M152 ⇔ `UNKNOWN` disfrazado de `LOW`.)
5. **El replay no inventa veredictos.** Cada pregunta declara su `sample`; sin los **dos** grupos que la
   comparación exige ⇒ `inconclusive`. Read-only, sin I/O, **sin re-simular órdenes**. (M155 ⇔ quitar la
   guarda de muestra; M156 ⇔ leer el refutado como soportado; M157 ⇔ invertir la cobertura.)
6. **La lectura es ADITIVA.** Sin `uncertainty` el plan y la evidencia son **byte-idénticos** a `AUTO-18`;
   el sello del reparto **no** se mueve. (M158 ⇔ arrastrar otro sello.)

## 2. Sin migración: qué se declara y qué **no**

- **`_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`** (medido en
  `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`): el intervalo y el replay son
  **recomputables** del material ya medido (fills/ciclos), así que no hay columna nueva.
- **Sin backfill**: la incertidumbre se calcula **cada vez** sobre el mismo material que `AUTO-18` mide;
  no se persiste por tick y no hay histórico que reconstruir.
- **La evidencia viaja en `healthByStrategy`/`evidence_for`** con **dos claves nuevas** (`expectancyInterval`,
  `edgeConfidence`) que **solo** aparecen cuando hay lectura: el **journal durable** (proyección por lista
  blanca `riskMultipliers` + `evidenceAxis`, `auto_adaptive_journal.py`) queda **byte a byte igual**.

## 3. El intervalo: bootstrap por EPISODIOS (no por ciclos)

| Punto | `ruta:línea` |
| --- | --- |
| `ADAPTIVE_UNCERTAINTY_METHOD = "bootstrap_episodes_v1"` | `auto_adaptive_uncertainty.py:94` |
| `level` por defecto `0.90` (clamp `[0.5, 0.99]`) | `auto_adaptive_uncertainty.py:99` |
| `seed` declarada (`42`) y `resamples` (`2000`) | `auto_adaptive_uncertainty.py:107` / `:103` |
| `min_episodes` declarado (`2`) | `auto_adaptive_uncertainty.py:111` |
| `percentile` (interpolación lineal, pura) | `auto_adaptive_uncertainty.py:155` |
| `ExpectancyInterval` | `auto_adaptive_uncertainty.py:175` |
| `_interval_from_episodes` (bootstrap por rachas) | `auto_adaptive_uncertainty.py:295` |
| `dispersion_r` (desviación de las medias bootstrap) | `auto_adaptive_uncertainty.py:360` |
| `regime_episodes` (rachas, **pública**) | `auto_adaptive_confidence.py:434` |
| `coverage_band` (convención de `AUTO-18`, **pública**) | `auto_adaptive_confidence.py:503` |

- **Se remuestrean rachas ENTERAS con reemplazo**: la dependencia dentro de una fase de mercado no se
  destruye (el error que cometería el bootstrap ingenuo por ciclos). 60 ciclos de **una sola** fase son
  **1** observación, y con una sola racha **no hay percentil honesto**: se publica el punto y se declara.
- **Reproducible y orden-invariante**: mismo material + misma semilla + mismos remuestreos ⇒ mismo
  intervalo; el orden de llegada de los ciclos **no** cambia la lectura (se ordena por instante, y las
  filas sin instante legible se ordenan al final y **se declaran**, `undated_cycles`).
- **Celdas sobre el MISMO material**: las celdas `strategy × regime` se miden sobre las rachas agrupadas
  por régimen, **no** sobre un segundo material que pudiera divergir; el orden de celdas lo manda el cruce
  que la confianza ya publica.

## 4. La confianza de EDGE: un eje distinto de la banda de medición

| Punto | `ruta:línea` |
| --- | --- |
| Bandas de EDGE (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`) | `auto_adaptive_uncertainty.py:119-131` |
| Notas declaradas (`crosses_zero`, `negative`, `low_coverage`…) | `auto_adaptive_uncertainty.py:135-141` |
| `_edge_confidence` (base por signo + degradaciones) | `auto_adaptive_uncertainty.py:375` |
| `_cell_uncertainty` (celda con la banda de ESA celda) | `auto_adaptive_uncertainty.py:438` |
| `_strategy_uncertainty` (estrategia y su desglose) | `auto_adaptive_uncertainty.py:477` |
| `build_adaptive_uncertainty` (fachada pura) | `auto_adaptive_uncertainty.py:554` |
| `RegimeUncertainty` / `StrategyUncertainty` / `AdaptiveUncertainty` | `:213` / `:237` / `:263` |

- **`confidence` no se renombra**: sigue siendo la banda de **MEDICIÓN** (contrato JSON sellado por
  `AUTO-12`/`AUTO-18`). `edgeConfidence` es el **eje nuevo** y se publica en campos separados.
  `measurement=HIGH` con `edge=LOW` significa «sabemos bien que ahora mismo **no** hay edge»;
  `measurement=LOW` con `edge=UNKNOWN` significa «no sabemos lo suficiente»: **dos hechos distintos**.
- **Suelo `LOW`, nunca `UNKNOWN` por degradación**: con medición, tres degradaciones bajan tres escalones
  y se quedan en `LOW`; `UNKNOWN` es **solo** no-medición (M152 lo fija).
- **`UNKNOWN` en `decay` no castiga**: no haber podido comparar no es deterioro (test dedicado).

## 5. El replay OOS: un instrumento, no una decisión

| Punto | `ruta:línea` |
| --- | --- |
| `REPLAY_METHOD = "statistical_oos_v1"` | `auto_adaptive_replay.py:91` |
| Fracción OOS `0.30` (clamp `[0.10, 0.40]`) | `auto_adaptive_replay.py:95-99` |
| Mínimos por tramo (`is=8`, `oos=4`, `cells=2`) | `auto_adaptive_replay.py:101-107` |
| `_compare` (veredicto con epsilon declarado) | `auto_adaptive_replay.py:137` |
| `ReplayCell` / `ReplayQuestion` / `ReplayReport` | `:147` / `:205` / `:225` |
| `_majority_regime` (régimen que dominó el OOS) | `auto_adaptive_replay.py:267` |
| `_build_cell` (split IS/OOS + errores + signos) | `auto_adaptive_replay.py:290` |
| Las cuatro preguntas | `:401` / `:436` / `:468` / `:501` |
| `build_replay_report` (fachada pura) | `auto_adaptive_replay.py:539` |
| CLI sin PG | `scripts/research/auto_replay_battery.py` |
| Fixture determinista | `packages/py/analytics/tests/fixtures/auto_replay_cycles.json` |

- **Split CRONOLÓGICO** por `strategyVersion`: el IS es el tramo **viejo** y el OOS el **reciente** (test
  que lo fija numéricamente: con 30 ciclos donde los 21 viejos valen `+1 R` y los 9 recientes `−1 R`, el
  `is_expectancy_r` es `1.0` y el `oos_expectancy_r` es `−1.0`). Los errores `|pred_IS − real_OOS|` solo
  existen si existen sus dos términos (nunca un cero de relleno).
- **Cuatro preguntas** con su `sample` y sus métricas: (1) shrinkage — error medio `shrunk` vs `raw` y
  acierto de signo; (2) `effective_N` — mediana y error del grupo alto vs bajo; (3) banda — dispersión OOS
  de `HIGH` vs `LOW` (solo celdas con ≥ 2 ciclos OOS); (4) cobertura — error de celdas cubiertas vs no
  cubiertas en el régimen que **dominó** el OOS.
- **La lectura del instrumento sobre el fixture sintético** (medida, se reproduce con el comando del §7):
  `shrinkage_improves_oos = supported` (error medio `0.2359` → `0.1650`), `effective_n_improves_calibration
  = supported` (error alto `0.1078` vs bajo `0.2999`, mediana `11`), `high_confidence_is_more_stable =
  not_supported` (dispersión `HIGH` `0.9662` vs `LOW` `0.5604`) y `coverage_improves_selection =
  inconclusive` (0 celdas cubiertas: sin los dos grupos **no hay veredicto**). **Que una pregunta refute y
  otra se declare inconclusa es la prueba de que el instrumento no es un sello de goma.**

## 6. Matriz de mutaciones `M149…M158`

10 etiquetas nuevas en el bloque AUTO-19A de `v2_44_mutation_audit.py`, cada una con los tests que la
muerden:

| Etiqueta | Qué rompe | Rojos (por nombre) |
| --- | --- | --- |
| `M149` episodios aplanados | remuestrea **ciclos** sueltos, no rachas | `test_one_single_regime_phase_does_not_fabricate_an_interval` |
| `M150` azar sin semilla | bootstrap sin la semilla declarada | `test_the_bootstrap_is_reproducible_and_order_invariant` |
| `M151` edge de la medición | `edgeConfidence` sale de la banda, no del intervalo | 15 tests de `EDGE`/intervalo |
| `M152` `UNKNOWN`→`LOW` | la ausencia se publica como edge bajo | `test_no_measurement_is_unknown_not_low`, `test_too_few_episodes_are_unknown_even_with_a_point`, `test_one_single_regime_phase_…`, `test_an_insufficient_interval_is_declared_not_fabricated` |
| `M153` rachas insuficientes calladas | percentil con una sola racha | `test_one_single_regime_phase_does_not_fabricate_an_interval` |
| `M154` replay sin partir | el IS incluye el OOS | `test_the_in_sample_is_the_old_tramo_and_the_out_of_sample_the_recent_one` |
| `M155` veredicto sin muestra | desaparece la guarda de `sample` mínimo | 3 tests de la batería |
| `M156` refutado→soportado | la comparación no distingue el grupo peor | las 4 preguntas |
| `M157` cobertura invertida | compara cubierto/no cubierto al revés | `test_the_coverage_question_compares_the_covered_regime` |
| `M158` sello movido | la lectura arrastra otro sello de reparto | 4 tests (incluida la costura) |

- **Corrida COMPLETA `M1…M158`**: **`158/158`** muerden, **`0`** en `NADA`, **`0`** fragmentos ausentes,
  restauración **byte a byte** y huella `git status` **idéntica** (`intacto: la sonda no altero el arbol`).
- **Realineos declarados: 0.** Ninguna etiqueta anterior (`M1…M148`) perdió su ancla: la promoción de
  `regime_episodes`/`coverage_band` a público **no** cambió el cuerpo de los fragmentos que la sonda muta.

## 7. Verificación (lo medido, y lo que no se pudo medir aquí)

- **Compuertas (comandos de CI):** `ruff check packages/py apps/api-python --config pyproject.toml` ⇒
  **`All checks passed!`**; `mypy` con el comando **exacto** del YAML ⇒ **`Success: no issues found in 499
  source files`**; `lint-imports --config packages/py/.importlinter` ⇒ **`4 kept, 0 broken`**.
- **Tramo de la fase** (12 suites: unit de incertidumbre y replay, `test_auto_adaptive.py`,
  `test_auto_adaptive_confidence.py`, `test_auto_self_evaluation_feed.py` y las costuras `v60`/`v59`/`v53`/
  `v54`×2/`v55`/`v57`) ⇒ **`271 passed`**, `0` rojos.
- **Batería pre-tag con la selección EXACTA del CI** (la lista literal de `python-ci.yml`, incluido
  `apps/api-python/tests` con sus `--ignore`) ⇒ **`2774 passed`**, `0` rojos, **`94.98 s`** (**+46** sobre
  `v2.59`: 20 unit de incertidumbre + 16 de replay + 4 de la costura nueva + 4 de los lectores públicos +
  2 de byte-identidad). Solo queda fuera lo que exige **PostgreSQL real**.
- **Delta simétrico FICHERO A FICHERO contra `HEAD`** (nunca restando totales): se corren las versiones de
  `HEAD` de los **dos** ficheros de test modificados (`test_auto_adaptive.py`,
  `test_auto_adaptive_confidence.py`) contra el árbol de la fase ⇒ **`144 passed`, `0` rojos**. La fase es
  **puramente aditiva**: no hay ni un rojo declarado que enumerar.
- **Reproducción del instrumento** (no reinventar comandos):

```bash
uv run --no-sync python scripts/research/auto_replay_battery.py
# -> ReplayReport JSON por stdout + la nota "material SINTÉTICO" por stderr
```

- **Lo que NO se pudo medir aquí:** las suites que exigen **PostgreSQL real** en local (las PG
  `--ignore`adas, `apps/api-python/tests/integration` y `chaos/live_a7`; importan `asyncpg`, ausente en
  esta máquina). Las **cierra** la CI del tag (ver §11). Esta fase **no** añade tests PG: no hay migración
  ni lectura durable nueva.

### 7.1 Re-verificación post-sello, sobre el árbol sellado (2026-09-24, 17:5x)

Las cifras de arriba **no** son de la corrida pre-sello: se **re-midieron después de sellar**, sobre el
mismo árbol que ve el auditor, y salieron **idénticas**. Es la prueba de que el paquete de docs y el
realineo de anclas (docs-only) no tocaron ni una medida:

| Comprobación | Resultado re-medido |
| --- | --- |
| Freeze: `git diff` del gobernador y de `auto_adaptive_journal.py` | **vacío** (los dos) |
| Ficheros congelados **dentro** del diff del PR (`audit-base-v2.59-beta..` head) | **ninguno** (lista vacía) |
| `ADAPTIVE_POLICY_VERSION` / `DATA_GATE_POLICY_VERSION` | **`auto18-v1`** / **`auto15-v1`** (`auto_adaptive_data_gate.py:76`) |
| `_ALEMBIC_HEAD` | **`046_fill_reference_mid`** |
| ruff / import-linter / mypy | **`All checks passed!`** / **`4 kept, 0 broken`** / **`0/499`** |
| Tramo de la fase | **`271 passed`** (4.45 s), `0` rojos |
| Verdes del replay sobre el fixture | **6 celdas**, `notes=['skipped_strategy:thin-edge']`, veredictos **`supported` / `supported` / `not_supported` / `inconclusive`** (muestras `6/6/4/6`) |

Los **cuatro veredictos** salen **distintos entre sí**: que una pregunta **refute** y otra se declare
**inconclusa** es la prueba de que el instrumento **no** es un sello de goma. El orden de la corrida es
**el declarado** en §5: el **instrumento** se mide; la estrategia **no** (el fixture es sintético).

## 8. Límites declarados (no silenciosos)

- **El intervalo es un bootstrap por EPISODIOS: una cota conservadora declarada**, no una varianza
  muestral teórica. Con pocos episodios **no hay intervalo** (y lo dice); no se interpola una normal.
- **El `dispersion_r` es la desviación de las medias bootstrap**, no un error estándar analítico: sirve para
  comparar estabilidad entre edges, no como intervalo.
- **El replay es ESTADÍSTICO**: re-aplica las estadísticas de decisión sobre ciclos **ya cerrados**; no
  re-simula órdenes, no toca la base de datos y sus veredictos **no** son una optimización de parámetros.
- **El fixture es SINTÉTICO y se declara** (en su `note` y en `stderr` del script): los veredictos que salen
  hoy miden **el instrumento**, no la estrategia real. El veredicto sobre material durable es del material.
- **`confidence` no se renombra** (contrato JSON sellado): el eje nuevo va en campos nuevos.
- **Sin UI, sin SHORT, sin backfill**; **el flag Adaptive sigue OFF** (con OFF nada de esto corre en
  producción).

## 9. Freeze respetado

- `auto_adaptive_journal.py`: **diff vacío** (`git diff --` sin salida). El contrato durable **no** cambia:
  la proyección por lista blanca no incluye las claves nuevas.
- `v2_43_governor_evidence.py`: **diff vacío**. El gobernador **no** se toca.
- `ADAPTIVE_POLICY_VERSION` sigue **`auto18-v1`** (`auto_adaptive.py:203`); `DATA_GATE_POLICY_VERSION` sigue
  **`auto15-v1`**. No se tocan `ADAPTIVE_ADVERSE_REGIMES`, los umbrales de rotación ni la tabla
  estado→efecto. `*.md` sin `prettier`; `governor.json` sin trackear.

## 10. Sellado

- **Bump:** `package.json` `1.84.0-beta` → **`1.85.0-beta`**.
- **Tag:** **`v2.60-beta`** sobre el commit del paquete de cierre; `main` en **fast-forward**; PR de
  auditoría abierto **después** del sello (mismo patrón que `AUTO-13`…`AUTO-18`), **no** vehículo de merge.
- **Cifras del sello:** en la §11 (se miden **después** de empujar el tag; no es un hallazgo que el run no
  exista antes).

## 11. CI del sello `v2.60-beta` (medida, no predicha)

> Sección completada en el commit de docs **posterior al sello** (el run del tag no existe hasta empujarlo),
> mismo patrón declarado que `AUTO-13`…`AUTO-18`. **Cifras medidas**, cada una con el run que las produjo.

- **Head de Alembic:** la guardia no se movió (`046_fill_reference_mid`), así que **no hay re-sello** por
  migración: el tag cubre el paquete completo **a la primera**, sin rojos y **sin flakes**.

### 11.1 El CI del tag: verde a la primera, sin re-run

| Corte | Run | Resultado |
| --- | --- | --- |
| `Release tag CI` (`cbd96bbe`) | [`35999631671`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631671) | **GREEN a la primera**: `10 success` + `1 skipped` (`playwright (integrated E2E, opt-in)`), `certify` en `success`. **Sin re-run**: no hubo ningún flake que declarar (contraste con el flake ajeno de lease que obligó a un re-run en `v2.59`) |
| job `python` del tag | run anterior | ruff `All checks passed!` · import-linter `4 kept, 0 broken` · mypy `Success: no issues found in 499 source files` · pytest **`2747 passed / 35 skipped`** (**+46** passed, **0** skips nuevos sobre `v2.59`) |
| `Python CI` per-commit del tag | [`35999631556`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631556) | **`5/5` jobs `success`** (`quality`, `auto-v2-durable-pg`, `grammar-discovery-pg`, `paper-forward-pg`, `lifecycle-pg`); job `quality` **`2736 passed / 38 skipped`** (125.36 s) |
| `Python CI` per-commit de `main` | [`35999579254`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999579254) | **`5/5` jobs `success`**; job `quality` **`2736 passed / 38 skipped`** (mismo corte que el tag) |
| `check-runs` del commit sellado `cbd96bbe` | API de checks | `total_count = 28` ⇒ **`27` success** + **`1` skipped** |
| `status` (Commit Status **legacy**) de `cbd96bbe` | `/commits/{sha}/status` | **`pending`** con **`0` statuses** *a la vez* que los `28` check-runs están `completed` ⇒ **cruce de API reproducido en vivo** (no es un hallazgo; §8 del arranque) |
| PR de auditoría [#69](https://github.com/jvelasca/Bolsa_V1/pull/69) | checks del PR | `audit-base-v2.59-beta` @ `9898c51a` → `auto-19a-incertidumbre-edge-replay` @ `7d3c3f23`: **25 ficheros, `+10780/−21`**, **4 commits** (los tres últimos **docs-only**: cifras del sello, superficie del PR y realineo de anclas); **`10/10` checks `SUCCESS`** en la cabeza medida (`057ab924`, job `quality` **`2736 passed / 38 skipped`**); superficie de auditoría, **no** vehículo de merge. Los commits **docs-only** posteriores al sello avanzan la cabeza **sin cambiar el tamaño del diff** (mismo patrón que el `auto-18` de `v2.59`) |

**+46 tests** sobre `v2.59` en los dos cortes (job `python` del tag `2701` → `2747`; job `quality` `2690` →
`2736`), que es **exactamente** la cuenta del tramo de la fase (§7): **0** skips nuevos.

### 11.2 El límite declarado del §7, cerrado por la CI del tag

El §7 declaró que los runs de CI y la batería **completa con PG real** no se pueden medir en esta máquina
(las suites PG importan `asyncpg`, ausente). **El tag las cierra**: los jobs `lifecycle-pg`, `a7-gate` y
`dr-verify` del `Release tag CI` y los cuatro jobs PG del `Python CI` per-commit salieron **verdes**. Esta
fase **no** añade tests PG (sin migración), así que los jobs PG corren **el mismo** material que `v2.59` y
verifican que `AUTO-19A` **no rompió** ninguno.

### 11.3 La ruta sin migración: qué NO se movió (medido)

- `_ALEMBIC_HEAD` (`test_discovery_evidence_snapshot_pg.py:43`) = **`046_fill_reference_mid`** (idéntico).
- `git diff` del gobernador (`v2_43_governor_evidence.py`) y del contrato durable
  (`auto_adaptive_journal.py`) ⇒ **vacíos**.
- `ADAPTIVE_POLICY_VERSION` = **`auto18-v1`** y `DATA_GATE_POLICY_VERSION` = **`auto15-v1`** (los dos intactos).
