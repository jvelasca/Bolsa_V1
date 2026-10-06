# Evidencia `v2.88.67-beta` — `NÚCLEO`: **cash suelto deja de ser puerta pública**

**Producto:** `V2.88.67-beta` · **Package:** `2.11.67-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.**

**Padre:** [`v2.88.66`](../v2.88.66/README.md).

## Qué cambia

`SqlAlchemyPortfolioRepository` ya no tiene `add_cash` ni `deduct_cash`. El movimiento de la fila es `_credit_cash_row` / `_debit_cash_row`. Depósito, retirada y custodia siguen escribiendo cash y ledger en el mismo savepoint.

## Test

`test_b3_deuda_directa_rompe_invariant_documental` — **passed**. Comprueba que la puerta pública no existe.
