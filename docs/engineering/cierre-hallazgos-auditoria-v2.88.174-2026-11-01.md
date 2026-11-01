# Cierre de hallazgos de la auditoría `v2.88.174-beta` — sellado en `v2.88.175-beta`

**Fecha:** 2026-11-01 · **Árbol de partida:** `17ab0ef9` (`v2.88.174-beta`) · **Delta de corrección:**
`12e2c871` · **Sello:** `v2.88.175-beta` (tag anotado sobre el cierre documental de este expediente).

El tag auditado **no contiene** este código: ni `_exclusivity_guard.py` ni este documento existen en
`v2.88.174-beta` —comprobado con `git cat-file -e "v2.88.174-beta:<ruta>"`, que falla para ambos—. Mientras
el delta vivió sin commitear, este documento afirmaba un cierre que el tag no respaldaba; por eso el delta
se sella aparte como `.175`, con bump propio, y cada hallazgo queda comprobable en `12e2c871` y en el árbol
del tag (ver «Verificabilidad en el tag»).

Cierra los cinco hallazgos abiertos de `AUDITORIA 1` (más dos de su sección de observaciones). `AUDITORIA 2`
es informativa (`.174` publicada y certificada por el CI del tag) y **no requería acción**. Los tres puntos
que quedaron en el expediente —lectura del verde con skips, aviso inexacto de la purga y alcance de la
certificación— se tratan en «Gate del CI», «Aviso `relation "investment_accounts" does not exist`» y
«Límites declarados».

## Tabla de cierre

| # | Hallazgo | Causa raíz | Corrección | Prueba que lo rompe |
| --- | --- | --- | --- | --- |
| **P-1b** | El placeholder `KILL_STATE_UNREADABLE` enmascara y después **borra** una parada real | `HardKillSwitch.engage()` con el latch activo solo incrementaba `reengagements` y conservaba el motivo; `_release_unreadable_placeholder` liberaba por ver el placeholder | El placeholder **no es una causa**: un motivo real lo **sustituye** (con su identidad y `changed=True` para persistirlo) y un placeholder nunca pisa un motivo real. `_v2_kill_state()` devuelve `None` con el placeholder ⇒ **no se persiste**, y se declara en el log | `test_auto_v2_audit_regressions.py::test_p1b_*` (4 casos: ascenso, no degradación, idempotencia entre motivos reales, no-liberación de la parada real) |
| **N-1** | «Deshabilitar Yahoo» solo cortaba el histórico (OHLCV) | El interruptor se evaluaba únicamente vía `resolve_capability(CAPABILITY_OHLCV)`; nueve consumidores llamaban al cliente por su cuenta | **Punto único de estrangulamiento** en el cliente (`_ensure_traffic_allowed` en `_get_client`), refrescado por el lector único de configuración (`list_configs`). Con Yahoo apagado no se construye ni un `httpx.AsyncClient`. Descripción del proveedor honesta y `409 provider_disabled:yahoo` en `/market/fx` | `packages/py/application/tests/test_yahoo_traffic_gate.py` (8 rutas × cero red, semáforo en ambos sentidos, sonda sin tráfico) + `apps/api-python/tests/test_market_fx_provider_gate.py` (409 / 200 / 502) |
| **N-2** | La sonda aceptaba `0.0`, negativos y `NaN` como precio válido | `_probe_yahoo` solo capturaba `TypeError`/`ValueError`; `fetch_spot_price` hacía `float(...)` sin validar; FX solo filtraba `== 0` en la inversa | `math.isfinite(p) and p > 0` en el origen (`fetch_spot_price`, con el valor crudo en el mensaje), en la sonda y en FX (directa **e** inversa) | `packages/py/market/tests/test_yahoo_spot_price.py`, `packages/py/application/tests/test_fx_rates.py`, caso parametrizado en `test_market_providers.py` |
| **N-3** | La copia de BD no declaraba que no pudo auditarse | `_record` hacía `except Exception: pass` y `_snapshot` devolvía `None` sin motivo | `audit_recorded` / `backups_error` en el caso de uso, el DTO, `types.ts`, el contrato y la UI (aviso ámbar); el fallo de auditoría **se loguea** | `test_database_backup.py` (2 casos), `test_database_backup_api.py` (2 casos), `database-maintenance-panel.test.tsx` (2 casos) |
| **N-4** | El grupo se daba por «fresco» con la medición **más reciente** | `max(measured)` en `summarize_provider_health` y en `ProviderHealthMonitor.last_measured_at` | `min(measured)`: el grupo está tan fresco como su proveedor **más viejo**, que es el que toca refrescar | `test_summary_stale_uses_the_oldest_measurement_not_the_newest`, `test_monitor_is_due_by_the_oldest_provider_measurement` |
| **Obs. 1** | Los dos `purge` de mantenimiento no exigían rol | `require_admin_when_auth_enabled` solo se aplicaba a `POST /database/backup` | Mismo criterio en `POST /database/orphans/purge` y `POST /database/closed-accounts/purge` (sin auth el comportamiento no cambia; el 403 ocurre **antes** de tocar la BD) | `apps/api-python/tests/test_database_purge_role_gate.py` (403 no-admin / 200 sin auth) |
| **Obs. 2** | El fichero creado se infería por `after − before` | El runner no leía la salida del script: cualquier fichero nuevo del directorio se atribuía a esta copia | Se parsea `[db-dump] Backup creado: <path>` y se **valida** (existe, es backup, cae en el directorio); el delta queda solo como compatibilidad declarada en el log | `test_the_declared_file_wins_over_a_foreign_file_in_the_directory`, `test_without_a_declared_line_the_delta_is_still_used_and_declared`, `test_a_declared_file_outside_the_backup_directory_is_not_trusted` |

## Decisiones de diseño

### N-1 — el interruptor se cierra en el cliente, no en las nueve rutas

El defecto original es exactamente «una ruta olvidada»: gatear ruta por ruta habría reproducido el mismo
fallo con la siguiente ruta añadida. El semáforo vive en el cliente Yahoo (`bolsa_market.yahoo_client`)
porque **todo** `fetch_*` pasa por `_get_client()` antes de tocar la red y antes de `_ensure_crumb`/
`_throttle`, y se refresca desde `MarketProviderConfigResolver.list_configs()` — el único lector de la
configuración, por el que pasan API, workers y sonda sin *plumbing* nuevo.

Consecuencia buscada: un proveedor apagado se comporta **igual que uno caído**, que es lo que cada
consumidor ya sabe degradar (chart → barras en caché, fundamentales → snapshot guardado, macro/noticias →
sin dato, FX → **409** de configuración). Desfase máximo: el TTL de la caché de configuración (30 s), el
mismo que para el resto de la configuración. Un proceso que nunca resuelve configuración (script suelto)
conserva el defecto **habilitado**: esta pieza no puede inventar una fila que nadie leyó.

### P-1b — el placeholder no es una causa

Un placeholder nace de **no poder leer** el espejo durable; guardarlo como parada real haría que un
reinicio posterior la restaurase con un motivo inventado (`SYSTEM_ERROR`) y borrase el rastro de lo que
pasó de verdad. Por eso:

* el placeholder **nunca** se persiste (`_v2_kill_state()` → `None`, con aviso en el log);
* un motivo real **sustituye** al placeholder (y pide persistencia: `changed=True`);
* un placeholder **nunca** degrada un motivo real;
* `_release_unreadable_placeholder` libera **solo** si `engaged && reason == KILL_STATE_UNREADABLE`, y esa
  condición es ahora la garantía (no una optimización) de que una lectura válida posterior no puede
  borrar un HALT real.

El ascenso **no reabre el motor**: solo cambia el motivo con el latch ya activo; las entradas siguen
vetadas en ambos sentidos.

## Verificación medida (local, 2026-11-01)

Cada fila es una **ejecución distinta** (comando, entorno y commit propios). **No se suman**: los
`4 582 + 1 454 + 2 677` de las tres categorías de tests **no** son una única pasada certificada. Todas se
midieron sobre el **árbol de trabajo con los cambios sin commitear** (Δ sobre `17ab0ef9`), en local (win32);
las pasadas de `pytest`/`vitest` fueron además con el stack de desarrollo vivo (API `:8000`, Vite `:5173`,
mock XTB `:3002`), que es justo la condición que contamina `chaos/live_a7`.

| Comprobación | Comando | Entorno | Commit | Salida | Código |
| --- | --- | --- | --- | --- | --- |
| `pytest` librerías | `pytest` de `packages/py/{market,application,analytics}/tests` | sin PG dedicada | árbol Δ `17ab0ef9` | **4 582 passed**, 0 skipped | `0` |
| `pytest` API | `pytest apps/api-python/tests --ignore=tests/integration` | PG dev `bolsa_v1` **compartida** | árbol Δ `17ab0ef9` | **1 454 passed**, **1 failed** (`chaos/live_a7/test_c3a_*`) | `1` |
| `pytest` API (el fallo, aislado) | `pytest` del nodo `test_c3a_*` | PG dev `bolsa_v1`, con el stack vivo | árbol Δ `17ab0ef9` | **1 passed** | `0` |
| `vitest` web completo | suite web completa | sin servicios | árbol Δ `17ab0ef9` | **356 ficheros · 2 677 tests** | `0` |
| `tsc -b --noEmit` (web) | — | — | árbol Δ `17ab0ef9` | **limpio** | `0` |
| `eslint` ficheros tocados | — | — | árbol Δ `17ab0ef9` | **0 errores** | `0` |
| `ruff check` | `ruff check packages/py apps/api-python --config pyproject.toml` | — | árbol Δ `17ab0ef9` | **All checks passed** | `0` |
| `pnpm types:py` (mypy) | — | — | árbol Δ `17ab0ef9` | **582 ficheros**, sin errores | `0` |
| `pnpm contract:check` | — | — | árbol Δ `17ab0ef9` | **OK** — `openapi.json` y `schema.d.ts` coincidentes | `0` |

**El `1 failed` de la pasada de API tiene causa propia, no timing** (corrección respecto al diagnóstico
inicial): la BD de esa pasada era `bolsa_v1` (compartida) y el `scheduler_worker` del stack dev drena la
fila sembrada. Ver «Guarda de exclusividad de `chaos/live_a7`».

Tests nuevos: **5 ficheros** (`test_yahoo_traffic_gate.py`, `test_fx_rates.py`, `test_yahoo_spot_price.py`,
`test_database_purge_role_gate.py`, `test_market_fx_provider_gate.py`) y **8 casos** añadidos a suites
existentes. La guarda de exclusividad añade **1 fichero nuevo** y **12 casos** (`test_exclusivity_guard.py`).

### Repetición sobre el árbol sellado (`12e2c871`)

Las filas de arriba se midieron sobre el delta **sin commitear**. Esta es la repetición sobre el commit que
se sella, limitada a los nodos tocados (las suites completas no se repitieron: la cifra anterior no se
reutiliza aquí como si fuera de este árbol).

| Comprobación | Comando | Salida | Código |
| --- | --- | --- | --- |
| `pytest` lado API (8 ficheros) | `test_auto_v2_audit_regressions`, `test_market_fx_provider_gate`, `test_database_purge_role_gate`, `test_database_backup_api`, `test_residual_purge_schema_guard`, `test_release_tag_ci_a7_gate_wiring`, `chaos/live_a7/test_exclusivity_guard`, `test_ci_test_selection_census` | **81 passed** | `0` |
| `pytest` lado librerías (6 ficheros) | `test_yahoo_spot_price`, `test_yahoo_traffic_gate`, `test_fx_rates`, `test_market_providers`, `test_database_backup`, `test_backup_runner` | **92 passed** | `0` |
| `ruff check` (ficheros tocados) | `ruff check … --config pyproject.toml` | **All checks passed** | `0` |
| `pnpm types:py` (mypy) | — | **582 ficheros**, sin errores | `0` |
| `pnpm contract:check` | — | **OK** | `0` |
| `tsc -b --noEmit` (web) | — | **limpio** | `0` |
| `vitest` (2 ficheros web tocados) | `database-maintenance-panel`, `market-providers-status-card` | **15 passed** (2 ficheros) | `0` |
| `chaos/live_a7` real-PG | `LIVE_A7_PG_REQUIRED=1` sobre `bolsa_v1_a7` (drop+create) | **19 passed, 0 skipped**, 15,19 s | `0` |

### Verificación de la guarda de exclusividad (local, 2026-11-01)

| Comprobación | Comando | Entorno | Salida | Código |
| --- | --- | --- | --- | --- |
| Contrato de la guarda (hermético) | `pytest apps/api-python/tests/chaos/live_a7/test_exclusivity_guard.py -q` | sin PG, sin red | **12 passed** | `0` |
| Batería completa con BD compartida | `pytest apps/api-python/tests/chaos/live_a7 -q -rs` | `bolsa_v1` + stack dev vivo | **12 passed, 7 skipped** — cada skip nombra la BD, el consumidor y el arreglo | `0` |
| Misma batería con el gate del CI | `LIVE_A7_PG_REQUIRED=1 pytest …/test_c3_crash_injection_recovery_worker.py -q` | `bolsa_v1` | **7 errors** — `AssertionError: live_a7 C3 required but BD no exclusiva …` | `1` |

**Regla de lectura (incorporada a raíz de la auditoría).** La fila del medio es un **diagnóstico**, no un
pase: `12 passed, 7 skipped` en verde **no** certifica A7 y no debe leerse como éxito. Lo que lo cubre es
`LIVE_A7_PG_REQUIRED=1`, que convierte el skip en `AssertionError`, junto con el job `a7-gate` —que fija esa
variable y del que `certify` depende— (ver «Gate del CI»). Desde esta pasada el propio mensaje del skip lo
dice: `describe()` termina declarando que ese run no certifica y que con el gate sería un fallo.

### Ejecución controlada con el stack parado (local, 2026-11-01)

Cierra la diferencia que la fila anterior deja abierta: **`12 passed, 7 skipped` no equivale a `19 passed`**. Esta pasada ejecuta los **19** casos —12 del contrato herméticamente aislado y **7 real-PG**— contra una BD dedicada `bolsa_v1_a7` (drop+create) y con el stack de desarrollo **detenido**, de modo que no queda ningún consumidor del outbox capaz de llevarse las filas sembradas. Árbol: Δ sin commitear sobre `17ab0ef9` (`git_sha` que declara `/api/health`).

| Paso | Comprobación | Resultado |
| --- | --- | --- |
| Origen | `pnpm dev` vivo: `run-dev.mjs` PID 3624, `scheduler_worker` 13704→8680, `queue_poll_worker` 5660→17316; `:8000`, `:5173`, `:3002` escuchando | condición contaminante confirmada antes de empezar |
| Parada | `taskkill /PID 3624 /T /F` | 13 procesos terminados; **0** `scheduler_worker`/`queue_poll_worker` residuales; `:8000`, `:5173`, `:3002` cerrados; PostgreSQL `:5432` intacto |
| BD dedicada | `docker exec bolsa-postgres psql -U bolsa -d bolsa_v1 -c "DROP DATABASE IF EXISTS bolsa_v1_a7 WITH (FORCE)" -c "CREATE DATABASE bolsa_v1_a7 OWNER bolsa"` | `DROP DATABASE` + `CREATE DATABASE`; el esquema vacío lo lleva a head el propio fixture (`ensure_migrated`) |
| Ejecución | `DATABASE_URL=…/bolsa_v1_a7 DB_NAME=bolsa_v1_a7 LIVE_A7_PG_REQUIRED=1 pytest apps/api-python/tests/chaos/live_a7 -q` | **19 passed, 0 skipped**, 17,12 s, código `0` |
| Residuo | `bolsa_v1_a7`: `live_orders` 0 (`status='UNKNOWN'` 0), `execution_events` 0, `investment_accounts` 0, `ledger_entries` 0, `instruments` `CF%` 0 | la purga autouse dejó la BD limpia |
| BD de desarrollo | `bolsa_v1`: `live_orders` 0, head `062_sync_settings_check_backfill` | **no se tocó**: la suite no escribió ni un `DELETE` ahí |
| Restauración | `node scripts/run-dev.mjs` (desacoplado; salida a `logs/dev/`) → `run-dev.mjs` 15840, API 12904→11920, `scheduler_worker` 19476→24800, `queue_poll_worker` 19892→15288 | `:8000`, `:5173`, `:3002` arriba; `/api/health` `status=ok`, `database=ok`, `schema_revision=062_sync_settings_check_backfill`, `git_sha=17ab0ef9` |

Los **7 real-PG** ejecutados, sin skip:

1. `test_c3a_crash_after_recovery_claim_then_second_is_exact_once`
2. `test_c3b_crash_after_resolve_put_no_double_on_relaunch`
3. `test_c3c_crash_financial_apply_reexecuted_exact_once`
4. `test_c3d_reclaim_applying_or_terminal_no_double`
5. `test_c3e_crash_after_financial_commit_no_second_effect`
6. `test_v220_two_workers_cas_exactly_one_owner`
7. `test_v220_stale_reaper_converges_orphaned_apply`

Los **12** restantes son el contrato de la guarda (`test_exclusivity_guard.py`).

Lectura del resultado: con `LIVE_A7_PG_REQUIRED=1` **un solo skip habría hecho fallar el run**. No hubo ninguno, así que C3-A y C3-B pasan con la fila sembrada reclamada por los procesos de la propia suite (nadie más barrió la tabla). No se invocó `_contention_reason` y **no se relajó ningún criterio** de C3-A ni de la guarda.

### Repetición sobre el árbol sellado, con el stack vivo (`12e2c871`)

La pasada anterior midió el delta **sin commitear** y con el stack parado. Esta repite la medición sobre el
commit que se sella y **con el stack de desarrollo vivo** a propósito: la condición dura de la guarda es la
BD, no los puertos, y eso queda así demostrado en vez de solo declarado.

| Paso | Comprobación | Resultado |
| --- | --- | --- |
| BD dedicada | `docker exec bolsa-postgres psql -U bolsa -d bolsa_v1 -c "DROP DATABASE IF EXISTS bolsa_v1_a7 WITH (FORCE)" -c "CREATE DATABASE bolsa_v1_a7 OWNER bolsa"` | `DROP DATABASE` + `CREATE DATABASE` (esquema vacío: lo migra el fixture) |
| Stack dev | `:8000` y `:5432` aceptando conexión; `bolsa-postgres` y `bolsa-ollama` `Up 25 hours (healthy)` | **stack vivo durante la pasada** |
| Ejecución | `DATABASE_URL=…/bolsa_v1_a7 DB_NAME=bolsa_v1_a7 LIVE_A7_PG_REQUIRED=1 pytest apps/api-python/tests/chaos/live_a7 -q -rs` | **19 passed, 0 skipped**, 15,19 s, código `0`, sin skips que reportar |
| Residuo | `bolsa_v1_a7`: `live_orders` 0 (`status='UNKNOWN'` 0), `execution_events` 0 | la purga autouse dejó la BD limpia |
| BD de desarrollo | `bolsa_v1`: `live_orders` 0, head `062_sync_settings_check_backfill` | intacta: la suite no escribió ahí |

Dos lecturas que añade esta repetición:

* **La condición dura es la BD, no los puertos.** Con `:8000` arriba la batería pasa 19/19 porque el
  `scheduler_worker` del stack apunta a `bolsa_v1`. La sonda de puertos del mensaje es informativa; el
  criterio que decide es el nombre de la BD y los claims ajenos sobre ESA BD.
* **La BD recién creada no emite el aviso de la purga.** El esquema estaba vacío al abrir la sesión y no
  apareció `relation "investment_accounts" does not exist` (ver la subsección siguiente).

### Aviso `relation "investment_accounts" does not exist` — corregido, no solo declarado

La auditoría señaló, con razón, que declararlo sin corregirlo era aceptable pero inexacto. Se corrige.

* **Causa:** la purga de residuos es `autouse` de SESIÓN y corre antes de que la batería lleve su BD a head
  (`ensure_migrated` del fixture `factory`). En una BD recién creada el esquema está vacío y
  `SELECT id FROM investment_accounts` fallaba con `UndefinedTable`, que `_purge_residuals_once` convertía
  en `warnings.warn` fail-soft.
* **Corrección:** `purge_all_residuals` consulta `to_regclass('public.investment_accounts')` antes de leer
  cuentas y, si la tabla no existe, **no purga y no avisa**: nada que limpiar no es un fallo. La red
  fail-soft (`ResidualsUnavailable`, `warnings.warn`) queda intacta para el caso que sí importa (BD caída).
* **Prueba:** `apps/api-python/tests/test_residual_purge_schema_guard.py` (3 casos: el predicado distingue
  tabla ausente de tabla vacía; con esquema sin migrar, cero `DELETE` y cero lectura de cuentas; con
  esquema migrado la purga sigue borrando instrumentos y workspaces, para que el cortocircuito no la deje
  muerta).
* **Medición:** recreada `bolsa_v1_a7` vacía y ejecutada la suite con `DATABASE_URL` apuntando ahí →
  **3 passed**, sin aviso en la salida.

## Gate del CI: por qué un A7 verde con skips no sella

El riesgo residual que señaló la auditoría es de **lectura**, no de código: `12 passed, 7 skipped` en verde
se puede leer como éxito. Lo que lo cubre es el cableado del job `a7-gate` del CI del tag, y ese cableado es
el que convierte un skip en un sello rojo:

| Pieza | Dónde | Qué hace |
| --- | --- | --- |
| `LIVE_A7_PG_REQUIRED: '1'` en el `env` del **job** | `release-tag-ci.yml`, job `a7-gate` | todos los steps del job heredan el gate (también los que preparan la BD) |
| `LIVE_A7_PG_REQUIRED: '1'` en el `env` del **step** de pytest | mismo job | el run de la batería lo declara explícitamente y no depende de que nadie mueva el `env` del job |
| Gate en la guarda | `_exclusivity_guard.require_exclusive` | convierte el `pytest.skip` en `AssertionError` |
| `a7-gate` en el `needs` de `certify` | mismo workflow | el sello espera al job |
| `needs.a7-gate.result != 'success'` ⇒ `exit 1` | step «Fail if any required job failed» | un fallo de A7 deja el release no-GREEN |
| `"a7-gate"` en el artefacto resumen | `release-tag-ci-summary.json` | la trazabilidad del sello lo nombra |

Con eso, un skip en `a7-gate` es rojo y `certify` no puede escribir `status: GREEN`. La regla de lectura
queda escrita: **el veredicto de A7 en un sello es el resultado de `a7-gate`, nunca un run local con
skips.**

El cableado es YAML y el YAML no lo ejecuta nadie en local, así que puede desaparecer en un refactor sin que
ningún test lo note: se ancla con
`apps/api-python/tests/test_release_tag_ci_a7_gate_wiring.py` (5 casos; parser por líneas con anclas
positivas, para que un parser roto falle por vacuo en vez de pasar en falso).

## Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Una parada real no se pierde bajo el placeholder | `test_p1b_a_real_halt_discovered_under_the_placeholder_is_never_released` |
| 2 | El placeholder no viaja al espejo durable | `test_p1b_the_placeholder_is_not_persisted_as_a_durable_halt` (0 `save`) |
| 3 | Con Yahoo apagado no hay tráfico | `test_every_yahoo_route_is_blocked_when_the_provider_is_disabled` (el transporte falla si se construye) |
| 4 | Apagar en Configuración apaga el cliente | `test_the_gate_follows_the_persisted_configuration` (ambos sentidos) |
| 5 | `/market/fx` declara configuración, no caída | `test_a_disabled_provider_returns_409_and_performs_no_traffic` |
| 6 | Un precio basura no verifica ni cotiza | casos parametrizados de N-2 (0, negativo, `nan`, `inf`) |
| 7 | Una copia sin auditoría se declara | `test_an_unaudited_copy_still_returns_200_and_declares_it` |
| 8 | «Caducado» se mide contra el más viejo | `test_summary_stale_uses_the_oldest_measurement_not_the_newest` |
| 9 | Los purges exigen admin con auth | `test_with_auth_enabled_a_non_admin_cannot_purge` |
| 10 | Se informa el fichero del script, no el ajeno | `test_the_declared_file_wins_over_a_foreign_file_in_the_directory` |
| 11 | Una BD no dedicada **no** certifica la batería (no se ejecuta en silencio) | `pytest …/live_a7 -rs` ⇒ 7 skips con la causa; `LIVE_A7_PG_REQUIRED=1` ⇒ `AssertionError` |
| 12 | La guarda no convierte el escenario real del CI en skip | con BD `*_a7` y sin claims ajenos la identidad pasa y `foreign_claim_reason` devuelve `None` (contrato: `test_a_shared_database_name_is_a_reason_and_a_dedicated_one_is_not`) |
| 13 | Con BD dedicada C3 corre **entero** (no skip silencioso) | `LIVE_A7_PG_REQUIRED=1 pytest …/live_a7` sobre `bolsa_v1_a7` ⇒ **19 passed, 0 skipped** (dos pasadas: stack parado y stack vivo, ver «Ejecución controlada» y su repetición); un skip habría dado `AssertionError` |
| 14 | Un A7 verde con skips **no** sella: el gate del CI es duro | `test_release_tag_ci_a7_gate_wiring.py`: quitar `LIVE_A7_PG_REQUIRED` del job o del step, sacar `a7-gate` de `needs`, o borrar el `exit 1` ⇒ rojo |
| 15 | La purga no habla de un esquema que no existe y sigue viva cuando existe | `test_residual_purge_schema_guard.py`: con esquema sin migrar, cero `DELETE`; con esquema migrado, borra instrumentos y workspaces |

## Guarda de exclusividad de `chaos/live_a7`

**Qué pasó, en cadena** (no «test inestable»):

1. La batería resuelve la BD por `get_settings().database_url`; el `.env` local apunta a **`bolsa_v1`**, la
   BD del stack de desarrollo. El job `a7-gate` del CI usa una BD dedicada **`bolsa_v1_a7`** (drop+create).
2. `pnpm dev` arranca un `python -m bolsa_api.workers.scheduler_worker`, que lanza el
   `LiveOrderRecoveryWorker` **on-by-default** con tick de 5 s. (La API `:8000` **no** es el consumidor: los
   workers no viven en su `lifespan`.)
3. `PostgresLiveOrderStore.claim_unknown_batch` es una barrida **global** de `status='UNKNOWN'`, sin filtro
   de cuenta (correcto en producción). Ese worker reclama la fila sembrada por C3-A.
4. Con la fila consumida, el segundo subproceso del escenario escribe `drained=0 resolved=0`: el síntoma
   parece un defecto del código de recovery.

**Qué hace la guarda** (`apps/api-python/tests/chaos/live_a7/_exclusivity_guard.py`):

* **Identidad de BD** (determinista, sin red, **antes** de abrir conexión): nombre dedicado por sufijo
  `_a7` o por `LIVE_A7_DB_NAME`. `LIVE_A7_ALLOW_SHARED_DB=1` lo relaja de forma explícita.
* **Claim ajeno fresco** (tras conectar): filas `UNKNOWN` con `recovery_claimed_at` dentro de la ventana
  viva y `recovery_worker_id` que **no** es de la suite (`live-a7-*`). Detecta un `scheduler_worker`
  apuntando a la BD dedicada.
* **Sonda del stack dev** (`:8000`, `:5173`, `:3002`): **solo informativa**, se nombra en el mensaje. No es
  criterio duro: la API puede apuntar a otra BD y produciría skips falsos.
* **Veredicto**: `pytest.skip` accionable (local) / `AssertionError` con `LIVE_A7_PG_REQUIRED=1` (CI). C3-A
  conserva además el diagnóstico causal: si el crasher no reclama o el segundo proceso no resuelve, se lee
  el lease y el estado de la fila y, **solo con evidencia** de otro consumidor, se declara precondición
  rota; sin evidencia el fallo sigue siendo una regresión real.

**Límite residual declarado:** un worker ajeno apuntando a la BD `*_a7` se detecta **si dejó un claim fresco
en la preflight**; uno que arranque después no se intercepta (el escenario lo diagnosticaría por lease). Los
puertos son solo contexto, no prueba de contención. La guarda no sustituye la ejecución aislada: certifica
que la BD es exclusiva, no que el escenario se haya ejecutado en un entorno libre de todo proceso.

## Límites declarados

* **El sello `.175` es el que contiene este código.** `.174` no lo contiene: se auditó su tag y ni la guarda
  ni este documento existen ahí. Este cierre va con bump propio (`2.11.175-beta`), tag anotado sobre el
  cierre documental y su `Release tag CI`, que es lo que certifica el sello.
* El corte de Yahoo es **global al proceso**: si el operador lo apaga, FX devuelve 409 y lo demás usa dato
  guardado o declara que no lo hay. Es el comportamiento pedido.
* La suite `chaos/live_a7` **no** tiene un «fallo inestable»: tiene una **precondición de BD exclusiva** que
  en local no se cumplía. Con el stack dev vivo (`pnpm dev`: API `:8000`, Vite `:5173`, mock XTB `:3002`) y
  la BD de desarrollo `bolsa_v1`, el `scheduler_worker` drena la fila UNKNOWN sembrada
  (`claim_unknown_batch` barre toda la tabla, sin filtro de cuenta) y el segundo proceso real lee
  `drained=0 resolved=0`. La causa es **determinista y reproducible en esa configuración**, no azar de
  timing. La precondición es **operativa**: la guarda `_exclusivity_guard.py` la verifica y la declara con
  mensaje causal (skip local / fallo con `LIVE_A7_PG_REQUIRED=1`), y la purga del `conftest` no escribe en
  una BD no dedicada. Resultado **certificable**: `chaos/live_a7` está validado **19/19** —12 del contrato
  de la guarda + 7 real-PG— contra una BD dedicada `bolsa_v1_a7`, en dos pasadas: con el stack **parado**
  (árbol sin commitear) y con el stack **vivo** sobre el árbol sellado. Lo que ninguna de las dos certifica
  es la convivencia con el stack **sobre la BD compartida**: ahí la guarda seguirá diagnosticando y saltando
  (correctamente), y la certificación de release sigue siendo el job `a7-gate` del CI, con BD dedicada y
  stack inexistente. El diff no toca `live_orders`, el recovery ni `execution_events`.
* `N-1` no cambia `capabilities` (cobertura del proveedor): cambia lo que **hace** el interruptor y lo dice
  en la descripción y en la UI.

## Verificabilidad en el tag

Cada fila se comprueba sobre `12e2c871` y sobre el árbol del tag `v2.88.175-beta`, sin depender de lo que
este documento afirme.

| Hallazgo | Commit | Nodo que lo prueba |
| --- | --- | --- |
| P-1b | `12e2c871` | `test_auto_v2_audit_regressions.py::test_p1b_a_real_reason_supersedes_the_placeholder`, `::test_p1b_the_placeholder_never_degrades_a_real_reason`, `::test_p1b_a_real_reason_does_not_reset_a_real_latch`, `::test_p1b_a_real_halt_discovered_under_the_placeholder_is_never_released`, `::test_p1b_the_placeholder_is_not_persisted_as_a_durable_halt` |
| N-1 | `12e2c871` | `packages/py/application/tests/test_yahoo_traffic_gate.py` (11 casos), `apps/api-python/tests/test_market_fx_provider_gate.py` (3) |
| N-2 | `12e2c871` | `packages/py/market/tests/test_yahoo_spot_price.py` (10 casos), `packages/py/application/tests/test_fx_rates.py` (10) |
| N-3 | `12e2c871` | `packages/py/application/tests/test_database_backup.py::test_an_unaudited_copy_is_declared_not_silent`, `apps/api-python/tests/test_database_backup_api.py::test_an_unaudited_copy_still_returns_200_and_declares_it`, `apps/web/src/features/config/database-maintenance-panel.test.tsx` |
| N-4 | `12e2c871` | `test_summary_stale_uses_the_oldest_measurement_not_the_newest`, `test_monitor_is_due_by_the_oldest_provider_measurement` |
| Obs. 1 | `12e2c871` | `apps/api-python/tests/test_database_purge_role_gate.py` (4 casos parametrizados) |
| Obs. 2 | `12e2c871` | `packages/py/infrastructure/tests/test_backup_runner.py::test_the_declared_file_wins_over_a_foreign_file_in_the_directory` (+2) |
| Guarda de exclusividad | `12e2c871` | `apps/api-python/tests/chaos/live_a7/test_exclusivity_guard.py` (12 casos) |
| Cableado del gate A7 en el CI | `12e2c871` | `apps/api-python/tests/test_release_tag_ci_a7_gate_wiring.py` (5 casos) |
| Purga en esquema sin migrar | `12e2c871` | `apps/api-python/tests/test_residual_purge_schema_guard.py` (3 casos) |

## Ficheros

| Capa | Ficheros |
| --- | --- |
| Motor / kill switch | `packages/py/analytics/src/bolsa_analytics/cognitive/hard_kill_switch.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` |
| Proveedores / mercado | `packages/py/market/src/bolsa_market/yahoo_client.py`, `packages/py/application/src/bolsa_application/market_providers.py`, `.../fx.py`, `packages/py/domain/src/bolsa_domain/entities/market_provider.py`, `apps/api-python/src/bolsa_api/api/v1/routes/market.py` |
| Copias / mantenimiento | `packages/py/application/src/bolsa_application/database_backup.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/backup_runner.py`, `apps/api-python/src/bolsa_api/api/v1/routes/database.py`, `apps/api-python/src/bolsa_api/schemas/database_maintenance.py` |
| Frontend | `apps/web/src/features/config/database-maintenance-panel.tsx`, `apps/web/src/features/settings/market-providers-status-card.tsx`, `apps/web/src/features/sync/sync-settings-panel.tsx`, `packages/shared/src/types.ts`, contrato generado (`apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`) |
| Guarda de exclusividad (`chaos/live_a7`) | `apps/api-python/tests/chaos/live_a7/_exclusivity_guard.py` (**nuevo**), `.../test_exclusivity_guard.py` (**nuevo**), `.../test_c3_crash_injection_recovery_worker.py`, `.../conftest.py` |
| Tripwires del cierre | `apps/api-python/tests/test_release_tag_ci_a7_gate_wiring.py` (**nuevo**), `apps/api-python/tests/test_residual_purge_schema_guard.py` (**nuevo**), `apps/api-python/tests/conftest.py` (guarda de esquema en la purga) |
