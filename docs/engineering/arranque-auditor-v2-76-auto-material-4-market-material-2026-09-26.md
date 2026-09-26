# Arranque del auditor — `v2.76-beta` (`AUTO-MATERIAL-4`: MARKET MATERIAL, forward PAPER)

> **AsOf:** 2026-09-26 · **Objeto:** `v2.76-beta` (tag **anotado**, objeto `12b46aff` → commit
> `703c8185`) · **Versión:** `2.01.0-beta` · **Base (diff):** `v2.75-beta` · **Alembic head:**
> `046_fill_reference_mid` (**SIN migración**)
> **Freeze:** `auto_simulation_worker.py` **intacto** · **Reparto:** `auto18-v1` / `auto15-v1`
> (`ALLOCATION = none`).
> **Regla de lectura:** esta fase **no** pretende acreditar un cierre estadístico. Acredita que el
> forward PAPER **ya toma precio y régimen del mercado** por el único seam del motor congelado, con el
> par de versiones cableado, y **declara** por qué el material sigue sin acumularse (calendario +
> agregado conservador de régimen).

## Qué auditar (12 puntos)

1. **El freeze no se toca**: `auto_simulation_worker.py` **idéntico** a `v2.75-beta`. El precio entra
   **solo** por el parámetro público `price_script` (`PriceScript = Callable[[str, int], float]`).
   Comprueba también el otro uso: `_compose_regime_source` / `_compose_atr_source` **intactos**.
2. **Fail-closed del precio**: `_usable_price` rechaza `None`, `NaN`, `±inf` y `<= 0`; `__call__`
   devuelve `0.0` cuando no hay dato (el motor lo lee como «sin precio»). ¿Puede un precio inventado
   colarse? Busca cualquier `or 100.0` / default en el camino del runner.
3. **Respaldo que no sobrescribe**: la cotización viva **gana** y el cierre durable solo rellena los
   símbolos **ausentes**. Verifica `M201` y `test_close_is_the_declared_fallback_for_unsupplied_symbols`.
4. **Aislamiento del cache**: un provider que devuelve símbolos **fuera** del watch no entra
   (`test_refresh_rebuilds_the_cache_without_carrying_stale_symbols`). ¿Puede un símbolo retirado del
   watch conservar precio del tick anterior?
5. **Par real de versiones**: la versión A estampa `auto-2.0:<vA>` (el prefijo que el worker
   **reconoce** para atribuir la estrategia) y la B estampa `active-strategy:<vB>`. ¿Puede un fill
   quedar atribuido a la versión equivocada? ¿Y dos versiones operar en cubos **distintos** (rompería
   `P3-2`)?
6. **Sin apilar**: con posición viva, A devuelve `HOLD`; con lectura de posición que **falla**, también
   `HOLD` (nunca se interpreta «no sé» como «plano»). Verifica `M203`.
7. **Reparto disjunto y exhaustivo**: `split_watch` normaliza, ordena y corta con
   `clamp(round(n·share), 1, n-1)`; con 1 solo símbolo, A lo recibe y B queda vacío (**declarado**).
   Verifica `M205` y que la unión de los tramos **es** el watch normalizado.
8. **Régimen NO forzado**: el runner **no** fija `AUTO_ENGINE_SIM_V2_REGIME`
   (`grep -n AUTO_ENGINE_SIM_V2_REGIME apps/api-python/scripts/v2_76_forward_market_material.py` debe
   salir **vacío**). El preflight **lee** las mismas piezas del tick (`make_bar_snapshot_loader`,
   `classify_market_regime`, `aggregate_trial_regime`, `map_trial_regime`) y **no escribe** nada:
   verifica que `--preflight-only` **no** siembra cuenta, ni material, ni toca disco.
9. **El veredicto lo firma el gate, no el runner**: el runner llama a
   `build_paper_material_readiness` (la MISMA pieza del CLI del gate) y publica `readiness.as_dict()`.
   ¿Hay una segunda aritmética de ciclos medibles en el runner?
10. **El agregado conservador de régimen** (§6 del plan): `_REGIME_CONSERVATIVE_PRIORITY` ordena
    `high_vol` > `trend_down` > `range` > `trend_up` > `low_vol`; con watch amplio, **un solo**
    `trend_down` ⇒ `BEAR_TREND` ⇒ veto `regime_invalid` de **todas** las entradas del tick.
    **Verifica que esta fase no lo ha tocado** (ni la prioridad, ni el clasificador, ni el mapa):
    `git diff v2.75-beta..v2.76-beta -- packages/py/application/src/bolsa_application/auto_v2_entry.py`
    y `.../discovery_market_regime.py` deben ser **vacíos**; `market_regime_gate.py` también.
11. **Umbrales**: `min cycles` 32, `min R`, `folds` 3, `min_is` 8, `min_oos` 4, `min_episodes`
    **intactos**. Ningún umbral cambia en este diff.
12. **Mutaciones**: `M201`–`M205` deben **morder** y restaurar **byte a byte**; la matriz pasa de
    **200/200** a **205/205**. Reejecuta la matriz **completa** y comprueba el árbol al final.

## Evidencia que debes mirar (cruda, en `docs/engineering/`)

| Fichero | Qué acredita |
|---|---|
| `evidencia-matriz-mutaciones-v2.76-205-2026-09-26.txt` | 205/205, restauración byte a byte, árbol intacto |
| `evidencia-ci-offline-quality-v2.76-2026-09-26.txt` | job `quality` (sin PG): 2914 tests, 2912 passed, 2 skipped |
| `evidencia-ci-offline-quality-local-con-pg-v2.76-2026-09-26.txt` | mismo bloque **con** PG: 1 fallo **pre-existente** (ver «Trampas») |
| `evidencia-forward-smoke-v2.76-2026-09-26.txt` | preflight + forward: precio 8/8, régimen real, veto declarado, 0 fills |
| `evidencia-regimen-mercado-v2.76-2026-09-26.txt` | clasificación **por símbolo** del catálogo real y agregado conservador |

## Comandos

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.76-beta && uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
cd packages/py/infrastructure && uv run alembic heads && cd -   # 046_fill_reference_mid
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py   # 205/205
uv run --no-sync pytest packages/py/application/tests/test_market_price_snapshot.py \
    packages/py/application/tests/test_auto_forward_deciders.py -q         # 25 passed
```

## Trampas conocidas (no confundir con hallazgos)

- **La sonda PG de `AUTO-23`** (`apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py`)
  **se salta** en CI (el job `quality` no tiene Postgres) y **falla en local con PG vivo**
  (`assert 17 == 26`) **también en `HEAD` prístino**: está **declarado** y es **pre-existente**; no es
  una regresión de esta fase (`evidencia-ci-offline-quality-local-con-pg`).
- **`market_close` en todas las fuentes de precio** en la evidencia significa que el bridge XTB **no**
  escuchaba en `:3002`; es el **respaldo declarado**, no un fallo silencioso ni un precio inventado.
- **`0 fills` en la evidencia forward** es el resultado **correcto y honesto** de un sábado con el
  universo en `BEAR_TREND`: no hay un bug que «arreglar» y **no** se debe forzar el régimen.
- **`--preflight-only` devuelve `exit 2`** cuando el eje veta las entradas: es un **veredicto**, no un
  error de ejecución.
- La matriz de mutaciones tarda ~10 min: no la interpretes como colgada.
- **El job `python` del tag corrió `2898 passed / 37 skipped`** (número **idéntico** a `v2.75-beta`):
  los **25** tests nuevos **no** estaban registrados en `release-tag-ci.yml` al sellar (solo en
  `python-ci.yml`, que es lo que pedía el to-do del plan). **No** es un fallo de producto ni de los
  puros (25/25 pasan y el comando de arriba los ejecuta): los mismos 25 **sí** corrieron en CI sobre el
  **MISMO commit**, en el job `quality` de `main` (`2912 passed / 40 skipped` = `2887 + 25`). La
  corrección está en `main` (`05b5fa85`, `fix(v2.76)`: los dos ficheros explícitos en el job `python`
  del `Release tag CI`) **sin mover el tag**, y queda **pendiente de ejercitarse en el próximo tag**
  porque ese workflow solo corre al empujar un tag. Declarado en el audit-pack, §10.

## Veredicto esperado

`APROBADO CON OBSERVACIONES` si el mecanismo (precio de mercado + régimen real + par de versiones +
mutaciones mordiendo) se sostiene y las declaraciones de lo **no** hecho se leen como tales. Lo que
**no** puede afirmarse: que `P3-2` / `P3-3` estén cerradas ni que exista material de mercado diverso —
**no hubo ventana** y el propio pack lo declara.
