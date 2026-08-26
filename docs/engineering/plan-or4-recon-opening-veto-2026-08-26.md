# Plan — OR-4 Reconciliation → opening veto

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **403**.
> **Relevo:** [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./traspaso-relevo-or4-recon-opening-veto-2026-08-26.md).

---

## Objetivo

OI-6 / LR-1 ya **detectan**. OR-4 hace que el informe **bloquee aperturas**:

```text
portfolio drift          → DENY new entries (paper y live)
live drift | unavailable → DENY new entries solo si venue = live
exit / exit_hint / reduce → ALLOW (protective / de-risk)
nunca auto-heal
```

ADR-035: Detect → Explain → Require resolution. UI de resolución plena = **fuera** (parked).

## Decisiones

| ID  | Decisión                                                                                                                                                                   |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Pure helper `reconciliation_opening_veto_reason` + espejo TS. Reasons: `reconciliation:portfolio_drift` · `reconciliation:live_drift` · `reconciliation:live_unavailable`. |
| D2  | `check_opening` aplica el veto **antes** del Cognitive Guard; **salta** en `exit` / `exit_hint` / `reduce` (mismo patrón DS-05/DS-03). Kill switch sigue primero.          |
| D3  | Gate off si no hay status ni `require` (tests legado). Con puertos inyectados → require + fail-closed si el lookup lanza.                                                  |
| D4  | OI-6 `drift` veta **siempre** (paper y live). LR-1 solo si `broker_venue=live`. Venue paper **no** se tumba por bridge ausente.                                            |
| D5  | `allow_opening_fill` + Confirm / Fill / HTTP gated / Router cablean puertos. Confirm/Fill resuelven venue (PA-1 coalesce) antes del gate.                                  |
| D6  | OE-1: dejar de mentir `not_wired` cuando OI-6 corre; status `ok`/`drift`/`error`/`unavailable`. Measure ≠ Accept. **No** heal.                                             |
| D7  | Sin Alembic · sin `contract:gen` · sin UI resolución · sin OR-5 suite · sin OR-6 CTA · sin auto-heal.                                                                      |
| D8  | Tests unidad (kernel + opening_permission + risk_engine) + Confirm drift veto + spine.                                                                                     |

## Kernel

```text
exit-like signal                         → skip recon veto
portfolio_recon_status == drift          → DENY portfolio_drift
venue == live && live == drift           → DENY live_drift
venue == live && live == unavailable     → DENY live_unavailable
venue == paper                           → ignore live status
puerto inyectado + boom                  → DENY (fail-closed en allow_opening_fill)
sin puertos                              → gate off (legado)
```

## Ficheros

- [`reconciliation_opening_gate.py`](../../packages/py/application/src/bolsa_application/reconciliation_opening_gate.py) + espejo TS
- [`risk_engine.py`](../../packages/py/application/src/bolsa_application/risk_engine.py)
- [`opening_permission.py`](../../packages/py/application/src/bolsa_application/opening_permission.py)
- Confirm / Fill / ExecuteGated / ExecutionRouter · `dependencies.py` · OE-1 route
- Tests: `test_reconciliation_opening_gate.py` · risk_engine · opening_permission · confirm
- Spine: `pnpm test:decision-spine`

## DoD

- [x] Drift paper → DENY apertura; exit ALLOW con drift.
- [x] Live `unavailable`/`drift` → DENY solo venue live; paper ignora live.
- [x] Confirm / Fill / HTTP / Router cableados; sin Alembic / `contract:gen` / OR-5/6.
- [x] OE-1 status OI-6 honesto cuando wire.
- [x] Docs: CURRENT_SYSTEM / ADR-035 / CHANGELOG / roadmap / relevo OR-4.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · no broker producción · no auto-heal · thin 5.x/8.x congelados · Lab ≠ mesa · OR-1…OR-3 intactos.

## E1

Tras OR-4: **OR-5** suite A–L **o** operar SEMI. **No** CTA LIVE (OR-6) en el mismo chat.
