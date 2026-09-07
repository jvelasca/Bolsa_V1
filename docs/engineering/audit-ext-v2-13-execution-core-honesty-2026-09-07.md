# Audit ext — V2.13 Live Execution Core (honesty)

> **AsOf:** 2026-09-07 · **Baseline auditado:** commit `34285584` — _"V2.13: live execution gates (XL-3 concurrency + financial invariants + honest cancel + reconcile)"_ (rama `live-honesty-post-tip-2026-09-07`, HEAD).  
> **Tip previo:** [`v2.12-beta`](./traspaso-relevo-tag-v2-12-beta-2026-09-07.md) → `6f8c747b` · package `1.41.0-beta`.  
> **Padres:** [relevo XL-3 durable core](./traspaso-relevo-xl3-durable-core-2026-09-07.md) · [roadmap LIVE Execution](./roadmap-live-execution-core-2026-09-07.md) · [honesty bridge XTB](./honesty-pack-xtb-bridge-external-2026-09-07.md).  
> **Veredicto:** la arquitectura XL-3 **no se ha roto**. La V2.13 aporta lease cross-PID (`SKIP LOCKED`), `NUMERIC(18,6)` **físico**, CHECK de invariante, y modelo honesto de cancel. **No obstante** Decimal sigue en `float` en dominio+store+TS, la cadena financiera LiveOrder→Ledger sigue **PARKED**, XTB query real no existe, no hay idempotencia por fill, y la reconciliación no cubre `live_orders`. → **V2.13 ≠ LIVE READY.**

Método: evidencia sobre **código real** (no documentación). Se consultó dominio, store PG/InMemory, worker de recovery, cableado de scheduler/dependencies, adaptador broker XTB, migración `021`, tabla ORM `live_orders`, y reconcile. Cada hallazgo va con su `file:line` y veredicto.

---

## 0. Lo que V2.13 hizo (delta 1 commit desde v2.12-beta)

| Pieza           | Qué cambió                                                                                              | Estado          |
| --------------- | ------------------------------------------------------------------------------------------------------- | --------------- |
| Lease recovery  | `claim_unknown_batch` (SELECT…FOR UPDATE SKIP LOCKED + `recovery_worker_id/claimed_at`) + ventana stale | 🟢 implementado |
| `put()` atómico | `ON CONFLICT DO UPDATE` (elimina TOCTOU read-modify-write)                                              | 🟢 implementado |
| Numérico físico | Migration `021`: cantidad/filled/remaining → `NUMERIC(18,6)`; ORM `Mapped[Decimal]`                     | 🟢 capa física  |
| Invariantes DB  | CHECK `quantity>0`, `filled∈[0,quantity]`, `remaining≥0`, `filled+remaining=quantity`                   | 🟢 implementado |
| Honest-cancel   | columnas `cancel_requested_*` (decisión local) vs `broker_cancel_confirmed_at` (resultado venue)        | 🟢 modelado     |
| Reconcile orden | `reconcile_live_order_vs_broker` declarativo (detecta, no auto-heal)                                    | 🟢 dominio      |

---

## 1. Tabla de hallazgos (matriz)

| Hallazgo                               | V2.12 | V2.13 | Estado               | Veredicto auditor                                                                        |
| -------------------------------------- | ----- | ----- | -------------------- | ---------------------------------------------------------------------------------------- |
| UNKNOWN sin re-POST                    | 🟢    | 🟢    | Cerrado              | `ALLOWED_LIVE_ORDER_TRANSITIONS` no contiene `SUBMITTING` desde `UNKNOWN`                |
| UNKNOWN durable                        | 🟢    | 🟢    | Cerrado              | `live_orders` PG + worker persiste la fila; no sintetiza ledger                          |
| Multi-worker recovery                  | 🔴/🟡 | 🟢    | **Cerrado (H2)**     | Test PG real de `claim_unknown_batch` con 2 sesiones/tx simultáneas (§5bis)              |
| Partial fill individual                | 🟡    | 🟡    | Gate (H3)            | Transición a nivel de orden; `execute_trade`/applier por fill **PARKED**                 |
| Idempotencia financiera                | 🔴    | 🔴    | Sigue abierta (H3)   | `financial_apply_count` **cero** llamadores en prod; decisión §5tetra                    |
| Fill individual (`venue_execution_id`) | 🟡    | 🟡    | Gate (H3)            | No hay columna/identity por fill en `live_orders` (decisión §5tetra)                     |
| Comisiones                             | 🟡    | 🟡    | Gate (H3)            | Sin evento de fill/comisión en cadena LIVE (decisión §5tetra)                            |
| Decimal                                | 🔴    | 🟢    | **Cerrado dominio**  | Dominio+store a `Decimal(6dp)` (invariante exacto); TS = proyección `number` (§5bis)     |
| DB invariants                          | 🟡    | 🟢    | Mejorado             | 021 + CHECK; ver §3 caveat de ruta real                                                  |
| Cancel broker-side                     | 🔴    | 🟢    | **Cerrado (H5)**     | `CANCEL_REQUESTED`+`set_broker_cancel_confirmed`; sólo ack del venue→`CANCELLED` (§5bis) |
| XTB query real                         | 🔴    | 🟢    | **Cerrado contrato** | Provider real por defecto con `XTB_BRIDGE_URL`; fail-closed `unavailable` (H6, §5ter)    |
| Reconciliation                         | 🟡    | 🟢    | **Mejorado (H7)**    | Reconcile drift de máquina `live_orders` colgado al tick (drift-only) (§5ter)            |
| LIVE real (fondo)                      | 🔴    | 🔴/🟡 | No desbloquear       | Tramo financiero `Broker→Ledger→Reconciliation` real sigue **gate** (H3·§5tetra)         |

---

## 2. Hallazgos con evidencia

### H1 — Decimal "a medio corregir" (P1 del owner, matizado)

Migration `021` y ORM sí mueven la capa física a `NUMERIC(18,6)`:

```python
    # 2) Determinismo numérico: Float → NUMERIC(18,6) en cantidades.
    for col in ("quantity", "filled_quantity", "remaining_quantity"):
        op.alter_column(_TABLE, col, type_=sa.Numeric(18, 6),
                        existing_type=sa.Float(), nullable=False)
```

Pero **dominio y store reconvierten a Python `float`** en cada escritura/lectura y validación:

```python
    quantity: float
    filled_quantity: float
    remaining_quantity: float
```

```python
    quantity=float(row.quantity),            # Decimal(BD) → float (dominio)
    filled_quantity=float(row.filled_quantity),
    remaining_quantity=float(row.remaining_quantity),
```

Su espejo TS usa `number`/`Number(...)` (binary float) — `packages/shared/src/cognitive/live-order.ts`.

**Lectura**: la _persistencia_ dejó de ser Float adánico, pero la _aritmética financiera_ (filled/remaining, `abs(filled - quantity) > 1e-9`, precio medio, comisiones) sigue sobre `float` en toda la pila: DB decimal, dominio float-in/float-out. Deuda **movida de DB → capa de aplicación**, no cerrada. Persistir con precisión decimal y releer a float reintroduce la pérdida en el siguiente compute.

### H2 — Multi-worker: mecanismo con lease, **sin prueba real de 2 sesiones**

Postura correcta y atómica en claim y put:

```python
    .with_for_update(skip_locked=True)
    ...
    pg_insert(LiveOrderRow).values(**values).on_conflict_do_update(...)  # put atómico
```

El propio diff V2.13 apunta el límite duradero del claim (flush sin commit, dependiente del `put()` por fila). Además no existe un test PG de **dos sesiones/transacciones concurrentes** sobre `claim_unknown_batch`: la exclusión mutua se cubre en InMemory (monoproceso) y el test de "no TOCTOU" llega a mockear `session.commit`. Es exactamente el patrón que "pasa en unit y puede fallar bajo concurrencia real".

### H3 — Cadena financiera LiveOrder→Ledger: **no construida (PARKED)**

`financial_apply_count` es un marcador monotónico de primera aplicación previsto para idempotencia del FILLED, pero ningún llamador de producción lo invoca (`apply_financial=True` solo en `tests/test_live_order.py`). El worker de recovery persiste la fila **sin sintetizar ledger** (veto XL-3 en su docstring). No existe flujo real `LiveOrder → PositionState → Ledger`; la única ruta LIVE que toca ledger es el **atajo síncrono** del adaptador XTB (§ H4). Sin identity por fill (`venue_execution_id` ausente en `live_orders`; esa identidad solo existe en el subsistema paper/lifecycle).

### H4 — Atajo síncrono `filled → execute_trade` (slice XL-2) sigue vivo

```python
    if order.status == "filled":
        trade = await self._execute_trade.execute(...)   # ledger directo, salta la máquina XL-3
```

Solo alcanzable cuando el bridge devuelve `filled` **síncrono** (hoy: el mock). Un broker real asíncrono nace `submitted`/`UNKNOWN`, y para ese camino **no hay query que lo cierre**. Resultado híbrido: "LIVE→ledger certificado" solo existe por el atajo mock-síncrono mientras el asíncrono queda abierto.

### H5 — Cancel: modelo honesto, pero sin consumidor que lo proteja

Columnas `cancel_requested_*` (intención) separadas de `broker_cancel_confirmed_at` (resultado). `cancel_order` pasa a `CANCELLED` (terminal) y deja confirm `NULL`. **No hay** estado `CANCEL_REQUESTED` en el grafo; `LiveOrder.to_dict` y su espejo TS emiten `status:"CANCELLED"` sin campo broker-confirm. Ni una capa de producción llama hoy `cancel_order` / `list_open_orders` / `get_cancel_meta` (todo en tests). Por tanto **cualquier** capa que llame `store.cancel_order` puede presentar `CANCELLED` sin confirm del venue.

### H6 — XTB query real no existe (worker inert en prod)

`start_live_order_recovery_worker` se arranca en `scheduler_worker.py` **solo** con `session_factory` (sin `query_provider`). El default `_no_query_provider` devuelve `None`:

```python
    if query is None or not order.venue_order_id:
        return await _refresh_unknown(store, order, account_id=account_id)
```

Por tanto en producción toda fila `UNKNOWN` queda `UNKNOWN` (solo bump `updated_at`) y el `claim_unknown_batch` drena pero no resuelve. El `XtbBridgeClient` real (`bolsa_market/providers.py`) no expone query de estado de orden ni cancel (solo `quote/cash/positions/POST /orders`). El único polling funcional es con `MockLiveOrderQuery`.

### H7 — Reconciliation no cubre la máquina `live_orders`

Los módulos de reconcile (LR-1/Excel apertura) no referencian `live_orders`/`list_open_orders`/la máquina. LR-1 (`XtbBridgeLiveVenueAdapter`) es read-only cash+positions. `list_open_orders`/`list_unknown` existen en el store pero **no hay orquestador** que las contraste con broker-truth para drift/pendientes. Reconciliación de orders/fills/pending de la máquina XL-3: ausente.

### H8 — Sin bypass en Decision/Risk/Authorization (buena noticia)

`live_auto` es estrictamente **dry-run**: `_evaluate_live_dry_run` pasa por `check_opening(auto_live=True)`, mandate, kill-switch, recon-veto sin `execute_trade`. La máquina `live_orders` solo se escribe con `pb.venue=="LIVE"` y `submitted|unknown` (no `executed|rejected`). No se identificó ruta que rodee Risk/Authorization en el nuevo código.

---

## 3. Caveats de evidencia verificados

- Ruta real del ORM: `packages/py/application/../bolsa_infrastructure/database/models/tables.py` (`LiveOrderRow`, `Numeric(18,6)` + `Mapped[Decimal]`).
- Migration `021` es idempotente/standalone (offline-safe, sin imports de ORM).
- Commit auditado = único delta entre `v2.12-beta` y HEAD; archivos tocados: recovery worker, store, dominio `live_order`, migración `021`, ORM `tables`, espejo TS `live-order.ts`, + tests.

---

## 4. Qué NO afirmar

- V2.13 = LIVE READY / Execution Core certificado.
- Que el `NUMERIC(18,6)` hace determinista el led leer/calcular en `float`.
- Que el lease cross-PID está validado bajo dos workers reales de PG.
- Que un UNKNOWN real se resuelve en runtime (no hay query provider cableado).
- Que `CANCELLED` sin `broker_cancel_confirmed_at` no puede mostrarse como cancel real.
- Que la reconciliación orden/fill/pendiente cubre `live_orders`.

---

## 5. Camino a LIVE READY (no desbloqueado)

Demostrar, ya sea en sandbox/mock con provider de query inyectado, el ciclo completo:
Decision → Proposal → Risk → Authorization → Submit → UNKNOWN → Broker Query → PARTIAL → FILL → PositionState → Ledger → Reconciliation, bajo crash + retry + dos workers + callback duplicado + caída de DB + timeout.
Hoy el tramo Broker Query→Ledger del LiveOrder es inalcanzable en runtime por H6 y H3/H4.

### Deuda prioritaria (por severidad)

1. Cerrar Decimal en dominio+store+TS (H1) — cumple `CHECK filled+remaining=quantity` en memoria.
2. Test PG real de 2 sesiones en `claim_unknown_batch` (H2) para subir multi-worker a 🟢 o confirmar bug.
3. Cercar el atajo síncrono `XtbBrokerAdapter.filled→execute_trade` (H4): el fill LIVE debe pasar por máquina XL-3 + ledger con identity.
4. Cablear broker-cancel: estado `CANCEL_REQUESTED` + consumidor que solo presente `CANCELLED` con `broker_cancel_confirmed` (H5).
5. XTB query real (`GET /orders/{id}`) + reconcile de `live_orders` (H6, H7).

---

## 5bis. Remediación aplicada (post-baseline, mismo tópico)

Tras la auditoría se cerraron **4 de los 6 puntos de deuda prioritaria** en código
(sin levantar el umbral LIVE READY), con suites locales verdes:

| Deuda                  | Qué se hizo                                                                                                                                                                                                                                                                                                                   | Dónde                                                               |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **H1 Decimal**         | Dominio PY migrado a `Decimal(6dp)` (paridad `NUMERIC(18,6)`): campos, `__post_init__` coerciona **toda** ruta de construcción, `filled+remaining==quantity` **exacto** en memoria (sin epsilon). `live_order_from_row` deja de castear a float. TS espejo **documentado** como proyección `number` (no aritmética de libro). | `cognitive/live_order.py` · `live_order_store.py` · `live-order.ts` |
| **H2 concurrencia PG** | Añadido test PG real de `claim_unknown_batch` con **2 sesiones/tx simultáneas** (sin mockear commit): determinista (A lockea, B la SKIP) + no-overlap al dividir lote. Corre en PG test (skips sin `DATABASE_URL`).                                                                                                           | `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`  |
| **H4 atajo síncrono**  | `XtbBrokerAdapter.submit` ya **no** invoca `execute_trade`; un `filled` síncrono retorna `unknown / live_sync_fill_blocked_requires_reconcile` → la máquina queda UNKNOWN durable para resolver por query real. Sync mock `filled`→ledger eliminado (tests migrados).                                                         | `broker_adapter.py` + tests                                         |
| **H5 cancel honesto**  | Estado **`CANCEL_REQUESTED`** en el grafo (PY+TS): `cancel_order` (decisión local) → `CANCEL_REQUESTED` NO terminal con `cancel_requested_*` sin `broker_cancel_confirmed_at`; **solo** `set_broker_cancel_confirmed` promueve a `CANCELLED` (terminal). Un consumidor ya no puede leer `CANCELLED` sin ack del venue.        | `live_order.py` · `live_order_store.py` · `live-order.ts`           |

**Pendiente (no aplicado aquí):** H6 XTB query real (`GET /orders/{id}`) y reconcile de
`live_orders` [H7]. Siguen siendo condición para subir a LIVE READY, junto a
demuestrar el ciclo completo crash+retry+doble worker+callback duplicado+fallo DB+timeout.

## 5ter. Avance H6 + H7 (segunda iteración post-baseline)

En esta iteración se **cerró parte de la deuda de broker-query y reconcile**, sin
levantar aún el umbral LIVE READY:

| Deuda                                          | Qué se hizo                                                                                                                                                                                                                                                                                                           | Dónde                                                                                                                                                    |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | -------- | ---------------------------------------------------------------------------------------------------------------- | ------ | ------------------ | ----------------------------- |
| **H6 contrato query mock**                     | El bridge mock (`scripts/xtb-bridge-mock.mjs`) ahora registra órdenes creadas y expone `GET /orders/{id}` (life-cycle ``working                                                                                                                                                                                       | partial                                                                                                                                                  | filled | rejected | cancelled`con`filledQty/remainingQty`). Parametrizable: `XTB_BRIDGE_ORDER_STATE`. POST conserva shape `submitted | filled | rejected`` legacy. | `scripts/xtb-bridge-mock.mjs` |
| **H6 query real en cliente**                   | `XtbBridgeClient.query_order` → `GET /orders/{vid}`; fail-closed ante 404/timeout/estado no reconocible lanza (worker lo traduce a `unavailable`/UNKNOWN). Validado con smoke real sobre el mock (submit→working/partial con qty exacta).                                                                             | `packages/py/market/.../providers.py` · `XtbBridgeOrderState` · `XtbBridgeOrderQueryState`                                                               |
| **H6 adapter real del recovery**               | `XtbLiveOrderQueryAdapter` implementa `LiveOrderQueryPort` mapeando bridge→`BrokerOrderQueryResult` con Decimal(6dp) exacto (tapona el hueco H1 del float en la cadena broker→máquina). Nunca fabrica ledger.                                                                                                         | `packages/py/application/.../broker_adapter.py` · `test_xtb_live_query_adapter.py` (6 tests)                                                             |
| **H6 wire default provider**                   | El recovery worker por defecto usa un query provider REAL cuando hay `XTB_BRIDGE_URL` (venu LIVE); sin ella cae a fail-closed (UNKNOWN).                                                                                                                                                                              | `apps/api-python/.../live_order_recovery_worker.py` (`build_live_query_provider`)                                                                        |
| **H7 reconcile máquina `live_orders` (drift)** | Nuevo orquestador read-only que consulta open (SUBMITTED/WORKING/PARTIAL/CANCEL_REQUESTED con id de venue) vía el mismo provider y reporta drift `cancel_broker_side`/`fill_unseen`/`state_mismatch`/`query_unavailable` — **no auto-heal, no muta** (fail-closed). Colgado al tick del recovery tras drenar UNKNOWN. | `packages/py/application/.../live_order_machine_reconcile.py` · `_reconcile_open_orders` en el worker · `test_live_order_machine_reconcile.py` (7 tests) |

**Faltante honesto (no ejecutable sin stack PG + bridge mock levantado):** demostración
**en runtime** del ciclo completo de 2 workers **reales de PG** resolviendo UNKNOWN
contra el bridge mock (submit→UNKNOWN→query→working/partial/filled) + callback duplicado

- timeout + drift H7. Hoy el e2e multiworker PG real (H2) valida solo el _claim/lease_;
  el tramo _query real broker→resolución_ está cubierto por unit del adapter/reconcile y
  por smoke real de cliente→mock, pero **no** por un e2e PG que integre worker+PG+bridge.
  Sigue siendo condición del paso a LIVE READY junto a idempotencia financiera (H3).

---

## 5tetra. Cierre de iteración — decisión H3 (mercado NO ampliado) y estado a auditar

Iteración post-§5ter sobre la **última deuda restante al umbral: H3** (idempotencia
financiera / cadena `LiveOrder → Ledger`). Se re-exploró el booking real del repo
(`ExecuteTrade.execute` → `portfolio_repo.execute_trade` + `ledger_repo.append_trade` +
`sync_position_after_ledger_fill`) y el contrato actual del push real (H6).

**Conclusión de la decisión tomada (registro honesto):**

1. El tramo financiero LIVE **no se amplía ni se construye en esta iteración**. La venu
   real (XTB `GET /orders/{id}`) **no garantiza por contrato** ni precio de ejecución por
   fill, ni `fills[]` con un `venueExecutionId` por llenada, ni fee desglosado. Hoy el
   resultado de la query (H6) sólo trae cantidades agregadas (`filledQty/remainingQty`).
2. Sin esas piezas (importe real por fill + identidad por llenada) **no existe un applier
   honesto**: abrir `ledger/positions` con un precio que la venu no confirmó **sería
   síntesis**, exactamente lo que esta auditoría veta. `financial_apply_count` seguiría
   siendo un marcador in-memory sin productor real y **cero llamadores** en prod.
3. Por tanto **H3 permanece como deuda + gate**, NO como código parcial "casi listo".
   Diseño del future H3 (si el contrato del bridge llega a dar `venueExecutionId` + price):
   reusar el backstop DB real `uq_ledger_entries_account_reference`
   (`(account_id, reference_type, reference_id, type)`) para idempotencia por fill;
   identity por llenada = `venue_order_id + fill sequence` (hoy no existe columna/identity);
   el applier se dispararía en `resolve_one_unknown` (UNKNOWN→PARTIAL/FILLED) y en el
   drift `fill_unseen` de H7 — con veto XL-3 intacto (no sintetizar `execute_trade`).

**Estado de la versión a subir/auditar:**

- HEAD `/ v2-13-1-rc-honesty-remediation`: `656c8b37` (V2.13.1-rc + H6/H7). Working tree
  intacto (sin cambios pendientes de cadena LIVE; sólo ediciones ajenas e2e/web-doc logs).
- Suites locales verdes (unit/integration): H1/H2/H4/H5 (§5bis) + H6/H7 (§5ter).
- **No se proclama LIVE READY financiero.** El tramo `Broker-Query→Ledger→Reconciliation`
  sobre una venu REAL sigue pendiente y es **gate**; ver §5 y §5ter.
- H3 (idempotencia financiera) → **Sigue abierta** (marcador). No hay bypass en
  Decision/Risk/Authorization (§H8), que se mantiene como buena noticia intacta.

## 6. Referencias

- Commit: `34285584` · rama `live-honesty-post-tip-2026-09-07`.
- Código: `packages/py/analytics/.../cognitive/live_order.py` · `packages/py/application/.../live_order_store.py` · `apps/api-python/.../background/live_order_recovery_worker.py` · `packages/shared/src/cognitive/live-order.ts` · `packages/py/infrastructure/.../models/tables.py` · migración `021_live_orders_financial_constraints.py`.
