# Evidencia `v2.88.17.1-beta` — W4.1 `GRANULARIDAD-OPERATIVA`: HOTFIX DEL CERTIFIER A11 (`lifecycle-pg`) — EL INSTRUMENTO DEJA DE SER UN SORTEO DEL VENUE (**TEST-ONLY**, `Δ src = 0`)

> **Clase: evidencia del hotfix del sello `W4`. ESTADO: cerrado en `main` — bump `2.11.17.1-beta` aplicado; tag y cita POST-TAG los realiza el SELLO.**
> **AsOf:** 2026-10-01. **Base:** tag rojo `v2.88.17-beta` (`cfd13f54`).
> **Plan de la fase:** [`plan-w4-precio-real-2026-10-01.md`](../plan-w4-precio-real-2026-10-01.md). **Evidencia del sello:** [`evidence/v2.88.17/README.md`](../v2.88.17/README.md).

`W4` quedó **sellado** y su tag `v2.88.17-beta` salió **rojo en un solo job** por un **sorteo del
arnés**, no por el producto: el certifier `A11` elegía el `instrument_id` con `uuid4()` mientras el
venue SIM ancla su ruido a la **barra** (`W3`). Este dossier documenta el rojo, la causa aislada y el
arreglo (`Δ src = 0`).

---

## 1. Por qué se sella (rojo declarado, no heredado)

**`Release tag CI` run [`36845274700`](https://github.com/jvelasca/Bolsa_V1/actions/runs/36845274700)**
(`ref=refs/tags/v2.88.17-beta`, HEAD `cfd13f54`, `2026-10-01T09:50:07Z`) ⇒ **`failure`**.

El *aggregate* `certify` publica el reparto **exacto** de jobs:

```
security=success  shared=success  spine=success  frontend=success  python=success
playwright-mock=success  replay-repro=success  dr-verify=success  a7-gate=success
lifecycle-pg=failure            →  "Release tag CI not GREEN"
```

Y el job `lifecycle-pg` muere en **una** prueba, con su traza:

```
apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py:376: in test_a11_discovery_to_auto_sim_pg
E   AssertionError: la ACTIVE debía abrir posición en el dataset determinista (sin SKIPPED)
E   where Decimal('0') = <built-in method get of dict object at 0x...>('inst-a11-fbb37d99e8', Decimal('0'))
FAILED apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py::test_a11_discovery_to_auto_sim_pg
1 failed, 165 passed, 2 warnings in 84.45s
```

⇒ **`python` verde** (ruff/imports/mypy/pytest offline) y **`replay-repro` verde**: el rojo **no** es
del motor, ni del artefacto OOS, ni de una expectativa de producto. Es el **arnés**.

## 2. Causa aislada (sonda PURA y reproducible byte a byte)

Desde `V2.88.16` (`W3`) el venue SIM deriva **todo** su ruido de
`sim_hash(seed, instrument_id, side, ...)` con el `seed` **anclado a la barra**:
`fill_seed(bar_tick(moment, timeframe), symbol)`. Consecuencia: **dentro de una barra el sorteo es una
constante** para un id dado, así que los **12 reintentos intra-barra** del worker no cambian el
desenlace. Si el id sorteado no llena, el certifier no abre posición y el `assert` de §1 se dispara.

**El id del CI, medido con la sonda** (`bar_tick` de la barra del run, `20727`):

| id | tick `20727` (barra del run) | tick `20728` |
| --- | --- | --- |
| `inst-a11-fbb37d99e8` (**el del rojo**) | `status=submitted`, `queue=ok`, **`fills=[]`** | `filled`, 4 tranchas (50 % + 23,5 % + 11,66 % + 14,84 %) |
| `inst-a11-7589ea7fa8` (repro local) | `status=unknown`, `queue=noise_unavailable`, **`fills=[]`** | `filled`, 4 tranchas |

**Barrido determinista** (rejilla de **20 000** ids `inst-a11-<uuid4hex10>` equiespaciados en el
espacio de 40 bits; re-corrible tal cual):

* **12,30 %** (2 460/20 000) **no llenan la pata BUY en la barra corriente**.
* **1,59 %** (319/20 000) no llenan en **ninguna** de las dos barras consecutivas.

**Los motivos NO son solo canales noisy** (desglose de los que no llenan):

| `status` / `queue_event` | ids | % de los que no llenan |
| --- | --- | --- |
| `submitted` / `ok` | 1 278 | **52,0 %** — el **corte de parciales** no deja ninguna trancha |
| `unknown` / `noise_timeout` | 518 | 21,1 % |
| `unknown` / `noise_unavailable` | 229 | 9,3 % |
| `rejected` / `noise_reject` | 200 | 8,1 % |
| `rejected` / `noise_market_closed` | 101 | 4,1 % |
| `unknown` / `noise_unknown` | 84 | 3,4 % |
| `submitted` / `noise_reconnect` | 30 | 1,2 % |
| `submitted` / `noise_duplicate` | 20 | 0,8 % |

⇒ La mitad de los rojos **no** habría sido un canal de error declarado (sería fácil de narrar como
«rechazo del venue»): es el **sorteo de las tranchas**. Por eso el arreglo **no clasifica motivos**:
exige `fills` **no vacío**.

## 3. Arreglo (**test-only**)

En `apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py`:

* `_bar_ticks()` — la barra corriente y la siguiente (mismo ancla que el motor ⇒ un cruce de
  medianoche UTC no fabrica un rojo nuevo).
* `_buy_fills(id, tick)` — **puro**: `simulated_fill_schedule` con los **mismos parámetros** que el
  worker (`_A11_FILL_CHUNKS = 4`, `base_mid = 100.0`, lote `100`).
* `_filling_instrument_id()` — barre hasta `_A11_FILL_DRAWS = 64` candidatos `uuid4` **frescos por
  run** y devuelve el primero que llena en BUY en **las dos** barras; si ninguno lo hace, **falla con
  diagnóstico propio** en vez de dejar el rojo al azar.

**Margen medido:** la barrida resuelve en **≤ 8 sorteos** (p99 = **4**) sobre 20 000 barridas
independientes ⇒ el tope de `64` tiene un margen de ~8× sobre el peor caso observado. Es el **MISMO**
patrón que ya declaraban `test_a9_scheduler_process_pg_zero_human._filling_instrument_id` y
`test_golden_day_v2_process_pg._filling_instrument_id`: el rebaseline de `W3` pasó por 8 arneses y
este quedó fuera.

**`Δ src = 0`:** sólo se tocan **tests** y la **matriz de mutaciones**. Nada del camino de producto.

## 4. Contrato fijado (test + mutación)

* **Test nuevo** `test_a11_instrument_id_comes_from_a_fill_sweep` (**puro**: sin PG, sin proceso):
  exige que el id elegido llene en BUY en **todas** las barras de `_bar_ticks()`. Si alguien devuelve
  el `uuid4` crudo, el test no protege (el sorteo es legal ~87,7 % de las veces) — lo que protege es
  la **mutación**:
* **Mutación nueva `M293`** (invierte la condición de la barrida) ⇒ **muerde** en ese test, árbol
  restaurado **byte a byte**. La matriz llega a **`M293`**.

## 5. Verificación local

* **Certifier A11 sobre PG real**: **3/3** verde con el arreglo (2,3 s cada corrida) y **25/25** en la
  sesión de diagnóstico (frente a **19/25** con el `uuid4` crudo ⇒ el rojo observado en `main`).
* **Guarda pura**: `1 passed`.
* **`M293`**: rojo en `test_a11_instrument_id_comes_from_a_fill_sweep`, `restaurado byte a byte: si`,
  `medidas 1/1`.
* **Lint/typing**: `ruff check … --config pyproject.toml` (el comando **exacto** del CI) limpio;
  `mypy` sobre el fichero: los **mismos 15 errores pre-existentes** que en `HEAD` (sólo se desplazan
  los números de línea; **0 nuevos**) — y el `mypy` del CI ni siquiera cubre `tests/`.
* **`replay-repro` intacto por construcción** (`Δ src = 0`): el job congeló el artefacto **verde** en
  el run rojo de §1 y nada del motor cambia aquí.

## 6. Supersede

`v2.88.17-beta` **queda rojo y no se reescribe** (mismo patrón que `v2.88.16-beta` → `v2.88.16.1-beta`
→ `v2.88.16.2-beta`): el sello del hotfix es **`v2.88.17.1-beta`**.

**Deuda declarada:** el rojo **no** está cubierto por un gate de CI propio (la matriz de mutaciones
mide el contrato, pero no se corre en el tag); su cita es la del **POST-TAG del sello `W4.1`**.
