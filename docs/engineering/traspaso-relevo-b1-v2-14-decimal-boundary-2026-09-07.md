# Traspaso de relevo — B1 V2.14 (Decimal al boundary financiero)

Fecha: 2026-09-07 · Rama `v2-14-financial-execution` (desde `v2-13-1-rc-honesty-remediation`).
Repo: `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`. Shell PowerShell (no `&&`).

> Sigue a [D0](./traspaso-relevo-d0-v2-14-foundation-2026-09-07.md). Pega todo este texto en el agente que continúe V2.14.

---

## RESULTADO B1 — auditor audit P1-03 + P2-02 + P2-03 (parcial decretada)

Eliminado el hueco-float en la **cadena broker/máquina/orders** (la más delicada para la decisión de fills):

- `packages/py/market/src/bolsa_market/providers.py`:
  - nueva helper `_to_dec()` (cualquier float/wire a `Decimal`, nunca negativo/NaN).
  - `XtbBridgeOrderState.filled_quantity/remaining_quantity` → `Decimal` (parse de `GET /orders/{id}`)
    tras `query_order` con `_to_dec` en lugar de `float`.
  - `XtbBridgeAccountCash.cash` → `Decimal` y `fetch_cash()` lo produce con `_to_dec`.
  - `XtbBridgePosition.quantity` → `Decimal` y `fetch_positions()` lo produce en `Decimal` (sin float).
- `packages/py/application/src/bolsa_application/live_order_query.py`:
  - `BrokerOrderQueryResult.filled_quantity/remaining_quantity` → `Decimal | None`, con `__post_init__`
    que cuantiza a `Decimal(6dp)` (`ROUND_HALF_UP`) y acepta float wire/DTO de constructores (test-safe).
  - helper `_to_decimal()` compartida.
- `packages/py/application/src/bolsa_application/broker_adapter.py` (`XtbLiveOrderQueryAdapter`):
  - `_qty/_dec` devuelven `Decimal` cuantizado (se elimina el ida-y-vuelta `Decimal→float(q)`); ya no baja a float.
- `packages/py/application/src/bolsa_application/live_order_machine_reconcile.py`:
  - `LiveOrderDrift.broker_filled/remaining_quantity` → `Decimal | None` (antes `float`); se hidrata desde
    `BrokerOrderQueryResult` directo (sin `or 0.0`).

Política `PositionState` (documentada, NO forzada a Decimal esta faena): `PositionState` es autoridad
post-entrada y sigue en float/JSONB (cuantos 6dp cuando se deriva w/ `_to_decimal`); la vía que sí alimenta
**Ledger** (fills LIVEs → `ExecuteTrade`/`append_*`) es Decimal en `live_orders` y en `BrokerOrderQueryResult`/
`drift`. La conversión a Decimal completa del agregado Account/Position del lado LR-1 (cash/positions snap
EPS) se difiere a **E2** (Full reconciliation) para no romper aislado un subsistema read-only de cifrado.

## Verificación B1 (pasada)

- ruff 0 en los 4 ficheros. mypy scoped 0 (follow-imports=skip en los 4).
- pytest 34 (query adapter + drift) · 19 (+reconcile ledger) · 26 (+recovery worker) · 11 opening-gate.
- Test del bridge real productor (XtbBridgeClient.fetch_cash/fetch_positions/query_order) no ejercido en CI
  unitaria por no mock HTTP; se recomienda un `test_xtb_bridge_client_decimal` en B2/E1 (módulo market).

## Archivos de B1

MOD (4): providers.py · live_order_query.py · live_order_machine_reconcile.py · broker_adapter.py.
NUEVO: este traspaso. ÍNDICE: entrada continuación (#92) en engineering-index.

## Remanente B1 honesto (no regresión)

`LiveLedgerReconciliation`/`LiveHoldingSnap`/`LivePositionSnap` EPS siguen en float para el comparador
read-only; NO es depósito a ledger. Positions/cash real XTB en el DOMINIO — no hay DB que lo tome aún en
float para gasto (solo lectura). Análisis a E2.

FIN DE TRASPASO B1
