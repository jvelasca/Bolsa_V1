# RELEVO — PA-1 Per-account broker venue · 2026-08-26

> **Padre:** [`plan-pa1-per-account-venue-2026-08-26.md`](./plan-pa1-per-account-venue-2026-08-26.md) · ADR-034 · RV-1 / VS-1.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).** ≠ thaw `PAPER_D_EXECUTE` · ≠ Accept estricto.

---

## Qué quedó hecho

| Pieza                                                        | Estado                                  |
| ------------------------------------------------------------ | --------------------------------------- |
| `settings_json.brokerVenue` + preserve en `update_settings`  | **Hecho**                               |
| Coalesce `memory ?? redis ?? account ?? env ?? paper`        | **Hecho**                               |
| Lazy resolve Confirm/Fill (`broker_adapter=None` en DI)      | **Hecho**                               |
| `GET/PATCH /api/accounts/{id}/broker-venue`                  | **Hecho**                               |
| `GET/POST /api/risk/broker-venue` global intacto (mesa)      | **Hecho**                               |
| Helpers FE `getAccountBrokerVenue` / `setAccountBrokerVenue` | **Hecho**                               |
| UI account-settings toggle                                   | **Skip** (API lista; mesa sigue global) |
| Tests unit (mocks; sin Docker Redis)                         | **Hecho**                               |
| `PAPER_D_EXECUTE` flip / Accept estricto                     | **No**                                  |

## Honesty

- Preferencia cuenta **no** sustituye override mesa/Redis global.
- Ausente `brokerVenue` = unset (cae a env / paper).
- Adapter inyectado en tests sigue ganando (compat).
- Status GET `/risk/broker-venue` = global only (RV-1).

## Siguiente chat

1. Thaw **estricto** Accept (deuda; DoD + palabra owner) — chat aparte.
2. UI preferencia cuenta (opcional; helpers ya en `api.ts`).
3. Redis per-account cache (deferred) — no mezclar.

## Sesión 2026-08-26 (cadena)

- **VS-1** Venue selector · **RV-1** Redis global · **JP-1** · thaw stamp · remasure estricto docs.
- **PA-1** per-account venue (este chat).

## Docs

- Plan PA-1 · roadmap v1.11 · CURRENT_SYSTEM · ADR-034 §15
- Tests: `test_broker_adapter.py` (coalesce) · `test_broker_venue_per_account.py` (lazy Confirm/Fill + preserve)
