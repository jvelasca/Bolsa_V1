# Audit-pack — `v2.78-beta` (`AUTO-MATERIAL-6`: OPERABILITY ACCOUNTING)

> **AsOf:** 2026-09-27 · **Versión:** `2.03.0-beta` · **Base (diff):** `v2.77-beta`
> (`2.02.0-beta`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **no** decide nada. **Corrige el instrumento**: la contabilidad del
> journal pasa a ser de **vetos puros** (`P3-6`) y la **ausencia** de medición se declara `unknown`
> (`P3-7`). **No** acredita cierre estadístico: la ventana de ≥4 días sigue **pendiente**.

## 1. Alcance del diff

| Tipo | Fichero |
|---|---|
| **Aditivo (dueño)** | `packages/py/application/src/bolsa_application/auto_reason_codes.py` (`DAY_EXIT_REASONS`) |
| **Corrección (puro)** | `packages/py/application/src/bolsa_application/market_operability.py` |
| **Puros (tests)** | `packages/py/application/tests/test_market_operability.py` (**25 → 37**) |
| **Sonda de mutaciones** | `apps/api-python/scripts/v2_44_mutation_audit.py` (**M211**–**M213**, 210 → 213) |
| **Docs/versión** | `package.json` (`2.02.0-beta` → `2.03.0-beta`), `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, `deuda-p3`, docs `*-v2-78-*`, evidencia cruda |

**No** se toca: `auto_simulation_worker.py`, `paper_material_readiness.py`, `portfolio_decision_engine.py`,
`opportunity_ranker.py`, `market_regime_gate.py`, `aggregate_trial_regime`, `TOP_N`,
`DATA_GATE_POLICY_VERSION`, `AUTO_ENGINE_SIM_V2_*`, `evidence_runs/`, `evidence_validations/`,
`governor.json`, la UI, ni **ningún workflow** de CI.

### 1.b Rango del diff tag → tag (**declarado al auditor**)

El diff `v2.77-beta..v2.78-beta` es **sólo de esta fase** (`feat` + `docs`), a diferencia de `v2.77`,
que arrastraba dos commits post-tag de `v2.76`. La **cita del CI del tag** se añade en un commit
**post-tag** (el workflow `Release tag CI` sólo corre al empujar el tag): mismo patrón declarado de
`v2.74`–`v2.77`.

## 2. El puro, pieza a pieza (qué se puede romper y qué lo muerde)

- **`NON_VETO_REASON_CODES`** = `{"approved"}` ∪ `DAY_EXIT_REASONS` ∪ `POSITION_SKIP_REASONS`, todos
  los literales **importados** de su dueño (`auto_reason_codes`): no se duplica ninguno. Son
  **atribuciones**, no vetos.
- **`split_journal_reasons`** es el **único** punto donde se decide qué es veto. Un código
  **desconocido NO es no-veto**: va al histograma y cae en `other`, **contado** (`M207` sigue
  mordiendo). **`M211`** (no filtra) ⇒ `approved`/`risk_exit` vuelven a contar como vetos. **`M213`**
  (filtra pero descarta) ⇒ se pierde el dato publicado.
- **`build_operability_record`** clasifica **sólo** `veto_reasons` y publica `nonVetoByCode` /
  `nonVetoCounted` / `measured` (`bool(turnTotals)`).
- **`operability_state`** con la **ausencia primero**: `not record` / `measured == False` / falta de
  `proposals`-`vetoes` ⇒ `STATE_UNKNOWN`; después `operated` / `no_signal` / `vetoed`. **`M212`**
  (sin el guardia de ausencia) ⇒ un payload sin medición se lee `no_signal`.
- **`render_operability_table`**: línea `aprobaciones/salidas: … (NO son vetos)` sólo si existen.
- **Contrato del dueño exhaustivo** (`test_every_decision_reason_code_is_declared_exactly_once`): cada
  literal de `DecisionReasonCode` está en **exactamente uno** de `VETO_BUCKET_BY_REASON` ∪
  `NON_VETO_REASON_CODES`. Si el motor añade un código y no se declara, el test cae.

## 3. Compatibilidad de lectura

`measured` ausente ⇒ `True` (una fila ya escrita en `operability_runs/journal.jsonl` —gitignoreado—
sigue leyéndose). Los casos legacy de `operability_state` (`proposals`/`vetoes` presentes, sin
`measured`) siguen dando `no_signal`/`vetoed`/`operated`.

## 4. Mutaciones (medidas)

`M211`–`M213`, matriz **213/213**, restauración **byte a byte** y árbol **intacto** (evidencia
`evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt`):

| Mutación | Qué rompe | Qué test muerde |
|---|---|---|
| `M211` | el no-veto se filtra (`approved`/`risk_exit` vuelven a contar como vetos) | `test_operated_day_accounts_only_pure_vetoes`, `test_split_journal_reasons_*`, `test_render_declares_the_non_vetoes_of_an_operated_day` |
| `M212` | la ausencia no se comprueba (payload sin medición ⇒ `no_signal`) | `test_a_truncated_payload_is_declared_unmeasured`, `test_state_unknown_*` |
| `M213` | el no-veto se descarta (se filtra pero no se publica) | `test_operated_day_accounts_only_pure_vetoes`, `test_render_declares_…`, `test_split_journal_reasons_*` |

## 5. Compuertas (medidas en local)

- `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` → **All checks
  passed!**
- `uv run --no-sync lint-imports --config packages/py/.importlinter` → **Contracts: 4 kept, 0 broken**
  (636 ficheros, 3441 dependencias).
- `uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src
  packages/py/application/src apps/api-python/src --follow-imports=silent` → **Success: no issues
  found**.
- `uv run --no-sync pytest packages/py/application/tests/test_market_operability.py -q` → **37
  passed**.
- `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` → **213/213**.

## 6. Evidencia cruda

- `evidencia-operabilidad-v2.78-2026-09-27.txt`: la tabla del smoke real (**sin cambios**) y la fila
  del **día operado**.

  | Día | Régimen | Long | SimbOper | Decid | Prop | Veto | Fills | Ciclos | Par | `vetoCounted` | `nonVetoCounted` |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | 2026-09-26 (smoke) | `BEAR_TREND` | `NO` | `4/8` | 64 | 0 | 64 | 0 | 0 | `CAPAZ` | 64 | 0 |
  | 2026-09-26 (operado) | `BEAR_TREND` | `NO` | `4/8` | 10 | 3 | 2 | 3 | 0 | `CAPAZ` | **2** | 4 (`approved=3`, `risk_exit=1`) |

- `evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt`: matriz completa **213/213**.

## 7. Declarado, NO hecho

- La **ventana de ≥4 días** de calendario **no se ejecutó** (los cubos salen de
  `created_at = datetime.now(UTC)`); `P3-2` y `P3-3` siguen **ABIERTAS** y `AUTO-22`/`AUTO-23` no se
  corren sin material.
- **`OBS-3`/`OBS-4`** (la cita del CI y el rango del diff viven post-tag) y **`OBS-5`**
  (`classify_veto_reasons` descarta conteos `<= 0` ante un mapping crudo; el camino real está a salvo
  por el parser del journal): **declaradas**, no abordadas.
- **`P3-5`** y la deuda PG `assert 17 == 26`: **ABIERTAS**, preexistentes y ajenas al diff.
- **Prerrequisito de `pairActive`**: sin estrategia **ACTIVE** + `EdgeReport`, el par queda `CAPABLE`
  pero no `ACTIVE`.

## 8. CI

- `test_market_operability.py` **ya estaba** registrado explícito en el job `quality` de
  `python-ci.yml` y en el job `python` de `release-tag-ci.yml`; esta fase **sólo añade casos al mismo
  fichero** (el job `python` del tag sube **+12**). **Ningún workflow se modifica** ⇒ no se repite el
  hueco de registro de `v2.76`.
- La sonda de mutaciones `v2_44_mutation_audit.py` no se invoca desde ningún workflow.

## 9. Veredicto esperado

`APROBADO CON OBSERVACIONES` si la contabilidad de vetos puros (día operado cuadra, `other` vacía,
no-veto publicado), la ausencia fail-closed (`unknown` en vez de `no_signal`), el contrato exhaustivo
del dueño y las mutaciones mordiendo/restaurando se sostienen. Lo que **no** puede afirmarse: que
`P3-2`/`P3-3` estén cerradas ni que exista material de mercado diverso — **no hubo ventana**.
