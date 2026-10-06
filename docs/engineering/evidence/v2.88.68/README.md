# Evidencia `v2.88.68-beta` — `NÚCLEO`: **CHECK de cash y cantidad**

**Producto:** `V2.88.68-beta` · **Package:** `2.11.68-beta` · **AsOf:** 2026-10-06. **Alembic:** `049_cash_quantity_nonneg_check`. **Δ motor = 0.**

**Padre:** [`v2.88.67`](../v2.88.67/README.md).

## Qué cambia

La migración cuenta `portfolios.cash < 0` y `positions.quantity < 0`. Si alguna cuenta no es cero, aborta con la muestra de filas y no borra nada. Si ambas son cero, crea `ck_portfolios_cash_nonneg` y `ck_positions_quantity_nonneg`.

## Test

`test_049_aborts_when_cash_or_quantity_is_negative` y `test_049_source_does_not_delete_rows` — **passed**.

## Lo que no se hizo

No se aplicó `alembic upgrade` en esta máquina: PostgreSQL en localhost no responde. No hay recuento inventado de filas vivas.
