# V2.78 / AUTO-MATERIAL-6 — OPERABILITY ACCOUNTING (contabilidad de vetos puros)

> **AsOf:** 2026-09-27 · **Versión:** `2.03.0-beta` · **Base:** `v2.77-beta` (`2.02.0-beta`)
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Reparto:** `auto18-v1` /
> `auto15-v1` (`ALLOCATION = none`) · **Freeze:** `auto_simulation_worker.py` **intacto**.
> **Tipo de fase:** **corrección del instrumento de medición**, no de decisión. El motor, el
> gobernador (`aggregate_trial_regime`), `TOP_N` y los umbrales estadísticos **no cambian**.

## Objetivo

Cerrar los dos hallazgos que la auditoría externa de `v2.77-beta` dejó en el **journal de
operabilidad** (`P3-6` MEDIUM y `P3-7` LOW), sin tocar el motor ni el reparto:

- **`P3-6`** — la contabilidad por familias **no es de vetos puros**: `approved` y `risk_exit` caen
  en `other` e **inflan** `vetoCounted`. El cuadre pasa **sólo** porque el smoke sellado tiene
  `proposals=0`; el instrumento **fallaría en los días que sí operan**, que es justo cuando el
  propietario lo lee.
- **`P3-7`** — `STATE_UNKNOWN` es **inalcanzable**: un payload vacío/malformado se lee `no_signal`
  (fail-**open** ante basura, en un módulo cuyo contrato es fail-closed).

Fuera de alcance, por decisión explícita: la ventana de **≥4 días** (`P3-2`/`P3-3`), que es
operación de mercado del propietario; `AUTO-22`/`AUTO-23`; y las observaciones de **proceso**
`OBS-3`/`OBS-4`/`OBS-5`, que se dejan declaradas.

## Contexto (medido)

El journal V2 estampa en el **mismo** array `reasonCodes` los motivos de la **entrada** y los de la
**salida**: una decisión `approved` (`auto_v2_entry.py:2247`) y una salida `risk_exit`
(`position_manager.py:71`). `VETO_BUCKET_BY_REASON` no tiene entrada para ninguno de los dos, así
que `classify_veto_reasons` los manda a `other` y `veto_counted` los suma. El único test que
afirmaba `vetoCounted == vetoes` usaba el smoke con `proposals=0` (0 propuestas ⇒ ningún `approved`):
la igualdad era una **coincidencia del fixture**, no una propiedad del instrumento.

En `operability_state`, la condición `proposals == 0 and vetoes == 0` se evaluaba **antes** de
`if not record`, de modo que un payload vacío (ambas cifras `0`) ganaba `no_signal` y
`STATE_UNKNOWN` nunca se publicaba.

## Qué se construye

### 1. Vocabulario del dueño (aditivo)

En `packages/py/application/src/bolsa_application/auto_reason_codes.py`, el mapa decisorio del día
`_DAY_EXIT_REASON_BY_PRIMARY` ya lista los motivos de salida (`time_exit`, `risk_exit`,
`regime_exit`, `kill_switch`, `structural_stop`, …). Se publica su conjunto de valores como
`DAY_EXIT_REASONS: frozenset[str]` (y entra en `__all__`), para que el lector de la operabilidad
**importe** los literales de su dueño en vez de duplicarlos (misma doctrina que `TOP_N_EXCLUDED`).

### 2. Puro — contabilidad de vetos PUROS + ausencia fail-closed

En `packages/py/application/src/bolsa_application/market_operability.py`:

- **`NON_VETO_REASON_CODES: frozenset[str]`** = `{"approved"}` ∪ `DAY_EXIT_REASONS` ∪
  `POSITION_SKIP_REASONS` (de `auto_reason_codes`). Son **atribuciones** (una aprobación, una
  salida de una posición viva, una gestión no realizada), no vetos de entrada.
- **`split_journal_reasons(reasons) -> (veto_reasons, non_veto_reasons)`**: el único punto donde se
  decide qué es veto. Un código **desconocido NO es no-veto**: va al histograma de vetos y cae en
  `other` (nunca se descarta).
- **`build_operability_record`** clasifica **sólo** `veto_reasons` y añade a la fila:
  - `nonVetoByCode` / `nonVetoCounted` — las atribuciones se **publican**, nunca se descartan
    (perderlas sería otra mutación).
  - `measured` — `bool(turnTotals)`; un payload sin `turnTotals` (vacío/truncado/malformado) se
    declara **no medido**.
- **`operability_state`** reordena con la **ausencia primero** (fail-closed): `not record` o
  `measured == False` ⇒ `STATE_UNKNOWN`; sin `proposals` **ni** `vetoes` ⇒ `STATE_UNKNOWN`; después
  `operated` / `no_signal` / `vetoed`. `measured` ausente ⇒ `True`, para seguir leyendo filas ya
  escritas en el journal.
- **`render_operability_table`** añade, **sólo si existen**, una línea por día con las
  aprobaciones/salidas (`aprobaciones/salidas: approved=3 risk_exit=1 (NO son vetos)`).

### 3. Puros, mutaciones y CI

- `packages/py/application/tests/test_market_operability.py`: **25 → 37** casos. Se refuerza el
  contrato del dueño a cobertura **exhaustiva y exclusiva** (cada literal de `DecisionReasonCode`
  está en **exactamente uno** de `VETO_BUCKET_BY_REASON` ∪ `NON_VETO_REASON_CODES`; antes
  `approved` se saltaba con un `continue`), se añade el **día que sí opera** (`approved` +
  `risk_exit`, `proposals>0`) y los casos de `P3-7` (payload vacío / no medido).
- `apps/api-python/scripts/v2_44_mutation_audit.py`: **M211–M213**, matriz **210 → 213**:
  - `M211` (`P3-6`): el no-veto se filtra ⇒ `approved`/`risk_exit` vuelven a contar como vetos.
  - `M212` (`P3-7`): no se comprueba la ausencia ⇒ un payload sin medición se lee `no_signal`.
  - `M213` (defensivo): el no-veto se filtra **y se descarta** (deja de publicarse) ⇒ pierde el dato.
- **CI sin cambios de workflow**: el fichero de tests ya está registrado **explícito** en el job
  `quality` de `python-ci.yml` y en el job `python` de `release-tag-ci.yml`; sólo se añaden casos al
  mismo fichero, así que el hueco de registro de `v2.76` no se repite.

### 4. Docs, bump y evidencia

- Docs de fase `*-v2-78-*`: plan, audit-pack, arranque-agente, arranque-auditor, relevo.
- `PROJECT_STATE.md`, `docs/engineering/engineering-index-2026-08-03.md`, `CHANGELOG.md`,
  `docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md` (`P3-6` y `P3-7` **CERRADAS**).
- Bump `2.02.0-beta` → **`2.03.0-beta`** (`package.json`); tag `v2.78-beta` al cerrar.
- Evidencia cruda: tabla de operabilidad del smoke real (sin cambios: `regime=40`, `top_n=24`,
  `vetoCounted=64`, `nonVetoCounted=0`) **y** la fila del **día operado** (con `approved` +
  `risk_exit`, `vetoCounted == vetoes`) + matriz `213/213`.

## Lo que NO cambia (reglas duras)

- No se toca `auto_simulation_worker.py`, `paper_material_readiness.py`, `aggregate_trial_regime`,
  `TOP_N` ni `auto18-v1`/`auto15-v1`. **Sin migración** (Alembic head `046_fill_reference_mid`).
  `ALLOCATION = none`.
- No se bajan `min cycles` / `min R` / `folds` / `min_episodes`; no se fuerza
  `AUTO_ENGINE_SIM_V2_REGIME`; no se backdatea `created_at`.
- `evidence_runs/` y `evidence_validations/` no se crean ni se sobrescriben; el journal sigue en
  `operability_runs/` (gitignoreado).
- Las filas ya escritas en el journal se siguen leyendo (defaults tolerantes: `measured` ausente ⇒
  medido), declarado.

## Deuda declarada (fuera de V2.78)

- `P3-2` / `P3-3`: **ABIERTAS** — exigen la ventana de ≥4 días de calendario (operación del
  propietario).
- `P3-5` (`reserved_risk` sobrecargado) y la deuda PG `assert 17 == 26`: **ABIERTAS**, ajenas a
  este diff.
- `OBS-3`/`OBS-4` (la cita del CI y el rango del diff viven post-tag) y `OBS-5`
  (`classify_veto_reasons` descarta conteos `<= 0` ante un mapping crudo): **declaradas**, no se
  abordan.

## Criterios de salida de V2.78

- `market_operability.py` + tests puros verdes (**37**); matriz **213/213** con restauración byte a
  byte y árbol intacto; `ruff`/`import-linter`/`mypy` limpios.
- Un día operado publica `vetoCounted == vetoes` y una familia `other` **vacía**; las
  aprobaciones/salidas se declaran aparte.
- Un payload vacío/no medido se lee `STATE_UNKNOWN`, nunca `no_signal`.
- Docs de fase, bump `2.03.0-beta` y tag `v2.78-beta`; `P3-2`/`P3-3` **siguen abiertas**.
