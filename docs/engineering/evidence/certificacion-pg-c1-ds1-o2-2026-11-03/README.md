# Certificación PostgreSQL de C-1, DS-1 y O-2 (auditoría 2.88.179)

**Fecha:** 2026-11-03
**Alcance:** cierre de las seis condiciones de integración que el dictamen exigía antes de sellar el bloque de concurrencia/atribución. Solo se marca verde lo que se ejecutó contra PostgreSQL real; ningún `skipped` cuenta como prueba superada.

## Entorno de la corrida

| Dato | Valor |
| --- | --- |
| Intérprete | `.venv\Scripts\python.exe` — Python 3.12.13 |
| Driver | `psycopg` 3.3.4 (binario, con `libpq`) |
| Servidor | PostgreSQL 16.14 en `127.0.0.1:5432`, base `bolsa_v1` |
| Head de esquema | `062_sync_settings_check_backfill` |
| SO | Windows 10.0.26200 (`WindowsSelectorEventLoopPolicy`) |

> **Nota de entorno (afecta a los tiempos, no al resultado).** En esta máquina, conectar a
> `localhost` cuesta **30,0 s por conexión** (resolución de nombre), mientras que `127.0.0.1`
> tarda **0,016 s**. Todas las corridas de esta evidencia se hicieron con
> `DATABASE_URL=postgresql://bolsa:bolsa_dev@127.0.0.1:5432/bolsa_v1`. Con `localhost` las suites
> PG parecen colgadas sin estarlo; no es un defecto del código ni de los tests.
> *(Corrección 2026-11-03: al re-medir el test multiproceso ese sobrecoste **no se reprodujo** —
> `localhost` 36,5 s frente a 35,6–39,6 s con `127.0.0.1` —, así que la cifra de 30 s/conexión no
> debe darse por universal. Ver [`deuda-multiproceso.md`](deuda-multiproceso.md) §3.)*

## Revaluación del "125 errores por libpq"

El dictamen no podía evaluar `apps/api-python/tests` porque `create_engine` fallaba con el
intérprete global. Con `.venv`:

```
1585 tests collected in 2.74s   (0 errores de colección)
```

La causa queda confirmada como ambiental: el intérprete global no cargaba `libpq`; `psycopg`
3.3.4 binario dentro de `.venv` sí. Los 125 errores no eran regresiones de los módulos tocados.

## Matriz condición → test → resultado

Comando base:

```powershell
$env:DATABASE_URL='postgresql://bolsa:bolsa_dev@127.0.0.1:5432/bolsa_v1'
$env:SCAN_QUEUE_PG_REQUIRED='1'
$env:AUTO_CHAIN_READ_GAPS_PG_REQUIRED='1'
$env:AUTO_PROPOSAL_OUTCOMES_PG_REQUIRED='1'
.\.venv\Scripts\python.exe -m pytest `
  apps/api-python/tests/test_scan_job_lease_pg.py `
  apps/api-python/tests/test_auto_chain_read_gaps_pg.py `
  apps/api-python/tests/test_estudio_daily_proposal_savepoint_pg.py `
  apps/api-python/tests/test_scan_queue_health_pg.py `
  -q -p no:cacheprovider
```

Resultado: **28 passed** (0 skipped, 0 failed).

| # | Condición del dictamen | Test (fichero `::` test) | Resultado |
| --- | --- | --- | --- |
| 1 | El fallo de lectura de propuestas queda aislado en `SAVEPOINT` y **no** tumba la sesión exterior | `test_auto_chain_read_gaps_pg.py::test_unreadable_proposals_do_not_abort_the_shared_session` | PASS |
| 1b | Cada etapa tiene su propio `SAVEPOINT`: un fallo DÍA-D no vacía las propuestas | `test_auto_chain_read_gaps_pg.py::test_unreadable_dia_d_does_not_empty_the_proposals_link` | PASS |
| 2 | Dos reconciliadores concurrentes del mismo `processing` obsoleto reencolan **exactamente una vez** | `test_scan_job_lease_pg.py::test_two_reconcilers_requeue_the_same_job_exactly_once` | PASS |
| 2b | Lo mismo con dos sesiones reales: el segundo reconciler toca 0 filas | `test_scan_job_lease_pg.py::test_reconcilers_on_two_sessions_do_not_double_requeue` | PASS |
| 3 | Renovar el lease **entre** el `SELECT` y el `UPDATE` del reaper anula el reencolado | `test_scan_job_lease_pg.py::test_renewal_between_select_and_update_cancels_the_reap` | PASS |
| 3b | Un job que late deja de ser huérfano en cada ciclo del vigía | `test_scan_job_lease_pg.py::test_heartbeat_keeps_a_long_job_alive_across_reconcile_cycles` | PASS |
| 3c | El latido no reabre un job ya cerrado o reencolado | `test_scan_job_lease_pg.py::test_renewal_of_a_job_that_is_no_longer_processing_returns_none` | PASS |
| 3d | El `UPDATE` del reaper no reabre un job terminado entre lectura y escritura | `test_scan_job_lease_pg.py::test_update_of_the_reaper_never_reopens_a_finished_job` | PASS |
| 4 | Agotado el tope de reaps, el job queda `failed` de forma **persistente** y deja de bloquear el dedupe diario | `test_scan_job_lease_pg.py::test_reap_cap_is_persistent_and_unblocks_the_daily_dedupe` | PASS |
| 4b | El reencolado conserva identidad/datos, no duplica filas y es reclamable | `test_scan_job_lease_pg.py::test_requeued_job_preserves_identity_and_is_claimable_again` | PASS |
| 4c | El reaper es acotado y no toca jobs con lease vivo | `test_scan_job_lease_pg.py::test_reap_is_bounded_and_skips_rows_outside_the_lease` | PASS |
| 5 | Fallo intermedio del sumidero: rollback **solo** del `SAVEPOINT`, sesión utilizable y commit posterior real | `test_estudio_daily_proposal_savepoint_pg.py::test_a_midway_failure_rolls_back_only_the_savepoint` | PASS |
| 5b | Las escrituras previas del turno sobreviven al fallo del sumidero | `test_estudio_daily_proposal_savepoint_pg.py::test_previous_writes_of_the_turn_survive_the_sink_failure` | PASS |
| 5c | Con éxito, el desenlace se commitea y es visible desde **otra** conexión | `test_estudio_daily_proposal_savepoint_pg.py::test_a_healthy_outcome_is_committed_and_visible_from_another_connection` | PASS |
| 5d | El sello es idempotente: un segundo desenlace no atribuye otro ciclo | `test_estudio_daily_proposal_savepoint_pg.py::test_a_second_outcome_on_the_same_proposal_is_not_consumed_again` | PASS |
| 6 | `readGaps` se publica en el artefacto y con todo medido no hay motivos | `test_auto_chain_read_gaps_pg.py::test_read_gaps_are_published_and_empty_when_every_stage_is_measured` | PASS |
| 6b | Con la lectura caída, el artefacto lo declara y la atribución es `unmeasured`, nunca `not_proposed` | `test_auto_chain_read_gaps_pg.py::test_read_gap_reaches_the_artifact_and_marks_the_attribution_unmeasured` | PASS |
| 6c | El veredicto del journal (`exact`) **no** se degrada por un fallo de lectura; el hueco va por su canal | `test_auto_chain_read_gaps_pg.py::test_a_durable_journal_verdict_is_not_degraded_by_a_read_failure` | PASS |
| 6d | Control negativo: si la lectura se hizo, la ausencia es `not_proposed` | `test_auto_chain_read_gaps_pg.py::test_a_measured_absence_is_still_not_proposed` | PASS |

### Cómo se fuerza un fallo REAL de lectura (sin mocks)

El test crea un esquema señuelo con una tabla homónima de columnas incompatibles y lo antepone en
`search_path`. PostgreSQL falla con `UndefinedColumn` —el `except` real del lector— y el
`SAVEPOINT` debe acotarlo. Se revierte con `DROP SCHEMA … CASCADE`. No hay `monkeypatch` del
camino SQL: el fallo es del motor.

## Pruebas por mutación (el test muerde)

Un test que pasa siempre no certifica nada. Se rompió a propósito cada protección y se comprobó
que el test correspondiente falla:

| Mutación aplicada | Test que debe fallar | Resultado observado |
| --- | --- | --- |
| Quitar `ScanJobRow.updated_at < stale_before` del `UPDATE` del reaper | `test_renewal_between_select_and_update_cancels_the_reap` | **FAILED**: `un lease renovado NO debe reencolarse` — el lease renovado se reencolaba |
| Quitar `async with session.begin_nested():` de `read_daily_proposals` | `test_unreadable_proposals_do_not_abort_the_shared_session` | **FAILED**: `InternalError (InFailedSqlTransaction) current transaction is aborted` en el `SELECT 1` siguiente |

Ambas mutaciones se revirtieron; el repo queda con las dos protecciones activas (verificado con la
segunda corrida verde de la matriz).

## Pruebas offline del latido y del vigía

| Test | Qué blinda |
| --- | --- |
| `test_scan_job_lease_heartbeat.py::test_interval_derives_from_the_lease_and_respects_the_floor` | 3 latidos por vida de lease; nunca por debajo del suelo |
| `::test_heartbeat_stops_as_soon_as_the_job_is_no_longer_processing` | el latido no refresca un job ya reencolado |
| `::test_heartbeat_uses_its_own_session_each_tick` | una sesión nueva por tick, jamás la sesión del job |
| `::test_a_failing_tick_does_not_kill_the_heartbeat` | un error transitorio de BD no detiene el scan |
| `::test_stop_cancels_a_running_heartbeat` | al terminar el job no queda tarea viva (idempotente) |
| `test_scheduler_worker.py::test_health_watchdog_never_overlaps_reconcile_cycles` | el vigía es secuencial: concurrencia observada = 1 |
| `test_scheduler_worker.py::test_health_watchdog_respects_the_interval_floor` | la cadencia nunca baja del suelo (60 s) |

Resultado: **17 passed** (`test_scan_job_lease_heartbeat.py` + `test_scheduler_worker.py`).

## Contrato publicado (`readGaps`)

Diff **aditivo**, sin cambios de comportamiento en el resto del esquema:

| Fichero | Cambio |
| --- | --- |
| `packages/py/application/src/bolsa_application/auto_chain_durable_reader.py` | `build_chain_evidence_artifact(..., read_gaps=...)` y `"readGaps"` en el artefacto |
| `apps/api-python/src/bolsa_api/api/v1/routes/auto_estudio_chain.py` | pasa `read_gaps` al artefacto y lo publica en `EstudioChainResponseDto` |
| `apps/api-python/scripts/v2_100_operational_certification_evidence.py` | el bundle pasa `read_gaps` al artefacto y publica `chainReadGaps` (antes solo copiaba `summary`/`meta`: el hueco se perdía al certificar) |
| `packages/shared/src/estudio-daily-ops.ts` | `readGaps: Record<string, string \| null>` en `EstudioChainResponseV1` |
| `apps/web/api/openapi.json` + `apps/web/src/api/schema.d.ts` | regenerados con `contract:gen` (+14 / +4 líneas) |

Tests del bundle: `test_operational_certification_evidence.py` (17 passed), con
`test_bundle_declares_chain_read_gaps` que blinda el cableado.

## Superficie de UI (`readGaps` deja de ser invisible)

Publicar el dato no bastaba: la ficha seguía sin distinguir «no hay propuestas» de «no se pudo
leer». Ahora la declara:

| Fichero | Cambio |
| --- | --- |
| `packages/shared/src/estudio-daily-ops.ts` | `chainReadGaps()` y `describeChainReadGaps()` (puras): solo un motivo no vacío es hueco; `null`/ausencia = medida; orden estable por etapa |
| `apps/web/src/features/auto-monitor/estudio-chain-evidence.tsx` | aviso `estudio-chain-read-gaps` con `data-read-gaps="<etapas>"`, en ámbar, junto a la atribución |

La frase es explícita: «Etapas no leídas: propuestas diarias del parte (falló la lectura). Su
ausencia no es una ausencia real.» Un estado o motivo desconocido se declara crudo en vez de
ocultarse.

Pruebas: `packages/shared/src/estudio-daily-ops.test.ts` (7 tests) y dos casos en
`estudio-daily-ops-panel.test.tsx` (aviso presente con `dailyProposals` ilegible y **ausente**
cuando todas las etapas están medidas).

Resultado de la verificación: `shared` **891 passed** (1 todo), `web` typecheck OK, panel
**38 passed**, lint `0 errors` (23 warnings preexistentes).

## Cableado de CI

- `python-ci.yml` → job `lifecycle-pg`: gates `SCAN_QUEUE_PG_REQUIRED`,
  `AUTO_CHAIN_READ_GAPS_PG_REQUIRED` y `AUTO_PROPOSAL_OUTCOMES_PG_REQUIRED`; los cuatro ficheros
  entran en el paso *Pytest A12 PG (fail if skipped)*. En el job offline van a `--ignore`.
- `release-tag-ci.yml` → job `lifecycle-pg` del tag: paso dedicado
  **Pytest DS-1 lease + C-1 readGaps + O-2 savepoint (PG, fail if skipped)** con `-rs` y un paso
  siguiente que falla si aparece cualquier `SKIPPED`. Los cuatro ficheros se añadieron también al
  `--ignore` offline: `test_scan_queue_health_pg.py` **no estaba** en esa lista, y por eso sus 9
  tests aparecían como `skipped` en el job de tag sin certificar nada.

Los dos workflows validan como YAML (`yaml.safe_load`) y `test_release_tag_ci_a7_gate_wiring.py`
sigue en verde (5 passed).

## Suites completas (reevaluación)

Todas con `.venv` (Python 3.12.13 + `psycopg` 3.3.4 binario) y `DATABASE_URL` apuntando a
`127.0.0.1`.

| Suite | Comando | Resultado |
| --- | --- | --- |
| Aplicación Python | `pytest packages/py/application/tests -q` | **3108 passed** ×2 corridas independientes (3107 antes del test de determinismo añadido) |
| API Python (todo, con PostgreSQL real) | `pytest apps/api-python/tests -q --ignore=test_auto_v46_multiprocess_pg.py --ignore=chaos` | **1565 passed** en 6 m 57 s |
| Colección `apps/api-python/tests` | `pytest apps/api-python/tests --collect-only -q` | **1585 collected, 0 errores** |
| Certificación PG (4 ficheros) | ver comando base | **28 passed** (0 skipped) |
| Offline del latido + vigía | `pytest test_scan_job_lease_heartbeat.py test_scheduler_worker.py` | **17 passed** |
| `test_lab_discovery_dispatch.py` | `pytest .../test_lab_discovery_dispatch.py` | **9 passed** |

**Actualización 2026-11-03 (post-arreglo):** el test multiproceso se ejecuta ahora aislado y en
verde — **5/5 corridas, ~36 s cada una** (antes 115 s y con fallo intermitente en CI). Detalle en
[`deuda-multiproceso.md`](deuda-multiproceso.md).

### Por qué la corrida completa se aísla de dos ficheros

`apps/api-python/tests/test_auto_v46_multiprocess_pg.py::test_n_real_processes_claim_one_signal_exactly_once_pg`
se excluía porque **gastaba el presupuesto entero del bucle de espera** (115 s por corrida en
Windows) y, en CI, fallaba de forma **intermitente también en Linux** (run
[`41594625695`](https://github.com/jvelasca/Bolsa_V1/actions/runs/41594625695): `assert
Decimal('0') > 0` en 5,68 s). No era una limitación de Windows ni una regresión de este bloque:
era un **defecto de sincronización del propio test**, que rompía el bucle en la ventana entre el
commit de la posición y el de la liberación de la reserva. Está diagnosticado y arreglado —el
bucle espera ahora la materialización durable— y verificado 5/5 en ~36 s por corrida:
ver [`deuda-multiproceso.md`](deuda-multiproceso.md). `chaos/` sigue excluido por su propia
naturaleza. Con esos dos excluidos, los 1565 restantes —incluidos todos los PG— pasan en verde.

## Flaky de `test_lab_discovery_dispatch.py`

El fichero es hermético. **No se reprodujo en 84 ejecuciones** (25 aisladas, 12 bajo carga, 40 con
distintos `PYTHONHASHSEED`, 4 con la política de event loop de Windows, 3 suites completas). En
lugar de dejar la duda abierta se añadió
`test_the_declarative_pipeline_is_deterministic_across_runs`, que ejecuta el mismo caso dos veces y
exige identidad exacta de campeón, trials, CPCV, WF y PBO: cualquier no-determinismo futuro falla
ahí, con nombre, en vez de aparecer como flaky intermitente.

Detalle completo en
[`flaky-lab-discovery.md`](flaky-lab-discovery.md).

## Verificación de calidad

| Gate | Comando | Resultado |
| --- | --- | --- |
| Ruff (como CI) | `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| TypeScript `shared` | `pnpm --filter @bolsa/shared typecheck` | OK |
| Tests `shared` | `pnpm --filter @bolsa/shared test` | **884 passed** (1 todo) |
| TypeScript `web` | `pnpm --filter @bolsa/web typecheck` | OK |
| Contrato | `pnpm contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |
| Wiring de CI del tag | `pytest test_release_tag_ci_a7_gate_wiring.py` | **5 passed** |

Ruff destapó dos `UP037` (anotación entrecomillada) en los dobles `_NestedTransaction` de
`test_auto_chain_durable_reader.py` y `test_estudio_daily_proposal_handoff.py`; se corrigieron con
`ruff --fix` (sin cambio de comportamiento).

## Riesgos residuales

1. **`localhost` en Windows.** Un entorno que use `localhost` para la BD debería evitarse en las
   suites PG: se midió un sobrecoste de ~30 s por conexión, aunque la re-medición del test
   multiproceso no lo reprodujo (ver [`deuda-multiproceso.md`](deuda-multiproceso.md) §3). CI usa
   `localhost` sobre Linux, donde no ocurre.
2. **El lease se apoya en `updated_at`.** La carrera se cierra revalidando `updated_at` en el
   `UPDATE` del reaper, no con un `lock_version`. Si en el futuro se añade un `UPDATE` que mueva
   `updated_at` sin querer refrescar el lease, el reaper lo tratará como latido.
3. **`readGaps` es aditivo y opcional aguas abajo.** Un cliente antiguo que ignore la clave no
   cambia de comportamiento; la UI nueva la usa para no confundir «no hay» con «no se pudo leer».
