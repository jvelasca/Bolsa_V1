# Plan — VS-1 Venue selector Paper | Live (DI + mesa)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo XL-2.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** XL-2 fill→ledger.

---

## Objetivo

Mesa puede elegir **Paper | Live** para Confirm / FillPending. Default **paper**. Live → `XtbBrokerAdapter` (fail-closed sin bridge). **No** thaw `PAPER_D_EXECUTE`.

## Decisiones

| ID  | Decisión                                                                               |
| --- | -------------------------------------------------------------------------------------- |
| D1  | `BROKER_VENUE=paper\|live` (Settings, default paper).                                  |
| D2  | Runtime override memoria de proceso (como kill switch), toggle desde mesa.             |
| D3  | DI Confirm + FillPending inyectan adapter vía `resolve_broker_adapter`.                |
| D4  | Live → `XtbBrokerAdapter(bridge_url, execute_trade)`; sin URL → `not_wired` honest.    |
| D5  | Paper → `PaperBrokerAdapter` (default).                                                |
| D6  | API: `brokerVenue` en kill-switch GET + `POST /api/risk/broker-venue`. UI mesa toggle. |
| D7  | Sin Alembic · sin account settings · sin thaw. Manual types en `api.ts` si hace falta. |
| D8  | Tests DI resolver + mesa bar.                                                          |

## Kernel

```text
effective_venue = runtime_memory ?? Settings.BROKER_VENUE ?? paper
paper → PaperBrokerAdapter(execute_trade)
live  → XtbBrokerAdapter(url, execute_trade)
```

## Freeze

LR-1 · XL-2 · Confirm firma · `PAPER_D_EXECUTE` off.

## E1

Parked: Redis persist venue · per-account venue · thaw.
