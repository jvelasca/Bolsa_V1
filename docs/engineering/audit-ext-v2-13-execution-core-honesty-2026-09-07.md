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

| Hallazgo                               | V2.12 | V2.13 | Estado               | Veredicto auditor                                                         |
| -------------------------------------- | ----- | ----- | -------------------- | ------------------------------------------------------------------------- |
| UNKNOWN sin re-POST                    | 🟢    | 🟢    | Cerrado              | `ALLOWED_LIVE_ORDER_TRANSITIONS` no contiene `SUBMITTING` desde `UNKNOWN` |
| UNKNOWN durable                        | 🟢    | 🟢    | Cerrado              | `live_orders` PG + worker persiste la fila; no sintetiza ledger           |
| Multi-worker recovery                  | 🔴/🟡 | 🟡    | **A comprobar**      | Mecanismo con lease correcto **pero sin test PG real de 2 sesiones**      |
| Partial fill individual                | 🟡    | 🟡    | A comprobar          | Transición a nivel de orden; `execute_trade` por fill **PARKED**          |
| Idempotencia financiera                | 🔴    | 🔴    | Sigue abierta        | `financial_apply_count` **cero** llamadores en prod                       |
| Fill individual (`venue_execution_id`) | 🟡    | 🟡    | A comprobar          | No hay columna/identity por fill en `live_orders`                         |
| Comisiones                             | 🟡    | 🟡    | A comprobar          | Sin evento de fill/comisión en cadena LIVE                                |
| Decimal                                | 🔴    | 🔴    | **A medio corregir** | DB=NUMERIC pero dominio+store+TS = `float`/`number`                       |
| DB invariants                          | 🟡    | 🟢    | Mejorado             | 021 + CHECK; ver §3 caveat de ruta real                                   |
| Cancel broker-side                     | 🔴    | 🟡    | A comprobar          | Modelo honesto; round-trip real **PARKED**                                |
| XTB query real                         | 🔴    | 🔴    | No desbloqueado      | `_no_query_provider`=None en prod; cliente XTB sin endpoint query         |
| Reconciliation                         | 🟡    | 🟡    | A comprobar          | LR-1 cash+positions; **no cubre máquina `live_orders`**                   |
| LIVE real (fondo)                      | 🔴    | 🔴/🟡 | No desbloquear       | Bridge mock-only; cliente XTB solo `quote/cash/positions/POST /orders`    |

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

---

## 6. Referencias

- Commit: `34285584` · rama `live-honesty-post-tip-2026-09-07`.
- Código: `packages/py/analytics/.../cognitive/live_order.py` · `packages/py/application/.../live_order_store.py` · `apps/api-python/.../background/live_order_recovery_worker.py` · `packages/shared/src/cognitive/live-order.ts` · `packages/py/infrastructure/.../models/tables.py` · migración `021_live_orders_financial_constraints.py`.
