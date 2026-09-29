# Evidencia cruda — Cierre del ciclo de reservas al cierre de turno (`v2.88`, 2026-09-29)

> **[SUPERADO — RE-SELLO `v2.88.1-beta`, 2026-09-29.]** El tag `v2.88-beta` quedó **rojo** en
> `lifecycle-pg` (fail-**OPEN** del cierre de turno). La evidencia vigente —con el rojo conservado, la
> prueba de causalidad y la corrección— está en
> [evidence/v2.88.1/README.md](../v2.88.1/README.md) y en
> [obs-14-correccion-fail-open-v2.88.1-2026-09-29.md](../../obs-14-correccion-fail-open-v2.88.1-2026-09-29.md).
> El texto sellado se conserva **verbatim**; esta nota es la única adición.

Resumen **verificable** del sello conjunto. El código de `v2.86`/`v2.87` **nunca se commiteó**; este
sello lo entrega junto con el cierre de motor de `OBS-14`. Las cifras son las que el árbol de trabajo
contiene, transcritas sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-16` (`v2.88`) — sello conjunto de `v2.86` + `v2.87` + cierre de `OBS-14` |
| Versión de paquete | `2.10.2-beta` → **`2.11.0-beta`** |
| Tag (lo crea el propietario) | **`v2.88-beta`** (anotado) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Base (HEAD antes del sello) | **`3483b6b5`** |
| Tag anterior | **`v2.85.2-beta`** |
| Fecha | 2026-09-29 (UTC) |
| Remote | `github.com/jvelasca/Bolsa_V1.git` |

## Diff del motor (hunk único)

`apps/api-python/src/bolsa_api/background/auto_simulation_worker.py`: **+7 / -0**, **un solo hunk**
(líneas **4937-4943**), en `real_turn`, **después** de `report = await self.auto_turn()` y **antes** de
`if auto_store is not None:`.

```diff
+            # OBS-14 — CIERRE del ciclo de reservas del turno: retira las reservas MUERTAS
+            # (la orden no llegó a materializarse dentro del tick) sobre la MISMA sesión del
+            # turno, sin reiniciar. ``startup=False`` porque la reserva no murió por un
+            # reinicio sino porque su orden no se materializó (``RESERVATION_RELEASED_BY_CANCEL``).
+            # Es el análogo de lo que el instrumento ``v2.87`` hace en su ``close_tick``; corre
+            # en CADA turno, no solo en la reconciliación de arranque.
+            await self._v2_reconcile_reservations(startup=False)
```

`git diff --numstat` del motor:

```
7	0	apps/api-python/src/bolsa_api/background/auto_simulation_worker.py
```

**NO** se tocó `auto_turn`, ni el interior de `_v2_reconcile_reservations`, ni la regla de retirada, ni
ningún umbral.

## Tests nuevos (nombres exactos)

`apps/api-python/tests/test_auto_v2_durable_cycle.py` (la suite pasa de **7 a 11**):

```
test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn
test_two_real_turns_do_not_drip_the_book_between_them
test_control_without_tick_close_reproduces_the_drip
test_closing_reconcile_keeps_captured_unapplied_capital_in_flight
```

`apps/api-python/tests/test_replay_oos_cli_renderers.py` (**3 tests**, arreglo del hallazgo de Bugbot):

```
test_v86_census_renderer_accepts_the_dict_that_main_passes
test_v86_census_renderer_declares_an_empty_sample
test_both_renderers_agree_on_the_same_payload
```

## Matriz de mutaciones

```
matriz total                                             246 (eran 239 al sellar v2.85.2)
M245 (render contra el dataclass)                        3/3 muerden, árbol restaurado byte a byte
M246 (cierre de turno revertido)                         3/3 muerden, árbol restaurado byte a byte
```

## Compuertas medidas

```
guardarraíles (10 suites)                                142 passed
ruff check packages/py apps/api-python --config pyproject.toml   All checks passed! (exit 0)
test_auto_v2_durable_cycle.py                            11 passed (7 -> 11)
test_replay_oos.py                                       18 passed
test_replay_oos_durable_cycle.py                         29 passed
test_replay_oos_cli_renderers.py                          3 passed
mypy / lint-imports                                       NO MEDIDO (no citados en el paquete de la fase)
```

## Defectos hallados en la revisión interna (Bugbot + Security review)

| # | Origen | Severidad | Fichero:línea | Defecto | Cierre |
| --- | --- | --- | --- | --- | --- |
| 1 | Bugbot | **medium** | `apps/api-python/scripts/v2_86_replay_oos_viability.py:448` | `_print_census` escrito contra `CensusReport` (atributos) pero `main` le pasa `evidence["census"]` = `census.to_dict()` (`dict`). Modo **texto** sin `--json` reventaba con `AttributeError: 'dict' object has no attribute 'watch'`. **Silencioso**: el `--out` se escribe **antes** del render. | `_print_census` consume el **`dict`** (renderer idéntico al de `v2.87`); 3 tests renderers; **`M245`** 3/3 |
| 2 | Security review | — | — | **Sin hallazgos**: el cambio no cruza fronteras de auth/tenant/privilegio/secretos/filesystem; único sumidero de escritura `Path(args.out).write_text(...)` con la ruta que teclea el operador; lecturas de BD read-only y parametrizadas; stores de la simulación en memoria (cero escrituras PG). | — |
| 3 | Coordinación | — | 6 documentos | **Versión inexistente**: 6 documentos afirmaban `2.11.0-beta`, que **nunca existió** (`package.json`, `CHANGELOG.md` y toda la historia de git dicen `2.10.2-beta`). | Corregidas **7 ocurrencias** (ver abajo) |
| 4 | Coordinación | — | ficheros de `v2.86`/`v2.87` | **7 errores `I001`** que habrían hecho fallar el job `quality` de CI (nunca se lintaron con la config de raíz). | Comando **exacto** de CI pasa |

Correcciones de la fila 3 — **7 ocurrencias** en:
`docs/engineering/PROJECT_STATE.md`, `docs/engineering/engineering-index-2026-08-03.md`,
`docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md`,
`docs/engineering/evidence/v2.86/README.md`, `docs/engineering/evidence/v2.87/README.md`,
`docs/engineering/replay-oos-viabilidad-auto-v2.86-2026-09-29.md` y
`docs/engineering/replay-oos-ciclo-durable-v2.87-2026-09-29.md`.

Nota de la fila 4: el comando **exacto** de CI es
`uv run ruff check packages/py apps/api-python --config pyproject.toml`. Invocar `ruff` **por fichero**
**sin** `--config` descubre la config anidada `apps/api-python/pyproject.toml` y da un resultado **distinto**.

## Declarado NO MEDIDO

- **Madurez de la cuenta real frente a `OBS-15`** (filas `APPLIED` acumuladas): **NO MEDIDA**. Una sonda
  read-only fue **bloqueada por la revisión automática**; no se estima.
- **`mypy` / `lint-imports`** de esta fase: **NO MEDIDO** (no citados en el paquete de verificación del sello).
- **Ventana PAPER real** (`P3-2`/`P3-3`): **NO MEDIDA** en esta fase; el sello **no** la sustituye.

## Deuda abierta tras el sello

`P3-2`, `P3-3`, **`OBS-15` (nueva, MEDIUM, alcance motor)**, `OBS-13`, `OBS-11`, `H-4`, `OBS-9`,
`P3-5`, `OBS-5`. **`OBS-14` CERRADA** por la ruta (a) de su criterio de cierre.

## Límite de esta evidencia

**NO** acredita `P3-2`/`P3-3` ni sustituye una ventana PAPER real. La evidencia de **operación** sigue
siendo la de `v2.86`/`v2.87` (reloj **simulado**, cuarentena en memoria), cuyos titulares se conservan
en [`../v2.86/README.md`](../v2.86/README.md) y [`../v2.87/README.md`](../v2.87/README.md). Esta entrega
acredita un **cierre de motor** (hunk + tests + mutaciones) y su **sello documental**.
