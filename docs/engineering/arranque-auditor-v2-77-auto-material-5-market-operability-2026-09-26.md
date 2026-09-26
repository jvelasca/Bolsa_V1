# Arranque del auditor — `v2.77-beta` (`AUTO-MATERIAL-5`: MARKET OPERABILITY)

> **AsOf:** 2026-09-26 · **Objeto:** tag **anotado** `v2.77-beta` → objeto `22da1bb0` → commit
> **`ade1df58`** (sello en dos commits: `233ef8cc` feat + `ade1df58` docs) · **Versión:**
> `2.02.0-beta` · **Base (diff):** `v2.76-beta` (`2.01.0-beta`) · **Alembic head:**
> `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **no** pretende acreditar un cierre estadístico ni atribuir la
> falta de material al gobernador. Acredita un **instrumento de medición** (journal diario de
> operabilidad + nomenclatura CAPABLE/ACTIVE) que **declara la causa** de cada no-operación y deja
> la ventana de ≥4 días como operación del propietario.

## Qué auditar (13 puntos)

1. **El freeze no se toca**: `auto_simulation_worker.py` **idéntico** a `v2.76-beta`. El único cambio
   en `v2_76_forward_market_material.py` es **aditivo** (nuevos campos `pairCapable`/`pairActive` +
   la etiqueta del print); `pairAvailable` se conserva como alias.
2. **El motor no cambia de decisión**: `portfolio_decision_engine.py`, `opportunity_ranker.py`,
   `market_regime_gate.py`, `aggregate_trial_regime`, `TOP_N` y `paper_material_readiness.py`
   **idénticos**. El puro nuevo **lee** literales del dueño (`TOP_N_EXCLUDED` se **importa**, no se
   duplica), no los redefine.
3. **Cobertura del vocabulario**: `test_every_decision_reason_code_has_a_declared_bucket` recorre
   `typing.get_args(DecisionReasonCode)` y exige familia para todos salvo `approved`. ¿Puede un
   código del motor quedar sin clasificar sin que caiga un test? Busca un `Literal` de motivos fuera
   de ese dueño.
4. **Fail-closed de la contabilidad**: un código sin familia va a `other` y **se cuenta** (`M207`);
   `veto_counted` suma **todas** las familias (`M210`). ¿Puede perderse una entrada del journal?
5. **`no_signal` no miente** (`M209`): sólo si `proposals == 0 and vetoes == 0`. Verifica en el smoke
   real (`proposals=0`, `vetoes=64`) que el estado es `vetoed`.
6. **Separación de causas** (`M206`): `regime` (hecho de mercado), `governor` (permiso) y `top_n`
   (tope de evaluación) son familias distintas. ¿Se mezclan en algún camino?
7. **CAPABLE ≠ ACTIVE** (`M208`): `pair_capable` **no** se deriva de `pair_active`. En el smoke real
   `pairCapable=true` y `pairActive=false` con `versionB=""`.
8. **`symbols_operable` no inventa**: `None` si no hay `bySymbol` ni `counts`; `4` en el smoke real.
9. **La sonda I/O es read-only de verdad**: `v2_77_market_operability.py` no abre PostgreSQL, no
   importa SQLAlchemy/asyncio, no escribe en `evidence_runs/`/`evidence_validations/` ni en el
   material durable; escribe **sólo** el journal (`operability_runs/`, gitignoreado). ¿Puede tocar
   algo más? `exit 2` sin registros.
10. **Idempotencia del journal**: re-ejecutar el mismo forward **no** duplica filas (identidad por
    `day`/`account`/`versionA`/`watchSize`).
11. **Sin migración y sin umbrales movidos**: `alembic heads` = `046_fill_reference_mid`;
    `min cycles` 32, `min R`, `folds` 3, `min_is` 8, `min_oos` 4, `min_episodes` **intactos**.
    `DATA_GATE_POLICY_VERSION` sigue `auto15-v1`.
12. **Mutaciones**: `M206`–`M210` deben **morder** y restaurar **byte a byte**; la matriz pasa de
    **205/205** a **210/210**. Reejecuta la matriz **completa** y comprueba el árbol al final.
13. **Rango del diff (declarado, no es un hallazgo)**: `v2.76-beta..v2.77-beta` tiene **4** commits y
    **dos son post-tag de `v2.76`** (`05b5fa85` fix de registro + `40d3d9dc` cita de su CI). Las dos
    entradas `M` de docs de `v2.76` en el diff **no** son de esta fase, y el cambio de
    `release-tag-ci.yml` combina las dos fases. Verifica además que el job `python` del tag mide
    **`2948/37`** = `2898` + `25` (puros de `v2.76`, ya ejercitados) + `25` (puros de `v2.77`): el
    **hueco de registro de `v2.76` queda cerrado** sin haber movido su tag.

## Evidencia que debes mirar (cruda, en `docs/engineering/`)

| Fichero | Qué acredita |
|---|---|
| `evidencia-operabilidad-v2.77-2026-09-26.txt` | tabla diaria sobre el forward smoke real: `BEAR_TREND`, `4/8`, `regime=40`, `top_n=24`, 0 fills, `CAPAZ` |
| `evidencia-matriz-mutaciones-v2.77-210-2026-09-26.txt` | 210/210, restauración byte a byte, árbol intacto |
| `evidencia-ci-tag-v2.77-2026-09-26.txt` | CI del tag: `Release tag CI` `36279417767` GREEN a la primera (10 jobs + `certify`), `python` del tag **`2948/37`**, 10/10 runs del commit `ade1df58` |
| `evidencia-forward-smoke-v2.76-2026-09-26.txt` | el JSON de origen (fuente del fixture del puro) |

## Comandos

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.77-beta && uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
cd packages/py/infrastructure && uv run alembic heads && cd -   # 046_fill_reference_mid
uv run --no-sync pytest packages/py/application/tests/test_market_operability.py -q   # 25 passed
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py               # 210/210
uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py \
    --render --journal operability_runs/journal.jsonl   # exit 2 si no hay journal
```

## Trampas conocidas (no confundir con hallazgos)

- **`0 fills` en el smoke** es el resultado **correcto y honesto** de un sábado con el universo en
  `BEAR_TREND`: el journal lo **declara** (`regime=40`), no lo repara y **no** debe forzarse el
  régimen.
- **`pairActive=false`** significa que sólo hay una versión operando (falta la ACTIVE + `EdgeReport`);
  **no** es un defecto del instrumento.
- **`market_close` en las 8 fuentes de precio** significa que el bridge XTB no escuchaba: es el
  respaldo **declarado**, no un precio inventado.
- La matriz de mutaciones tarda ~10 min: no la interpretes como colgada.
- **No hubo ventana**: `P3-2`/`P3-3` siguen abiertas y `AUTO-22`/`AUTO-23` no se corrieron. Esto está
  declarado y **no** es un incumplimiento de la fase.
- **Deuda PG pre-existente**: `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py`
  (`assert 17 == 26`) se **salta** en CI sin Postgres y falla en local con PG vivo **también en `HEAD`
  prístino**: está declarada, es ajena al diff y no es una regresión de esta fase.

## Veredicto esperado

`APROBADO CON OBSERVACIONES` si el instrumento (clasificación por familia, `no_signal` fail-closed,
CAPABLE ≠ ACTIVE, mutaciones mordiendo y restaurando, sonda read-only) se sostiene y las
declaraciones de lo **no** hecho se leen como tales. Lo que **no** puede afirmarse: que `P3-2`/`P3-3`
estén cerradas, que el gobernador conservador «sea el problema» (el instrumento **mide**, no
concluye) ni que exista material de mercado diverso — **no hubo ventana**.
