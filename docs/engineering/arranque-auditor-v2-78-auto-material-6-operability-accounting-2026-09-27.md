# Arranque del auditor — `v2.78-beta` (`AUTO-MATERIAL-6`: OPERABILITY ACCOUNTING)

> **AsOf:** 2026-09-27 · **Objeto:** tag **anotado** `v2.78-beta` → commit del sello (feat + docs) ·
> **Versión:** `2.03.0-beta` · **Base (diff):** `v2.77-beta` (`2.02.0-beta`) · **Alembic head:**
> `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **corrige el INSTRUMENTO**, no decide. Cierra `P3-6` (la
> contabilidad por familias no era de vetos puros) y `P3-7` (`STATE_UNKNOWN` inalcanzable) **sin**
> tocar el motor, el gobernador, `TOP_N` ni un umbral.

## Qué auditar (12 puntos)

1. **El freeze no se toca**: `auto_simulation_worker.py`, `portfolio_decision_engine.py`,
   `opportunity_ranker.py`, `market_regime_gate.py`, `aggregate_trial_regime`, `TOP_N` y
   `paper_material_readiness.py` **idénticos** a `v2.77-beta`. El puro nuevo **lee** literales del
   dueño (`DAY_EXIT_REASONS`, `POSITION_SKIP_REASONS`, `TOP_N_EXCLUDED` se **importan**, no se
   duplican).
2. **`P3-6` — contabilidad de vetos puros**: `split_journal_reasons` separa VETOS de ATRIBUCIONES
   (`approved`, motivos de salida, saltos de gestión) **antes** de clasificar. En un día operado,
   `vetoCounted == vetoes` y `vetoByBucket["other"]` está **vacía**. Verifica con el fixture del día
   operado (`_OPERATED_DAY`) y en el test `test_operated_day_accounts_only_pure_vetoes`. ¿Puede
   algún camino volver a contar un `approved`/`risk_exit` como veto?
3. **El no-veto NO se pierde**: `nonVetoByCode` / `nonVetoCounted` se **publican** (no se
   descartan). Un código **desconocido** tampoco es no-veto: cae en `other` y **se cuenta** (`M207`
   sigue mordiendo).
4. **`P3-7` — ausencia fail-closed**: `operability_state` comprueba **primero** `not record` /
   `measured == False` / ausencia de `proposals`-`vetoes`; un payload vacío o sin `turnTotals` se lee
   `STATE_UNKNOWN`, **nunca** `no_signal`. `M212` debe morder.
5. **Contrato del dueño exhaustivo**: `test_every_decision_reason_code_is_declared_exactly_once`
   recorre `typing.get_args(DecisionReasonCode)` y exige que cada literal esté en **exactamente uno**
   de `VETO_BUCKET_BY_REASON` ∪ `NON_VETO_REASON_CODES`. Antes `approved` se saltaba con un
   `continue`; busca un `Literal` de motivos fuera de ese dueño.
6. **Compatibilidad de lectura**: las filas ya escritas en el journal (sin `measured`) se siguen
   leyendo (`measured` ausente ⇒ `True`); los casos legacy de `operability_state` siguen dando
   `no_signal`/`vetoed`/`operated`. Verifica que no se rompe el journal acumulado.
7. **El render declara lo que no es veto**: la línea `aprobaciones/salidas: … (NO son vetos)` sale
   **sólo** si hay no-vetos (el smoke no la lleva).
8. **Sin migración y sin umbrales movidos**: `alembic heads` = `046_fill_reference_mid`; `min cycles`
   32, `min R`, `folds` 3, `min_is` 8, `min_oos` 4, `min_episodes` **intactos**.
   `DATA_GATE_POLICY_VERSION` sigue `auto15-v1`.
9. **Mutaciones**: `M211`–`M213` deben **morder** y restaurar **byte a byte**; la matriz pasa de
   **210/210** a **213/213**. Reejecuta la matriz **completa** y comprueba el árbol al final.
10. **CI sin huecos nuevos**: `test_market_operability.py` sigue registrado **explícito** en el job
    `quality` de `python-ci.yml` y en el job `python` de `release-tag-ci.yml`; sólo se añadieron
    casos al mismo fichero. El job `python` del tag debe subir en **+12** respecto a `v2.77` (los
    casos nuevos), sin tocar ningún workflow.
11. **La sonda I/O sigue read-only**: `v2_77_market_operability.py` no se modifica ni abre
    PostgreSQL; el journal vive en `operability_runs/` (gitignoreado).
12. **Rango del diff (declarado, no un hallazgo)**: el diff `v2.77-beta..v2.78-beta` es **sólo de
    esta fase** (a diferencia de `v2.77`, que arrastraba dos commits post-tag de `v2.76`). La cita
    del CI del tag vive **post-tag** (patrón `v2.74`–`v2.77`), declarado en la cabecera de la
    evidencia.

## Evidencia que debes mirar (cruda, en `docs/engineering/`)

| Fichero | Qué acredita |
|---|---|
| `evidencia-operabilidad-v2.78-2026-09-27.txt` | el smoke **sin cambios** (`regime=40`, `top_n=24`, `vetoCounted=64`, `nonVetoCounted=0`) **y** el día operado (`approved=3`, `risk_exit=1`, `vetoCounted == vetoes`, `other` vacía) |
| `evidencia-matriz-mutaciones-v2.78-213-2026-09-27.txt` | 213/213, restauración byte a byte, árbol intacto |
| `evidencia-operabilidad-v2.77-2026-09-26.txt` | la tabla del smoke en `v2.77` (punto de comparación: `nonVetoCounted` aún no existía) |

## Comandos

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.78-beta && uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
cd packages/py/infrastructure && uv run alembic heads && cd -   # 046_fill_reference_mid
uv run --no-sync pytest packages/py/application/tests/test_market_operability.py -q   # 37 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py               # 213/213
```

## Trampas conocidas (no confundir con hallazgos)

- **El smoke NO cambia**: como tenía `proposals=0`, `approved` no aparecía y `vetoCounted` ya valía
  `64`. La corrección de `P3-6` se demuestra con el **día operado**, no con el smoke. No leas «el
  smoke cuadra» como «el defecto no existía».
- **`nonVetoCounted=0` en el smoke** es correcto: no hubo aprobaciones ni salidas.
- **`state=unknown`** es una declaración de **no medido**, no un fallo: un payload truncado **debe**
  leerse así.
- La matriz de mutaciones tarda ~10 min: no la interpretes como colgada.
- **No hubo ventana**: `P3-2`/`P3-3` siguen abiertas y `AUTO-22`/`AUTO-23` no se corrieron.
- **Deuda PG pre-existente**: `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py`
  (`assert 17 == 26`) se **salta** en CI sin Postgres; es ajena al diff.
- **`OBS-5`** (el parser `classify_veto_reasons` descarta conteos `<= 0` ante un mapping crudo)
  sigue **declarada**: el camino real está a salvo por el parser del journal.

## Veredicto esperado

`APROBADO CON OBSERVACIONES` si la contabilidad de vetos puros (día operado cuadra, `other` vacía,
no-veto publicado), la ausencia fail-closed (`unknown` en vez de `no_signal`), el contrato exhaustivo
del dueño y las mutaciones mordiendo/restaurando se sostienen. Lo que **no** puede afirmarse: que
`P3-2`/`P3-3` estén cerradas ni que exista material de mercado diverso — **no hubo ventana**.
