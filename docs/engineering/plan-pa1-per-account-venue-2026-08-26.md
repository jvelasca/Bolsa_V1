# Plan — PA-1 Per-account broker venue

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · RV-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**
> **Relevo:** [`traspaso-relevo-pa1-per-account-venue-2026-08-26.md`](./traspaso-relevo-pa1-per-account-venue-2026-08-26.md).

---

## Objetivo

Preferencia **Paper | Live** por cuenta en `settings_json.brokerVenue`, con override global VS-1/RV-1 por encima. Lazy resolve en Confirm/Fill cuando hay `account_id`. Default **paper**. **No** Alembic. **No** thaw `PAPER_D_EXECUTE`.

## Decisiones

| ID  | Decisión                                                                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Persist `settings_json.brokerVenue` (`paper`\|`live`); ausente = unset. Preserve en `update_settings` como `equityMarks`/`labEvidence`. **No** Alembic. |
| D2  | Precedence: `runtime_memory ?? redis_global ?? account.settings_json.brokerVenue ?? Settings.BROKER_VENUE ?? paper`.                                    |
| D3  | Lazy resolve: Confirm/FillPending resuelven venue **tras** conocer `account_id`; `resolve_broker_adapter(..., venue=)`.                                 |
| D4  | `GET/POST /api/risk/broker-venue` sigue **global**. Additive: lectura/escritura preferencia cuenta (merge settings o endpoint mínimo).                  |
| D5  | Mesa toggle = override **global** (RV-1). Opcional control en account settings para preferencia cuenta.                                                 |
| D6  | **No** tipar `AccountSettings` fees. **No** thaw. **No** renombrar Redis key global. Redis per-account deferred.                                        |
| D7  | Freeze: Confirm firma · PH-1 · LR-1/XL-2/VS-1/RV-1 · `PAPER_D_EXECUTE` off · mesa default paper · ≠ Accept estricto.                                    |
| D8  | Tests: coalesce + account mock; lazy Confirm/Fill; preserve key; mesa global intacta; mocks (sin Docker Redis).                                         |

## Kernel

```text
effective(account_id) =
  memory ?? redis_global ?? settings_json.brokerVenue ?? env ?? paper
Confirm/Fill → resolve(account_id) → resolve_broker_adapter(venue=)
POST /risk/broker-venue → global only (RV-1)
GET/PATCH /accounts/{id}/broker-venue → preference (merge_settings_json)
```

## Freeze

VS-1 · RV-1 · JP-1 · thaw stamp · Confirm firma · `PAPER_D_EXECUTE` off · Accept estricto parked · default-on parked.

## E1

Parked: Redis per-account cache · Accept estricto · default-on (palabra owner) · typed AccountSettings.brokerVenue · UI account-settings toggle (API + api.ts helpers listos).
