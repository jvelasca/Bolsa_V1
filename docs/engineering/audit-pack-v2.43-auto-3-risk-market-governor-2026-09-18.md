# Audit pack — V2.43 / AUTO-3 slice 1: `MarketRegime` × `RiskRegime` × `OperationalState` (ejes, tabla y gate de ENTRADAS) (`1.68.0-beta`)

**Qué es:** el **primer slice de `AUTO-3`** (§5 del [roadmap AUTO](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md)).
Instala los **tres ejes** (`MarketRegime`, `RiskRegime`, `OperationalState`), la **tabla de decisión** con
su gate puro y cablea el **permiso operativo solo a las ENTRADAS** detrás de un flag **OFF por defecto**.

**Ref auditada:** versión `1.68.0-beta`, partiendo del tag anterior **`v2.42.2-beta` → `3e8aa359`**. El
sello de este slice es el tag anotado **`v2.43-beta`**, que apunta al **commit de sellado**; el **commit de
fase del código** es `7ca4a0e1` (23 ficheros, `+3677/−58`) y los commits de sellado son **docs-only**.
**Desviación declarada del patrón de `v2.42.2`** (allí el commit docs-only de evidencia de CI quedaba
**fuera** del tag): aquí el sello lo **incluye**, para que la ref sellada no cite ninguna ref inexistente.
Si una auditoría necesita reconstruir "el código tal cual se selló", ese commit es `7ca4a0e1`.

**Evidencia de CI del commit de fase (ya medida):** `Python CI` **GREEN 5/5** en `main` (run
[`35322991385`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35322991385): `quality` **1983 passed, 38
skipped** en 114,94 s; `auto-v2-durable-pg` **39 passed** con su gate fail-if-skipped; `grammar-discovery-pg`,
`paper-forward-pg` y `lifecycle-pg` per-commit también en verde). La certificación de la **ref del tag**
(`Python CI` en la ref + `Release tag CI` con `certify`) está medida en el §8.1.

**Alcance de la auditoría:** este slice **y** la afirmación de que la tabla **gobierna** la decisión (no la
decora). Lo publicado en `AUTO-2` (2a/2b/2c) **ya se auditó** en sus packs; aquí se re-mide lo que este
slice toca (baterías completas en §8.2). El trabajo pesado de auditoría está en el §5 (mutaciones), el §6
(límites) y el §9 (arranque).

---

## 1. Qué afirma esta versión (y qué no)

**Afirma:**

1. Que la tabla `(MarketRegime × RiskRegime × DrawdownBand × VolatilityBand × LiquidityBand) →
OperationalState` es **total** (todo eje tiene default `UNKNOWN` ⇒ nunca una combinación sin respuesta)
   y **monótona** (más riesgo nunca produce un estado más permisivo). Certificado **por test sobre el
   producto cartesiano** de los ejes codificados (1 728 combinaciones) y, además, **mutado** para medir que
   los tests defienden las propiedades (§5: M4 rompe la monotonía y pone **11** tests en rojo).
2. Que **ningún eje `UNKNOWN` es "libre"**: cada eje tiene techo declarado (`_MARKET_CAP`/`_RISK_CAP`/
   `_DRAWDOWN_CAP`/`_VOLATILITY_CAP`/`_LIQUIDITY_CAP`) y un `UNKNOWN` cae en `ENTRY_RESTRICTED` o
   `EXIT_ONLY`, nunca en `ENTRY_ALLOWED`. Hay **un test por eje** que lo exige.
3. Que "el mercado está bajista" (hecho de mercado) y "AUTO tiene prohibido abrir" (permiso) son hechos
   **distintos y explícitos**: viajan en campos separados (`marketRegime` / `riskRegime` /
   `operationalState`) y el veto de permiso tiene **motivo propio** (`governor_exit_only` /
   `governor_halted`), distinto de `regime_invalid`.
4. Que el motor **lee** el permiso y **no reconstruye política**: el gate se inserta **después** del
   régimen direccional y **solo endurece** (un `ENTRY_RESTRICTED` sube el listón de edge con
   `restricted_edge_factor ≥ 1`, invariante del constructor de la política; un factor que lo relajara
   **lanza**).
5. Que el **tamaño se deriva del estado resuelto** (`risk_scale` = 1,00 / 0,75 / 0,50) con la composición
   declarada **"el más estricto gana"** (no producto de factores): dos ejes al 75 % no dan 56 %.
6. Que con `AUTO_ENGINE_SIM_V2_GOVERNOR=0` (default) el camino V2 es **byte-idéntico**: el journal **no
   emite** las tres claves, `governor_states` queda vacío y `drawdown_pct` **ni se mide** (`None`, sin pagar
   el cómputo). Medido por test y por el control de cada tramo de la evidencia.
7. Que la **procedencia de la medida** es explícita: sin drawdown medido el eje de riesgo es `UNKNOWN`
   (nunca 0), y una medición que no es `COMPLETE` no autoriza aunque el número exista (es un **suelo**).
8. Que `LOW_VOL` **deja de ser un valor muerto** (nunca producido antes): la matemática `v1` de
   `discovery_market_regime` (opt-in por env) añade `low_vol` con umbral declarado, **sin cambiar `v0` ni
   una etiqueta** (mismo test exige las dos cosas).
9. Que la env del gobernador se **sanea como bloque**: un corte no creciente, un número no finito o un
   factor `< 1` descartan **todos** los umbrales de env y quedan los defaults declarados (nunca a medias,
   nunca tumbando el tick).
10. Que existe **evidencia reproducible** de que la tabla gobierna: un script sin PG ni red que corre la
    escalera de drawdown por el camino **real** (`_v2_snapshot` → `plan_v2_tick`), con **control con el
    flag OFF en cada tramo**, y que **sale ≠ 0** si la tabla no gobierna.

**NO afirma:**

1. Que el gobernador **cierre** posiciones. En este slice el permiso gobierna **solo entradas**: el camino
   de salida no cambia (`REGIME_EXIT` legacy queda intacto).
2. Que `REGIME_EXIT` / `RISK_EXIT` sean **eventos del FSM**: **no lo son**; su instalación y la decisión de
   **precedencia y atribución** del día quedan para el slice siguiente (§6).
3. Que `HALTED` tenga **productor propio** (política de kill switch): aquí es alcanzable por la tabla y por
   el parámetro `halted`, sin política nueva.
4. Que los umbrales de drawdown (5/10/15/20 %) estén **calibrados con datos**: son **declarados**,
   configurables, con el mecanismo separado del número.
5. Que la evidencia sea una **sesión de mercado real**: es un día **hermético** (stores `InMemory*`, precios
   y ATR inyectados, sin PG).
6. Que el flip a **default ON** esté hecho: es decisión del owner con el número delante.
7. Que se haya medido **PG real** en esta máquina: **no** (el `connect` del DSN local se cuelga; es la
   trampa declarada del traspaso §4). La durabilidad la certifica CI en sus jobs con PG — y este slice,
   por diseño, **no toca** ningún fichero `*_pg*`, store durable ni migración.
8. Que el eje de volatilidad mida volatilidad **de mercado**: `volatility_band_for` deriva de la etiqueta
   del clasificador de barras más la **disponibilidad** de ATR; con el ATR sintético (`precio × 2 %`) el
   eje sigue midiendo una etiqueta real y una geometría declarada, no una volatilidad calibrada.

---

## 2. Punto de partida verificado (lo que este slice resuelve)

`AUTO-2` cerró con evidencia (slice 2c) y dejó declarado, en el §3 del
[traspaso post-v2.42.2](./traspaso-relevo-post-v2-42-2-auto-2-slice-2c-2026-09-18.md), lo que faltaba:

| Deuda declarada antes de V2.43                                                     | Qué hace este slice                                                                                        |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| El régimen de mercado y el riesgo de cartera **no** existían como hechos separados | Se instalan `MarketRegime` y `RiskRegime` como ejes con fuente, y el **permiso** derivado como tercer eje  |
| La tabla de decisión y su invariante de monotonía **no** existían                  | `resolve_operational_state` (total, monótona, fail-closed) + certificación por test sobre el cartesiano    |
| El V2 **no recibía drawdown** (siempre `None` ⇒ el eje de riesgo no podía existir) | `EquityMarkBook` inyectable en el worker + P&L realizado/no realizado ⇒ `drawdown_pct` **medido** por tick |
| `LOW_VOLATILITY` era un valor **muerto** (nunca producido)                         | Matemática `v1` opt-in que lo produce, con `v0` **intacto**                                                |
| `REGIME_EXIT` existe en el camino legacy pero **no** como evento del FSM           | **Fuera de alcance** aquí: se difiere con la decisión de precedencia/atribución (§6)                       |

---

## 3. Matriz afirmación → código → test

### a) Ejes, tabla y monotonía (el corazón del slice)

- **Código:** `packages/py/analytics/src/bolsa_analytics/cognitive/operational_governor.py`
  - ejes y codificaciones: `MarketRegime`, `RiskRegime`, `OperationalState`, `DrawdownBand`,
    `VolatilityBand`, `LiquidityBand` + `ENCODED_*` (para recorrer los ejes en tests);
  - **la política, a la vista:** `_MARKET_CAP` (l. 141), `_RISK_CAP` (l. 152), `_DRAWDOWN_CAP` (l. 161),
    `_VOLATILITY_CAP` (l. 171), `_LIQUIDITY_CAP` (l. 178);
  - severidad y tamaño: `_STATE_SEVERITY` (l. 117) y `RISK_SCALE_BY_STATE` (l. 127);
  - resolución: `strictest_state` (l. 294) y `resolve_operational_state` (l. 309) = máximo de severidad de
    los techos por eje, con `halted` forzando `HALTED`;
  - lectura completa: `OperationalAssessment` (l. 335), `_binding_axis` (l. 377), `assess_operational_state`
    (l. 409), `assess_from_measurements` (l. 597);
  - derivación de bandas: `DrawdownPolicy` (l. 450, cortes estrictamente crecientes o `ValueError`),
    `risk_regime_from` (l. 495), `volatility_band_for` (l. 518), `liquidity_band_for` (l. 539),
    `to_market_regime` (l. 569), `GovernorPolicy` (l. 580, `restricted_edge_factor ≥ 1`).
- **Test:** `packages/py/analytics/tests/test_operational_governor.py` (**25**): `test_resolution_is_total_
over_the_cartesian_product` (1 728 combinaciones), `test_more_risk_never_yields_a_more_permissive_state`,
  `test_declared_caps_are_the_roadmap_policy`, `test_state_severity_is_strictly_ordered`,
  `test_risk_scale_never_exceeds_one_and_never_grows_with_severity`,
  `test_unknown_axis_never_allows_entry` (parametrizado **por eje**), `test_kill_switch_forces_halted_over_
everything`, `test_strictest_state_keeps_the_worst`, `test_drawdown_policy_rejects_non_monotone_cuts`,
  `test_governor_policy_never_relaxes`, `test_unrecognized_labels_are_unknown_and_fail_closed`.

### b) Gate de permiso en el motor (solo entradas)

- **Código:** `packages/py/application/src/bolsa_application/portfolio_decision_engine.py`
  - `DecisionReasonCode.governor_exit_only` / `governor_halted` (l. 133-134) y su alta en
    `_NO_TRADE_REASONS` (l. 165-166) — sin eso un veto del gobernador **no contaría** como no-trade;
  - `PortfolioDecisionConfig.governor` (l. 217, aditivo, `None` = no consultado = histórico);
  - lectura del permiso (l. 462-468, con estado no canónico ⇒ `HALTED`) y gate en el **paso 3.b**
    (l. 507-513): `EXIT_ONLY → HOLD/governor_exit_only`, `HALTED → HOLD/governor_halted`;
  - `PortfolioDecision.market_regime` / `risk_regime` / `operational_state` (l. 247-249) y `to_dict()`
    (l. 273-276), que **solo** emite las claves cuando el gobernador se consultó.
- **Test:** `packages/py/application/tests/test_auto_v3_governor_gate.py` (**20**):
  `test_exit_only_vetoes_with_its_own_reason_code`, `test_halted_vetoes_with_its_own_reason_code`,
  `test_governor_only_hardens_the_directional_rule`, `test_unmeasured_drawdown_is_exit_only_not_free`,
  `test_decide_portfolio_reads_the_permission_from_the_assessment`,
  `test_decision_config_without_governor_is_the_historical_one`.

### c) Tamaño y listón de edge (el número, derivado del veredicto)

- **Código:** `packages/py/application/src/bolsa_application/auto_v2_entry.py`
  - `decision_config(governor=...)` (l. 237-266): con `allows_new_entry` aplica `scale = risk_scale` y, en
    `ENTRY_RESTRICTED`, `min_edge * governor_restricted_edge_factor`;
  - `plan_v2_tick` (l. 800-816): lectura **por candidata** (volatilidad y liquidez son datos de la
    candidata) y `governor_states` (l. 875) con el estado **efectivo** por instrumento.
- **Test:** `test_reduced_state_scales_risk_down`, `test_restricted_state_scales_risk_and_raises_the_edge_
bar`, `test_liquidity_threshold_can_restrict_an_entry`, `test_governor_policy_tunables_are_calibrable`.
  La medida **del factor** (no de la teoría) la da la evidencia: `_scale(measured) = quantity_on /
quantity_control` con el control sobre **el mismo snapshot** (§4).

### d) Drawdown medido (el eje de riesgo no existía sin esto)

- **Código:** `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`
  - `equity_marks=` inyectable (l. 534) y `EquityMarkBook` inicializado (l. 638) + `_sim_realized_pnl`
    (l. 639, alimentado en la venta aplicada l. 3030);
  - `_v2_governor_drawdown_pct()` (l. 1153): `None` **con el flag OFF** (ni se mide), y con el flag ON el
    `daily_pct` de la marca sobre equity = base + realizado + no realizado;
  - publicación al snapshot (l. 1222) y `DiscoveryRegimeSource` con `math_version` (l. 3389-3391, cableado
    desde `tunables_from_env().regime_math_version` en l. 3742).
- **Test:** `test_worker_publishes_measurement_only_with_the_flag_on` (evidencia, seam declarado) y el
  tramo `unrealizedLeg` de la evidencia (una posición viva que cae mueve el gobernador **aunque la equity
  base no cambie**).

### e) Journal: las tres dimensiones

- **Código:** `auto_v2_entry.py::_journal_entry` (l. 1351-1357): publica `marketRegime` / `riskRegime` /
  `operationalState` **solo** cuando la decisión trae la lectura.
- **Test:** `test_non_trade_decision_publishes_the_three_dimensions` (un veto por gobernador **declara** las
  tres, no las omite) y `test_dimensions_travel_also_on_decisions_that_did_not_read_the_governor` (los
  hechos viajan aunque el permiso no se consultara). En la evidencia, cada tramo exige
  `journalKeys == ["marketRegime", "operationalState", "riskRegime"]`.

### f) `LOW_VOL` producible y env saneada

- **Código:** `discovery_market_regime.py` — `MATH_VERSION_MARKET_REGIME_V1` (l. 45), `REGIME_LOW_VOL`
  (l. 53), `TRIAL_REGIMES_V1` (l. 65), `_LOW_VOL_RATIO_THRESHOLD = 0.005` (l. 92), `_classify_v0` (l. 179)
  / `_classify_v1` (l. 197), el mapa `_CLASSIFIERS` (l. 224) y `is_valid_regime(..., math_version=...)`
  (l. 265). Env: `auto_v2_entry.py::_governor_env_overrides` (l. 350-405).
- **Test:** `test_math_v1_adds_low_vol_without_changing_v0`, `test_math_v1_keeps_the_priority_of_v0`,
  `test_regime_math_version_env`, `test_governor_env_flag_and_thresholds`,
  `test_governor_env_invalid_values_fall_back`, `test_governor_env_non_monotone_cuts_fall_back_as_a_block`.

### g) Alias aditivos por colisión de nombre (cero blast radius)

- **Código:** `MacroRegime = MarketRegime` en `weight_rules.py`, `FinancialIntegrityState =
OperationalState` en `reconcile_financial_integrity.py` (con comentario de que el eje canónico de AUTO-3
  vive en `operational_governor`) y export `GovernorMarketRegime` en `cognitive/__init__.py`. **Ningún eje
  existente cambia de significado** — lo comprueban las baterías completas de §8.2, que incluyen los tests
  previos de `weight_rules`, `reconcile_financial_integrity` y `market_regime_gate`.

---

## 4. Matriz de mutaciones **medida** (7 mutaciones, 7 rojos)

Aplicada sobre el árbol final, con el target acotado, **revirtiendo y verificando el contenido exacto**
(hash del fichero mutado antes y después). Ninguna mutación queda en el árbol. Reproducible: el script que
la orquesta no se versiona (aplica/corre/revierte); las tres que más valor tienen son M3, M4 y M5.

| #   | Mutación                                                                     | Fichero                                | Rojos medidos                                                                              |
| --- | ---------------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------ |
| M1  | Un techo de eje mal mapeado (`_MARKET_CAP["HIGH_VOL"] → ENTRY_ALLOWED`)      | `operational_governor.py`              | **1 rojo** (`test_declared_caps_are_the_roadmap_policy`)                                   |
| M2  | Quitar `UNKNOWN ⇒ nunca libre` (`_LIQUIDITY_CAP["UNKNOWN"] → ENTRY_ALLOWED`) | `operational_governor.py`              | **3 rojos** (techos, `test_unknown_axis_never_allows_entry[liquidity_band]`, `assess` E2E) |
| M3  | `EXIT_ONLY` deja pasar entradas (solo `HALTED` veta)                         | `portfolio_decision_engine.py`         | **4 rojos** (permiso, medición ausente, journal, lectura directa del motor)                |
| M4  | Romper monotonía (`strictest_state` devuelve el **menos** severo)            | `operational_governor.py`              | **11 rojos** (totalidad, monotonía, `UNKNOWN`, ejes, `binding_axis`)                       |
| M5  | `drawdown_pct` no cableado (el worker publica siempre `0.0` ⇒ banda `FULL`)  | `auto_simulation_worker.py`            | **3 rojos** (escalera, pata no realizada, seam de medición)                                |
| M6  | Journal sin las tres dimensiones                                             | `auto_v2_entry.py` (`_journal_entry`)  | **2 rojos** (journal del gate + evidencia)                                                 |
| M7  | `risk_scale` ignorado en el sizing (`scale = 1.0`)                           | `auto_v2_entry.py` (`decision_config`) | **2 rojos** (REDUCED al 75 %, RESTRICTED al 50 %)                                          |

**Dos mutaciones nacieron verdes y NO eran agujero de cobertura, eran mutación mal puesta** (la lección
del traspaso §4: comprueba que la mutación rompe **comportamiento**, no una línea):

- **M5 primera versión** (devolver `0.0` en vez de `None` con el flag OFF) ponía en rojo el test de
  byte-identidad por un motivo **distinto** del que se quería medir; se rehízo como "el worker publica
  siempre `0.0` **con el flag ON**", que es el fallo de cableado real, y entonces la escalera entera cae.
- **M6 primera versión** (quitar las claves del payload de `PortfolioDecision.to_dict()`) la tapaba el
  propio `_journal_entry`, que las volvía a poner: **dos sensores se cubrían entre sí**. Se rehízo sobre
  `_journal_entry`, que es el único escritor del payload del tick.

---

## 5. Cambios observables declarados

- **Nuevos motivos de no-trade** en el journal: `governor_exit_only` y `governor_halted` (ambos en
  `_NO_TRADE_REASONS`).
- **Nuevas claves en el payload del journal** (solo con el gobernador consultado): `marketRegime`,
  `riskRegime`, `operationalState`.
- **Nuevo env** (default OFF): `AUTO_ENGINE_SIM_V2_GOVERNOR`; umbrales
  `AUTO_ENGINE_SIM_V2_GOV_DD_REDUCED_PCT` / `_HALF_PCT` / `_NO_ENTRY_PCT` / `_EXIT_ONLY_PCT`,
  `AUTO_ENGINE_SIM_V2_GOV_MIN_LIQUIDITY`, `AUTO_ENGINE_SIM_V2_GOV_RESTRICTED_EDGE_FACTOR` y
  `AUTO_ENGINE_SIM_V2_REGIME_MATH` (`v0` default).
- **Sin breaking** en contratos existentes: `build_worker_snapshot(drawdown_pct=...)`,
  `PortfolioDecisionConfig.governor`, `PortfolioDecision.{market_regime,risk_regime,operational_state}`,
  `V2TickPlan.governor_states` y `construct_worker(equity_marks=...)` son **aditivos** con default
  histórico. Los alias de §3.g son **aditivos**; ningún símbolo existente cambia de valor.
- **Sin migración:** Alembic head sigue en `042_portfolio_reservations`; no hay fichero nuevo en
  `alembic/versions`.

---

## 6. Límites declarados (deuda, no silencio)

1. **Eventos FSM `REGIME_EXIT` / `RISK_EXIT`**: no existen como eventos. `REGIME_EXIT` existe en el camino
   **legacy** con precedencia absoluta; al cablearlo al FSM hay que decidir **precedencia y atribución**
   (hallazgo que arrastra `AUTO-2`). Es el slice siguiente.
2. **Políticas completas de `VolatilityGovernor` / `LiquidityGovernor`**: aquí son **bandas con umbral
   declarado** (volatilidad desde la etiqueta del clasificador + disponibilidad de ATR; liquidez contra
   `min_liquidity_notional`), no calibración por ADV/spread medido.
3. **Productor real de `HALTED`**: alcanzable por tabla y por el parámetro `halted`; sin política propia de
   kill switch.
4. **Flip a default ON**: pendiente de decisión del owner con el número delante.
5. **Regla "solo el mejor candidato" en `RESTRICTED`**: en este slice `RESTRICTED` = tamaño reducido +
   umbral de edge más exigente, no una selección de un único candidato.
6. **El gobernador no cierra**: el permiso solo gobierna entradas; los caminos de salida quedan como en
   `v2.42.2`.
7. **La evidencia es hermética**: stores `InMemory*`, precios/ATR inyectados, sin PG ni red. Es el camino
   **real** del worker (`_v2_snapshot` → `plan_v2_tick`), no una sesión de mercado.

---

## 7. Freeze comprobado

| Freeze                                                       | Comprobación                                                                                                              |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `AUTO_ENGINE_SIM_V2=0` sigue siendo `v2.39.x`                | el gate vive **dentro** del pipeline V2; con V2 OFF no se construye snapshot V2 ni se llama al motor                      |
| Con `AUTO_ENGINE_SIM_V2_GOVERNOR=0` el camino V2 es idéntico | test de byte-identidad del journal con y sin `drawdown_pct` en el snapshot + `governor_states == ()` + control del script |
| Sin migración                                                | Alembic head `042_portfolio_reservations`; ningún fichero nuevo en `alembic/versions`                                     |
| Gates PG intactos                                            | no se toca ningún `*_pg*`, store durable ni el worker de reservas                                                         |
| `v0` del clasificador de régimen intacto                     | `test_math_v1_adds_low_vol_without_changing_v0` + `test_math_v1_keeps_the_priority_of_v0`                                 |
| Cero blast radius por los alias                              | baterías completas de `weight_rules` / `reconcile_financial_integrity` / `market_regime_gate` en §8.2                     |

---

## 8. Verificación medida

### 8.1 CI del sello

**Commit de fase `7ca4a0e1` en `main` — medido:** `python-ci.yml` **GREEN 5/5** (run
[`35322991385`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35322991385)): `quality` **1983 passed,
38 skipped** (114,94 s), `auto-v2-durable-pg` **39 passed** (gate fail-if-skipped activo, 5,75 s),
`grammar-discovery-pg`, `paper-forward-pg` y `lifecycle-pg` per-commit en verde. Los 38 skips del job
`quality` son las suites gated por `DATABASE_URL`/`*_PG_REQUIRED`, que corren en sus jobs dedicados.

**Ref sellada:** tag anotado **`v2.43-beta` → `4fc09f08`** (commit de sellado, docs-only), que incluye el
commit de fase del código **`7ca4a0e1`**. **Medido:**

- `Python CI` en la **ref del tag** (run
  [`35323452519`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452519)): **GREEN 5/5** — `quality`
  **1983 passed, 38 skipped** (116,14 s), `auto-v2-durable-pg` **39 passed** (6,09 s, gate fail-if-skipped
  en `success`), `grammar-discovery-pg`, `paper-forward-pg` y `lifecycle-pg` per-commit en verde.
- `Release tag CI` (run
  [`35323452639`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452639)): **GREEN** con `certify
(aggregate + artifact)` en `success` (artifact `release-tag-ci-summary`, 405 B) — job `python`
  (ruff/imports/mypy/pytest offline) **1994 passed, 35 skipped** (58,64 s), `lifecycle-pg` con PG real
  **144 passed** (90,49 s) + **45 passed** (14,55 s), `shared`, `security (gitleaks)`, `dr-verify`,
  `decision-spine`, `frontend`, `a7-gate` y `shared` en verde; `playwright (integrated E2E)` `skipped` por
  ser opt-in.
- `Frontend CI`, `Optimize lab`, `Fase 2 scientific` y `Gitleaks` de `main` en verde tras el push del sello.

Con eso, el tag↔commit y la certificación de la ref quedan verificables por el auditor con los tres runs
citados (más el del commit de fase, arriba).

### 8.2 Baterías (medido en la máquina del autor, árbol final del slice)

| Qué                                                                                                                  | Medida                                                                                   |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                              | **All checks passed**                                                                    |
| `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` | **487 ficheros, 0 issues**                                                               |
| `uv run lint-imports --config packages/py/.importlinter`                                                             | **4 kept / 0 broken**                                                                    |
| Suites **nuevas** del slice (los 3 ficheros)                                                                         | **48 passed** (25 puros + 20 gate + 3 evidencia) en 0,81 s                               |
| Evidencia: `uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json`                    | **exit 0** — `OK: la tabla gobierna la decisión de entrada`                              |
| Bloque offline `python-ci.yml` job `quality` (targets y `--ignore` **extraídos del YAML**)                           | 42 rutas objetivo, 8 PG a `--ignore` ⇒ **1983 passed / 0 failed / 0 skipped** (`exit 0`) |
| Bloque offline `release-tag-ci.yml` job `python` (ídem)                                                              | 51 rutas objetivo, 8 PG a `--ignore` ⇒ **1994 passed / 0 failed / 0 skipped** (`exit 0`) |

Las dos cifras offline incorporan los **48 tests nuevos** (1935 + 48 = 1983 en `quality`; 1946 + 48 = 1994
en el job del tag), que es la comprobación de que lo nuevo **sí** corre en CI. Medición con
`scripts/verify/offline_ci_run_yaml.py` (extrae la lista **del YAML**, verifica que cada ruta existe y mide
por **JUnit XML**: bajo `subprocess` en Windows el stdout de pytest llega truncado).

### 8.3 Evidencia de la escalera (el criterio: la tabla **gobierna**)

Cada tramo se mide **con su control con el flag OFF sobre el mismo snapshot**, así que el escalado se lee
como factor del gobernador y los vetos se leen como "fue el gobernador quien frenó" (el control aprobaba):

| Drawdown                   | `OperationalState` | Efecto medido                                                                                   |
| -------------------------- | ------------------ | ----------------------------------------------------------------------------------------------- |
| 0 %                        | `ENTRY_ALLOWED`    | aprobada, cantidad **× 1,00** sobre su control                                                  |
| 6 %                        | `ENTRY_REDUCED`    | aprobada, cantidad **× 0,75** sobre su control                                                  |
| 12 %                       | `ENTRY_RESTRICTED` | **vetada** con `edge_below_threshold` (control **aprobaba** ⇒ frenó el listón)                  |
| 12 % (factor relajado 1,2) | `ENTRY_RESTRICTED` | aprobada, cantidad **× 0,50** sobre su control                                                  |
| 15 %                       | `EXIT_ONLY`        | **vetada** con `governor_exit_only` (control aprobaba)                                          |
| 22 %                       | `HALTED`           | **vetada** con `governor_halted` (control aprobaba)                                             |
| pata no realizada          | `ENTRY_REDUCED`    | una posición viva a −10 % sobre 60 000 de exposición ⇒ 6 % de DD **con la equity base intacta** |
| control OFF                | sin dimensiones    | el mismo −22 % **no** cambia la decisión, **no** emite claves y **no** mide drawdown (`None`)   |

---

## 9. Arranque del auditor

Orden de lectura y comandos listos: [`arranque-auditor-v2-43-auto-3-risk-market-governor-2026-09-18.md`](./arranque-auditor-v2-43-auto-3-risk-market-governor-2026-09-18.md).
Las tres preguntas que el auditor debe poder responder **solo con este pack**:

1. _¿Se puede abrir una entrada con un eje `UNKNOWN`?_ No: cada eje `UNKNOWN` tiene techo declarado
   (`ENTRY_RESTRICTED` o `EXIT_ONLY`) y hay un test **por eje**; M2 mide que quitarlo pone 3 tests en rojo.
2. _¿El gobernador puede **relajar** algo?_ No: se inserta después del régimen, solo añade vetos y sube el
   listón (`restricted_edge_factor ≥ 1` prohibido por construcción); M3 mide que dejar pasar `EXIT_ONLY`
   pone 4 tests en rojo.
3. _¿Puede una env mal puesta tumbar el tick o relajar el listón?_ No: los umbrales se validan **como
   bloque** y caen a los defaults declarados.
