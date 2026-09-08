# RELEVO — v2.14-beta elevado a `main` → auditoría externa (2026-09-08)

> **Padre:** [índice #89–96](./engineering-index-2026-08-03.md) · plan [V2.14 Financial Execution & Full Reconciliation](./plan-v2-14-financial-execution-reconciliation-2026-09-07.md).
> **Estado:** **CERRADO.** V2.14 **elevada a `main`** en el SHA certificado por Release-tag CI.
> **Tip código (cert)**: [`78dd3f9a`](https://github.com/jvelasca/Bolsa_V1/commit/78dd3f9a) == `main` == tag [`v2.14-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.14-beta).
> **Package `1.43.0-beta`** (bump en este commit de elevación, sobre `1.42.0-beta`).

## 1. Elevación (auditable desde GitHub)

| Pieza          | Valor                                                                                                                                                                |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rama           | `main` → `78dd3f9a` (fast-forward desde `v2.13-beta` `6e279e2d`)                                                                                                     |
| Tag            | [`v2.14-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.14-beta) → `78dd3f9a`                                                                            |
| Previo         | [`v2.13-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.13-beta) → `6e279e2d`                                                                            |
| Release-tag CI | [run 34208259186](https://github.com/jvelasca/Bolsa_V1/actions/runs/34208259186) **`conclusion=success`** (SHA `78dd3f9a`, status artifact `release-tag-ci-summary`) |
| Bump           | `1.42.0-beta` → **`1.43.0-beta`** (commit de elevación en `main`)                                                                                                    |
| Código tip     | `78dd3f9a` (feat E2-full + C1 fixes mypy) · `24b36bf4` (stamp docs, en la rama)                                                                                      |

## 2. Qué cubre la versión elevada (padre decreto)

Cerrado aquí (faenas previas en índice #89–95, faena de hoy en índice #96):

1. **E2-full**: P2-01 writer durable `live_drift` (`publish_order_live_drifts`; kinds
   accionables `cancel_broker_side`/`fill_unseen`/`state_mismatch`; `query_unavailable`
   transitorio NO abre veto) + P1-02 recon posición LR-1 continua, **ambos** cableados en
   el recovery worker baja el MISMO go (`LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED`/gate). NOTA
   de auditoría: sigue **GATED** — nada se materializa como Position/Ledger real por defecto.
2. **C1 real-PG**: migración `022_live_orders_exec` (head) + batería real-PostgreSQL en
   scratch `bolsa_c1_scratch` 001→022 — dedup OPEN 2-sesión real, `query_unavailable` NO abre,
   `sync_opening_incidents` idempotente, CHECKs financieros 021 vigentes bajo 022.
3. **Release-tag CI real**: `v2.14-beta` → run 34208259186 `conclusion=success` observado
   (disciplina V2.10.1: GREEN solo con success en GitHub).

Detalle por faena: [`traspaso-relevo-e2-v2-14-order-drift-durable-2026-09-08.md`](./traspaso-relevo-e2-v2-14-order-drift-durable-2026-09-08.md) (ADDENDO C1) y docs de faena previas.

## 3. Qué auditar externamente desde GitHub

- **Bifurcación de referencia `main`** (source of truth del auditor) en el SHA `78dd3f9a`.
- Tag de pre-release [`v2.14-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.14-beta) == `main`.
- Tronco de la cadena auditora: `Fill → ExecutionEvent → PositionState → Ledger → Full Reconciliation`,
  idempotencia, partial fills, Decimal end-to-end, reconciliación account/position/order,
  cancelación broker, recovery post-restart, UNKNOWN, kill switch, concurrencia multi-worker,
  PostgreSQL real + migración `022`, CI Release-tag.
- Referencias directas: migración `packages/py/infrastructure/alembic/versions/022_live_orders_exec.py`;
  `execution_event.py` (idempotencia `ON CONFLICT`); `order_live_drift_incident.py` (P2-01);
  `live_order_machine_reconcile.py`/`reconcile_live_positions.py` (P1-02/LR-1);
  `operational_incident_store.py` (dedup OPEN multi-worker); recovery worker (cableado gated);
  test real-PG `apps/api-python/tests/test_e2_v2_14_incident_dedup_pg.py`.

## 4. Freeze

NO LIVE · `PAPER_D_EXECUTE` default off · GATED (`LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED`,
`E2_PG_REQUIRED`) fail-closed · E1 apply a Ledger/Position **NO** por defecto (H4) ·
XTB cancel real **PARKED** (bridge sin `POST /orders/{id}/cancel`) · package `1.43.0-beta`.

## 5. Next (para el auditor)

- Auditar contra `main @ 78dd3f9a` == tag `v2.14-beta` (Release-tag CI run 34208259186 success).
- V2.15 Shadow LIVE / V2.16 cert (decreto numeración) — no reabrir V2.14 salvo hallazgo de auditoría.

FIN DEL RELEVO — V2.14 preparada para auditoría externa.
