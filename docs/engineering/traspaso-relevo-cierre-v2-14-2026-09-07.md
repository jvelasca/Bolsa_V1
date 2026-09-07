# Relevo — Cierre V2.14 (para agente de mañana 2026-09-08)

Pegar TODO este texto en el agente que cierre V2.14 mañana, sobre la rama `v2-14-financial-execution`
(base: `git describe` = v2.13-beta-2-g<commit V2.14 últimas>; repo en
`C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`).

> Propósito: terminar **E2 completo** y **C1** (real-PG + Release-tag CI). Honestidad: no afirmar CI GREEN
> sin observar `conclusion=success` en GitHub; no aplicar la migración 022 al PG del dev sin go del usuario.

---

## 1. Estado commiteado y VERIFICADO (no rehacer)

Rama local `v2-14-financial-execution` (faenas con ruff/mypy/pytest verdes):

- `b54c92d8` D0 — decree V2.14 (Financial Execution & Full Reconciliation) · índice #89–91.
- `462a30cb` B1 — Decimal al boundary financiero (broker order/cash/position query + drift) · #92.
- `67867a04` B2 — lease por env `LIVE_RECOVERY_CLAIM_STALE_SECONDS` · cancel XTB **PARKED** · #93.
- `f29e452c` E1 — `022_live_orders_exec` (observabilidad cols + tabla `execution_events`) · ORM ·
  `execution_event.py` idempotencia `ON CONFLICT execution_id` **GATED** · tests · #94.
- `2942fec1` E2-PARTIAL — dedup OPEN multi-worker en `PostgresOperationalIncidentStore.put` · #95.

Docs de relevo por faena (leer en orden): `traspaso-relevo-d0/b1/b2/e1/e2-dedup-partial-2026-09-07.md`

- decree `plan-v2-14-financial-execution-reconciliation-2026-09-07.md` (numeración).

## 2. PENDIENTE (hacer mañana, agente nuevo)

### 2.1 E2 (full):

1. `reconcile_live_ledger.py`/`live_order_machine_reconcile.py` → extender a **posición broker↔local**
   (v.g. AAPL 120 vs 100) y derivar drift+futuro incidente. `XtbBridgePosition.quantity` ya Decimal (B1).
2. **Durable máquina-drift (P2-01)**: un writer que convierta `LiveOrderDrift` en `OperationalIncident`
   durable `live_drift` por cuenta (reusar `sync_opening_incidents`/OR-4, ya cableados como veto de
   apertura); encenderlo en el recovery worker bajo go; + OR-4 new-opening DENY.
3. Test PG **2-sesión** de dedup OPEN (el corte 2942fec1 está semanticamente probado; falta el determinista
   real PG) y tests de drift position→incident.

### 2.2 C1 (real-PG + Release-tag) — SOLO con go del usuario:

1. Aplicar la migración al PG local: `cd packages/py/infrastructure && <venv>/python -m alembic -c alembic.ini
upgrade head` (DB ahora en `021_live_orders_fin`; verificable con `command.current`). Muta el PG dev →
   pide go (approval nativo) ANTES de correr. Inyectar legacy-like rows + verificar constraints + downgrade.
2. Guards head ya endulzados a `startswith("02")`. Verificar `execution_events` materializable con
   `PostgresExecutionEventStore`.
3. Battery multi-worker/concurrency/recon completa sobre PG real.
4. **Release-tag CI**: subir/abrir rama+tag del cierre, dejar correr GH Actions y leer `gh run watch`/
   `statuses`; escribir en el handover `Release-tag CI = GREEN` SOLO si `conclusion=success` observado
   (disciplina V2.10.1). No fabricarlo.

## 3. Fronteras que NO cruzar

- Nunca abrir el apply de `execution_event.py` a Ledger/Position real por defecto (E1 GATED): solo tras go,
  revisado H4/H3.
- Cancel XTB: PARKED (bridge/mock NO tiene `POST /orders/{id}/cancel`).
- Preservar `apps/api-python/logs/**` + `packages/py/application/logs/**` (.jsonl) y los cambios de
  worktree e2e/web ajenos. `git add` explícito por faena, nunca `-A`.

FIN DEL RELEVO (preparado para agente de 2026-09-08)
