# Arranque del auditor — v2.43.3-beta (AUTO-3 reliability closure)

**Fecha:** 2026-09-20 · **Ref a atacar:** `v2.43.3-beta` (`1.68.3-beta`) · **Pack que manda:**
[`audit-pack-v2.43.3-auto-3-reliability-closure-2026-09-20.md`](./audit-pack-v2.43.3-auto-3-reliability-closure-2026-09-20.md).
Si algo de este arranque contradice al pack, **manda el pack**.

Este documento es de **solo lectura** y existe para una cosa: que el auditor externo no gaste su
presupuesto redisculpiendo lo ya medido. Las rutas y líneas están **verificadas en el árbol** del commit
de fase; cada afirmación trae **el comando exacto** para medirla.

---

## 1. Qué se cierra aquí (y por qué importa)

Cinco hallazgos, **una sola familia de error**: un hecho que pertenecía a la **RAM del proceso** y que
el sistema presentaba como si fuera del **sistema**.

1. **P0-1** el `HardKillSwitch` era un objeto por worker: `WORKER 1 → KILL ON → CRASH → WORKER 2`
   reabría el motor.
2. **P0-2** la identidad de una salida era `exit:{engine}:{symbol}:{seq}` con `seq` de un contador de
   proceso que **volvía a 0** ⇒ un reinicio podía **reutilizar** una identidad histórica.
3. **P1-4** si la reserva de salida no era durable, el SELL se emitía **igual** y sin rastro.
4. **P1-5** el fold ordenaba por **cadena** ISO, no por instante.
5. **P0-3** las cuatro ventanas de crash no estaban cubiertas por ningún test.

## 2. Orden de ataque recomendado (por coste/beneficio)

### A1 · El arranque vuelve a olvidar el HALT (P0-1) — _el más caro si falla_

```bash
sed -n '1290,1340p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # _v2_load_kill_state
sed -n '1370,1415p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # engage/release durable
sed -n '170,237p'   packages/py/application/src/bolsa_application/kill_switch_store.py   # PostgresKillSwitchStore
```

Preguntas abiertas (busca el camino en el que **no** se restaura o en el que se restaura **de más**):

- ¿Algún camino de arranque llama a `readopt_positions()` **antes** de `_v2_load_kill_state()`?
- ¿Un `engaged=true` con `reason` **no canónico** se rehidrata como `SYSTEM_ERROR` (fail-closed) y no
  como "sin motivo ⇒ sin parada"? (`HardKillSwitch.from_persisted`).
- ¿Un `release` con `reconciliation_ok=False` **no** libera, y con `reconciliation_id` vacío **tampoco**?
- ¿Un fallo de **lectura** del store se interpreta alguna vez como "no hay parada"? (debe vetar).
- ¿`_v2_persist_kill_state` puede devolver `True` sin haber escrito (store `None`)? El contrato dice
  `False`; comprueba que quien lo consume no lo toma por protegido.

### A2 · La identidad de salida se puede reutilizar o perder (P0-2)

```bash
sed -n '2140,2245p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # _v2_reserve_exit
sed -n '2436,2478p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # _v2_sync_exit_orders
sed -n '186,250p'   packages/py/analytics/src/bolsa_analytics/cognitive/exit_order.py     # with_*/apply_fill/as_emergency/abandon
git diff -- apps/api-python/src/bolsa_api/background/auto_simulation_worker.py | rg '_v2_exit_seq'
```

Preguntas abiertas:

- ¿Queda **algún** uso de `_v2_exit_seq` o de un contador de proceso en la formación de identidades?
- El `_v2_sync_exit_orders` casa por `order.reservation_id` contra `outcomes` (que son
  `reservation.reservation_id`): ¿hay un camino donde la reserva se libera con **otro** id y el intent
  queda vivo para siempre? ¿Y donde dos reservas comparten instrumento y el intent se aplica a la que
  no era?
- `_v2_apply_exit_fill` cae al store si el intent no está en la caché: ¿puede **resetear** un intent
  avanzado (aplicar dos veces el mismo fill)? La idempotencia real la da `execution_id`, no el intent:
  mide si un fill re-aplicado mueve `filled_qty` dos veces.
- ¿`ExitOrder.apply_fill` puede dejar `remaining_qty` negativo o superar `requested_qty`? (dice que no;
  mide con un fill mayor que la cola).

### A3 · La política B no es B (P1-4)

```bash
sed -n '2205,2240p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # rama de fallo
sed -n '3530,3550p' apps/api-python/src/bolsa_api/background/auto_simulation_worker.py   # veto del call-site
uv run pytest apps/api-python/tests/test_auto_v44_exit_crash_matrix.py -q -k p1_4
```

Preguntas abiertas: ¿hay algún otro call-site de `_v2_reserve_exit` que ignore el `None`? ¿El intent de
emergencia guarda `requested_qty` correcta y **no** cuenta como materializado? ¿El HALT por
`SYSTEM_ERROR` se persiste **y** se declara en el journal?

### A4 · El orden temporal (P1-5)

```bash
sed -n '320,372p' packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py
uv run pytest packages/py/analytics/tests/test_position_ledger.py -q
```

Preguntas abiertas: un **naive** se asume UTC (¿es correcta esa suposición en todos los productores?);
un `int`/`float` se interpreta como epoch (**decisión declarada**: sí, es un instante), un `bool` **no**;
¿un hecho sin fecha determina que el P&L del instrumento quede `PARTIAL`/`UNKNOWN` y que ningún lector
lo presente como exacto?

### A5 · La 043 (migración) y su reversibilidad

```bash
sed -n '145,215p' packages/py/infrastructure/alembic/versions/043_exit_identity_and_kill_state.py
rg -n "AutoKillStateRow|AutoExitOrderRow|exit_order_id" \
   packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py
```

Preguntas abiertas: paridad 1:1 migración↔row model (tipos, `NULL`/`default`, longitudes);
`downgrade` **simétrico** (¿retira el índice **antes** de la columna? ¿y las tablas después?);
`reason VARCHAR(32)` (¿cabe todo motivo canónico? `RECONCILIATION_FAILURE` son 22);
`String(16)` en `side` (¿cabe "sell"/"buy"/algo más?).

## 3. Qué **NO** es un hallazgo (declarado por adelantado)

- **Los tests PG no se midieron en la máquina del autor.** Es un **límite declarado**, no un agujero:
  el gate `AUTO_RESERVATION_PG_REQUIRED=1` convierte un skip mudo en fallo duro en CI. Si el auditor
  tiene PG, es la medida que más aporta (comando en el §6 del pack).
- `force_protective_exits` sin productor automático y el emisor de `RECONCILED` inexistente: **deuda
  heredada declarada** de `AUTO-2`, fuera del alcance de esta versión.
- El gobernador **default OFF** y sus umbrales sin calibrar: decisión de roadmap, no un bug.
- Los **4 nacimientos verdes** de la matriz de `v2.43.2` (M6, M10, M12, M13): confirmación, no hallazgo
  nuevo (§10.1 del pack anterior).
- **Nota de método**: una mutación **verde** no es por defecto agujero de cobertura. Hay que descartar
  antes que el mutante sea **más fuerte** o **más débil** que el bug (errata ya declarada en `v2.43.1`).

## 4. Comandos de arranque (copia-pega)

```bash
git log --oneline -5
cat package.json | head -5                      # 1.68.3-beta
cd packages/py/infrastructure && uv run alembic heads    # 043_exit_identity_and_kill_state (head)

uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el gobernador NO se movió (debe salir vacío y exit 0)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores   # 2042 passed
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores  # 2053 passed
uv run --no-sync python apps/api-python/scripts/v2_43_3_mutation_audit.py     # 6/6 muerden
```

## 5. Formato de hallazgo

`P0/P1/P2 · afirmación · ruta:línea · comando · salida · ¿ya declarado en el pack §7?` — a responder en
el hilo del [issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62).
