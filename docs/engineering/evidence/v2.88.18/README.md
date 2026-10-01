# Evidencia cruda — `v2.88.18-beta` (G2 `CI-TEST-SELECTION` / peaje `OBS-19`, 2026-10-01)

> **Objeto:** sello **`2.11.18-beta`** (tag anotado `v2.88.18-beta`). **Sin migración** (Alembic head
> `046_fill_reference_mid`). **Padre del diff:** `v2.88.17.1-beta`.
> **Hermano:** [`CHANGELOG.md`](../../../../CHANGELOG.md) (entrada `2.11.18-beta`) ·
> [`criterio-salida-beta-2026-10-01.md`](../../criterio-salida-beta-2026-10-01.md) (compuerta **G2**).
> **AsOf:** 2026-10-01. **Máquina del sello:** Windows 10.0.26200, Python 3.12 (`.venv`), `uv`.

Este directorio guarda **la salida cruda del instrumento**, no una narración: lo que se puede
re-ejecutar y comparar. Todo comando se cita **literal**, y todo número de aquí sale de una corrida
registrada abajo.

---

## 0. Qué se sella

| Pieza | Fichero(s) | Naturaleza |
| --- | --- | --- |
| Cableado por **pase de directorio** | `.github/workflows/python-ci.yml`, `.github/workflows/release-tag-ci.yml` | CI |
| Censo + línea base declarada | `scripts/ci/test_selection.py`, `scripts/ci/ci-test-selection-baseline.json` | instrumento |
| Guarda del peaje (5 tests) | `apps/api-python/tests/test_ci_test_selection_census.py` | test |
| Denominador de R derivado (AUTO-23) | `apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py` | test-only |
| Timeout de conexión a BD | `packages/py/infrastructure/src/bolsa_infrastructure/{config,session}.py` | **`src`** (`+21 / −2`) |
| Teardown con tope y aviso visible | `apps/api-python/tests/conftest.py` | test-only |
| Residuo por `engine_id` | `apps/api-python/tests/test_concurrent_auto_pg.py` | test-only |

**El agujero, medido:** línea base declarada **205 → 53** ficheros. De los 205, **152** eran
**herméticos** («pasa offline; pendiente de cableado») ⇒ existían, pasaban y **no corrían**.

---

## 1. El censo y la línea base (§G2: la lista se DERIVA, no se escribe a mano)

```text
$ uv run --no-sync python scripts/ci/test_selection.py --missing
apps/api-python/tests/integration/test_accounts.py
...
apps/api-python/tests/test_workspaces.py
packages/py/application/tests/test_auto_engine_state_store_hermetic.py
...
packages/py/infrastructure/tests/test_r8c_ledger_balance_atomic.py
# (53 líneas en total)
```

```text
$ uv run --no-sync python -c "<carga el módulo y llama a report()>"
ejecutados: 504 | invisibles: 53 | sin declarar: 0 | entradas caducadas: 152
clasificados hermeticos aun sin cablear: []
```

La última línea es la que **impide la trampa**: si algún fichero **hermético** se hubiera quedado en
un `--ignore`, aparecería aquí y el sello sería falso. **Sale vacía.**

```text
$ uv run --no-sync python scripts/ci/test_selection.py --write-baseline
# línea base escrita: 53 ficheros declarados en .../scripts/ci/ci-test-selection-baseline.json
entradas: 53 | maxUndeclared: 0 | asOf: 2026-10-01
Counter({'W-G2/2': 34, 'W-G2/3': 19})
```

**Reparto de lo que queda (declarado, con motivo y tanda):** **34** `W-G2/2` (PostgreSQL o BD
dedicada) + **19** `W-G2/3` (API/red o E2E integrado, job `playwright-integrated` opt-in).
**Total 53.** Cero herméticos.

---

## 2. Oráculo de cableado (§ el número que prueba que el cambio es el que se dice)

Se comparan los ficheros que **recolectan los dos jobs offline** antes (`HEAD`) y después del cambio,
y se contrasta con el oráculo real `pytest --collect-only`.

```text
ficheros offline antes: 315 | ahora: 467
perdidos (antes si, ahora no): []
apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -> antes: True | ahora: True
packages/py/infrastructure/tests/test_lifecycle_event_store_pg.py -> antes: False | ahora: False
tests recogidos ahora: 4199
    0 packages/py/infrastructure/tests/test_lifecycle_event_store_pg.py
    0 packages/py/infrastructure/tests/test_f3b_alembic_data_epoch.py
    0 packages/py/infrastructure/tests/test_ledger_entries_reference_unique.py
    0 packages/py/application/tests/test_live_order_store_pg.py
    0 packages/py/application/tests/test_submit_intent_store_pg.py
    0 packages/py/infrastructure/tests/test_execution_event_fence_pg.py
```

Lectura: **`+152` exactos** (los herméticos), **`perdidos = []`** (nada que corriera dejó de correr) y
los **6** PG aportan **0** tests. La línea
`test_auto_scheduler_real_pg_zero_human_intervention.py -> antes: True` es la que **exculpa** al sello
del cuelgue local (§5).

---

## 3. Corrida de los 152 recién cableados (la carga del pase de directorio)

```text
$ uv run --no-sync python -m pytest <152 ficheros de packages/py/{application,infrastructure,ai}/tests> -q
1 failed, 884 passed, 1 skipped, 6 errors in 324.74s (0:05:24)
```

**Los 7 rojos son 2 de los 6 ficheros PG** (`test_f3b_alembic_data_epoch.py`,
`test_ledger_entries_reference_unique.py`) que **no** se filtraron en esa corrida exploratoria (el
filtro iba por nombre y su nombre no contiene `pg`); **son exactamente los que el sello manda a
`--ignore`** porque su certificación vive en `lifecycle-pg`. Retirados, la carga queda
**`884 passed, 1 skipped`** — el `skip` es el de Ollama, por diseño.

---

## 4. Guarda del censo (corrida por el propio job offline)

```text
$ uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q
.....                                                                    [100%]
5 passed, 1 warning in 3.35s
```

El aviso es el del teardown (§6) y es **la señal de que la red de seguridad ahora se ve**:

```text
UserWarning: [conftest] limpieza final de residuos omitida: la BD no responde (OperationalError).
Si esperabas PostgreSQL, revisa DATABASE_URL (una variable heredada puede tener prioridad sobre el
.env de la raíz).
```

---

## 5. Lo que **no** se pudo cerrar en esta máquina (declarado, no escondido)

`DATABASE_URL` **heredada** en el entorno apunta a `127.0.0.1:59999` (rango reservado de Windows: el
SYN se descarta y **no llega ni `ECONNREFUSED`**). Consecuencia medida:

* **Antes del arreglo del timeout:** el **teardown de sesión** costaba **~131 s** (el `print` lo
  escondía). **Después: 1,1 s.**
* La batería offline **completa** no llegó a terminar: se cuelga en
  `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`, un test **PG** que el
  pase de directorio de `apps/api-python/tests` **ya recogía ANTES de este sello** (§2, `antes: True`).
  En CI, sin `DATABASE_URL`, ese fichero skipea. **No es un efecto de `W-G2/1`.**
* **Deuda derivada (no arreglada aquí):** hay ficheros **PG** dentro del pase de directorio del job
  **offline**; con una `DATABASE_URL` *negra* (ni viva ni rechazada) el job **se cuelga** en vez de
  skipear. Encaja en `W-G2/2` (cablear PG por job con PG).

---

## 6. Lint y tipos (los comandos del CI, no equivalentes)

```text
$ uv run ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!
$ uv run ruff check scripts/ci --config pyproject.toml
All checks passed!
$ uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
      packages/py/application/src apps/api-python/src --follow-imports=silent
Success: no issues found in 512 source files
```

**Nota de formato (declarada):** `ruff format --check` marcaría 4 ficheros, pero **el CI solo ejecuta
`ruff check`** y las desviaciones de `config.py` son **preexistentes** (`git show HEAD:<fichero>` las
tiene igual). No se reformatea para no mezclar ruido en el sello.

---

## 7. Reproducir esta evidencia

```bash
# 1. El agujero y su reparto (debe dar 53 y cero herméticos)
uv run --no-sync python scripts/ci/test_selection.py --missing
# 2. La guarda (debe dar 5 passed)
uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q
# 3. Que ningún job haya dejado de recolectar lo que ya recolectaba
git diff --stat v2.88.17.1-beta..v2.88.18-beta -- .github/workflows
```

**Cita POST-TAG:** **PENDIENTE** (se añade en el commit siguiente al push del tag `v2.88.18-beta`).
