# Evidencia `v2.88.64-beta` — `NÚCLEO`: **positions.quantity contra el ledger**

**Producto:** `V2.88.64-beta` · **Package:** `2.11.64-beta` · **AsOf:** 2026-10-06. **Δ motor = 0**. **SIN migración.**

**Padre:** [`v2.88.63`](../v2.88.63/README.md).

## Qué añade

`test_position_quantity_matches_signed_ledger_qty` ejecuta una compra de 10 y una venta de 4 con `ExecuteTrade` y compara `positions.quantity` con la suma firmada de las filas de ledger `buy` y `sell` del mismo instrumento. La fila de comisión no tiene cantidad.

Si esa igualdad falla, este sello no reescribe el libro. El test es la barrera.

## Ejecución local

`pytest packages/py/infrastructure/tests/test_m2_ledger_cash_reconciliation.py::test_position_quantity_matches_signed_ledger_qty` — **skipped**. PostgreSQL en `localhost:5432` agotó el tiempo de conexión. No es un rojo.
