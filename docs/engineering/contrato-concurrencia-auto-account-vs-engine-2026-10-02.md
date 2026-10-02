# Contrato de CONCURRENCY del monitor AUTO — `account` vs `engine` (2026-10-02)

> **Clase:** **deuda arquitectónica declarada** (docs-only; **SIN bump, SIN tag**). Fija el
> contrato que hoy está **implícito** en el agregado de concurrencia del monitor y lo deja listo
> para decidirse antes de introducir multi-engine real.
> **AsOf:** 2026-10-02. **Base:** `v2.88.24-beta` (`2.11.24-beta`).
> **Origen:** auditoría externa de `v2.88.24` §7 (consecuencia nueva de A4: `lastDecisionAt` ya es
> por motor, pero los contadores de concurrencia siguen agregándose por cuenta).
> **Padres:** [`evidence/v2.88.24/README.md`](./evidence/v2.88.24/README.md) §7 ·
> `packages/py/application/src/bolsa_application/auto_operational_monitor.py`.

---

## 0. El hecho

Tras `v2.88.24` (A4), la lectura de la ÚLTIMA DECISIÓN quedó acotada por motor:

- El trazado sella `payload.engineId` (`auto_simulation_worker._v2_journal_entry_decisions`).
- La lectura filtra `payload->>'engineId' == engine_id`
  (`SqlAlchemyJournalRepository.list_entries(..., engine_id=...)`).
- El header del monitor se acota por `engine_id`.

Pero los **contadores de concurrencia** que pinta el panel siguen agregándose solo por
`account_id`:

- `SqlAlchemyJournalRepository.aggregate_auto_operational_audit(account_id=...)` cuenta TODOS los
  `auto_reservation_claim` y `auto_reservation_reconciliation` de la CUENTA:
  `claimAttempts`, `successfulClaims`, `lostClaims`, `raceConflicts`, `reconciliations`,
  `graceWindowKeeps`.
- `PostgresReservationStore.count_forced_releases(account_id, ...)` cuenta las reservas de la
  CUENTA.
- `activeSessions` es un `DISTINCT` de sesiones del spine dentro de la ventana de la CUENTA.

⇒ Con **un solo motor por cuenta** (el caso real hoy) `account` y `engine` son lo mismo y no hay
ambigüedad. Con **dos motores en la misma cuenta**, `lastDecisionAt` sería específico de motor pero
los contadores de concurrencia serían **globales de la cuenta**.

---

## 1. Decisión (estado ACTUAL declarado)

**`CONCURRENCY` es account-scoped.** El compromiso de capital, la carrera por la clave determinista
de reserva y el barrido de reconciliación se definen hoy a nivel de **cuenta**: una reserva viva de
cualquier motor de la cuenta bloquea la emisión de otra reserva para el mismo instrumento
(la identidad determinista de la reserva es `(account_id, instrument_id, ...)`). Por tanto los
contadores de concurrencia **deben** seguir siendo de cuenta: son la medida de ese mecanismo.

La única lectura que es **por motor** es `lastDecisionAt` (y lo seguirá siendo), porque la decisión
de inversión sí es de un motor concreto.

| Magnitud | Alcance declarado | Por qué |
| --- | --- | --- |
| `lastDecisionAt` / `nextDecisionAt` | **engine** | La decisión de entrada es de un motor. |
| `claimAttempts`, `successfulClaims`, `lostClaims`, `raceConflicts` | **account** | La PK determinista de la reserva es de cuenta. |
| `reconciliations`, `graceWindowKeeps`, `forcedReleases` | **account** | El barrido y la retirada son de la cuenta. |
| `activeSessions` | **account** (suelo) | `DISTINCT` de sesiones del spine de la cuenta. |
| `heartbeatsPersisted` | **engine** | `auto_engine_ticks.engine_id` es por motor. |

No se cambia ningún código en este documento: **se declara el contrato**. La UI y el DTO ya viajan
con `engineId` en el header y con los contadores sin sufijo de motor, que es coherente con este
contrato.

---

## 2. Cuándo habría que revisar esta decisión (disparador)

Solo si el producto introduce **multi-engine real por cuenta** (varios motores operando a la vez
sobre la misma cuenta). En ese momento hay que decidir explícitamente:

1. **Mantener account-scoped** (recomendado): el mecanismo de reserva sigue siendo de cuenta y los
   contadores miden ese mecanismo. Se documenta que "concurrencia" es una propiedad de cuenta.
2. **Migrar a engine-scoped**: exige (a) acotar la identidad de la reserva por motor, y
   (b) añadir `payload->>'engineId'` al `WHERE` de `aggregate_auto_operational_audit()` y a
   `count_forced_releases()`, y (c) revisar `activeSessions`. Es un cambio de **contrato**, no un
   ajuste de UI: obliga a re-sellar el monitor.

No se implementa (b) ahora porque hoy sería **código sin hecho que lo ejerza** (un solo motor por
cuenta): declararlo es lo honesto, implementarlo sería especular.

---

## 3. Qué NO cambia

- No cambia ningún umbral ni ninguna decisión del motor.
- No cambia el alcance de `lastDecisionAt` (ya es por motor).
- No cambia el esquema (el `engineId` vive en el `payload` JSONB; sin migración).
- No cierra ninguna otra deuda (`ENTRY_ORDER`/`SETTLEMENT`/`price_source` se tratan en `v2.88.25`).
