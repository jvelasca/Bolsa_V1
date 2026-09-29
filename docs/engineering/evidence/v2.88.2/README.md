# Evidencia cruda — Corrección fail-OPEN de CARRERA en el cierre de turno (`v2.88.2`, 2026-09-29)

Resumen **verificable** del RE-SELLO que sustituye a `v2.88.1-beta`. Conserva el **rojo original** de
`v2.88.1-beta` (no se borra: es parte de la evidencia), la traza del diagnóstico y la validación de la
corrección. Las cifras están transcritas de las corridas, sin edición.

## Identidad del sello

| | |
| --- | --- |
| Fase | `AUTO-MATERIAL-16b` (`v2.88.2`) — corrección fail-OPEN de CARRERA del cierre de turno |
| Versión de paquete | `2.11.1-beta` → **`2.11.2-beta`** |
| Tag (lo crea el propietario) | **`v2.88.2-beta`** (anotado) |
| Tags SUPERADOS | **`v2.88-beta`** (rojo: crash/recovery) y **`v2.88.1-beta`** (rojo: carrera concurrente) |
| Base del diff | **`dd8a16a5`** (= `v2.88.1-beta`) |
| Alembic head | **`046_fill_reference_mid`** (**SIN migración**) |
| Diff de la corrección | **4 ficheros, +212 / −15** (sin contar este informe ni la evidencia) |

## 1. El rojo que motiva este RE-SELLO (`v2.88.1-beta` = `dd8a16a5`)

`Release tag CI` run `36548125321`
(`https://github.com/jvelasca/Bolsa_V1/actions/runs/36548125321`):

| Job | Resultado |
| --- | --- |
| shared / frontend / playwright (mock) / decision-spine / security | success |
| **python (ruff/imports/mypy/pytest offline)** | **success** |
| dr-verify | success |
| **lifecycle-pg (Alembic + auth + golden restart)** | **failure** |

Pasos del job `lifecycle-pg` (conclusiones reales):

| Paso | Resultado |
| --- | --- |
| Alembic upgrade head · Pytest lifecycle PG + auth + golden V1.88–V1.96 | success |
| Prepare dedicated iso scratch DB · Pytest account-isolation gate V2.15.4 | success |
| **Pytest Golden Day 2.0 (proceso scheduler V2 + PG)** | **success** |
| **Pytest Crash/Recovery Day (proceso matado en sucio + PG)** | **success** ← la guarda `attribute_fills` de `v2.88.1` funcionó |
| **Pytest Concurrent AUTO (3 sesiones concurrentes + PG)** | **FAILURE** |
| Fail on skipped Concurrent AUTO | success |
| Pytest HardKill · crash injection matrix · multiprocess AUTO | **skipped** (saltados por el fallo previo) |
| Fail on skipped HardKill / crash injection / multiprocess | failure (logs vacíos ⇒ "certificación no válida") |

Aserto exacto del fallo:

```
apps/api-python/tests/test_concurrent_auto_pg.py:326: in test_concurrent_auto_n_sessions_claim_one_signal_pg
    assert released == held, (
E   AssertionError: lo liberado por fill debe ser exactamente lo materializado:
                   released=200.000000 materializado=147.000000
E   assert Decimal('200.000000') == Decimal('147.000000')
3 failed in 2.18s
```

### 1.b El mismo defecto en `v2.88-beta` estaba ENMASCARADO

En `Release tag CI` run `36544461660` (`v2.88-beta`), el paso de Concurrent AUTO figura como **skipped**
(el job murió antes en crash/recovery): no hay ninguna corrida que certifique que aquel tag lo pasaba.

## 2. Diagnóstico (traza del punto único de liberación)

Instrumentación **temporal** de `reservation_store._release` y de los dos puntos de decisión (retirada
después: `git diff` limpio, sin residuos de `DEBUG-TEMP`):

```
[RECON]  worker=…354656 startup=False attr=False measurable=True in_flight=[] facts=[]
         live=[('RES-dec-d37b52','inst-v46conc-0000000063','buy','200.0','2026-09-29T09:28:57+00:00')]
[RULE]   id=RES-dec-d37b52 key=('inst-v46conc-0000000063','buy') created=2026-09-29 09:28:57+00:00
         filled=0.0 available=0.0 fill_qty=0.0 remain=200.0 attr=False measurable=True
[RELEASE] id=RES-dec-d37b52ff59bb status=RELEASED_BY_CANCEL reason=cancel delta=None remain_before=200.0
          stack=release<_v2_release_reservation<_v2_reconcile_reservations<real_turn<run_tick<_run
[HOTFILL] worker=…575904 symbol=inst-v46conc-0000000063 qty=147.000000 side=buy
          book=[('RES-dec-d37b52','inst-v46conc-0000000063','buy','200.0',True)]
```

Lectura: **una sola** liberación, `CANCEL` total (`remain_before=200.0`) desde el **cierre de turno** de
la sesión **perdedora**; el fill del **ganador** llega después y su `store.release` no encuentra fila viva.
`facts=[]` y `in_flight=[]` con `measurable=True` ⇒ la regla 2 ve «orden muerta sin llenar».

## 3. Prueba de causalidad (A/B en el mismo árbol)

| Experimento | Resultado |
| --- | --- |
| Cierre con `attribute_fills=False` (`v2.88.1`) | **3 failed** — `released=200.000000` vs `materializado=147.000000` |
| `git checkout HEAD~1 -- …/auto_simulation_worker.py` (cierre `v2.88-beta`, regla 1 activa) | **3 failed** — **idénticos** (`200` vs `147`) |
| Tras el acotado por propiedad (este sello) | **7 passed** |

## 4. Validación tras la corrección

| Medición | Comando | Resultado |
| --- | --- | --- |
| Carrera entre sesiones | `pytest apps/api-python/tests/test_concurrent_auto_pg.py` | **7 passed** |
| Ciclo durable + costura | `pytest apps/api-python/tests/test_auto_v2_durable_cycle.py` | **14 passed** |
| Instrumento | `pytest packages/py/application/tests/test_replay_oos.py` | **14 passed** |
| Vecinos del motor | crash/recovery PG + partial fills + worker integration + lifecycle PG | **49 passed** |
| Pasos SALTADOS en CI (1ª vez) | HardKill + crash injection matrix + multiprocess PG | **5 passed** |
| Estilo | `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| Mutaciones `M249`–`M251` | `python apps/api-python/scripts/v2_44_mutation_audit.py --only M249 M250 M251` | **3/3 detectadas**, árbol intacto |
| **Matriz COMPLETA** (tras el re-anclaje) | `python apps/api-python/scripts/v2_44_mutation_audit.py` | **`251/251` medidas**, ninguna sin fragmento · árbol **intacto** · `exit 0` |

### 4.b RE-ANCLAJE de 4 mutaciones previas (trazabilidad, no maquillaje)

Este sello cambió **el texto exacto** que cuatro mutaciones anteriores anclaban (el cierre de turno pasó
de una llamada de una línea a una llamada multilínea con `only_ids`, tanto en el motor como en la costura
del replay). Una primera corrida de la **matriz completa** terminó en **ROJO** por eso, con cuatro
etiquetas declaradas **sin medir**:

```
  !! mutaciones SIN medir (fragmento ausente): M240 …, M246 …, M247 …, M248 …
  La matriz no puede afirmar cobertura sobre esas etiquetas: sonda en ROJO.
```

Se **re-anclaron** al código nuevo —**sin cambiarles la semántica**—, conservando su intención original:

| Mutación | Intención (intacta) | Fragmento nuevo (resumen) |
| --- | --- | --- |
| `M240` | el cierre de tick del replay deja de retirar la huérfana | retira la llamada multilínea completa de `close_tick` |
| `M246` | el motor deja de retirar la reserva muerta al cerrar el turno | `…only_ids=…` → `pass` |
| `M247` | el cierre de turno vuelve a repartir el histórico (drena la cola viva) | `attribute_fills=False` → `True` **en el cierre de turno** |
| `M248` | la costura del replay vuelve a repartir el histórico | `attribute_fills=False` → `True` **en `close_tick`** |

Certificado del re-anclaje (salida transcrita, exit `0`):

```
$ python apps/api-python/scripts/v2_44_mutation_audit.py --only M240 M246 M247 M248
### M240 …  rojo en: test_book_does_not_drip_over_n_ticks_when_the_cycle_is_durable,
                    test_close_tick_does_not_re_attribute_fills,
                    test_orphan_reservation_is_released_as_cancel_at_tick_close
### M246 …  rojo en: test_closing_reconcile_does_not_touch_another_sessions_reservation,
                    test_closing_reconcile_keeps_captured_unapplied_capital_in_flight,
                    test_real_turn_releases_the_orphan_reservation_at_the_end_of_the_same_turn,
                    test_two_real_turns_do_not_drip_the_book_between_them
### M247 …  rojo en: test_closing_reconcile_keeps_the_live_tail_of_a_partially_filled_order
### M248 …  rojo en: test_close_tick_does_not_re_attribute_fills
  restaurado byte a byte: si (las cuatro)
  medidas: 4/4 (ninguna se quedo sin fragmento)
```

Certificado de la **matriz completa** con las cuatro ya re-ancladas (salida transcrita, `exit 0`,
`742 886 ms`):

```
=== huella del arbol ===
  intacto: la sonda no altero el arbol
  medidas: 251/251 (ninguna se quedo sin fragmento)
```


Salida del arnés (transcrita):

```
=== linea base (sin mutacion) ===
  apps/api-python/tests/test_auto_v2_durable_cycle.py -> ninguno
### M249 (cierre sin propiedad): …
  rojo en: test_closing_reconcile_does_not_touch_another_sessions_reservation
### M250 (arranque acotado por propiedad): …
  rojo en: test_closing_reconcile_does_not_touch_another_sessions_reservation
### M251 (costura sin propiedad): …
  rojo en: test_close_tick_does_not_re_attribute_fills
  medidas: 3/3 (ninguna se quedo sin fragmento)
```

## 5. Contenido del diff (4 ficheros, +212 / −15)

| Fichero | Cambio |
| --- | --- |
| `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` | `only_ids` en la firma + `_v2_owned_reservations` + alta de propiedad en `_v2_persist_tick_reservations` y `_v2_reserve_exit` + poda al final de la reconciliación + cierre de turno con `only_ids=frozenset(self._v2_owned_reservations)` + docstrings |
| `packages/py/application/src/bolsa_application/replay_oos.py` | `close_tick` pasa `only_ids` del worker (fidelidad motor↔instrumento) + docstring |
| `apps/api-python/tests/test_auto_v2_durable_cycle.py` | `test_closing_reconcile_does_not_touch_another_sessions_reservation` + propiedad explícita en los tests de las guardas `in_flight`/`filled` + dobles con la firma nueva |
| `apps/api-python/scripts/v2_44_mutation_audit.py` | `M249` + `M250` + `M251` (matriz `248` → `251`) + **re-anclaje** de `M240`/`M246`/`M247`/`M248` al texto nuevo (sin cambiar su semántica) |

## 6. Límite declarado (no se maquilla)

- **`OBS-14.b` (deuda nueva, MEDIUM):** el barrido de **ARRANQUE** sigue siendo global y tampoco distingue
  una huérfana de una reserva **viva de otra sesión a mitad de turno** (reinicio rodante con otro motor
  operando). Precedente: ya era así en `v2.85.2`; el arreglo acordado es de **alcance** (cierre de turno).
  Discriminador posible, no implementado: **ventana de gracia por EDAD**. El test
  `test_closing_reconcile_does_not_touch_another_sessions_reservation` **caracteriza** ese barrido (lo
  fija como comportamiento conocido), no lo aprueba.
- El artefacto multianual de `v2.86`/`v2.87` sigue **exigiendo RE-EJECUCIÓN** (medido con la costura previa
  a `attribute_fills=False`): no se usa como evidencia de estrategia ni para mover `P3-2`/`P3-3`.
- `mypy` **NO MEDIDO en local** (Windows Application Control bloquea `mypy.main` y `uvx`): lo mide el job
  `python (ruff/imports/mypy/pytest offline)` del CI del tag.

## 7. CI del objeto vigente (`v2.88.2-beta`)

<!-- PENDIENTE-TAG: se rellena en el commit POST-TAG con las URLs y conclusiones del CI del tag vigente. -->

Pendiente de medir: se publica en cuanto el tag `v2.88.2-beta` dispare `Release tag CI`.
