# Arranque del auditor — `v2.80-beta` / `AUTO-MATERIAL-8`: MARKET WINDOW

> **Para:** el auditor externo de `v2.80-beta`. **AsOf:** 2026-09-27.
> **Objeto:** tag anotado `v2.80-beta` · **Versión:** `2.05.0-beta` · **Base:** `v2.79-beta`
> (`0314199c`, `2.04.0-beta`) · **Alembic head:** `046_fill_reference_mid` (**SIN migración**).
> **Método esperado:** clon **temporal** del tag (nunca el árbol local); demostrar que el árbol queda
> **intacto** (tree id idéntico antes/después de la matriz y `git status --porcelain` vacío).

## 1. Los 12 puntos del arranque (qué mirar y por qué)

1. **El freeze no se toca.** `git diff v2.79-beta..v2.80-beta -- auto_simulation_worker.py
   portfolio_decision_engine.py opportunity_ranker.py market_regime_gate.py paper_material_readiness.py
   packages/py/application/src/bolsa_application/auto_reason_codes.py` ⇒ **vacío**. `TOP_N` default `5`;
   `DATA_GATE_POLICY_VERSION == "auto15-v1"`; `ADAPTIVE_POLICY_VERSION == "auto18-v1"`; umbrales
   `32/3/8/4/2`.
2. **Auditoría 2 (`STATE_UNRESOLVED`).** `operability_state` devuelve `unresolved` para `proposals>0`,
   `vetoes==0` y sin fill/cierre; `vetoed` si hay veto; `operated` si hay fill/close; la **ausencia**
   sigue ganando (`unknown`). El orden se ve en el código.
3. **Auditoría 1 §20 (aviso).** Un código desconocido ⇒ `otherCount>0`, `contractViolation is True`, y el
   render publica `ALERTA CONTRATO: other>0 …`; **no** hay excepción ni `exit` distinto de `0` con filas.
4. **Auditoría 1 §21 (cobertura).** `DECLARED_REASON_CODES == frozenset(VETO_BUCKET_BY_REASON) |
   NON_VETO_REASON_CODES`; `reason_catalog_coverage` publica `declared`/`observed`/`unknown`; el día de
   reversión (`_AUDIT_REVERSAL_DAY`) tiene `observed==4`, `unknown==0`.
5. **Fila de ventana.** `build_window_row` publica el linaje (`account`, `instruments`, `versions`,
   `cycleIds`) y **declara** los huecos como `None` (`pairCapable`/`pairActive`/`priceSources`). El R sale
   de `measured_r` (el mismo lector que el informe).
6. **Gate de la ventana.** `window_gate` cuenta **días distintos** (4 filas del mismo día ⇒ `days==1`);
   `READY` sólo con ≥4 días **y** ≥2 episodios **y** ≥32 ciclos medibles.
7. **Capturador read-only.** `v2_80_market_window.py` no escribe en el journal durable ni en
   `evidence_runs`/`evidence_validations`; su único append es el journal de `operability_runs/`
   (gitignoreado); `exit 2` sin días.
8. **Registro en CI.** `test_operability_window.py` **explícito** en `python-ci.yml` (job `quality`) y en
   `release-tag-ci.yml` (job `python`).
9. **Mutaciones.** `M220`–`M225` muerden y restauran byte a byte; matriz **225/225**; `git status` limpio.
10. **Compuertas.** `ruff` limpio, import-linter `4 kept/0 broken`, `mypy` `0 issues (506 files)`,
    `alembic heads` `046_fill_reference_mid`.
11. **`H-4`.** Comprobar que **sigue ABIERTO** y que el nuevo instrumento lo **declara**:
    `build_operability_record({"journalReasons": ["signal_duplicate:2", …], "turnTotals": {"vetoes": 0, …}})`
    ⇒ `otherCount>0`, `contractViolation is True`, `reasonCatalogCoverage["unknown"]==1` y el render con
    `ALERTA CONTRATO`.
12. **CI del tag.** `Release tag CI` de `v2.80-beta` verde en la primera pasada, con los jobs PG intactos.

## 2. Qué NO se puede afirmar (declarado por la fase)

- **`P3-2`/`P3-3` siguen ABIERTAS**: sin material PAPER real no hay ventana; la tabla se re-deriva con
  fixtures. **No hubo ventana** ⇒ nada de estadística certificada.
- **Sin PostgreSQL local**: los jobs PG se verifican **por CI**.
- **`H-4` no se cierra aquí**: esta fase lo hace **visible**, no lo corrige.
- `P3-5` y `OBS-5` siguen declaradas.

## 3. Trampas conocidas (leer antes de medir)

- La **`other` vacía** de un smoke con `proposals=0` **no** prueba nada: el caso que importa es el **día
  operado** (`_AUDIT_REVERSAL_DAY`), donde `vetoCounted == vetoes == 2` y `other` está vacía.
- El commit con la **cita del CI** vive **fuera** del tag (patrón `v2.74`–`v2.79`): `release-tag-ci.yml`
  sólo corre al empujar el tag, así que la evidencia del CI no puede habitar el commit del sello.
- `v2_77_market_operability.py` (sonda del runner JSON de `v2.77`) **no** está en el diff; el capturador de
  esta fase es **otro** fichero (`v2_80_market_window.py`, journal durable).
