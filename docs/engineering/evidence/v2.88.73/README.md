# Evidencia `v2.88.73-beta` — `NÚCLEO`: **el id de Alembic 050 cabe en varchar(32)**

**Producto:** `V2.88.73-beta` · **Package:** `2.11.73-beta` · **AsOf:** 2026-10-06. **SIN migración nueva.** **Δ motor = 0.**

**Padre:** [`v2.88.72`](../v2.88.72/README.md).

## Qué cambia

La revisión de la migración 050 pasa a `050_idem_key_not_null` (21 caracteres). El identificador anterior, `050_transaction_idempotency_key_not_null` (40), no cabe en `alembic_version.version_num varchar(32)`. El `ALTER` de `transactions.idempotency_key NOT NULL` no cambia. No hay migración 051 y no se rellenan claves.

Las guardas de head de `lifecycle-pg` dejan de exigir `048_journal_entry_dedupe_key` y apuntan a `050_idem_key_not_null`. Los `downgrade` de esas pruebas siguen en `045` y `047`.

## Por qué

El tag `v2.88.72-beta` no se mueve. Su `Release tag CI` [`37446072486`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37446072486) quedó **ROJO** en `upgrade head` (`lifecycle-pg`, `replay-repro`, `dr-verify`): PostgreSQL rechazó el `UPDATE` de `alembic_version` con `value too long for type character varying(32)`. Los tests del libro no llegaron a ejecutarse en ese run. `python`, `frontend`, `shared`, `decision-spine` y `gitleaks` sí estaban verdes.

El tag `v2.88.68-beta` ([`37441669343`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37441669343)) ya había mostrado el segundo rojo: `049` sí cabe, y `lifecycle-pg` cae porque la guarda sigue en `048`.

## Cita POST-TAG

Pendiente del `Release tag CI` de `v2.88.73-beta`. Esta sección se completa solo si `certify` queda verde.
