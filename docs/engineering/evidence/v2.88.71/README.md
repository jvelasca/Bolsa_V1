# Evidencia `v2.88.71-beta` — `NÚCLEO`: **dividendo con retención**

**Producto:** `V2.88.71-beta` · **Package:** `2.11.71-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.**

**Padre:** [`v2.88.70`](../v2.88.70/README.md).

## Qué cambia

`CreditDividend` acredita el bruto y retiene con `dividend_withholding_pct` del perfil de la cuenta. Los asientos `dividend` y `dividend_withholding` comparten `idempotency_key` y el mismo savepoint. Un reintento no vuelve a mover el cash.

El turno AUTO no llama a este use-case. No hay UI ni lectura de hechos societarios.

## Test

`test_split_dividend_withholds_nineteen_percent`, `test_credit_dividend_posts_gross_and_withholding_once`, `test_credit_dividend_rejects_reused_key_with_other_gross` y `test_auto_turn_does_not_call_the_dividend_use_case` — **passed**.
