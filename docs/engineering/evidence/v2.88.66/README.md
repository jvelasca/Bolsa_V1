# Evidencia `v2.88.66-beta` — `NÚCLEO`: **IdempotencyKeyReused marca FAILED**

**Producto:** `V2.88.66-beta` · **Package:** `2.11.66-beta` · **AsOf:** 2026-10-06. **SIN migración.** **Δ motor = 0.**

**Padre:** [`v2.88.65`](../v2.88.65/README.md).

## Qué cambia

Una misma `idempotency_key` con otro payload ya no vuelve del applier SIM como `False`. Ese `False` hacía que el store programara `RETRY`. Ahora la excepción sube y el store marca `FAILED`.

## Tests

- `test_applier_propagates_idempotency_key_reused`
- `test_durable_apply_idempotency_reused_marks_failed`

Ambos **passed**.
