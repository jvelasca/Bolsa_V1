# Plan de fase — `v2.80` / `AUTO-MATERIAL-8`: MARKET WINDOW (instrumento + capturador de ventana)

> **AsOf:** 2026-09-27 · **Versión:** `2.04.0-beta → 2.05.0-beta` · **Tag:** `v2.80-beta` ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Freeze:** `auto_simulation_worker.py`
> **intacto** · **Reparto:** `auto18-v1` / `auto15-v1` (`ALLOCATION = none`).

## 1. Contexto y origen

`v2.79-beta` (`2.04.0-beta`) ya separa el censo de **ENTRADA** de los **eventos de POSICIÓN** y tiene CI
de tag verde. La auditoría de `v2.79` deja dos frentes de código, más el bloqueo real (la ventana de
mercado):

- **Auditoría 2 (matiz):** `operability_state` etiqueta como `vetoed` el caso `proposals>0, vetoes==0,
  fills==0` — cuando literalmente **no hubo ningún veto registrado**. Falta un quinto estado explícito
  (`STATE_UNRESOLVED`).
- **Auditoría 1 §20:** con el catálogo ya acotado, `other>0` debe leerse como **violación de contrato**,
  no como un cubo más. Decisión ratificada: **aviso**, no fallo duro.
- **Auditoría 1 §21:** publicar `reasonCatalogCoverage` (declarado / observado / desconocido) para probar
  que `other==0` no es accidental.
- **Auditoría 1 §17–19:** una versión de **observación** que emita la serie diaria (ENTRY, VETOS,
  POSITION EVENTS, TOP_N, RESERVAS, FILLS, CYCLES, R, RÉGIMEN, PRICE SOURCE, STRATEGY A/B) con linaje
  (`account`, `instrument`, `strategy_version`, `cycle_id`) para poder reconstruir la ventana ≥4 días.

Alcance ratificado por el propietario: el capturador **lee el journal durable**; la ventana ≥4 días la
corre el propietario (no es una fase de código).

## 2. Alcance (ficheros)

- `packages/py/application/src/bolsa_application/market_operability.py` — `STATE_UNRESOLVED`;
  `DECLARED_REASON_CODES` + `reason_catalog_coverage` + `other_veto_count`; `otherCount`/
  `contractViolation`; aviso en el render.
- `packages/py/application/src/bolsa_application/operability_window.py` **(nuevo, puro)** — fila diaria de
  la ventana, linaje, `render` de la serie y `window_gate`.
- `apps/api-python/scripts/v2_80_market_window.py` **(nuevo)** — capturador read-only sobre el journal
  durable + reservas; `--render` / `--json` / `--out` / `--journal` / `--no-write`.
- `packages/py/application/tests/test_market_operability.py` — `STATE_UNRESOLVED`, cobertura, contrato
  `other>0`.
- `packages/py/application/tests/test_operability_window.py` **(nuevo)** — fila/linaje/gate/render.
- `apps/api-python/scripts/v2_44_mutation_audit.py` — `M220`–`M225` (matriz **219 → 225**).
- `.github/workflows/python-ci.yml` y `.github/workflows/release-tag-ci.yml` — registrar **explícitamente**
  `test_operability_window.py` (lección de `v2.76`: no basta con que exista el fichero).
- `package.json` — `2.04.0-beta → 2.05.0-beta`.
- `docs/engineering/*-v2-80-*`, `PROJECT_STATE.md`, `engineering-index-*.md`, `CHANGELOG.md`,
  `deuda-p3-*.md` — paquete de fase y sello.

**No se toca:** `auto_simulation_worker.py` (congelado), `portfolio_decision_engine.py`,
`opportunity_ranker.py`, `market_regime_gate.py`, `aggregate_trial_regime`, `paper_material_readiness.py`,
`TOP_N` ni umbrales. `auto_reason_codes.py` **no cambia**: el catálogo declarado se deriva del dueño ya
existente.

## 3. Pasos

### 3.1 `STATE_UNRESOLVED` (auditoría 2)

En `market_operability.py`: nueva constante `STATE_UNRESOLVED = "unresolved"` (+ `__all__`) y rama en
`operability_state` **después** de `operated` y `no_signal`, **antes** del `vetoed` final:

```python
if _count(record.get("fills")) > 0 or _count(record.get("closed")) > 0:
    return STATE_OPERATED
if _count(record.get("proposals")) == 0 and _count(record.get("vetoes")) == 0:
    return STATE_NO_SIGNAL
if _count(record.get("vetoes")) == 0:
    # proposals>0, sin ningun veto registrado y sin desenlace: el nombre no puede
    # afirmar "el motor las rechazo" (auditoria 2). Sigue siendo fail-closed: nunca no_signal.
    return STATE_UNRESOLVED
return STATE_VETOED
```

La ausencia (`not record` / `measured == False` / falta de `proposals`-`vetoes`) **sigue ganando** ⇒
`STATE_UNKNOWN`.

### 3.2 Cobertura del catálogo (auditoría 1 §21)

Catálogo declarado = unión de los dos conjuntos que el test `H-2` ya prueba exhaustivos y disjuntos:

```python
DECLARED_REASON_CODES: frozenset[str] = frozenset(VETO_BUCKET_BY_REASON) | NON_VETO_REASON_CODES

def reason_catalog_coverage(observed: Iterable[str]) -> dict[str, int]:
    codes = {str(code).strip() for code in observed}
    codes.discard("")
    unknown = {code for code in codes if code not in DECLARED_REASON_CODES}
    return {"declared": len(DECLARED_REASON_CODES), "observed": len(codes), "unknown": len(unknown)}
```

`build_operability_record` publica `reasonCatalogCoverage` sobre la unión de códigos vistos en **todos**
los canales (`veto` + `nonVeto` + `positionEvent`).

### 3.3 Violación de contrato `other>0` como AVISO (auditoría 1 §20)

En `build_operability_record`: `otherCount = sum(bucket others)` y `contractViolation = otherCount > 0`. En
el render, línea explícita sólo si hay violación:

```text
ALERTA CONTRATO: other>0 (motivo(s) no catalogado(s): xyz=2) — revisar alta de reason code
```

Y en `v2_80_market_window.py`, aviso a `stderr` (`# ALERTA CONTRATO …`). **No** tumba la corrida
(ratificado: aviso). El exit code sigue siendo `0` con registros / `2` sin registros legibles.

### 3.4 Módulo puro de la ventana — `operability_window.py`

Una fila por día con las dimensiones de §17 y **linaje**, declarando huecos como `None` (jamás `0`
inventado):

- Identidad/linaje: `day`, `account`, `capturedAt`, `strategyVersions`→`versions`, `symbolsObserved`,
  `cycleIds` (lista), `instruments`.
- Entrada: `regime`, `regimeMeasurement`, `symbolsOperable`→`symbolsObserved`, `priceSources`
  (`live`/`close`/`missing` o `None`), `decided`, `proposals`, `vetoes`, `vetoByBucket` (con `top_n` y
  reservas visibles), `vetoCounted`, `otherCount`, `contractViolation`.
- Posición (canal separado): `positionEventByCode`, `positionEventCounted`.
- Resultado: `fills`, `cycles`, `measurableCycles`, `rSum`/`rMean`, `rMeasurement`, `pairCapable`,
  `pairActive`.
- `reasonCatalogCoverage` por día.

Piezas puras: `build_window_row(...)`, `render_window_series(rows)` (tabla
`Día/Régimen/ENTRY/VETOS/FILLS/CYCLES/R/Estado` + desglose por familia + `eventos/posicion` aparte) y:

```python
MARKET_WINDOW_MIN_DAYS = 4
MARKET_WINDOW_MIN_EPISODES = 2
MARKET_WINDOW_MIN_CYCLES = 32

def window_gate(rows) -> dict:
    # Cubos de CALENDARIO compartidos (días distintos), NO número de filas;
    # episodios de régimen distintos; ciclos medibles acumulados.
    # ready = days>=4 and episodes>=2 and cycles>=32; si no => INCONCLUSIVE / NO MEDIDO.
```

### 3.5 Capturador — `v2_80_market_window.py`

Script read-only (patrón de sesión de `v2_76`/`paper_material_readiness`).

- Lee el journal durable (`SqlAlchemyJournalRepository.list_entries`, paginado) y los fills por versión
  (`PostgresSimFillFinanceContextStore`).
- R y régimen: `read_all_reservations` + `read_cycle_regimes` + `cycle_risk_from_reservations` +
  `adaptive_instrument_cycles` (denominador único, huecos declarados); R por ciclo con `measured_r`.
- Reutiliza **tal cual** `collect_journal_reasons` / `split_journal_reasons` / `classify_veto_reasons` /
  `reason_catalog_coverage` (una sola puerta del censo).
- `--days N` / `--since`, `--account-id`, `--render`, `--json`, `--out operability_runs/window-YYYYMMDD.json`,
  `--journal operability_runs/window.jsonl`, `--no-write`. Journal **no versionado** (gitignoreado).
- En `win32`, `WindowsSelectorEventLoopPolicy` (mismo quirk psycopg que `auto_evidence_run.py`).
- Salida: exit `0` con filas; exit `2` declarado si no hay material legible; **nunca** rellena una
  dimensión ausente.

### 3.6 Tests y mutaciones

Tests (`test_market_operability.py`): `unresolved`; cobertura (`declared`/`observed`/`unknown`); contrato
(`other>0` ⇒ `contractViolation`, sin excepción; pero `other==0` en el día de reversión).

Tests (`test_operability_window.py`, puros, sin PG): fila con linaje y huecos declarados (`None`, nunca
`0`); `window_gate` (4 filas del mismo día **no** cumplen; 4 días + 2 episodios + 32 ciclos ⇒ ready);
render determinista y canales separados.

Mutaciones `M220`–`M225` (byte a byte, árbol intacto): `M220` `unresolved` colapsa a `vetoed`; `M221`
`unknown` de cobertura forzado a `0`; `M222` `contractViolation` nunca se marca; `M223` `window_gate`
cuenta filas en vez de días; `M224` dimensión ausente coaccionada a `0`; `M225` eventos de posición
vuelven al censo de vetos.

### 3.7 Sello y documentación

Bump `2.05.0-beta`, tag `v2.80-beta`; paquete de fase (plan, audit-pack, arranque del agente, arranque del
auditor, relevo) + evidencia cruda (matriz 225/225, CI del tag) + actualizar `PROJECT_STATE.md`, índice,
`CHANGELOG.md` y `deuda-p3-*.md`. Actualizar el
[runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md) para incluir el capturador y la
tabla ≥4 días.

## 4. Criterios de aceptación

- `ruff` limpio · import-linter `4 kept, 0 broken` · `mypy` `0 issues` · alembic head
  `046_fill_reference_mid` (sin migración).
- `test_market_operability.py` **48 → 58** y `test_operability_window.py` (13 nuevos, 71 en total) verdes;
  registrados en `python-ci.yml` y `release-tag-ci.yml`. *(Medido: la estimación inicial de 11 puros en
  `market_operability` quedó en 10 y los de la ventana en 13; el total de la suite de aplicación es
  `2061 passed`.)*
- Día de reversión: `vetoCounted == vetoes == 2`, `other` vacía, `unknown == 0`, `contractViolation is
  False`.
- `unresolved` alcanzable y distinguible de `vetoed`/`no_signal`/`unknown`.
- `window_gate` honesto: sin 4 días + 2 episodios + 32 ciclos ⇒ `INCONCLUSIVE`/`NO MEDIDO`.
- `M220`–`M225` muerden y restauran byte a byte; matriz **225/225**; árbol idéntico antes/después;
  `git status` limpio.
- CI del tag `v2.80-beta` verde en primera pasada, con los jobs PG intactos.

## 5. Reglas duras que siguen vigentes

- **No** se toca el freeze del worker ni el gobernador (`aggregate_trial_regime`), `TOP_N`, los umbrales,
  `min cycles`/`min R`/`folds`/`min_is`/`min_oos`/`min_episodes`.
- **No** se fuerza `AUTO_ENGINE_SIM_V2_REGIME`, **no** se backdatea `created_at`, **no** se sobrescribe
  `evidence_runs`/`evidence_validations`.
- **Forward, no replay.** Veredicto honesto `INCONCLUSIVE`/`NO MEDIDO` si el material es degenerado.
- **Sin migración**; `ALLOCATION = none`; reparto `auto18-v1`/`auto15-v1`.
- El capturador es **read-only** sobre el dinero y el journal durable; el journal de la ventana vive en
  `operability_runs/` (no versionado).

## 6. Fuera de alcance (operación del propietario)

- **Correr la ventana ≥4 días** y cerrar `P3-2`/`P3-3` (`AUTO-22`/`AUTO-23`): es operación, no código. Esta
  fase **prepara el instrumento**; no certifica nada estadísticamente.
- **`H-4` (LOW)** sigue declarado **ABIERTO**: el vocabulario de rechazo pre-ranqueo de `auto_v2_entry`
  (`signal_duplicate`, `signal_stale`, `signal_identity_missing`, `signal_superseded_by_candidate`,
  `signal_distinct_strategy_not_representable`) no tiene familia declarada; el nuevo `otherCount`/
  `contractViolation` y la cobertura `unknown` son **el instrumento que lo hace visible**.
- `P3-5` (`reserved_risk` sobrecargado) y `OBS-5` siguen declaradas.
- `ALLOCATION` dinámica y `LIVE` siguen **correctamente congelados**.
