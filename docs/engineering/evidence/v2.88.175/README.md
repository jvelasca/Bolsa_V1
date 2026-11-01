# Evidencia `v2.88.175-beta` — el cierre de la auditoría `.174` se vuelve verificable: hallazgos sellados, gate A7 duro y la purga sin aviso inexacto

## 1. Qué publica este sello

Sello de **corrección** posterior a `2.11.174-beta`. No mueve motor ni decisión:

- **`Δ motor = 0`** · **`Δ decisión = 0`** · **SIN migración** (`head` sigue
  `062_sync_settings_check_backfill`).
- **Bump** `2.11.174-beta` → `2.11.175-beta` (+ los **13** `meta.bump`, **14 literales**;
  `test_dia_d_bump_guard` **2 passed**; el literal congelado `2.11.0-beta` de `v2_87` no se toca).
- **Pin de ventana re-anclado DESPUÉS del bump** (`pnpm window:freeze` → `freeze OK`).

Cierra los cinco hallazgos de `AUDITORIA 1` y sus dos observaciones: **P-1b** (el placeholder del kill switch
no enmascara ni borra una parada real), **N-1** (el interruptor de Yahoo se cierra en el cliente: no hay
tráfico, y `/market/fx` declara `409 provider_disabled:yahoo`), **N-2** (precios no finitos se rechazan en
origen, en la sonda y en FX), **N-3** (una copia sin auditoría se declara), **N-4** («caducado» se mide
contra el proveedor más viejo), **Obs. 1** (los dos `purge` exigen admin con auth) y **Obs. 2** (el fichero
creado se lee del script, no por delta).

Añade además lo que el expediente de auditoría dejó abierto:

- **Gate A7 duro y anclado.** El job `a7-gate` fija `LIVE_A7_PG_REQUIRED=1` en el `env` del job y del step de
  pytest, `certify` lo tiene en `needs` y hace `exit 1` si no es `success`. Un skip deja el sello en rojo.
  `test_release_tag_ci_a7_gate_wiring.py` (5 casos) lo impide deshacer en silencio.
- **Purga sin aviso inexacto.** `purge_all_residuals` comprueba `to_regclass('public.investment_accounts')` y,
  con el esquema sin migrar, no purga y no avisa. `test_residual_purge_schema_guard.py` (3 casos).

El detalle por hallazgo —causa raíz, corrección, prueba que la rompe y tabla de verificabilidad por nodo—
está en [`../../cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md`](../../cierre-hallazgos-auditoria-v2.88.174-2026-11-01.md).

## 2. Qué NO certifica

| No certifica | Por qué |
| --- | --- |
| **Que `.174` contuviera este código** | No lo contenía: `git cat-file -e "v2.88.174-beta:<ruta>"` falla para `_exclusivity_guard.py` y para el documento de cierre. Ese tag se auditó tal cual se publicó y **no se reescribe**. |
| **La GitHub Release** | No se emite, mismo criterio que `.173` y `.174`. |
| **Rentabilidad ni operativa** | Un sello de corrección no añade evidencia de resultados. AUTO **OFF**; PAPER **`INCONCLUSIVE`**. |
| **Las suites completas sobre este árbol** | No se repitieron. Las cifras de `.174` (`4 582` / `1 454` / `2 677`) **no se heredan**: aquí solo se midieron los nodos tocados. |
| **`chaos/live_a7` conviviendo con el stack sobre la BD compartida** | Ahí la guarda seguirá diagnosticando y saltando (correctamente). La certificación es el job `a7-gate`, con BD dedicada `bolsa_v1_a7` y sin stack. |
| **El E2E en la nube** | No se repitió E2E para este sello: el diff no toca flujo de UI nuevo (solo avisos de N-3 y descripciones de N-1). |

## 3. Ficheros del sello

| Capa | Ficheros |
| --- | --- |
| Motor / kill switch | `packages/py/analytics/src/bolsa_analytics/cognitive/hard_kill_switch.py`, `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` |
| Proveedores / mercado | `packages/py/market/src/bolsa_market/yahoo_client.py`, `packages/py/application/src/bolsa_application/market_providers.py`, `.../fx.py`, `packages/py/domain/src/bolsa_domain/entities/market_provider.py`, `apps/api-python/src/bolsa_api/api/v1/routes/market.py` |
| Copias / mantenimiento | `packages/py/application/src/bolsa_application/database_backup.py`, `packages/py/infrastructure/src/bolsa_infrastructure/database/backup_runner.py`, `apps/api-python/src/bolsa_api/api/v1/routes/database.py`, `.../schemas/database_maintenance.py` |
| Frontend | `apps/web/src/features/config/database-maintenance-panel.tsx`, `.../settings/market-providers-status-card.tsx`, `.../sync/sync-settings-panel.tsx`, `packages/shared/src/types.ts`, contrato generado (`apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts`) |
| Guarda de exclusividad | `apps/api-python/tests/chaos/live_a7/_exclusivity_guard.py` (**nuevo**), `.../test_exclusivity_guard.py` (**nuevo**), `.../test_c3_crash_injection_recovery_worker.py`, `.../conftest.py` |
| Tripwires del cierre | `apps/api-python/tests/test_release_tag_ci_a7_gate_wiring.py` (**nuevo**), `apps/api-python/tests/test_residual_purge_schema_guard.py` (**nuevo**), `apps/api-python/tests/conftest.py` |

## 4. Verificación medida (local, 2026-11-01)

Cada fila es una ejecución distinta; no se suman.

| Comprobación | Comando | Salida | Código |
| --- | --- | --- | --- |
| `pytest` lado API (8 ficheros tocados) | `test_auto_v2_audit_regressions`, `test_market_fx_provider_gate`, `test_database_purge_role_gate`, `test_database_backup_api`, `test_residual_purge_schema_guard`, `test_release_tag_ci_a7_gate_wiring`, `chaos/live_a7/test_exclusivity_guard`, `test_ci_test_selection_census` | **81 passed** | `0` |
| `pytest` lado librerías (6 ficheros tocados) | `test_yahoo_spot_price`, `test_yahoo_traffic_gate`, `test_fx_rates`, `test_market_providers`, `test_database_backup`, `test_backup_runner` | **92 passed** | `0` |
| `pytest` bump guard | `apps/api-python/tests/test_dia_d_bump_guard.py` | **2 passed** | `0` |
| `chaos/live_a7` real-PG (stack vivo) | `DATABASE_URL=…/bolsa_v1_a7 DB_NAME=bolsa_v1_a7 LIVE_A7_PG_REQUIRED=1 pytest apps/api-python/tests/chaos/live_a7 -q -rs` | **19 passed, 0 skipped**, 15,19 s | `0` |
| `chaos/live_a7` real-PG (stack parado) | misma batería sobre el delta de corrección | **19 passed, 0 skipped**, 17,12 s | `0` |
| Purga en BD vacía | `pytest apps/api-python/tests/test_residual_purge_schema_guard.py -q` con `DATABASE_URL=…/bolsa_v1_a7` recién creada | **3 passed**, sin aviso `does not exist` | `0` |
| `ruff check` (ficheros tocados) | `ruff check … --config pyproject.toml` | **All checks passed** | `0` |
| `pnpm types:py` (mypy) | — | **582 ficheros**, sin errores | `0` |
| `pnpm contract:check` | — | **OK** | `0` |
| `tsc -b --noEmit` (web) | — | **limpio** | `0` |
| `vitest` (2 ficheros web tocados) | `database-maintenance-panel`, `market-providers-status-card` | **15 passed** (2 ficheros) | `0` |
| `pnpm window:freeze` | tras el re-anclaje | **freeze OK** | `0` |
| `pnpm window:test` | — | **50 / 50** | `0` |

Estado de las BD tras la pasada de `chaos/live_a7`: `bolsa_v1_a7` con `live_orders` 0 (`UNKNOWN` 0) y
`execution_events` 0; `bolsa_v1` intacta (`live_orders` 0, head `062_sync_settings_check_backfill`).

## 5. Límites declarados

- El sello es el `Release tag CI` **del tag**: los gates de rama no lo sustituyen.
- `chaos/live_a7` certifica C3 **aislado** contra BD dedicada; la convivencia con el stack sobre la BD
  compartida queda diagnosticada y saltada a propósito, no certificada.
- La guarda detecta un worker ajeno **si dejó un claim fresco** en la preflight; uno que arranque después no
  se intercepta (el escenario lo diagnosticaría por lease). Los puertos son contexto, no prueba.
- No se re-miden E2E ni las suites completas sobre este árbol.

## 6. Publicación

| Paso | Estado |
| --- | --- |
| Delta de corrección | `12e2c871` |
| Cierre documental (expediente) | `aef2187b` |
| Bump `2.11.175-beta` | `4b3bbad3` |
| Re-anclaje del pin | `0e5a7517` |
| Tag anotado `v2.88.175-beta` | sobre el commit de este documento (cierre documental), patrón `.173`/`.174` |
| `Release tag CI` del tag | pendiente del push; se anotan los run IDs al leerlos |
| GitHub Release | **no se emite** (mismo criterio que `.173` y `.174`) |

## 7. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Una parada real no se pierde bajo el placeholder | `test_p1b_a_real_halt_discovered_under_the_placeholder_is_never_released` |
| 2 | El placeholder no viaja al espejo durable | `test_p1b_the_placeholder_is_not_persisted_as_a_durable_halt` (0 `save`) |
| 3 | Con Yahoo apagado no hay tráfico | `test_every_yahoo_route_is_blocked_when_the_provider_is_disabled` |
| 4 | `/market/fx` declara configuración, no caída | `test_a_disabled_provider_returns_409_and_performs_no_traffic` |
| 5 | Un precio basura no verifica ni cotiza | parametrizados de N-2 (0, negativo, `nan`, `inf`) |
| 6 | Una copia sin auditoría se declara | `test_an_unaudited_copy_still_returns_200_and_declares_it` |
| 7 | «Caducado» se mide contra el más viejo | `test_summary_stale_uses_the_oldest_measurement_not_the_newest` |
| 8 | Los purges exigen admin con auth | `test_with_auth_enabled_a_non_admin_cannot_purge` |
| 9 | Se informa el fichero del script, no el ajeno | `test_the_declared_file_wins_over_a_foreign_file_in_the_directory` |
| 10 | Una BD no dedicada no certifica la batería | `pytest …/live_a7 -rs` ⇒ 7 skips con la causa; `LIVE_A7_PG_REQUIRED=1` ⇒ `AssertionError` |
| 11 | Un A7 verde con skips no sella | `test_release_tag_ci_a7_gate_wiring.py`: quitar el gate del job o del step, sacar `a7-gate` de `needs` o borrar el `exit 1` ⇒ rojo |
| 12 | La purga no habla de un esquema que no existe y sigue viva cuando existe | `test_residual_purge_schema_guard.py` (cero `DELETE` sin esquema; borra con esquema) |

## 8. Bitácora

| Paso | Hecho |
| --- | --- |
| 1 | Auditado el tag `.174`: `17ab0ef9` no contiene la guarda ni el documento de cierre. El delta estaba sin commitear. |
| 2 | Corregida la purga (guarda de esquema) y sellado con `test_residual_purge_schema_guard.py`. |
| 3 | Reforzado el mensaje de la guarda (el run no certifica) y anclado el cableado de `a7-gate` con `test_release_tag_ci_a7_gate_wiring.py`. |
| 4 | Repetida `chaos/live_a7` contra `bolsa_v1_a7`: 19/19 con el stack vivo y sin el aviso de la purga. |
| 5 | Bump `2.11.175-beta` (`4b3bbad3`) y re-anclaje del pin (`0e5a7517`), `freeze OK` y `window:test` 50/50. |
| 6 | Este documento; el tag va sobre su commit. |
