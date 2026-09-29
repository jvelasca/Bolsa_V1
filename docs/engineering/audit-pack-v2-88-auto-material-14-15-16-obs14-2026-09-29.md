# Audit-pack — `AUTO-MATERIAL-14/15/16` / `V2.88` — SELLO CONJUNTO: cierre de `OBS-14` (reconciliación al cierre de turno) + `v2.86` + `v2.87` + `OBS-15`

> **[OBJETO VIGENTE — RE-SELLO `v2.88.2-beta`, 2026-09-29.]** Los tags `v2.88-beta` y `v2.88.1-beta` del
> que habla este pack quedaron **públicos con `Release tag CI` en ROJO** (`lifecycle-pg`): primero el
> cierre de turno del `OBS-14` **re-liberaba fills ya liberados** y **drenaba la cola viva** de las
> órdenes parcialmente llenadas (fail-**OPEN**); y, tras la guarda `attribute_fills`, el mismo cierre
> **liberaba la reserva VIVA de otra sesión** en una carrera concurrente (fail-**OPEN**). El objeto a
> auditar es ahora el tag anotado **`v2.88.2-beta`** (**Versión `2.11.2-beta`**), que incluye la guarda
> `attribute_fills` **y** el **alcance por PROPIEDAD** (`only_ids`) del cierre de turno, más la costura
> del replay alineada. El resto de este pack se conserva **verbatim** y sigue siendo válido para
> `v2.86`/`v2.87`/`OBS-14`/`OBS-15`; para el delta de las correcciones, ver
> [obs-14-correccion-fail-open-v2.88.1-2026-09-29.md](./obs-14-correccion-fail-open-v2.88.1-2026-09-29.md),
> [obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md](./obs-14b-carrera-entre-sesiones-v2.88.2-2026-09-29.md)
> y [evidence/v2.88.1/README.md](./evidence/v2.88.1/README.md) +
> [evidence/v2.88.2/README.md](./evidence/v2.88.2/README.md) (con los dos rojos conservados).
>
> **Deuda nueva declarada — `OBS-14.b` (MEDIUM):** el barrido de **ARRANQUE** sigue siendo global y
> tampoco distingue una reserva huérfana de una reserva **viva de otra sesión a mitad de turno**
> (reinicio rodante con otro motor operando). Ya era así en `v2.85.2`; el arreglo acordado es de
> **alcance** (cierre de turno). Discriminador posible, **no** implementado: ventana de gracia por EDAD.

> **Objeto a auditar:** tag anotado **`v2.88-beta`** (lo crea el propietario) · **Versión:** `2.11.0-beta`
> (**bump** `2.10.2-beta → 2.11.0-beta`) · **Base del diff:** `v2.85.2-beta` (commit base **`3483b6b5`**)
> · **AsOf:** 2026-09-29 · **Alembic head:** `046_fill_reference_mid` (**SIN migración**) · **Remote:**
> `github.com/jvelasca/Bolsa_V1.git`.
> **Sello conjunto:** el tag sella **tres** incrementos ya implementados y **sin commitear** — `v2.86`
> (`AUTO-MATERIAL-14`), `v2.87` (`AUTO-MATERIAL-15`) y el cierre de `OBS-14` (`AUTO-MATERIAL-16`).

## 1. Qué es esta fase

Fase que **sella conjuntamente** tres incrementos y **cierra** la observación **`OBS-14`** (MEDIUM,
alcance motor) de la auditoría interna de `v2.87`, además de **abrir** `OBS-15` (MEDIUM, alcance motor).

- **`v2.86` / `v2.87`** (instrumento de investigación) viajan **verbatim**: módulo puro
  `bolsa_application.replay_oos`, los CLI `v2_86_replay_oos_viability.py` y
  `v2_87_replay_oos_durable_cycle.py`, sus tests y su evidencia. Ver
  [`replay-oos-viabilidad-auto-v2.86-2026-09-29.md`](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md)
  y [`replay-oos-ciclo-durable-v2.87-2026-09-29.md`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md).
- **El cierre de `OBS-14`** es el **único cambio de motor** de la fase: **+7 / -0**, **un solo hunk**
  (líneas 4937-4943) en `real_turn`, justo después de `report = await self.auto_turn()` y antes de
  `if auto_store is not None:`; la línea añadida es
  `await self._v2_reconcile_reservations(startup=False)`.
- **Dos defectos extra corregidos:** (1) 6 documentos afirmaban `2.11.0-beta`, que **nunca existió**
  (7 ocurrencias corregidas); (2) **7 errores `I001`** que habrían hecho fallar el job `quality` de CI
  (los ficheros de `v2.86`/`v2.87` nunca se commitearon, así que nunca se lintaron con la config de raíz).

**No** se cambia el gobernador (`aggregate_trial_regime`), `operability_window.py`,
`v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI ni migraciones. La migración
**no se mueve** (Alembic head `046_fill_reference_mid`).

## 2. Diff esperado (acotado)

- `package.json` (`2.10.2-beta → 2.11.0-beta`).
- `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (**+7 / -0**, un hunk, `real_turn`).
- `apps/api-python/tests/test_auto_v2_durable_cycle.py` (7 → **11**: +4 tests de `OBS-14`).
- `apps/api-python/tests/test_replay_oos_cli_renderers.py` (**+3** tests, arreglo del hallazgo de Bugbot).
- `apps/api-python/scripts/v2_86_replay_oos_viability.py` (arreglo de `_print_census`).
- `apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py` y
  `apps/api-python/scripts/v2_44_mutation_audit.py` (**+`M245`**, **+`M246`**; matriz **246**).
- `packages/py/application/src/bolsa_application/replay_oos.py` + sus tests (`test_replay_oos.py` **18**,
  `test_replay_oos_durable_cycle.py` **29**).
- `docs/engineering/*` (audit-pack, arranque del auditor, informe/relevo, `evidence/v2.86`, `evidence/v2.87`,
  `evidence/v2.88`, `PROJECT_STATE`, índice, deuda P3) + `CHANGELOG.md`.

### 2.1 Anexo declarado (fuera de las tesis falsables de §3)

La nota de **contexto POSTERIOR** en los informes y evidencias de `v2.86`/`v2.87` (que declara que estas
fases viajan dentro del tag `v2.88-beta` y que su «SIN tag» describe el **estado al autorarlas**) se añade
**sin reescribir** el texto sellado: se conserva **verbatim** y la nota va aparte (patrón ya usado en el repo).

**Ficheros PROHIBIDOS en el diff** (si aparecen, la fase se sale de alcance): el gobernador
`aggregate_trial_regime`, `operability_window.py`, `v2_80_market_window.py`, cualquier `alembic/` o
migración, `apps/web/**`, y cualquier cambio de `TOP_N`/umbrales/allocation/pesos. En el motor, **solo**
se admite el hunk `+7 / -0` de `real_turn`: **no** se admite ningún cambio en `auto_turn` ni en el interior
de `_v2_reconcile_reservations` ni en la regla de retirada.

## 3. Tesis falsables (lo que el auditor debe intentar **romper**)

1. **`OBS-14` cerrado por la ruta (a):** la retirada de una reserva muerta ocurre al **cierre de turno**
   en el camino durable (`real_turn`), con `startup=False`, y con etiqueta
   **`RESERVATION_RELEASED_BY_CANCEL`** (no `..._BY_RESTART`). (Regresión: **`M246`**.)
2. **El cierre es fiel y no degrada:** la reserva **no** se retira si su orden está **en vuelo** o si su
   fill está **capturado y no aplicado** (guarda `instrument not in in_flight`); el test de **control**
   reproduce el goteo previo. (`test_closing_reconcile_keeps_captured_unapplied_capital_in_flight`,
   `test_control_without_tick_close_reproduces_the_drip`.)
3. **`auto_turn` y los umbrales intactos:** `git diff --numstat` del motor = **`7  0`**; ningún cambio fuera
   del hunk 4937-4943; ninguna migración (Alembic head `046_fill_reference_mid`).
4. **El arreglo del hallazgo de Bugbot es real:** `_print_census` consume el **`dict`** que `main` pasa
   (`evidence["census"] = census.to_dict()`); los renderers de `v2.86` y `v2.87` **coinciden** con el mismo
   payload. (Regresión: **`M245`**; llave: `test_both_renderers_agree_on_the_same_payload`.)
5. **El silencio del defecto queda fijado:** el `--out` JSON se escribe **antes** del render, así que el
   artefacto sobrevivía; el test es de **contrato** (no se puede leer atributos de un `dict`), no de formato.
6. **Los dos defectos extra, corregidos:** ningún documento dice ya `2.11.0-beta` salvo donde el **sello**
   lo acuña; el comando **exacto** de CI `uv run ruff check packages/py apps/api-python --config pyproject.toml`
   pasa (y **no** se confunde con `ruff` por fichero **sin** `--config`, que descubre la config anidada).
7. **`OBS-15` (nueva, MEDIUM, alcance motor) está declarada, no cerrada:** el techo de **1000 filas
   `APPLIED`** puede parar el motor; **pre-existente**; la madurez de la cuenta real está **NO MEDIDA**
   (sonda read-only **bloqueada** por la revisión automática). Intenta refutar que sea preexistente o que
   el disparador sea `>=1000` filas `status='APPLIED'`.
8. **Compuertas verdes y reproducibles** (§4).
9. **Sin cierre de deuda por documentación:** `P3-2`/`P3-3`/`OBS-15`/`OBS-13`/`OBS-11`/`H-4`/`OBS-9`/`P3-5`/`OBS-5`
   siguen **ABIERTOS**; **`OBS-14`** es lo único que se **cierra**, y se cierra **con código + tests + mutación**.

## 4. Compuertas medidas (números exactos)

```powershell
uv run ruff check packages/py apps/api-python --config pyproject.toml   # All checks passed! (exit 0)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py # matriz 246 (eran 239 en v2.85.2)
git diff --numstat -- apps/api-python/src/bolsa_api/background/auto_simulation_worker.py  # 7  0
```

Grabaciones:

```
guardarraíles (10 suites)                    142 passed
test_auto_v2_durable_cycle.py                 11 passed (7 -> 11)
test_replay_oos.py                            18 passed
test_replay_oos_durable_cycle.py              29 passed
test_replay_oos_cli_renderers.py               3 passed
M245 / M246                                   3/3 y 3/3 muerden, árbol restaurado byte a byte
matriz de mutaciones                          246 total
```

Titulares del instrumento que sella el tag (leídos de
[`evidence/v2.87/README.md`](./evidence/v2.87/README.md), no recalculados): **1224 ticks**, **210 órdenes /
752 fills / 62 ciclos**, reservas vivas máx **1** y final **0**, `horizon.completed=true`; control
`--no-durable-cycle` **31 / 118 / 13**, máximas vivas **15**, `finalReservedRisk` **5 999.9998**,
`risk_budget_exceeded` **1 400** frente a **11**.

**Evidencia cruda del cierre:** [`evidence/v2.88/README.md`](./evidence/v2.88/README.md).

## 5. Límites declarados (honestidad)

- **`OBS-15` (MEDIUM, alcance motor) ABIERTA, no arreglada aquí.** El techo de **1000 filas `APPLIED`**
  (`DEFAULT_APPLIED_LIMIT`) puede **parar el motor**: `truncated = len(events) >= limit` ⇒
  `MEASUREMENT_UNKNOWN` ⇒ la reconciliación **no puede** ser COMPLETE y el motor **veta aperturas**.
  **Preexistente** (la reconciliación de arranque lee idénticamente) y **no** introducido por `OBS-14`.
  Radio: afecta también a la reconstrucción de **posición** (`read_position_ledger`). **Madurez de la
  cuenta real: NO MEDIDA** (sonda read-only **bloqueada** por la revisión automática). La retención de
  **900** de `v2.87` es una mitigación **interna al instrumento**, **no** existe en producción.
- **NO** cierra `P3-2`/`P3-3` (ventana PAPER **real** ≥4 días **con material**): el sello no mide ventana.
- **NO** afirma edge: no cambia ninguna cifra del material real; cierra una **parada de apertura** del motor.
- **`mypy` / `lint-imports` de esta fase: NO MEDIDO** (no citados en el paquete de verificación del sello).
- **Sello pendiente, con motivo.** El tag anotado **`v2.88-beta`** y su **cita de CI** los crea el
  propietario: `Release tag CI` **solo corre al empujar**, así que su resultado es **POST-TAG** por
  construcción (patrón `OBS-3`/`OBS-4`). **No** se cita aquí ningún `run`: **`(pendiente)`** hasta que
  exista el tag.
- **Paso 4 parcial:** la actualización de registros (`PROJECT_STATE`, índice, deuda P3) se hace en esta
  fase; cualquier re-sello/tag es **decisión del propietario**.

Referencias: [informe/relevo del cierre](./obs-14-cierre-por-turno-v2.88-2026-09-29.md) ·
[arranque del auditor](./arranque-auditor-v2-88-auto-material-16-obs14-2026-09-29.md) ·
[evidencia cruda `v2.88`](./evidence/v2.88/README.md) ·
[`v2.86`](./replay-oos-viabilidad-auto-v2.86-2026-09-29.md) ·
[`v2.87`](./replay-oos-ciclo-durable-v2.87-2026-09-29.md) ·
[deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) ·
[índice](./engineering-index-2026-08-03.md) ·
[audit-pack de la fase anterior `v2.85`](./audit-pack-v2-85-auto-material-13-obs10-comportamiento-2026-09-28.md).
