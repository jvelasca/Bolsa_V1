# Evidencia `v2.88.72-beta` — `NÚCLEO`: **certificación del libro AUTO**

**Producto:** `V2.88.72-beta` · **Package:** `2.11.72-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.**

**Padre:** [`v2.88.71`](../v2.88.71/README.md).

## Qué cambia

`transactions.idempotency_key` queda `NOT NULL` en SQLAlchemy y en Prisma. No hay migración nueva: Alembic 050 sigue siendo el `ALTER` y conserva su identificador.

El día SIM sobre PostgreSQL afirma, para cada fill, transacción, posición, ledger y cash. Tras la venta de cierre la posición desaparece y el cash es el depósito más el P&L menos las comisiones. Reaplicar el fill devuelve `already_applied` y no mueve el libro.

Dos `ExecuteTrade` simultáneos con la misma clave devuelven la misma transacción. Hay una fila, una posición y Σ ledger = cash.

## Test

`test_finance_auto_day_materializes_executetrade_exactly_once`, `test_concurrent_same_key_buy_returns_original_once`, `test_m2_ledger_cash_reconciliation`, `test_get_summary_no_price_fallback` y `test_v190_golden_confirm_position_sync_lifecycle_snapshot` — **passed** (PostgreSQL local).
