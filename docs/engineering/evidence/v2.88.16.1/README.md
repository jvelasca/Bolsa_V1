# Evidencia del sello `v2.88.16.1-beta` (`2.11.16.1-beta`)

> **Qué es este documento.** El **dossier del hotfix** `W3.1` de la serie `GRANULARIDAD-OPERATIVA`.
> No sustituye al dossier del producto (`W3`), que sigue vigente **sin cambios**:
> [`evidence/v2.88.16/README.md`](../v2.88.16/README.md). Aquí se documenta **por qué** el sello
> `v2.88.16-beta` salió rojo, **cuál es la causa raíz medida** y **cuál es el arreglo** (test-only),
> con los números de las baterías **exactas** del job `lifecycle-pg`.

---

## 1. Resumen ejecutivo

| Campo | Valor |
| --- | --- |
| Tag | **`v2.88.16.1-beta`** (anotado) |
| Versión de paquete | **`2.11.16.1-beta`** (`2.11.16-beta` → `2.11.16.1-beta`) |
| Migración | **ninguna** (Alembic head sigue en `046_fill_reference_mid`) |
| Alcance | **SÓLO** `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` (**+70 / −3**) |
| `src` tocado | **0** (la semántica de producto de `W3` no cambia) |
| Migraciones tocadas | **0** |
| Supersede | tag **`v2.88.16-beta`** (run **`36783698699`**, **ROJO** en `lifecycle-pg`) |
| Precedente del patrón | `V2.40.2` (rojo `lifecycle-pg`) → `V2.40.3` (hotfix) |

---

## 2. El rojo que este sello supersede (declarado, no heredado)

`Release tag CI` **run `36783698699`** (`ref=refs/tags/v2.88.16-beta`, HEAD `0af7af6b`):

| Job | Resultado |
| --- | --- |
| `python (ruff/imports/mypy/pytest offline)` | **VERDE** — `3166 passed, 38 skipped` |
| `lifecycle-pg (Alembic + auth + golden restart)` | **ROJO** |
| resto de jobs | verdes / `skipped` por diseño |

Fallo verbatim del step grande:

```
FAILED apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py::test_auto_scheduler_real_pg_zero_human_intervention
    AssertionError: TurnReport(decided=1, proposals=1, vetoes=1, orders=1, fills=1, opened=0, closed=0, venue='simulated')
    assert (TurnReport(...) is not None and 0 == 1)
```

`assert report_close is not None and report_close.closed == 1, report_close`

El job `python` sí encajó la predicción del dossier `W3` (**`3166` = `3142` + `24`**, mismos `38`
skips). El tag **no se reescribe**: queda rojo y lo **supersede** `v2.88.16.1-beta`.

---

## 3. Causa raíz (medida)

Este certificador A9 del **día AUTO real** (`AutoSimRuntime` + PG) **no** estaba en la lista de
rebaseline al ancla de barra de `W3` (los **8** arneses que sí se rebaselinaron fueron
`test_auto_v2_durable_pg`, `test_concurrent_auto_pg`, `test_auto_v46_concurrent`,
`test_auto_v46_crash_recovery`, `test_auto_v74_producer_pg_e2e`, `test_crash_recovery_day_process_pg`,
`test_golden_day_v2_process_pg` y `test_a9_scheduler_process_pg_zero_human`).

Sembraba un `instrument_id` **aleatorio**:

```python
instrument_id = f"inst-auto-{uuid.uuid4().hex[:10]}"
```

y confiaba en el comentario heredado de la etapa del **ancla de minuto**:

> «Un tick SELL puede quedar sin fill por la cola noisy determinista (comportamiento realista del
> venue SIM): **el motor reintenta**, no es un fallo.»

Con el ancla de **BARRA** (`W3`) el reintento **intra-barra** es **idempotente**: el mismo compromiso
reproduce el **mismo** sorteo (`fill_seed(bar_tick, symbol)`), así que un `noise_reject`/parcial **no**
se rescata re-tickeando. El libro no queda plano y el assert `closed == 1` revienta.

**Reproducción local** (mismo árbol, PG real, `AUTO_SCHEDULER_PG_REQUIRED=1`):

```
E   AssertionError: TurnReport(decided=1, proposals=1, vetoes=2, orders=0, fills=0, opened=0, closed=0, venue='simulated')
```

→ el **SELL ni se emite** (rechazo del venue en la barra). **No es defecto del motor**: es la
**semántica intencionada** de `W3` (un desenlace por barra), el mismo motivo por el que los otros
**8** arneses se rebaselinaron.

---

## 4. Arreglo (test-only, patrón de los otros 8 arneses)

En `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py`:

1. **`_filling_instrument_id(prefix)`** — barrida **pura** (sin BD, sin proceso) con el **MISMO** ancla
   temporal que el motor (`bar_tick`/`fill_seed`), sobre las barras que un run de reloj REAL puede
   atravesar (**la de ahora y la siguiente**, por si cruza la medianoche UTC):
   - **BUY** debe llenar en **≥2 tranchas** (`len(fills) >= _MIN_BUY_CHUNKS`, `_FILL_CHUNKS = 4`);
   - **SELL** debe llenar **COMPLETO** (`status == "filled"`) — propiedad del **sorteo**, **no** de la
     cantidad ⇒ garantiza libro **PLANO** sea cual sea la cantidad viva;
   - si ningún candidato cumple, el test **falla con diagnóstico propio** en vez de dejar el rojo al azar.
2. `instrument_id = _filling_instrument_id("inst-auto-")` en vez de un id aleatorio.
3. `_seed_instrument` **idempotente** (un rerun del mismo día reusa la **MISMA PK**).
4. Comentario del exit **corregido** para declarar la idempotencia intra-barra de `W3`.

---

## 5. Verificación local (baterías EXACTAS del job `lifecycle-pg`)

Gates fail-if-skipped **activos** (`LIFECYCLE_PG_REQUIRED`, `AUTO_SCHEDULER_PG_REQUIRED`,
`AUTO_V2_DURABLE_PG_REQUIRED`, `AUTO_GOLDEN_DAY_V2_PG_REQUIRED`, `AUTO_CRASH_RECOVERY_PG_REQUIRED`,
`AUTO_CONCURRENT_PG_REQUIRED`, `AUTO_HARDKILL_PG_REQUIRED`, `AUTO_CRASH_INJECT_PG_REQUIRED`,
`AUTO_MULTIPROCESS_PG_REQUIRED`, y el resto de `*_PG_REQUIRED` del job).

| Batería | Resultado |
| --- | --- |
| Step grande (`Pytest lifecycle PG + auth + golden …`, 35 ficheros) | **`166 passed in 106.49s`** (0 skipped) |
| Steps dedicados (`Golden Day 2.0` + `Crash-Recovery Day` + `Concurrent` + `HardKill` + `crash-injection` + `multiprocess`) | **`10 passed in 131.78s`** (0 skipped) |
| Certificador aislado | **`2 passed`** |

## 6. Gates de calidad

| Gate | Resultado |
| --- | --- |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **`All checks passed!`** |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **`Success: no issues found in 511 source files`** |
| `uv run lint-imports --config packages/py/.importlinter` | **`Contracts: 4 kept, 0 broken.`** |

---

## 7. Predicción de la cita POST-TAG (Encaje `ESPERADO = OBSERVADO`)

Como el código de **producto** es **idéntico** al de `v2.88.16-beta` (`Δ src = 0`), la predicción es la
misma que la del dossier `W3`:

- job `python` **`3166 passed, 38 skipped`** = los **`3142`** de `v2.88.15` + **`24`** del bundle `W3`,
  con los **mismos `38` skips** y `ruff`/`import-linter`/`mypy` con los mismos veredictos;
- job **`lifecycle-pg` VERDE** con el certificador rebaselinado.

**Se cita el run, no se hereda.**

> **PENDIENTE DE CITA.** Este documento se sella con la predicción y el encaje que cierra; la cita
> verbatim del run se añade en `main` como commit **POST-TAG** cuando el propietario publique
> `v2.88.16.1-beta` (mismo patrón que `v2.88.16`/`v2.88.15`/`v2.88.14`).

> **CITA REAL (POST-TAG, 2026-10-01) — TAG `v2.88.16.1-beta` PARCIALMENTE ROJO; lo `W3.1` se cumple, lo
> cierra `W3.2`.** `Release tag CI` run **`36785738058`** (`ref=refs/tags/v2.88.16.1-beta`):
> **10 jobs VERDES**, 1 *skip* y **2 rojos**.
> - **`lifecycle-pg` VERDE** ⇒ **el objeto de este hotfix se cumple**: el certificador A9 del día AUTO
>   vuelve a ser ejecutable con el ancla de barra (era el rojo de `v2.88.16-beta`).
> - **`python` VERDE** con **`3166 passed, 38 skipped`** ⇒ **`ESPERADO = OBSERVADO`** (`Δ = 0`).
> - **`replay-repro` ROJO** (y **`certify`** en cascada): el job congela **byte a byte** un artefacto del
>   replay OOS cuya referencia nació en **`v2.88.7`** (**anterior** a `W3`), y el replay conduce el
>   **`AutoSimulationWorker` real** ⇒ `W3` lo movió **por construcción**. **No es de este hotfix**
>   (`Δ src = 0`), pero **hace que el tag como tal sea ROJO**.
> - **Verdes:** `frontend`, `shared`, `decision-spine`, `a7-gate`, `security`, `playwright (mock)`,
>   `dr-verify`.
>
> ⇒ El tag **`v2.88.16.1-beta` NO se reescribe** y lo **supersede** **`v2.88.16.2-beta`**, que re-apunta
> el artefacto OOS con la causa **aislada por ablación** (el ancla del fill) y declara el delta con su
> **banda**: [`evidence/v2.88.16.2/README.md`](../v2.88.16.2/README.md).

---

## 8. Deudas que este sello NO cierra

Ni abre. Siguen **ABIERTAS**: `OBS-19` (causa estructural de las listas pytest manuales), `OBS-15`,
`OBS-16`, `P3-2`/`P3-3`, `OBS-22`, `OBS-14.b`, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`, `P3-5`, `OBS-5`.
`OBS-21`/`OBS-23` siguen **CERRADAS**.

**Nota de honestidad:** este hotfix **no** acredita `W3` más allá de lo que ya acreditaba su dossier;
lo único que corrige es que la **certificación PG del día AUTO** vuelva a ser ejecutable (y verde) con
el ancla de barra. El producto sellado sigue siendo el de `v2.88.16-beta`.

---

## 9. Ficheros del sello

| Ruta | Cambio |
| --- | --- |
| `apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py` | `+70 / −3` — `_filling_instrument_id` + alta idempotente + comentario |
| `package.json` | bump `2.11.16-beta` → `2.11.16.1-beta` |
| `CHANGELOG.md` | bloque `[2.11.16.1-beta]` |
| `docs/engineering/PROJECT_STATE.md` | SELLO `V2.88.16.1` + cita real (rojo) del `v2.88.16` + relevo vivo |
| `docs/engineering/engineering-index-2026-08-03.md` | entrada `205` |
| `docs/engineering/evidence/v2.88.16.1/README.md` | este documento (**nuevo**) |
