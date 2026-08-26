# Plan — PH-1 Confirm protect honesty (persist None)

> **Padre:** [`roadmap-v111-operational-integrity-2026-08-26.md`](./roadmap-v111-operational-integrity-2026-08-26.md) · ADR-034 · relevo [`traspaso-relevo-brokeradapter-2026-08-26.md`](./traspaso-relevo-brokeradapter-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO.**
> **Relevo previo:** BrokerAdapter (mock) cerrado.

---

## Objetivo

Confirm **no miente** en Proteger: si H2 / `PersistPositionFromProtect` no actualiza (`persist` → `None`), `trade.status` **no** es `protect_applied`. UI y journal no celebran un stop que no se persistió.

≠ broker live / XTB · ≠ thaw `PAPER_D_EXECUTE` · ≠ PaperBroker / BrokerAdapter · H2 factories intactas.

Proteger = cero ledger. El éxito **es** persistir el stop. `None` ≠ aplicado.

## Decisiones

| ID  | Decisión                                                                                                                                                                                                     |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | `persist` truthy → `protect_applied` + journal `protect_applied` + `positionPersist.applied` + intent `executed`.                                                                                            |
| D2  | `persist` → `None` (H2 empeora sin override, u otro no-update) → `trade.status=skipped` / `reason=stop_not_applied`; `positionPersist.skipped`; **sin** journal `protect_applied`; intent **no** `executed`. |
| D3  | `persist` lanza → `skipped` / `persist_error` + `positionPersist.error`; **sin** `protect_applied`; intent no `executed`.                                                                                    |
| D4  | UI Confirm: log muestra stop no aplicado; **no** saca de cola ni graba mandato si `stop_not_applied`.                                                                                                        |
| D5  | HELP Hoy: Proteger no aplicado ≠ `protect_applied`.                                                                                                                                                          |
| D6  | Sin Alembic · sin `contract:gen` · sin thaw · **sin live XTB**.                                                                                                                                              |
| D7  | Tests Confirm + SEMI e2e H2 None + spine.                                                                                                                                                                    |
| D8  | Broker live **parked** (chat aparte).                                                                                                                                                                        |

## Kernel

```text
ExitPermission ALLOW
  persist row → protect_applied + journal + intent executed
  persist None → skipped stop_not_applied (no journal applied)
  persist boom → skipped persist_error
```

## Ficheros

- `confirm_recommendation.py` — rama protect
- `test_persist_position_from_fill.py` · `test_semi_triggered_confirm_protect.py`
- `supervised-f3-panel.tsx` · `hoy-en-la-mesa.tsx`
- Docs: roadmap · ADR-034 · CURRENT_SYSTEM · HELP · CHANGELOG · relevo

## Freeze

ADR-033 · Confirm = firma · OI-1…OI-6 · PaperBroker · BrokerAdapter mock · `PAPER_D_EXECUTE` off · broker live no · Lab ≠ mesa · thin 5.x/8.x congelados · H2 factories sin campos extra.

## E1

Broker live (XTB, chat aparte). **No** mezclar live con este slice.
