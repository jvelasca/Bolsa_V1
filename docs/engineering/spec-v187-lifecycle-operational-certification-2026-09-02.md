# Spec — V1.87 Lifecycle Operational Integration & Concurrency Certification

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** · **stamp CI GREEN remoto** — tip [`v1.87-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.87-beta) → [`646b97ac`](https://github.com/jvelasca/Bolsa_V1/commit/646b97ac) · [run 33689747400](https://github.com/jvelasca/Bolsa_V1/actions/runs/33689747400) **success**.  
> **Padre:** [`respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md`](./respuesta-auditor-v186-lifecycle-event-store-2026-09-02.md) · [`spec-v186-lifecycle-event-store-2026-09-02.md`](./spec-v186-lifecycle-event-store-2026-09-02.md).  
> **Partida tip:** `v1.86-beta` → [`baaa7034`](https://github.com/jvelasca/Bolsa_V1/commit/baaa7034). **No** LIVE · **no** V1.88 golden integrado obligatorio.

```text
Request
  → JWT principal (401 si falta)
  → resolve account (referencia, no autoridad)
  → verify position/account ownership (403 si ajeno)
  → lock aggregate (SELECT … FOR UPDATE)
  → read log ORDER BY sequence_no
  → validate (domain)
  → assign sequence_no
  → INSERT UNIQUE(position_id, sequence_no)
  → commit
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler · sin bump `1.35.0-beta` · sin `dryRun=false` browser.  
V1.73–V1.86 mock paths intactos. **No** Playwright en `frontend-ci`. **No** sustituir `/portfolio` ni unificar ledger. **No** integrated E2E obligatorio (V1.88).

## 1. Auth / isolation (P0)

`POST /api/lifecycle/events` y `GET /api/lifecycle/positions/{position_id}/snapshot`:

| Caso                                  | HTTP |
| ------------------------------------- | ---- |
| Sin JWT                               | 401  |
| Principal dueño de la cuenta/posición | 200  |
| Principal ajeno                       | 403  |
| Posición inexistente (GET)            | 404  |

`accountId` del body es **referencia comprobada** contra el principal y, si el log ya existe, contra el `account_id` persistido. Nunca es autoridad.

## 2. Serialización (P1)

Tabla `lifecycle_aggregates` (`position_id` PK) + columna `lifecycle_events.sequence_no`.

- Lock: `INSERT … ON CONFLICT DO NOTHING` + `SELECT … FOR UPDATE` sobre el agregado.
- `UNIQUE(position_id, sequence_no)`.
- `ORDER BY sequence_no` (el tiempo `at` es metadata).
- Dos POST concurrentes sobre el mismo `position_id`: exactamente una transicion legal; la otra `illegal_transition` / 409.

## 3. Alembic (P1)

- `015`: tabla ausente → create; tabla presente → **ensure** índices/constraints (no return temprano).
- `016`: `sequence_no` + agregado + unique de secuencia.
- Job `lifecycle-pg`: **no** `metadata.create()`. `alembic upgrade head` sobre Postgres vacío, luego tests.

## 4. DTO + dinero

- `LifecycleEventRequestDto`: `extra="forbid"` (typo → 422).
- Cantidades/precios/fees/cash/PnL: `Decimal` en dominio y columnas `Numeric`; JSON wire sigue siendo número.

## 5. IntegrityError

Clasificar por constraint: `fill_id` → `duplicate_fill_id`; `event_id` → `event_id_conflict`; `sequence_no` → conflicto de secuencia (no fingir event_id).

## 6. IN / OUT

**IN:** auth JWT + isolation · sequence + lock · Alembic from-zero · `extra="forbid"` · Decimal domain→DB · tests concurrencia/auth · CI `lifecycle-pg` con `upgrade head`.

**OUT:** V1.88 golden integrado + kill/restart API · recon real · LIVE · bump · unificar ledger · `last_price_for_stage` de producción · Playwright en `frontend-ci`.
