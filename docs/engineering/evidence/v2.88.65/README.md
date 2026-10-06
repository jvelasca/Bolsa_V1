# Evidencia `v2.88.65-beta` — `NÚCLEO`: **la venta compara Decimal**

**Producto:** `V2.88.65-beta` · **Package:** `2.11.65-beta` · **AsOf:** 2026-10-06. **SIN migración.**

**Padre:** [`v2.88.64`](../v2.88.64/README.md).

## Qué cambia

`execute_trade` ya no admite una venta con `float(posición) < cantidad`. Usa `sell_quantity_exceeds_held`: `held < Decimal(str(quantity))`.

El caso que el float dejaba pasar:

- posición `999999999999.000062`
- `float` de esa cantidad, cuyo `Decimal(str(...))` es `999999999999.0001`
- el `float` no ve exceso; el `Decimal` sí

## Test

`pytest packages/py/infrastructure/tests/test_sell_admission_decimal.py` — **2 passed**.
