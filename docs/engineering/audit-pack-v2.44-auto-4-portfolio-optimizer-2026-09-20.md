# Audit-pack v2.44-beta — AUTO-4 · Portfolio Optimizer + valor esperado económico

**Fecha:** 2026-09-20 · **Versión:** `1.69.0-beta` (bump desde `1.68.3-beta`) · **Migración:** ninguna
(el optimizador es **puro** y el journal es **aditivo**: no hay tabla, ni columna, ni head nuevo de
Alembic; el head sigue siendo `043_exit_identity_and_kill_state`).

**Plan de fase:** [`plan-v2-44-auto-4-portfolio-optimizer-2026-09-20.md`](./plan-v2-44-auto-4-portfolio-optimizer-2026-09-20.md)
(su §7 es el estado de ejecución con las **desviaciones declaradas**).
**Roadmap:** §6 de [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).

> **Aviso de numeración (declarado otra vez):** el plan de `v2.43.2` reutilizó la etiqueta «v2.44» para
> Exit Governance. Esta fase es la **`V2.44` del roadmap**: `AUTO-4 — Portfolio Optimizer`.

---

## 1. El invariante que instala (en una frase)

> **El ranking deja de ser la decisión: la cartera elige el CONJUNTO que maximiza valor esperado
> sujeto a riesgo.**

Hasta `v2.43.3`, `plan_v2_tick` hacía `rank_opportunities → select_top_opportunities(top_n)` y decidía
**una a una** en ese orden: la primera del ranking entraba y las siguientes solo si la anterior dejaba
hueco. El ranking **era** la respuesta. Con `AUTO_ENGINE_SIM_V2_OPTIMIZER=1`, el `top_n` pasa a ser el
**tamaño del conjunto candidato** y la combinación la elige la cartera **antes** de decidir.

**Lo que NO cambia (freeze respetado):**

- `AUTO_ENGINE_SIM_V2=0` sigue siendo `v2.39.x`.
- `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` (**default**) ⇒ **byte-identidad** con `v2.43.3`: no se construye
  ninguna candidata, no se llama al optimizador, `V2TickPlan.optimizer` queda `None` y el journal **no
  gana ninguna clave**.
- El **gobernador** (`operational_governor.py`) y su tabla **no se tocan**; su evidencia
  (`v2_43_governor_evidence.py`) sigue **byte a byte igual**, con `"bump"` en `1.68.0-beta`.
- La decisión por candidata, `_working_snapshot`, las reservas, el kill switch y la degradación a
  `RESERVATION_FAILED` quedan **intactos**.
- **Sin migración.** El head de Alembic no se mueve.

---

## 2. Piezas nuevas (puras, sin I/O)

### 2.1 `expected_value.py` — la magnitud que faltaba

`packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py`

Hasta aquí la decisión comparaba **heurísticas**: `OpportunityScore` es una suma ponderada de
componentes normalizados a `[0, 1]`, y el `edge` que entra en ella es una **confianza declarada**, no
dinero. Este módulo aporta la economía:

```text
Expected R      = p·avg_win_r + (1 − p)·avg_loss_r      (con avg_loss_r <= 0)
Expected €      = Expected R × risk_amount              (1R en dinero)
Expected € neto = Expected € − coste de ida y vuelta    (vía TradingCostModel, la casa única del coste)
```

**Disciplina de medición (la del repo).** Un dato ininterpretable **no** se convierte en `0` ni en un
default plausible:

| Dato                                             | Estado    | `notes`                                                       |
| ------------------------------------------------ | --------- | ------------------------------------------------------------- |
| `p_win` fuera de `[0, 1]` (o ausente)            | `UNKNOWN` | `p_win_out_of_range`                                          |
| sin `avg_win_r` y sin `target` del que derivarla | `UNKNOWN` | `avg_win_r_missing`                                           |
| sin `avg_loss_r` (con `p < 1`)                   | `UNKNOWN` | `avg_loss_r_missing`                                          |
| `avg_win_r < 0` / `avg_loss_r > 0`               | `UNKNOWN` | `avg_win_r_negative` / `avg_loss_r_positive`                  |
| geometría invertida (`stop >= entry`)            | `PARTIAL` | `geometry_unmeasured` (**nunca riesgo 0**)                    |
| coste no medible                                 | `PARTIAL` | `cost_unmeasured`                                             |
| `avg_win_r` tomada del `target`                  | (sigue)   | `avg_win_r_derived_from_target` (**declarada**, no inventada) |

`measurement`: `COMPLETE` (neto cerrado) / `PARTIAL` (hay `Expected R`, no hay neto) / `UNKNOWN` (no hay
ni `Expected R`).

### 2.2 `portfolio_optimizer.py` — el conjunto, no la lista

`packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py`

- **Objetivo.** Máximo `Σ net_expected_currency` de la combinación.
- **Desempate declarado** (el «MIN Portfolio Risk» del roadmap, implementado como desempate + restricción
  dura, **no** como optimización multi-objetivo con pesos): a igual valor esperado gana la de **menor
  riesgo** (`Σ risk_amount`); a igual riesgo, la combinación **lexicográficamente menor**.
- **Restricciones duras:** capacidad (`|S| <= max_positions`), capital (`Σ notional <= available_cash`),
  concentración sectorial **de la combinación** (`<= max_sector_pct · equity`), correlación
  (`<= max_correlation`, **fail-closed** si es desconocida), liquidez (`>= min_liquidity_notional`) y
  permiso de riesgo nuevo (`new_risk_allowed`). Un límite `None` = **sin límite declarado** (no "cero");
  una restricción **activa** exige el dato que la verifica y su ausencia es **infeasible**.
- **La opción «no operar» compite:** el conjunto vacío vale `0`; si ninguna combinación factible tiene
  valor **positivo**, se elige **no operar** (`notes=("empty_set_wins",)`). Un optimizador que siempre
  encuentra algo que comprar no es un optimizador.
- **Enumeración EXACTA acotada.** Se enumeran **todos** los subconjuntos de tamaño `1..max_positions`
  (no greedy, no heurística). Si el espacio supera `max_combinations`, **no se optimiza**:
  `measurement=UNKNOWN` + `optimizer_enumeration_cap_exceeded` y el tick **cae al camino del ranking**
  (no hay greedy silencioso). Default `4096` (`2^12`); con `top_n=5` el espacio es `2^5 = 32` ⇒ el tope
  no ata en el caso nominal.
- **Determinismo:** la entrada se ordena por `instrument_id` antes de enumerar; la misma cartera da la
  misma combinación con cualquier orden de llegada (test).

### 2.3 Cableado en `plan_v2_tick` (flag OFF por defecto)

`packages/py/application/src/bolsa_application/auto_v2_entry.py`

- `V2Tunables.optimizer_enabled: bool = False`, `optimizer_max_combinations: int = 4096`,
  `optimizer_max_positions: int | None = None` (⇒ `top_n`), leídos de env:
  `AUTO_ENGINE_SIM_V2_OPTIMIZER`, `AUTO_ENGINE_SIM_V2_OPT_MAX_COMBINATIONS`,
  `AUTO_ENGINE_SIM_V2_OPT_MAX_POSITIONS`. Un valor ilegible **no se "sana a medias"**: queda el default
  declarado (el tope es la barrera anti-explosión combinatoria).
- **Sonda de sizing (desviación D1 del plan §7.1).** `_optimizer_candidate` pide el tamaño al **mismo**
  motor (`decide_portfolio`) contra la foto **inicial** del tick, con la **misma** caída de ATR
  (`atr_pct_fallback`) y leyendo `quantity`/`stopDistance`/`positionValue`/`riskAmount` de su
  `allocation`. No hay segunda fórmula de stop ni de sizing: si el motor no dimensiona la candidata, la
  candidata **no es medible** y el optimizador lo declara.
- **Con ON:** tras el rankeo y el `select_top_opportunities` (= **conjunto candidato**), el `ordered` de
  evaluación pasa a ser la **combinación elegida** en su orden determinista. Las candidatas del TOP que
  **no** entran se journalizan con su **motivo REAL** y su **score real** (nunca `edge_below_threshold`,
  que sería falso).
- **Con OFF:** `ordered` es el de siempre y `V2TickPlan.optimizer` queda `None`.
- **El gobernador manda (desviación D4).** La restricción de conjunto recibe `new_risk_allowed =
not halted` (la parada dura es del tick); los vetos **por candidata** del gobernador (`EXIT_ONLY`,
  listón de edge escalado, bandas de volatilidad/liquidez) siguen aplicándose **sin cambios** en el
  bucle de decisión. El optimizador solo decide **qué** candidatas se evalúan y **en qué orden**.

### 2.4 Campos nuevos en `V2Signal` (aditivos, opcionales)

`target_price`, `p_win`, `avg_win_r`, `avg_loss_r`. Sin ellos la oportunidad no es comparable
económicamente y el optimizador la declara; **nunca** se puntúa `0`.

### 2.5 Reason codes (el journal tiene una sola casa)

`packages/py/application/src/bolsa_application/auto_reason_codes.py` re-exporta `OPTIMIZER_REASONS`
(los literales viven en `portfolio_optimizer`): `optimizer_not_selected`,
`optimizer_expected_value_unmeasured`, `optimizer_notional_unmeasured`, `optimizer_risk_unmeasured`,
`optimizer_correlation_unknown`, `optimizer_correlation_exceeded`, `optimizer_liquidity_unknown`,
`optimizer_liquidity_below_minimum`, `optimizer_capital_exceeded`, `optimizer_sector_unmeasured`,
`optimizer_sector_exceeded`, `optimizer_drawdown_blocks_new_risk`,
`optimizer_enumeration_cap_exceeded`.

---

## 3. Matriz afirmación → código → test

| #   | Afirmación                                                                    | Código                                                  | Test                                                                                                                                          |
| --- | ----------------------------------------------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | El EV se compone de `p·win + (1−p)·loss` y su 1R sale de la geometría real    | `expected_value.build_expected_value`, `_risk_geometry` | `test_expected_r_and_net_currency_come_from_the_declared_means`                                                                               |
| A2  | El coste se resta (no se ignora)                                              | `estimate_trading_cost` (casa única)                    | `test_the_cost_is_subtracted_from_the_expected_value`                                                                                         |
| A3  | Un dato ininterpretable **degrada** y lo declara; nunca `0.0`                 | `build_expected_value` (5 ramas)                        | `test_p_win_out_of_range_…`, `test_a_missing_win_mean_…`, `test_a_missing_loss_mean_…`, `test_a_negative_win_mean_and_a_positive_loss_mean_…` |
| A4  | Un stop del lado equivocado **no** es "riesgo 0"                              | `_risk_geometry` (`s >= e`)                             | `test_an_inverted_geometry_does_not_turn_risk_into_zero`                                                                                      |
| A5  | El `target` puede sustituir a la media histórica, pero se declara derivada    | `_target_r` + `EV_WIN_DERIVED_FROM_TARGET`              | `test_a_win_mean_derived_from_the_target_is_declared_not_silent`                                                                              |
| A6  | Con `p = 1` no se exige media perdedora                                       | `build_expected_value`                                  | `test_a_certain_win_does_not_need_a_loss_mean`                                                                                                |
| B1  | El capital elige el subconjunto pagable, **no** el nº1 del ranking            | `_combination_verdict` (capital)                        | `test_capital_picks_the_affordable_subset_instead_of_the_top_of_the_ranking`                                                                  |
| B2  | El conjunto vacío compite y gana si nada es positivo                          | `optimize_portfolio` (`item.value <= 0.0`)              | `test_the_empty_set_wins_when_no_combination_has_a_positive_expectation`                                                                      |
| B3  | Correlación desconocida con límite activo ⇒ infeasible (fail-closed)          | `_candidate_verdict`                                    | `test_a_known_correlation_limit_makes_an_unknown_correlation_infeasible`                                                                      |
| B4  | Tope de combinatoria ⇒ **no** se optimiza (nada de greedy silencioso)         | `optimize_portfolio` (`total_subsets > cap`)            | `test_the_enumeration_cap_aborts_without_a_silent_greedy`                                                                                     |
| B5  | Un EV no medido **no** se puntúa `0`                                          | `optimize_portfolio` (rechazo explícito)                | `test_an_unmeasured_expectation_is_never_scored_as_zero`                                                                                      |
| B6  | Sin `risk_amount` medido no se entra                                          | `_combination_verdict` (riesgo)                         | `test_a_candidate_without_measured_risk_cannot_enter`                                                                                         |
| B7  | Desempate: valor → riesgo → lexicográfico                                     | `_better`                                               | `test_a_tie_on_value_prefers_the_lower_risk`, `test_a_full_tie_is_broken_lexicographically_for_reproducibility`                               |
| B8  | La concentración sectorial se mide sobre la COMBINACIÓN                       | `_combination_verdict` (sector)                         | `test_joint_sector_concentration_rejects_a_combination_of_acceptable_singles`                                                                 |
| B9  | Vetar el riesgo nuevo es una decisión COMPLETA de no operar                   | `optimize_portfolio` (`new_risk_allowed`)               | `test_no_new_risk_is_a_complete_decision_to_not_trade`                                                                                        |
| B10 | Determinismo: el orden de entrada no cambia la combinación                    | orden por `instrument_id`                               | `test_the_result_is_independent_of_the_input_order`                                                                                           |
| B11 | El no seleccionado siempre tiene motivo declarado                             | `rejections`                                            | `test_unselected_candidates_are_declared_and_never_silent`                                                                                    |
| C1  | Flag OFF por defecto ⇒ no se construye ni se journaliza nada nuevo            | `V2Tunables.optimizer_enabled`                          | `test_the_optimizer_is_off_by_default`, `test_with_the_flag_off_no_optimizer_key_or_reason_is_emitted`                                        |
| C2  | El flag se enciende por env y un valor ilegible cae al default                | `tunables_from_env`                                     | `test_the_flag_can_be_turned_on_explicitly`, `test_invalid_optimizer_env_falls_back_to_the_declared_default`                                  |
| C3  | Con ON, el nº1 del ranking **sin economía** no se evalúa y el nº2 sí          | cableado + `optimizer_expected_value_unmeasured`        | `test_with_the_flag_on_the_unmeasurable_top_of_the_ranking_is_not_evaluated`                                                                  |
| C4  | El descartado por el optimizador publica su **score real**                    | `_rejected_signal_entry(score=…)`                       | `test_with_the_flag_on_the_rejected_candidate_publishes_its_real_score`                                                                       |
| C5  | El conjunto candidato se reparte **exactamente** entre elegidos y motivos     | cableado                                                | `test_with_the_flag_on_the_approved_set_never_exceeds_the_top_n`                                                                              |
| C6  | El worker real: con ON y **sin productor de economía**, no opera y lo declara | `_v2_signals` (sin `p_win`) + optimizador               | `test_v2_optimizer_on_without_an_economic_producer_is_fail_closed`                                                                            |

**Recuento de lo nuevo (33 tests):** `test_expected_value.py` **12** + `test_portfolio_optimizer.py`
**12** (analytics, entran por pase de directorio) + `test_auto_v4_optimizer_wiring.py` **8**
(aplicación, **explícito** en las listas de los dos workflows) + **1** en
`test_auto_v2_worker_integration.py` (`apps/api-python/tests`, pase de directorio).

---

## 4. Matriz de mutaciones (MEDIDA, no esperada)

Sonda: `apps/api-python/scripts/v2_44_mutation_audit.py` (patrón de `v2_43_3_mutation_audit.py`:
restauración **desde memoria**, nunca `git checkout --`, y verificación de **huella del árbol**
`git status --porcelain` de los ficheros tocados antes/después).

| #      | Mutación                                       | Dirección del error                                                | Rojos medidos                                                                                                                                                                                                                                                                               |
| ------ | ---------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M1** | `_better` deja de comparar                     | gana la primera combinación factible (greedy disfrazado)           | `test_a_tie_on_value_prefers_the_lower_risk`, `test_capital_picks_the_affordable_subset_instead_of_the_top_of_the_ranking`                                                                                                                                                                  |
| **M2** | no se descartan las combinaciones no positivas | el optimizador siempre "encuentra algo que comprar"                | `test_the_empty_set_wins_when_no_combination_has_a_positive_expectation`                                                                                                                                                                                                                    |
| **M3** | se ignora el tope de combinatoria              | un espacio grande bloquea el tick en vez de ceder paso al ranking  | `test_the_enumeration_cap_aborts_without_a_silent_greedy`                                                                                                                                                                                                                                   |
| **M4** | la candidata sin economía entra y suma `0.0`   | se cuela como "la peor de las medidas" y puede ganar por desempate | `test_an_unmeasured_expectation_is_never_scored_as_zero`                                                                                                                                                                                                                                    |
| **M5** | correlación desconocida deja de ser infeasible | el gate de correlación es fail-open                                | `test_a_known_correlation_limit_makes_an_unknown_correlation_infeasible`                                                                                                                                                                                                                    |
| **M6** | el journal miente con `edge_below_threshold`   | el operador lee un motivo FALSO                                    | `test_with_the_flag_on_the_rejected_candidate_publishes_its_real_score`, `test_with_the_flag_on_the_unmeasurable_top_of_the_ranking_is_not_evaluated`                                                                                                                                       |
| **M7** | el flag ON deja de gobernar                    | con ON el tick vuelve al ranking **sin declararlo**                | `test_v2_optimizer_on_without_an_economic_producer_is_fail_closed`, `test_with_the_flag_on_the_approved_set_never_exceeds_the_top_n`, `test_with_the_flag_on_the_rejected_candidate_publishes_its_real_score`, `test_with_the_flag_on_the_unmeasurable_top_of_the_ranking_is_not_evaluated` |

**Resultado: 7 de 7 muerden**, y la sonda deja la huella del árbol **intacta**.

---

## 5. Verificación medida (2026-09-20, máquina del autor)

```text
ruff check packages/py apps/api-python --config pyproject.toml     → All checks passed (0)
mypy <5 paquetes + apps/api-python/src> --follow-imports=silent    → Success: 489 ficheros, 0 issues
lint-imports --config packages/py/.importlinter                    → 4 kept, 0 broken (607 ficheros)
offline_ci_run_yaml.py ... python-ci.yml quality --with-pg-ignores → 2075 passed, 0 skipped, 0 failed
offline_ci_run_yaml.py ... release-tag-ci.yml python --with-pg-ignores
                                                                   → 2086 passed, 0 skipped, 0 failed
baseline de la sonda (sin mutación)                                → ninguno rojo en las 3 listas
v2_44_mutation_audit.py                                            → 7/7 muerden, huella intacta
```

**Delta exacto de tests (medido, no estimado):**

| Bloque                          | v2.43.3 | v2.44    | Δ       |
| ------------------------------- | ------- | -------- | ------- |
| `python-ci.yml` · `quality`     | 2042    | **2075** | **+33** |
| `release-tag-ci.yml` · `python` | 2053    | **2086** | **+33** |

Los 33 son exactamente los tests nuevos de §3. El delta es **idéntico en los dos workflow** porque el
test de aplicación va **explícito** en ambos: si solo estuviera en uno, el otro bloquearía menos.

**Nada de esto corre PG:** no hay migración nueva y ninguna suite PG se toca. Los jobs PG de CI
(`auto-v2-durable-pg`, `lifecycle-pg`, `paper-forward-pg`, `grammar-discovery-pg`) no cambian de
números por esta fase; el head de Alembic sigue en `043`.

---

## 6. Comandos exactos de CI

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió: esto debe salir VACÍO y el script exit 0
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# bloques offline extraídos del YAML (medida por JUnit XML, no copia a mano)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# las suites nuevas + el gate del worker
uv run pytest packages/py/analytics/tests/test_expected_value.py \
              packages/py/analytics/tests/test_portfolio_optimizer.py \
              packages/py/application/tests/test_auto_v4_optimizer_wiring.py -q
uv run pytest "apps/api-python/tests/test_auto_v2_worker_integration.py::test_v2_optimizer_on_without_an_economic_producer_is_fail_closed" -q

# matriz de mutaciones
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

---

## 7. Límites declarados y deuda diferida

**Límites (declarados, no hallazgos):**

- **No hay productor de economía en el camino del tick.** `_v2_signals` no pasa `p_win`/medias, así que
  con el flag ON **todas** las candidatas son `optimizer_expected_value_unmeasured` y el tick **no
  opera**. Es fail-closed declarado y **fijado en test**; el productor real es de `AUTO-7`. Con el flag
  **OFF por defecto**, el camino de producción no cambia.
- **La restricción de correlación usa el dato que hoy existe** (`TradeContext.correlation`), no una
  matriz por pares: una matriz es de `AUTO-4`/`AUTO-8` según el roadmap §11.
- **El objetivo es EV neto con desempate por riesgo**, no una frontera eficiente completa: el «MIN
  Portfolio Risk» del roadmap se implementa como **desempate + restricciones duras**, no como
  optimización multi-objetivo con pesos continuos.
- **Umbrales declarados y no calibrados** (`max_combinations = 4096`, `max_positions = top_n`).
- **Duplicidad declarada de gates:** capital/sector/correlación/liquidez se comprueban en el optimizador
  (sobre la foto **inicial**) **y** en el motor de decisión (sobre la foto **de trabajo**). No es un
  fallo: el optimizador mide **encaje de conjunto** con lo que hay antes de comprometer nada, y el motor
  sigue siendo la autoridad final sobre lo ya reservado. Se declara porque es una segunda pasada.
- **El punto 6 del gate (Golden Day) se midió en dos capas** (tick + worker real), no con un día dorado
  multi-fase con ON; con el límite del párrafo 1, ese día dorado no podría diferir del ranking por una
  razón de fondo. Desviación **D5** del plan §7.1.
- **`max_drawdown_used_pct` no existe** como restricción numérica: el veto de drawdown entra como
  permiso de cartera (`new_risk_allowed`). Desviación **D3**.

**Deuda diferida (fuera de esta versión):** productor de `p_win`/medias (AUTO-7); matriz de correlación
por pares; calibración de umbrales del optimizador; `pending_entry`/`pending_exit` separados;
hysteresis del gobernador; gobernador ON por defecto; tags firmados / CI attestation.

---

## 8. Reproducibilidad e inventario

- **Ficheros nuevos:** `expected_value.py`, `portfolio_optimizer.py`,
  `test_expected_value.py`, `test_portfolio_optimizer.py`, `test_auto_v4_optimizer_wiring.py`,
  `v2_44_mutation_audit.py`, el plan de fase, este pack y el arranque del auditor.
- **Ficheros modificados:** `auto_v2_entry.py` (tunables + sonda de candidata + bloque del optimizador +
  `V2TickPlan.optimizer`), `auto_reason_codes.py` (`OPTIMIZER_REASONS` + re-exports),
  `test_auto_v2_worker_integration.py` (+1 test), `python-ci.yml` y `release-tag-ci.yml` (el test de
  aplicación **explícito** en ambos + comentario), `CHANGELOG.md`, `PROJECT_STATE.md`,
  `engineering-index`, `package.json`.
- **Versionado:** bump `1.68.3-beta` → `1.69.0-beta`; **Alembic head sin cambios (`043`)**.

## 9. Sello

**SELLADO (2026-09-20).** Commit de fase **`f692159d`** (18 ficheros, `+2728/−2`) y tag anotado
**`v2.44-beta`** sobre el commit de sellado **docs-only** (convención de `v2.43-beta`…`v2.43.3-beta`:
la ref sellada no cita refs inexistentes); `v2.43-beta`/`v2.43.1-beta`/`v2.43.2-beta`/`v2.43.3-beta`
**no se mueven** (ref nueva y aditiva).

**CI real medida del commit de fase (`f692159d`):**

| Workflow            | Run                                                                            | Resultado     |
| ------------------- | ------------------------------------------------------------------------------ | ------------- |
| `Python CI`         | [`35510546044`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546044) | **GREEN 5/5** |
| `Gitleaks`          | [`35510546045`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546045) | **GREEN**     |
| `Optimize lab`      | [`35510546041`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546041) | **GREEN**     |
| `Fase 2 scientific` | [`35510546060`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546060) | **GREEN**     |

Desglose de `Python CI` (medido, no esperado):

- `quality` **2075 passed, 38 skipped** en **89,26 s** — exactamente **+33** sobre los **2042** de
  `v2.43.3-beta`, que son los 33 tests nuevos de `AUTO-4` (12 EV + 12 optimizador + 8 cableado + 1
  worker real). El bloque offline local anticipó el mismo número (**2075**): la red de CI **no** corre
  nada menos que el bloque reproducido a mano.
- `auto-v2-durable-pg (Alembic 040-043 + reinicio real)` **43 passed** — sin cambio respecto de
  `v2.43.3-beta`, como debe ser: `AUTO-4` **no** trae migración y el head sigue en `043`.
- `paper-forward-pg` **2 passed** · `grammar-discovery-pg` **21 passed** · `lifecycle-pg` **13 passed**.

**Nota de honestidad:** el `+33` del CI es la única prueba de que el test de aplicación
(`test_auto_v4_optimizer_wiring.py`) corre **en CI** y no solo en local — el YAML lo lista
explícitamente en `quality` y en `python` del tag, y el incremento coincide dígito a dígito con el
recuento local de tests nuevos.
