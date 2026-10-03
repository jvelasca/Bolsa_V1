# Evidencia cruda — `v2.88.33-beta` (AUTO: sandbox **DÍA-D AUTO** read-only + vista en `/auto-monitor`)

> **Objeto:** package **`2.11.33-beta`** · Alembic head **`048_journal_entry_dedupe_key`** (**sin migración**) · fecha **2026-10-03**.
> **Clase:** entrega de **investigación/sandbox** sobre el motor AUTO. Añade un modo **DÍA-D AUTO** que sitúa el motor AUTO real en una **fecha pasada** `D` con reloj/precio inyectados (mismo harness hermético de `v2.86`/`v2.87`), recoge lo **declarado**, lo compara con lo **ejecutado real** (hechos durables de `D`, leídos read-only) y con el **OOS real** posterior a `D`; se sirve por una ruta **read-only** y se pinta en `/auto-monitor`.
> **`Δ decisión motor = 0`:** no se toca motor, gobernador, `TOP_N`, umbrales, allocation, pesos A/B ni migraciones. `AutoSimulationWorker` y los módulos congelados **no se editan**: el sandbox solo los **conduce** con reloj/precio/stores en memoria.
> **Padre:** [`evidence/v2.88.32/README.md`](../v2.88.32/README.md) (runner operativo de la ventana PAPER).
> **Nomenclatura:** `AUTO engineering release = v2.88.33-beta` · `application package = 2.11.33-beta`.

---

## 0. Qué entrega este sello

| # | Pieza | Qué hace |
|---|---|---|
| **1 · Lógica pura** | `packages/py/application/src/bolsa_application/dia_d_auto.py` | `build_dia_d_auto_artifact(...)` + `compare_declared_vs_executed(...)`: veredictos deterministas `MATCH \| DIVERGENT \| NOT_MEASURED` por paso de la cadena `SIGNAL → … → CYCLE_CLOSED`, y un veredicto global `MATCH`/`DIVERGENT`/`PARTIAL`/`NOT_MEASURED`. Un valor no medido viaja `None` + `UNKNOWN`; **nunca `0`**. Sin reloj ni ULID: `sort_keys=True` y determinista. |
| **2 · CLI sandbox** | `apps/api-python/scripts/v2_89_dia_d_auto_replay.py` | Reutiliza el harness hermético de `v2.86`/`v2.87` (`--at D`, `--history-days`, `--horizon-days`). Corre el replay hasta `D` y lo captura como **declarado**; lee **read-only** los hechos durables de `D` (`sim_fill_finance_context`, `portfolio_reservations`, `auto_exit_orders`, `decision_journal_entries`) como **ejecutado**; mide el **OOS real** del ciclo de `D`. Escribe `operability_runs/dia-d-auto/dia-d-auto-<D>.json` (globs no versionados). |
| **3 · Ruta read-only** | `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py` | `GET /api/auto/dia-d-replay` (lista de días) y `GET /api/auto/dia-d-replay/{day}` (artefacto). Fail-closed: sin cuenta visible ⇒ vacío con `no_account_scope`; sin artefacto ⇒ `available=false` + `artifact_not_found`; día inválido ⇒ `invalid_day`. |
| **4 · Contrato** | `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` + `apps/web/src/lib/api.ts` | Regenerado (`contract:gen`); métodos `getAutoDiaDReplayDays` / `getAutoDiaDReplay`. |
| **5 · UI** | `apps/web/src/features/auto-monitor/dia-d-auto-toolbar.tsx`, `dia-d-auto-panel.tsx`, `use-auto-dia-d-replay.ts`, `auto-monitor-page.tsx` | Toggle `Ventana actual / DÍA-D AUTO` en `/auto-monitor`; selector de fecha `max=hoy` + panel con una fila por paso (**Declarado** / **Ejecutado** / **Veredicto**) + bloque OOS + límites. Las queries DÍA-D son **perezosas** (solo se disparan al abrir la vista): el monitor de producción no paga llamadas extra. |

---

## 1. Afirmaciones falsables (con su modo de ruptura)

| # | Afirmación | Cómo se rompe (falsación) | Comando / evidencia |
|---|---|---|---|
| **C1** | Un paso con ambos lados medibles y **distintos** es `DIVERGENT`; iguales es `MATCH`; con cualquier lado sin medir es `NOT_MEASURED`. | Coercer `None` a `0` ⇒ un hueco se leería como `MATCH` contra `0`. | `test_dia_d_auto.py` (16 tests): `test_divergent_when_both_sides_differ`, `test_not_measured_when_either_side_is_missing`, `test_empty_string_is_a_gap_not_a_measurement` |
| **C2** | Un hueco **nunca** se rellena con `0`: `0` es una **medición** ("no pasó nada") y `None` un **hueco**. | Convertir el hueco en `0.0` en el builder o en el comparador. | `test_zero_is_measured_and_distinct_from_a_gap`; el panel pinta `NO MEDIDO` (`test` de UI) |
| **C3** | El veredicto global **no** esconde una divergencia real detrás de un hueco: `DIVERGENT` gana a `PARTIAL`. | Priorizar `PARTIAL` cuando hay `notMeasured > 0`. | `test_summary_prefers_divergence_over_gap` |
| **C4** | El artefacto es **determinista**: mismo estado ⇒ mismo payload byte a byte (sin reloj ni aleatoriedad). | Introducir un timestamp/ULID en el builder. | `test_artifact_is_deterministic_and_json_stable` |
| **C5** | La ruta es **fail-closed**: sin cuenta ⇒ `no_account_scope`; sin artefacto ⇒ `artifact_not_found`; día inválido ⇒ `invalid_day`. | Devolver el artefacto con scope `None` o con un día malformado. | `test_auto_dia_d_route.py` (6 tests) |
| **C6** | El CLI es **read-only** sobre la BD durable y **no toca** la ventana PAPER: las únicas lecturas son barras, sectores y hechos durables de `D`; el motor corre con stores en memoria. | Añadir un `save`/`commit` durable o reutilizar `datetime.now` como reloj del replay. | Cabecera del CLI (declara los límites) + `_configure_env` sin forzar régimen + `AUTO_ENGINE_SIM_REAL_PRICE=0`; `ReplayCursor` inyecta reloj/precio |
| **C7** | El monitor actual no se degrada: la vista DÍA-D **no** dispara queries al montarse en modo `Ventana actual`. | Consultar `getAutoDiaDReplayDays` incondicionalmente en la página. | `auto-monitor-page.test.tsx` sigue verde (solo mockea `getAutoOperationalMonitor`); `useAutoDiaDReplayDays` tiene `enabled` |

---

## 2. Verificación (re-ejecutada en el momento del sello)

| Comando | Resultado |
|---|---|
| `python -m pytest packages/py/application/tests/test_dia_d_auto.py -q` | **16 passed** |
| `python -m pytest apps/api-python/tests/test_auto_dia_d_route.py -q` | **6 passed** |
| `pnpm --filter @bolsa/web contract:gen` | `OpenAPI dumped … (215 paths, 450 schemas)` · `contract:gen OK` |
| `pnpm --filter @bolsa/web contract:check` | `contract:check OK — openapi.json y schema.d.ts coinciden con el commit.` |
| `pnpm --filter @bolsa/web typecheck` | **sin errores** (`tsc -b --noEmit`) |
| `pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/…` | **3 passed** (`dia-d-auto-panel.test.tsx` 2 · `auto-monitor-page.test.tsx` 1) |
| `pnpm window:test` | **`tests 25 · pass 25 · fail 0`** (sin regresión del runner) |
| CLI de humo (`--at 2026-09-15 --watch <4 ids> --history-days 30 --horizon-days 5`) | replay `36/36` días (`fills=18 vetoes=138 libro=COMPLETE`); artefacto `operability_runs/dia-d-auto/dia-d-auto-2026-09-15.json` (4096 B · `sha256 83E242AB81C0320B1C48DD2D31EDB27E0799075FE6A4DF74D329B11EAF5893A3`); veredicto global **`NOT_MEASURED`** (lado ejecutado sin hechos durables para un `D` histórico — el comportamiento honesto esperado) |

> **CLI de humo con barras selladas.** El `D` de humo (`2026-09-15`) se corrió sobre las barras
> congeladas de `docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson` sembradas en la PG local
> (rango `2021-09-14 … 2026-09-29`). El lado **declarado** sale medido (`SIGNAL=4`, `RISK=4`,
> `PROTECTION=1`, `FILL=0`); el **ejecutado** es `NO MEDIDO` porque la ventana PAPER no operó ese día
> (no hay hechos durables de `2026-09-15`). En cuanto la ventana PAPER opere un día `D`, la columna
> `Ejecutado` deja de ser `NO MEDIDO` **sin cambiar código**.

---

## 3. Límites declarados (lo que este sello **NO** hace)

1. **No sustituye la ventana PAPER.** El cubo de calendario sale del **reloj de pared**
   (`sim_fill_finance_context.created_at`); un replay **no** fabrica cubos durables. `≥4 días` /
   `≥2 episodios` / `≥32 ciclos` sigue **abierta**.
2. **No cierra `P3-2`/`P3-3`** ni `H-4`: es evidencia de **investigación**, clase distinta.
3. **Aproximación D1:** un día = un tick. El replay no fabrica cubos de calendario.
4. **El artefacto es hermético por CLI, no por HTTP.** El motor AUTO no corre en el proceso FastAPI
   (vive en `scheduler_worker`, env-gated): la ruta **solo sirve** el artefacto ya escrito.
5. **`AUTO_ENGINE_SIM_REAL_PRICE` se fija a `0`** en el sandbox: el precio del replay es el
   `price_script` histórico inyectado (opens reales), no una lectura en vivo. No se fuerza régimen ni
   se baja ningún umbral.
6. **La columna `Ejecutado` es `NO MEDIDO` sobre días históricos** sin hechos durables. No se
   rellena con `0`: se declara el hueco.
7. **Freeze del runner:** este sello **mueve el árbol** `apps`/`packages`; el runner de la ventana se
   **re-ancló** a los hashes del árbol sellado (`WINDOW_CONFIG.appsHash` = `91dc9e04a8b75d6124a03cb70f227846e8f3e13a`,
   `packagesHash` = `a4e30f951b49aaeebc1708d9111b614b8a5e17e5`, `commit` = `v2.88.33-beta`). El hash
   acaba de ser **exacto** al commitear esta entrega: hasta entonces `git rev-parse HEAD:apps` sigue
   dando el árbol anterior (`2237f069…`) y el runner declara `TREE_MOVED` (comportamiento correcto).
   `pnpm window:test` (25/25) **no** se ve afectado.

   > **Superado (2026-10-03):** `v2.88.33` se **absorbió** en el commit de `v2.88.34-beta` (nunca se
   > commiteó por separado), así que su árbol no existe como objeto `HEAD:apps`/`packages`. El pin **vivo**
   > del runner es el de `v2.88.34-beta` (`apps` `69bd72d8…` / `packages` `2c15ecb8…`): ver
   > [`evidence/v2.88.34/README.md`](../v2.88.34/README.md) §3.8.
   > **Re-anclado de nuevo (2026-10-03, cierre `G2`):** el pin **vivo** pasa a `apps` `71c3024c…` /
   > `packages` `21b2585b…` (`commit` = `05c429a8`) porque el cierre de `G2` tocó tests+seed bajo
   > `apps`/`packages` (`Δ motor = 0`).

---

## 4. Comandos (reproducir)

```bash
# Tests puros + ruta read-only
python -m pytest packages/py/application/tests/test_dia_d_auto.py apps/api-python/tests/test_auto_dia_d_route.py -q

# Contrato + UI
pnpm --filter @bolsa/web contract:gen
pnpm --filter @bolsa/web contract:check
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web exec vitest run src/features/auto-monitor/dia-d-auto-panel.test.tsx src/features/auto-monitor/auto-monitor-page.test.tsx

# Sandbox (read-only) sobre un día D real
uv run --no-sync python apps/api-python/scripts/v2_89_dia_d_auto_replay.py --at 2026-09-15 --json
#   -> operability_runs/dia-d-auto/dia-d-auto-2026-09-15.json

# Runner de la ventana (sin regresión)
pnpm window:test
```

---

## 5. Sello

- **Versión:** `2.11.33-beta` (base `2.11.32-beta`); **SIN migración** — Alembic head sigue `048_journal_entry_dedupe_key`.
- **Ficheros añadidos:** `packages/py/application/src/bolsa_application/dia_d_auto.py`, `packages/py/application/tests/test_dia_d_auto.py`, `apps/api-python/scripts/v2_89_dia_d_auto_replay.py`, `apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py`, `apps/api-python/tests/test_auto_dia_d_route.py`, `apps/web/src/features/auto-monitor/{dia-d-auto-toolbar.tsx,dia-d-auto-panel.tsx,use-auto-dia-d-replay.ts,dia-d-auto-panel.test.tsx}`.
- **Ficheros modificados:** `apps/api-python/src/bolsa_api/api/v1/router.py`, `apps/web/src/lib/api.ts`, `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`, `apps/web/src/features/auto-monitor/auto-monitor-page.tsx`, `package.json`, `CHANGELOG.md`, docs.
- **`Δ motor = 0`:** ningún fichero de motor (`auto_simulation_worker.py`, `auto_v2_entry.py`, `sim_durable_store.py`, `market_operability.py`, `replay_oos.py`) tocado.
- **CI DE TAG:** **PENDIENTE** — este sello **no** se ha etiquetado ni empujado desde esta sesión; no se cita ningún run de CI. La verificación local (arriba) es la que se puede afirmar. Al sellar el tag, **citar** el `Release tag CI` real y confirmar que `git rev-parse "HEAD:apps" "HEAD:packages"` devuelve `91dc9e04…` / `a4e30f95…` (freeze ya re-anclado en el runner).
