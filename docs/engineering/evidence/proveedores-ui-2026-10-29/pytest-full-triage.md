# Triaje de la suite completa de Python (2026-10-29)

Comando ejecutado:

```
python -m pytest packages/py/application/tests apps/api-python/tests -q -p no:cacheprovider
```

Resultado: **4455 passed, 5 failed**, 197 warnings, 653 s (`pytest-full.txt`).

Este documento separa lo que es del área (proveedores y sincronismo) de lo que no, con la
comprobación hecha en cada caso. **Nada de lo de abajo se cuenta como verde del área.**

## 1. Fallos reproducidos en aislamiento como rojo real (fuera del área)

| Test | Error | Diagnóstico |
| --- | --- | --- |
| `test_auto_dia_d_trace_pg.py::test_dia_d_chain_is_fully_traced_and_pnl_reconciled_pg` | `monitor=-27.255746 libro=-27.255745` | Diferencia de **1×10⁻⁶ €** en la conciliación monitor ↔ libro aplicado |
| `test_auto_dia_d_trace_pg.py::test_dia_d_trace_reconciles_per_value_and_cycle_pg` | `ciclos=-66.705234 libro=-66.705233` | Misma diferencia de 1×10⁻⁶ € |
| `test_auto_estudio_chain_evidence_pg.py::test_estudio_chain_evidence_covers_nine_steps_per_value_pg` | `ciclos=-66.705234 libro=-66.705233` | Idéntica a la anterior (mismo arnés de día dorado) |

Se reproducen **también en aislamiento**, así que no son interferencia entre tests. Pertenecen
a la conciliación de P&L del ciclo AUTO/día-D (arnés `test_golden_day_v2_process_pg`), no al
camino de proveedores:

- La diferencia es de 10⁻⁶ € (unidades de cuantización monetaria), no un valor distinto: un
  cambio de configuración de proveedor no puede producir ese desplazamiento.
- Los ficheros de ese camino (`auto_v2_entry.py`, `portfolio_decision_engine.py`,
  `auto_reason_codes.py`) se modificaron por última vez a las **09:40–09:58**, antes del
  trabajo de esta área (**11:21**), y su diff no toca la cuantización de dinero.
- No los arregla este plan: quedan declarados como **rojo preexistente** del área AUTO, para
  tratarse en su propia consolidación.

## 2. Fallos de entorno (pasan en aislamiento) — causa raíz verificada

| Test | Error en la suite completa | Comprobación |
| --- | --- | --- |
| `test_discovery_evidence_snapshot_pg.py::test_migration_040_roundtrip` | `DeadlockDetected` al hacer `ALTER TABLE positions DROP CONSTRAINT …` (bloqueado por otro proceso) | Pasa al ejecutarse solo (7 passed) |
| `chaos/live_a7/test_c3_crash_injection_recovery_worker.py::test_c3b_crash_after_resolve_put_no_double_on_relaunch` | `primer resolve no reclamó la fila: 'drained=0 resolved=0'` | Pasa al ejecutarse solo (1 passed) |

### Causa raíz (confirmada, no supuesta)

Los tests de roundtrip de migraciones **no usan una BD aislada**: leen
`get_settings().database_url` (la BD real `bolsa_v1`, puerto 5432) y ejecutan
`alembic downgrade … → upgrade head` sobre ella. Ejemplo real en
`test_discovery_evidence_snapshot_pg.py`:

```python
settings = get_settings()
url = settings.database_url          # ← la BD del operador
command.downgrade(cfg, "039_research_trials_regime")   # ← borra la 040..059
command.upgrade(cfg, "head")                          # ← las recrea VACÍAS
```

Consecuencias observadas y verificadas en esta pasada:

1. **El deadlock** del `040_roundtrip` es el `ALTER TABLE` del test chocando con el API en
   vivo (que estaba sirviendo peticiones en ese momento).
2. **El stack en vivo perdió tablas a media ejecución** (10:31–10:58): el log del API muestra
   `relation "alert_deliveries" does not exist`, `relation "auto_ops_jobs" does not exist` y
   `column signal_alert_subscriptions.account_id does not exist` mientras la suite corría.
   Vite acabó saliendo con `exit=1` y el stack se detuvo.
3. **Se borró la configuración de proveedores de la sesión en vivo**: el `downgrade` elimina
   `market_provider_settings` (migración 059) y el `upgrade` la recrea vacía, de modo que la
   primera lectura posterior la vuelve a sembrar con **defaults**. Estado actual leído
   directamente de la BD (`select … from market_provider_settings`):

   ```
   alembic head: 059_market_provider_settings
   ('xtb',   priority=20, min_interval_seconds=0, last_check_at=NULL)
   ('yahoo', priority=10, min_interval_seconds=2, last_check_at=NULL)
   ```

   Es decir: la persistencia **funcionó** (está probada por `red-providers-tras-recarga.json`,
   capturado tras recargar con los valores aún en BD) y lo que ocurrió después fue un **borrado
   por la suite**, no un fallo del guardado.

### Regla operativa que se deriva

- La suite completa **no debe ejecutarse con el stack en vivo levantado**: no solo fallan dos
  tests, sino que el propio test suite muta el esquema de la BD compartida.
- Las pruebas PG **del área de proveedores** sí son seguras: escriben dentro de una transacción
  que revierten (`test_market_providers_pg.py`), pero eso **no** protege de los roundtrips de
  migración de otras suites.
- No se toca nada de esto aquí: es un límite del arnés de tests, ajeno al área.

## 3. Lo que sí es del área

- `packages/py/application/tests/test_market_providers.py`
- `packages/py/application/tests/test_sync_provider_gate.py`
- `apps/api-python/tests/test_market_providers_api.py`
- `apps/api-python/tests/test_market_providers_pg.py`

**38 passed** (`pytest-area.txt`), incluidos los PG reales de la migración `059`.
