# ADR 026: Custodia Opción B — tabla de obligación pendiente + cobro completo (forward-only)

## Estado

**Propuesto** — 2026-08-21
(**Fase R-10 F4a** en ejecución; requiere aprobación del propietario antes de implementar código.)

## Contexto

`ApplyCustodyFees` cobra la custodia anual con **cargo parcial silencioso**: si la cartera no tiene saldo suficiente, descuenta lo que hay, marca el periodo como liquidado en el ledger y **pierde la obligación del saldo restante**.

El núcleo defectuoso está en `packages/py/application/src/bolsa_application/accounts.py:623-647`:

- `deduct_cash(charge_legacy_id, fee_amount, allow_partial=True)` (`:624-627`): la cartera se descuenta **parcialmente** si no hay saldo, sin lanzar error.
- `charged = cash_before - balance_after` (`:629-631`): se registra únicamente el importe efectivamente cobrado (con el `balance_after` truncado a `row.cash`).
- `append_custody_fee(account_id=..., amount=charged, ..., reference_id=f"custody-{period}")` (`:639-647`): escribe la entrada `fee` de `reference_type="custody"` por el importe **parcial** → el guard duradero (`last_custody_charge_at`, `:580-584`) considera el periodo **DONE** y el mutex idempotente (R-9 F3) se libera (`:651`) → en años siguientes nunca se re-cobra el saldo pendiente.

La causa raíz del truncado: `allow_partial=True` en `deduct_cash` (`packages/py/infrastructure/.../repositories/portfolio_repository.py:447-448`), que hace `debit = min(debit, row.cash)` y devuelve el `cash` sin lanzar.

El bug está documentado como hallazgo **#2 de la auditoría externa** en `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md:35` (`accounts.py:623-647`, `allow_partial=True`, `charged = cash_before - balance_after`, `append_custody_fee(amount=charged, ...)`).

## Decisión

Aprobada por el propietario (**Opción B**, decisiones **D3/D3.1** y **D6**):

- **Registrar la obligación de custodia pendiente como estado/tabla en DB** (nueva tabla dedicada `custody_obligation`) — no columna JSON (D3.1, `plan-r10 ...md:99`).
- **Cobrar completo SOLO cuando haya saldo suficiente** (`cash >= fee`); mientras `cash < fee`, **no** se descuenta ni se escribe ledger y la obligación queda **PENDING** para reintento posterior (D3, `plan-r10 ...md:98`).
- **NO marcar DONE parcialmente** y **nunca perdonar la obligación en silencio**.
- **Histórico forward-only (D6, `plan-r10 ...md:103`)**: no se re-cobra ni se crean PENDING retroactivos para periodos ya liquidados como `custody-YYYY`/`fee` en v1.2.0. La corrección aplica desde el **próximo periodo nuevo** y al periodo en curso **solo si aún no existe** fila `custody-YYYY` ya liquidada.

Formalización del alcance F4a y de los requisitos de ADR/migración/decisión previa en `plan-r10 ...md:187-199` (bloque F4a) y `plan-r10 ...md:227-228` (§5 punto F4a — ADR del modelo de obligación pendiente, pendiente de apertura).

Se mantienen intactas las protecciones de carrera:

- **Mutex idempotente de custodia (R-9 F3)**: clave `custody|{account_id}|{period}` (`make_custody_idempotency_key`, `risk_runtime.py:183-185`), `claim_custody_charge` (`:188-218`, SET NX con `CUSTODY_TTL_SEC = 48h` en `:22`/`:21`) y `release_custody_charge` (`:221-236`).
- **UNIQUE parcial del ledger** `uq_ledger_entries_account_reference` sobre `(account_id, reference_type, reference_id, type)` (`tables.py:1179-1191`, espejo en el plan `:35`) y su migración `004_ledger_reference_unique.py:33,38,78-82`.
- **Invariante `Σ ledger.amount == cash`** (plan `:41`): mientras `cash < fee`, ni se escribe `ledger_entries` ni se descuenta `cash`, por lo que el invariante se mantiene.

## Detalle técnico (borrador, a confirmar en la fase)

### Tabla `custody_obligation` (campos propuestos)

Siguiendo la convención de tablas de estado por cuenta del repo (PK `account_id` FK, `updated_at` UTC):

- `account_id` — `String`, **PK**, FK → `investment_accounts.id` con `ondelete="CASCADE"` (patrón de `supervised_f3_account_state`, `tables.py:1375-1378`, y `core_r_account_state`, `tables.py:1357-1360`). **Cardenalidad decidida: una fila por cuenta** (único periodo pendiente activo en curso).
- `period` — `String` (formato `"YYYY"`, igual que `period = now.strftime("%Y")` en `accounts.py:575`). Forma la referencia de cargo `f"custody-{period}"`.
- `status` — enum/string **`PENDING` | `APPLIED`** (decidido; no usar DONE parcial ni estados intermedios sin aprobación explícita).
- `outstanding` — `Numeric(18,6)` (importe pendiente; al crearse y mientras `cash < fee`, `outstanding == fee_amount`).
- `total_fee` — `Numeric(18,6)` opcional (importe total original, para descripción/historial).
- `updated_at` — `DateTime(timezone=True)` con `default=lambda: datetime.now(tz=UTC)` (patrón `tables.py:1365-1367` y `:1382-1384`).
- `UNIQUE`: **PK `account_id`** actúa de `UNIQUE` natural (una fila/periodo en curso por cuenta); el `period` se sobrescribe en cada ciclo anual re-cobrable.

### Migración Alembic prevista (no se implementa ahora)

- Nueva versión `005_custody_obligation` con `down_revision = "004_ledger_reference_unique"` (`004_ledger_reference_unique.py:33-34`).
- `op.create_table("custody_obligation", ...)` + índice/constraint UNIQUE si procede. Los periodos liquidados en v1.2.0 **no** se backfillean (D6): la tabla nace vacía o solo con el periodo en curso si aplica re-cobro.

### Puntos de integración

- `ApplyCustodyFees.execute` (`accounts.py:568+`): antes de `deduct_cash`, consultar `custody_obligation`;
  - si `cash >= fee_amount` → cobrar el **total**, escribir el ledger vía `append_custody_fee` (`ledger_repository.py:201-232`, `reference_type="custody"`, `reference_id=f"custody-{period}"`) y marcar la obligación `APPLIED`;
  - si `cash < fee_amount` → **no** escribir ledger ni descontar; upsert `outstanding` y dejar `status=PENDING` para reintento en un job posterior (relacionado con F4b, fuera de este ADR).
- Repos: nuevo `custody_obligation_repository` (o método en `ledger_repository`) para lectura/upsert del saldo pendiente.

## Alternativas consideradas y por qué se descartan

| Alternativa                                                                 | Por qué se descarta                                                                                                                                                                                                                                       |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Columna JSON en `investment_accounts`**                                   | Rechazada por D3.1 (`plan-r10 ...md:99`): mezcla estado/obligación transaccional con la fila de cuenta, no es consultable/constraint-able de forma fiable y complica el borrado canónico y la reconciliación. Se prefiere una **entidad/tabla dedicada**. |
| **Re-cobro retroactivo de periodos liquidados en v1.2.0**                   | Rechazada por D6 (forward-only, `plan-r10 ...md:103`): re-cobrar o crear PENDING retroactivo muta el histórico de dinero/verdad y choca con el invariante de reconciliación; se evita el backfill.                                                        |
| **Marcar DONE solo con saldo completo (sin tabla)**                         | Rechazada: sin registro de la obligación, un intento con `cash < fee` no cobra nada y **no queda rastro**, reproduciendo el mismo defecto silencioso (solo que sin cargo parcial). La tabla es lo que elimina la pérdida de obligación.                   |
| **Cargo parcial + saldo residual no contabilizado** (comportamiento actual) | Es el bug P1.2 (`plan-r10 ...md:35`): pierde la obligación y rompe la semántica de DONE. Descartado.                                                                                                                                                      |

## Consecuencias

### Positivas

- Elimina la **pérdida silenciosa de obligación** (P1.2): mientras haya pendiente, queda registrado `outstanding`/`PENDING`.
- Cobro **completo con saldo suficiente**; sin DONE parciales.
- Invariante `Σ ledger.amount == cash` intacto (no se escribe ledger si `cash < fee`).
- Compatible con el **job programado de F4b** (custodia fuera del GET, decisión D4): el `PENDING` queda listo para reintento.

### Negativas / coste

- **Nueva migración Alembic** (`005_custody_obligation`) + nueva tabla/mapeo SQLAlchemy + repositorio nuevo (a diseñar en la fase, no en este ADR).
- **Complejidad añadida** en `ApplyCustodyFees`: rama `cash < fee` (no descontar / upsert) vs `cash >= fee` (cobrar completo / liquidar).
- De momento el **reintento requiere job** (F4b); sin él, la obligación podría quedar PENDING largo tiempo (dependencia de fase cruzada).

### Riesgos mitigados

- Corrupciones/mutación de la carrera de custodia: se mantienen el mutex (`risk_runtime.py:183-236`) y el UNIQUE (`tables.py:1179-1191`) intactos.
- No se altera el histórico de v1.2.0 (D6); la tabla nace sin backfill.
- La fecha del periodo en curso re-cobrable se acota a "si aún no existe fila `custody-YYYY` liquidada", evitando doble cargo con periodos ya cerrados.

## Decisiones del propietario (cerradas en la fase)

1. **Cardenalidad de la tabla** `custody_obligation`: **una fila por cuenta** (PK `account_id`, un único periodo pendiente activo; el `period` se sobrescribe en cada ciclo anual re-cobrable). _(Decidido 2026-08-21.)_
2. **Vocabulario del estado `status`**: **`PENDING` | `APPLIED`** exclusivamente. No se añaden `CANCELLED`/`WRITTEN_OFF` ni ningún estado que pueda perdonar silenciosamente la obligación sin aprobación explícita. _(Decidido 2026-08-21.)_

## Pendiente de decisión del propietario (no auto-resueltas)

1. **Alcance del reintento del `PENDING`**: el job de F4b (custodia fuera del GET, D4) decide en qué job/frecuencia se reintenta el saldo pendiente; este ADR registra la obligación, pero **el disparador de reintento depende de F4b** y queda abierto a esa fase.

## Referencias

- Plan director R-10 / v1.2.1: `docs/engineering/plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md` — §1.3 hallazgo #2 (`:35`) · §3 D3 (`:98`) / D3.1 (`:99`) · §4 F4a (`:187-199`) · §5 punto ADR F4a (`:227-228`).
- Traspaso R-10: `docs/engineering/traspaso-relevo-cierre-r10-f3-f4a-apertura-f4b-2026-08-21.md` (F4a hecha, fichero en lectura directa).
- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md`.
- Premisas de proyecto: `docs/PROJECT_PREMISES.md` (§0 E1–E9, aprobación por commit).
- ADR previo de cuentas/ledger/custodia: `docs/adr/008-investment-accounts-and-ledger.md`.
- Modelo de datos / fuentes de verdad: `docs/adr/025-data-model-source-of-truth.md`.

## Historial

| Fecha      | Evento                                                                                                                                                 |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-08-21 | ADR creado (Propuesto) dentro de la fase R-10 F4a; documenta D3/D3.1/D6 y el núcleo buggy verificado en `accounts.py:623-647`.                         |
| 2026-08-21 | Propietario fija cardinalidad (PK `account_id`, una fila/cuenta) y vocabulario `PENDING`/`APPLIED`. ADR listo como docs-only; código en fase separada. |
