# Evidencia `v2.88.69-beta` — `NÚCLEO`: **idempotency_key NOT NULL**

**Producto:** `V2.88.69-beta` · **Package:** `2.11.69-beta` · **AsOf:** 2026-10-06. **Alembic:** `050_transaction_idempotency_key_not_null`. **Δ motor = 0.**

**Padre:** [`v2.88.68`](../v2.88.68/README.md).

## Qué cambia

La migración cuenta los nulos de `transactions.idempotency_key`. Cero nulos: `SET NOT NULL`. Cualquier nulo: `RuntimeError`, sin `UPDATE` y sin tocar el unique `(portfolio_id, idempotency_key)`.

## Test

`test_050_aborts_when_null_keys_exist` y `test_050_source_does_not_backfill_or_drop_unique` — **passed**.

## Lo que no se hizo

No se contaron filas vivas. PostgreSQL en localhost no responde, así que este sello no afirma que el conteo sea cero. La guarda vive en `upgrade`.
