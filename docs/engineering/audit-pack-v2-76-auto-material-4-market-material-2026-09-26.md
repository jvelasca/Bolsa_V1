# Audit-pack — `v2.76-beta` · `AUTO-MATERIAL-4`: MARKET MATERIAL (forward PAPER con precio real)

> **AsOf:** 2026-09-26 · **Versión:** `2.01.0-beta` · **Base auditada (diff):** `v2.75-beta`
> **Alcance:** (A) cablear **precio de MERCADO** en el forward PAPER por el **único seam** que el motor
> expone (`price_script`), sin tocar el freeze; (B) correr **DOS versiones** sobre **una** cuenta
> (determinista + estrategia ACTIVE) para que `AUTO-23` tenga par; (C) **declarar** (preflight) si el
> universo puede operar antes de comprometer días; (D) registrar los puros nuevos en CI y **subir la
> matriz** a 205/205. **NO** se ejecutó la ventana de acumulación de ≥4 días reales (ver §9).
> **SIN migración** (head `046_fill_reference_mid`). **Freeze intacto.** **`auto18-v1` / `auto15-v1` no
> se mueven** (`ALLOCATION = none`).
> **Aviso de procedencia:** el precio es de **mercado** (cotización viva + cierre durable) y el régimen
> sale de **barras reales**; **los cubos de calendario salen del reloj real**, así que esta fase
> **no** puede cerrar `P3-2` / `P3-3` por sí sola.

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Evidencia |
|---|---|---|---|
| 1 | El precio entra por el **único** seam (`PriceScript`); el freeze **no** se toca | `git diff` del worker **vacío** + runner inyecta `price_script=` | §7 |
| 2 | La cotización **viva** manda y el cierre es **respaldo declarado**, no sobrescritura | `market_price_snapshot.py` + `M201` | §3, `evidencia-forward-smoke` |
| 3 | Un valor no utilizable (`None`/`NaN`/`inf`/`<=0`) **no se sirve como precio** (fail-closed) | `_usable_price` + `M202` | §3 |
| 4 | Un provider que devuelve símbolos **fuera** del watch no contamina el cache | filtro estricto por `watch` | §3 (`test_refresh_...stale_symbols`) |
| 5 | La versión A **no apila**: con posición viva devuelve `HOLD` | `VersionedReentryDecider` + `M203` | §3 |
| 6 | El enrutado por símbolo es **real y disjunto**: A no recibe el watch de B | `SplitWatchDecider` + `M204` | §3 |
| 7 | El reparto del watch es **disjunto y exhaustivo** (sin tramos solapados) | `split_watch` + `M205` | §3 |
| 8 | El régimen **no** se fuerza: sale de barras reales | `AUTO_ENGINE_SIM_V2_REGIME` **no** fijado | §5, `evidencia-regimen-mercado` |
| 9 | El gate sigue siendo **la misma pieza**: el runner no recalcula el veredicto | runner llama a `build_paper_material_readiness` | §4 (lectura del script) |
| 10 | El respaldo declarado funciona con el bridge caído (8/8 por cierre) | `XTB_BRIDGE_URL` sin escuchar | `evidencia-forward-smoke` |
| 11 | El agregado conservador de régimen **veta con watch amplio** (hallazgo declarado) | `_REGIME_CONSERVATIVE_PRIORITY` | §5 |
| 12 | Freeze, reparto y migración **intactos** | `git diff` + Alembic head `046` | §7 |

## 2. Qué cambia (y qué no)

**Cambia.**

- `packages/py/application/src/bolsa_application/market_price_snapshot.py` (**NUEVO**): cache de precio
  con providers inyectados (cotización viva + cierre durable) y lectura síncrona para `PriceScript`.
- `packages/py/application/tests/test_market_price_snapshot.py` (**NUEVO**, **14** puros, sin red).
- `packages/py/application/src/bolsa_application/auto_forward_deciders.py` (**NUEVO**): `split_watch`,
  `VersionedReentryDecider`, `SplitWatchDecider`, `build_forward_pair_decider`.
- `packages/py/application/tests/test_auto_forward_deciders.py` (**NUEVO**, **11** puros).
- `apps/api-python/scripts/v2_76_forward_market_material.py` (**NUEVO**, solo I/O): runner forward +
  **preflight de mercado** read-only (`--preflight-only`).
- `.github/workflows/python-ci.yml`: los dos ficheros puros nuevos **EXPLÍCITOS** en el job `quality`.
- `.github/workflows/release-tag-ci.yml` (**corrección POSTERIOR al tag**, `05b5fa85`): los **mismos
  dos** ficheros **EXPLÍCITOS** en el job `python` del `Release tag CI`. Faltaban al sellar (ver §10);
  el tag **no** se movió.
- `apps/api-python/scripts/v2_44_mutation_audit.py`: **M201–M205**; matriz **200 → 205**.
- `docs/engineering/evidencia-*-v2.76-2026-09-26.txt` (**4 capturas crudas**), plan, audit-pack,
  arranques y relevo. `CHANGELOG.md` + `package.json` (`2.00.0-beta` → **`2.01.0-beta`**).
  `PROJECT_STATE.md`, `engineering-index`, `deuda-p3-post-auditoria-v2.70`.

**No cambia.**

- **El instrumento**: `paper_material_readiness.py`, `auto_evidence_run.py`,
  `auto_evidence_validate.py`, `auto_paper_material.py`, el clasificador de régimen y el gate del
  gobernador — **intactos**. Ni un umbral.
- **El worker congelado** `auto_simulation_worker.py`: **intacto** (no se desactiva ningún dedupe ni
  gate; el runner solo lo **cablea** y usa su seam público de precio).
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`; `ALLOCATION = none`. **Sin migración** (head `046`).
- **`evidence_runs/` / `evidence_validations/`**: no se crean ni se sobrescriben (no hubo ventana).
- **La UI**: no cambia.

## 3. Sin cambios de umbral y con 5 mutaciones nuevas

Lógica **pura** nueva ⇒ mutaciones nuevas: `M201` (el cierre no sobrescribe la cotización viva),
`M202` (un valor no utilizable no se sirve), `M203` (la versión A no apila con posición viva),
`M204` (el enrutado por símbolo no se rompe) y `M205` (el reparto no deja tramos solapados). La matriz
pasa de **200/200** (`v2.74`) a **205/205**, con restauración **byte a byte** y árbol **intacto**.

## 4. Cómo auditar (desde un clon de GitHub)

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1
git checkout v2.76-beta
uv sync
# Compuerta estática (debe salir limpia):
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
    packages/py/application/src apps/api-python/src --follow-imports=silent
# Alembic (head esperado 046_fill_reference_mid):
cd packages/py/infrastructure && uv run alembic upgrade head && cd -
# Matriz de mutaciones completa (205/205, restauración byte a byte):
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
# Los dos puros nuevos (25 tests):
uv run --no-sync pytest packages/py/application/tests/test_market_price_snapshot.py \
    packages/py/application/tests/test_auto_forward_deciders.py -q
# Preflight de MERCADO (read-only, no escribe nada): ¿puede entrar este universo hoy?
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --preflight-only --watch-size 20
# Forward (reloj real; requiere PostgreSQL y, para el intradía, XTB_BRIDGE_URL vivo):
BROKER_VENUE=paper uv run --no-sync python apps/api-python/scripts/v2_76_forward_market_material.py \
    --watch-size 20 --interval-seconds 60 --json --out evidencia-forward.json
```

## 5. Evidencia cruda (resumen)

- **Matriz de mutaciones**: **205/205** medidas, **0** sin fragmento, restauración **byte a byte**,
  árbol **intacto** (621 s). `M201`–`M205` muerden tests **con nombre**.
- **CI offline (job `quality`, emulado sin PG)**: **2914** tests, **2912 passed**, **2 skipped**,
  `exit 0`. Con PostgreSQL vivo en local: **2913 passed / 1 failed** — el fallo es la sonda PG de
  `AUTO-23` (`test_auto_v70_auto23_evidence_validation.py`), que en CI **se salta** (ese job no tiene
  Postgres) y que **falla igual en `HEAD` prístino** (verificado con `git stash`: `assert 17 == 26`).
  Pre-existente y ajena al diff.
- **Estáticas**: `ruff` limpio · `mypy` **0 errores** (504 ficheros) · import-linter **4/4** kept.
- **Preflight de MERCADO (2026-09-26)**: 12 símbolos, `{range: 5, trend_down: 6, trend_up: 1}` ⇒
  agregado `trend_down` ⇒ eje **`BEAR_TREND`** ⇒ `entriesAllowedLong = false` ⇒ `exit 2`.
- **Forward (8 ticks, reloj real, precio de mercado)**: `pricesServed: 8/8`, todas las fuentes
  `market_close` (el bridge XTB **no** escuchaba en `:3002`: respaldo declarado, no fallo silencioso);
  `journalReasons = {regime_invalid: 40, top_n_excluded: 24}`; **0 fills**, **0 ciclos**;
  veredicto `BLOCKED`; `exit 2`.
- **Alembic**: `046_fill_reference_mid (head)`, única head.

## 6. Hallazgo central de esta fase (declarado)

**Con watch amplio, el agregado conservador de régimen hace raros los días operables.** El agregado es
el veredicto **más conservador presente** (`high_vol` > `trend_down` > `range` > `trend_up` >
`low_vol`), así que **un solo** `trend_down` deja el eje en `BEAR_TREND` y el motor **long-only** veta
por `regime_invalid` **todas** las entradas del tick. No es un defecto del runner ni del motor: es una
propiedad del instrumento **congelado**, y explica por qué el material forward no se acumula en un
sábado con el universo mixto. La respuesta de la fase es **declararlo y medirlo** (preflight), **no**
forzar `AUTO_ENGINE_SIM_V2_REGIME` ni elegir un watch a propósito para que «pase».

## 7. Verificación de invariantes

```bash
git diff v2.75-beta..v2.76-beta -- apps/api-python/src/bolsa_api/background/auto_simulation_worker.py  # vacío
git diff v2.75-beta..v2.76-beta -- packages/py/application/src/bolsa_application/paper_material_readiness.py  # vacío
git diff v2.75-beta..v2.76-beta -- packages/py/application/src/bolsa_application/auto_adaptive.py      # vacío
cd packages/py/infrastructure && uv run alembic heads   # 046_fill_reference_mid (única head)
grep -rn "AUTO_ENGINE_SIM_V2_REGIME" apps/api-python/scripts/v2_76_forward_market_material.py  # sin resultados
```

## 8. Lo que este tag NO acredita (declarado)

- **No** acredita `EVIDENCE_READY` sobre material de mercado: **no hubo ventana**. Lo que acredita es
  que el **mecanismo** está cableado, probado y **medido** (precio de mercado servido, régimen real
  leído, veto honesto declarado).
- **No** cierra `P3-2` / `P3-3`: exigen **≥4 cubos** y **≥2 episodios** de material real, es decir
  **≥4 días de calendario**. Siguen **ABIERTAS** y el motivo es de **tiempo real**, no de código.
- **No** hay `evidence_runs/` ni `evidence_validations/` nuevos: correr `AUTO-22`/`AUTO-23` sobre
  material vacío no aportaría nada y no se hace para «tener un bundle».
- La muestra forward fue **8 ticks en un sábado** (mercado cerrado): sirve para certificar el
  **camino**, no para inferir mercado.

## 9. Estado de la operación de cierre (honesto)

La ventana de acumulación (**≥4 días de calendario**) **no** se ejecutó dentro de esta fase: es
**operación de tiempo real** del propietario y no puede comprimirse (los cubos salen de
`created_at = datetime.now(UTC)`). El relevo deja el comando exacto, la cadencia diaria, el preflight
previo y los criterios de cierre de `P3-2` / `P3-3`. Lo que esta fase sí entrega es que **ya no hace
falta código** para que esa ventana produzca material diverso: el precio es de mercado, el régimen es
de barras y el par de versiones está cableado.

## 10. CI del tag `v2.76-beta` (medido, primera pasada) y hueco declarado

**Sello:** `main` `2c55a465..703c8185` (dos commits: `34b68dd6` `feat` + `703c8185` `docs`); tag
**anotado** `v2.76-beta`, objeto `12b46aff` → commit `703c8185`.

**Verde en la primera pasada** (`attempt: 1`):

| Workflow (tag `v2.76-beta`) | Run | Cifras |
|---|---|---|
| `Release tag CI` | `36257688157` | **9m15s** · **9** jobs en `success` + `certify` en `success` · `playwright (integrated E2E, opt-in)` **skipped** por diseño |
| ↳ job `python (ruff/imports/mypy/pytest offline)` | | `All checks passed!` · `Contracts: 4 kept, 0 broken` · `mypy` `0 issues (504 files)` · **`2898 passed / 37 skipped`** |
| ↳ `lifecycle-pg` | | `165 passed` + gates fail-if-skipped (`45`, `1`, `1`, `3`, `2`, `2`, `1`) |
| ↳ `decision-spine` · `a7-gate` · `shared` · `frontend` · `playwright (mock E2E)` | | `604` · `7` · `786` · `1339` (232 ficheros) · `76` (+21 skipped) |
| `Python CI` `36257688137` · `Frontend CI` `36257688152` · `Optimize lab` `36257688154` · `Fase 2 scientific` `36257688143` | | `success` |

**En `main`** (mismo commit y tag; runs `36257682064`, `36257682063`, `36257682069`, `36257682081`,
`36257682114`): todo en `success`; el job `quality` dio **`2912 passed / 40 skipped`**.

**Hueco declarado (corregido DESPUÉS del tag).** El job `python` del **tag** corrió
**`2898 passed / 37 skipped`**, número **idéntico** a `v2.75-beta`: los **25** tests nuevos **no**
estaban registrados en `release-tag-ci.yml` (ese directorio **no** tiene pase de directorio en ese job
y cada fichero va explícito); solo se registraron en `python-ci.yml`, que es lo que pedía literalmente
el to-do del plan. **Los 25 tests SÍ se ejercitaron en CI sobre el MISMO commit**: el job `quality` de
`main` dio **`2912 passed / 40 skipped`** = **`2887 + 25`** sobre `v2.75`, y el auditor los corre
**explícitamente** (§4, «25 passed»). La corrección entra en `main` como **`05b5fa85`**
(`fix(v2.76)`: los dos ficheros explícitos en el job `python` del `Release tag CI`) **sin mover el
tag**: queda **pendiente de ejercitarse en el próximo tag**, porque el workflow del tag solo corre al
empujar un tag.

**Lo que este hueco NO es:** no es un fallo de producto ni de los puros (25/25 pasan); es un **hueco de
registro en un workflow** y se declara aquí en lugar de citar `2898/37` como si incluyera los 25.
